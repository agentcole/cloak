"""Fuzzy coreference grouping (cloak.coref) and its vault/engine wiring."""

from __future__ import annotations

from cloak import Cloak, CloakPolicy
from cloak.coref import CorefIndex
from cloak.strategies.placeholder import PlaceholderStrategy
from cloak.types import Entity
from cloak.vault import Vault


def _ent(type_: str, text: str) -> Entity:
    return Entity(type_, 0, len(text), text, 0.9, "ner")


# -- clustering ----------------------------------------------------------


def test_person_variants_share_canonical():
    idx = CorefIndex.build([("PERSON", "Jane Doe"), ("PERSON", "Jane"), ("PERSON", "Ms. Doe")])
    assert idx.canonical("PERSON", "Jane") == "Jane Doe"
    assert idx.canonical("PERSON", "Ms. Doe") == "Jane Doe"
    assert idx.canonical("PERSON", "Jane Doe") == "Jane Doe"


def test_distinct_people_stay_separate():
    idx = CorefIndex.build([("PERSON", "Jane Doe"), ("PERSON", "John Smith")])
    assert idx.canonical("PERSON", "Jane Doe") != idx.canonical("PERSON", "John Smith")


def test_ambiguous_short_mention_is_not_merged():
    # "Jane" is a subset of two clusters -> it must not collapse them.
    idx = CorefIndex.build([("PERSON", "Jane Doe"), ("PERSON", "Jane Roe"), ("PERSON", "Jane")])
    assert idx.canonical("PERSON", "Jane") == "Jane"
    assert idx.canonical("PERSON", "Jane Doe") == "Jane Doe"


def test_structured_types_only_merge_on_exact_value():
    # Two emails sharing a domain are different entities — never merged.
    idx = CorefIndex.build([("EMAIL", "a@acme.com"), ("EMAIL", "b@acme.com")])
    assert idx.canonical("EMAIL", "a@acme.com") == "a@acme.com"
    assert idx.canonical("EMAIL", "b@acme.com") == "b@acme.com"


def test_case_and_punctuation_variants_merge():
    idx = CorefIndex.build([("LOCATION", "München"), ("LOCATION", "münchen")])
    assert idx.canonical("LOCATION", "münchen") == idx.canonical("LOCATION", "München")


# -- vault wiring --------------------------------------------------------


def test_vault_uses_coref_for_one_token_and_canonical_restore():
    idx = CorefIndex.build([("PERSON", "Jane Doe"), ("PERSON", "Jane")])
    v = Vault(salt="s", coref=idx.canonical)
    strat = PlaceholderStrategy()
    t_full = v.allocate(_ent("PERSON", "Jane Doe"), strat)
    t_short = v.allocate(_ent("PERSON", "Jane"), strat)
    assert t_full == t_short == "[PERSON_1]"
    # Both variants restore to the canonical (fullest) form.
    assert v.restore("saw [PERSON_1] today") == "saw Jane Doe today"


def test_coref_can_be_disabled_via_policy():
    c = Cloak(CloakPolicy(detectors=["regex"], coref=False))
    # With coref off the vault has no canonicalizer.
    res = c.mask_text("a@x.com and a@x.com")
    assert res.vault._coref is None
    # Exact coreference still holds (same value -> same token).
    assert res.text.count("[EMAIL_1]") == 2
