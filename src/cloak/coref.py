"""Coreference grouping: map variant mentions of one entity to a single token.

Within a masking scope (a string, a set of messages, or a whole document) the
same real-world entity is often named several ways — ``"Jane Doe"``, ``"Jane"``,
``"Ms. Doe"``. Plain vault coreference keys on the exact ``(type, text)`` pair,
so those would get three different tokens. This module clusters such variants so
they share one numbered token (``[PERSON_1]``).

It is deliberately **conservative** and dependency-free:

* Only *name-like* types (person, organization, location, address) are linked
  fuzzily. Structured PII (email, IBAN, phone, …) only ever merges on an exact
  value match — a domain shared between two emails must never collapse them.
* A shorter mention joins a longer one only when its normalized tokens are a
  strict subset of the longer's *and* the match is unambiguous. If a short
  mention (``"Jane"``) could attach to two clusters, it stays on its own rather
  than risk merging two distinct people.
* The canonical mention (the token's restored value) is the longest surface
  form in the cluster — the most complete, most informative one.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Types whose mentions may be linked by subset (not just exact equality).
FUZZY_TYPES: frozenset[str] = frozenset(
    {"PERSON", "ORGANIZATION", "ORG", "LOCATION", "LOC", "GPE", "ADDRESS", "FACILITY", "NORP"}
)

# Honorifics stripped from PERSON mentions before comparison.
_TITLES: frozenset[str] = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "miss",
        "mx",
        "dr",
        "prof",
        "sir",
        "madam",
        "lady",
        "herr",
        "frau",
        "fraulein",
        "dott",
        "ing",
        "mme",
        "mlle",
        "monsieur",
    }
)

_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(text: str, type_: str) -> list[str]:
    """Lowercased word tokens, with honorifics dropped for PERSON."""
    toks = [t.lower() for t in _WORD.findall(text)]
    if type_ == "PERSON":
        toks = [t for t in toks if t not in _TITLES] or toks
    return toks


def _link_ok(type_: str, short: list[str], long_: list[str]) -> bool:
    """Whether ``short`` (a strict token-subset of ``long_``) may join it.

    Requires a distinctive (len>=3) shared token so we never link on initials or
    stopwords. For PERSON additionally requires either a single shared token or a
    shared surname (the canonical's last token), guarding against two people who
    merely share a given name.
    """
    short_set = set(short)
    if not any(len(t) >= 3 for t in short_set):
        return False
    if type_ == "PERSON":
        return len(short_set) == 1 or long_[-1] in short_set
    return True


class CorefIndex:
    """Maps each ``(type, surface)`` mention to its cluster's canonical surface."""

    def __init__(self) -> None:
        self._canonical: dict[tuple[str, str], str] = {}

    def canonical(self, type_: str, text: str) -> str:
        """Return the canonical surface form for a mention (itself if unknown)."""
        return self._canonical.get((type_, text), text)

    @classmethod
    def build(cls, mentions: Iterable[tuple[str, str]]) -> CorefIndex:
        index = cls()
        by_type: dict[str, list[str]] = {}
        for type_, surface in mentions:
            seen = by_type.setdefault(type_, [])
            if surface not in seen:
                seen.append(surface)
        for type_, surfaces in by_type.items():
            for canonical, members in cls._cluster(type_, surfaces):
                for member in members:
                    index._canonical[(type_, member)] = canonical
        return index

    @staticmethod
    def _cluster(type_: str, surfaces: list[str]) -> list[tuple[str, list[str]]]:
        """Group ``surfaces`` of one type into (canonical, members) clusters."""
        fuzzy = type_ in FUZZY_TYPES
        # Longest first so a cluster's first (canonical) member is the fullest
        # form; ties broken lexicographically for determinism.
        order = sorted(surfaces, key=lambda s: (-len(s), s))

        clusters: list[dict] = []  # {canon: str, tokens: list[str], members: list[str]}
        for surface in order:
            toks = _tokens(surface, type_)
            tok_set = set(toks)
            matches = []
            for cluster in clusters:
                ctoks = cluster["tokens"]
                if tok_set == set(ctoks):
                    matches.append(cluster)
                elif fuzzy and tok_set < set(ctoks) and _link_ok(type_, toks, ctoks):
                    matches.append(cluster)
            if len(matches) == 1:
                matches[0]["members"].append(surface)
            else:  # no match, or ambiguous (>1) — keep it separate
                clusters.append({"canon": surface, "tokens": toks, "members": [surface]})
        return [(c["canon"], c["members"]) for c in clusters]
