"""Overlap/containment resolution in the Resolver."""

from __future__ import annotations

from cloak.policy import CloakPolicy
from cloak.resolver import Resolver
from cloak.types import Entity


def _resolve(text: str, entities: list[Entity], **policy_kw) -> list[Entity]:
    return Resolver(CloakPolicy(**policy_kw)).resolve(entities, text)


def test_contained_span_yields_to_its_container():
    # A confident city LOCATION inside a full ADDRESS must NOT win and leak the
    # street: the containing ADDRESS span is kept, the contained one dropped.
    text = "Rosenheimer Str. 103, 81669 München"
    addr = Entity("ADDRESS", 0, len(text), text, 0.6, "regex")
    city = Entity("LOCATION", 28, len(text), "München", 0.9, "ner")
    out = _resolve(text, [city, addr])
    assert [e.type for e in out] == ["ADDRESS"]
    assert out[0].text == text


def test_partial_overlap_still_resolved_by_score():
    # Neither span contains the other -> the higher-confidence one wins, as before.
    text = "abcdefghij"
    a = Entity("EMAIL", 0, 6, "abcdef", 0.98, "regex")
    b = Entity("PERSON", 4, 10, "efghij", 0.80, "ner")
    out = _resolve(text, [a, b])
    assert [e.type for e in out] == ["EMAIL"]


def test_equal_spans_decided_by_score_not_dropped():
    # Same offsets, different type -> containment pre-pass keeps both; score picks.
    text = "0123456789"
    low = Entity("HANDLE", 0, 10, text, 0.50, "regex")
    high = Entity("CREDIT_CARD", 0, 10, text, 0.90, "regex")
    out = _resolve(text, [low, high])
    assert [e.type for e in out] == ["CREDIT_CARD"]


def test_nested_chain_keeps_only_outermost():
    text = "x" * 20
    outer = Entity("ADDRESS", 0, 20, text, 0.6, "regex")
    mid = Entity("LOCATION", 5, 15, text[5:15], 0.9, "ner")
    inner = Entity("US_ZIP", 8, 13, text[8:13], 0.7, "regex")
    out = _resolve(text, [inner, mid, outer])
    assert [e.type for e in out] == ["ADDRESS"]


def test_disjoint_spans_all_kept():
    text = "aaaa bbbb cccc"
    e1 = Entity("EMAIL", 0, 4, "aaaa", 0.9, "regex")
    e2 = Entity("PHONE", 5, 9, "bbbb", 0.9, "regex")
    out = _resolve(text, [e1, e2])
    assert {e.type for e in out} == {"EMAIL", "PHONE"}
    assert [e.start for e in out] == [0, 5]  # returned in document order
