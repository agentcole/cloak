"""Eval harness: markup parsing, metrics math, and a regex-tier regression."""

from __future__ import annotations

from pathlib import Path

from cloak import Cloak, CloakPolicy
from cloak.evaluate import Metrics, evaluate, load_corpus, parse_markup

GOLD = Path(__file__).resolve().parent.parent / "eval" / "gold.txt"

# Structured types the regex tier is responsible for (NER types excluded).
STRUCTURED = {
    "EMAIL",
    "PHONE",
    "SSN",
    "CREDIT_CARD",
    "IBAN",
    "IP_ADDRESS",
    "MAC_ADDRESS",
    "URL",
    "API_KEY",
    "CRYPTO_ADDRESS",
    "DATE",
    "NATIONAL_ID",
    "EIN",
    "MEDICAL_ID",
    "VIN",
    "US_ZIP",
    "GEO_COORDINATE",
    "ADDRESS",
}


def test_parse_markup_recovers_text_and_offsets():
    text, ents = parse_markup("Email [[EMAIL|a@b.com]] now")
    assert text == "Email a@b.com now"
    assert ents == [{"type": "EMAIL", "start": 6, "end": 13, "text": "a@b.com"}]
    assert text[ents[0]["start"] : ents[0]["end"]] == "a@b.com"


def test_parse_markup_multiple_spans_offsets_are_exact():
    text, ents = parse_markup("[[PERSON|Jane]] at [[EMAIL|j@x.io]]")
    for e in ents:
        assert text[e["start"] : e["end"]] == e["text"]


def test_load_corpus_skips_comments_and_blanks():
    examples = load_corpus(str(GOLD))
    assert len(examples) > 20
    # Negative lines parse to (text, []) and must be present.
    assert any(gold == [] for _text, gold in examples)


def test_metrics_math():
    m = Metrics(tp=8, fp=2, fn=2)
    assert m.precision == 0.8
    assert m.recall == 0.8
    assert round(m.f1, 3) == 0.8
    # Empty case: no predictions and no gold -> perfect by convention.
    assert Metrics().precision == 1.0 and Metrics().recall == 1.0


def test_regex_tier_regression_on_gold():
    cloak = Cloak(CloakPolicy(detectors=["regex"]))
    report = evaluate(cloak, load_corpus(str(GOLD)))

    # Regex tier must never false-positive on this corpus.
    assert report.overall.precision == 1.0, report.format_table()
    # Every structured type present should be fully recalled.
    for etype, m in report.by_type.items():
        if etype in STRUCTURED:
            assert m.recall == 1.0, f"{etype} recall {m.recall} < 1.0\n{report.format_table()}"
    # Overall recall is dragged down only by the unscored NER types.
    assert report.overall.recall >= 0.8
