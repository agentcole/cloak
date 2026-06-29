"""Document scan/mask/redact and rendering.

The masker and renderers are dependency-free, so most tests build synthetic
``SegmentedDoc``s and need no docling. The real docling parse is opt-in via
``CLOAK_TEST_DOCLING=1`` (and docling installed), mirroring the GLiNER/Ollama
opt-in tests.
"""

from __future__ import annotations

import importlib.util
import os

import pytest

from cloak import Cloak, CloakPolicy
from cloak.documents import (
    DocumentResult,
    Segment,
    SegmentedDoc,
    mask_document,
    scan_document,
)
from cloak.documents.parser import DoclingParser


def _engine(**kw) -> Cloak:
    kw.setdefault("detectors", ["regex"])
    return Cloak(CloakPolicy(**kw))


def _doc() -> SegmentedDoc:
    return SegmentedDoc(
        segments=[
            Segment(text="Quarterly Report", order=0, kind="section_header", page=1),
            Segment(text="Contact jane@acme.com about SSN 123-45-6789.", order=1, page=1,
                    bbox=(72.0, 700.0, 520.0, 712.0)),
            Segment(text="Escalate to jane@acme.com if urgent.", order=2, page=2),
        ],
        source_path="report.pdf",
    )


# -- scan ----------------------------------------------------------------

def test_scan_document_tags_provenance():
    ents = scan_document(_doc(), _engine())
    by_type = {e.type for e in ents}
    assert {"EMAIL", "SSN"} <= by_type
    ssn = next(e for e in ents if e.type == "SSN")
    assert ssn.page == 1
    assert ssn.bbox == (72.0, 700.0, 520.0, 712.0)
    assert ssn.text == "123-45-6789"


# -- mask (reversible) ---------------------------------------------------

def test_mask_document_masks_every_segment():
    res = mask_document(_doc(), _engine())
    assert isinstance(res, DocumentResult)
    joined = " ".join(s.text for s in res.doc.segments)
    assert "jane@acme.com" not in joined
    assert "123-45-6789" not in joined
    assert "[EMAIL_1]" in joined and "[SSN_1]" in joined


def test_mask_document_shares_vault_for_coreference_across_pages():
    res = mask_document(_doc(), _engine())
    # The same email on page 1 and page 2 -> the same token.
    seg1 = next(s for s in res.doc.segments if s.order == 1)
    seg2 = next(s for s in res.doc.segments if s.order == 2)
    assert "[EMAIL_1]" in seg1.text
    assert "[EMAIL_1]" in seg2.text


def test_mask_document_vault_restores_text_answer():
    res = mask_document(_doc(), _engine())
    answer = "I emailed [EMAIL_1] about [SSN_1]."
    assert res.vault.restore(answer) == "I emailed jane@acme.com about 123-45-6789."


def test_mask_document_does_not_mutate_input_segments():
    doc = _doc()
    mask_document(doc, _engine())
    assert "jane@acme.com" in doc.segments[1].text  # original untouched


# -- redact (one-way) ----------------------------------------------------

def test_redact_mode_is_irreversible():
    res = mask_document(_doc(), _engine(), mode="redact")
    joined = " ".join(s.text for s in res.doc.segments)
    # Numbered redaction: coreferent mentions are visibly linked, but nothing
    # reversible is stored, so restoring a token is a no-op.
    assert "[EMAIL_1]" in joined and "jane@acme.com" not in joined
    assert res.vault.restore("[EMAIL_1]") == "[EMAIL_1]"
    assert res.mode == "redact"


def test_redact_mode_coreference_shares_one_token():
    # The same email on both pages must redact to the SAME numbered token.
    res = mask_document(_doc(), _engine(), mode="redact")
    seg1 = next(s for s in res.doc.segments if s.order == 1)
    seg2 = next(s for s in res.doc.segments if s.order == 2)
    assert "[EMAIL_1]" in seg1.text and "[EMAIL_1]" in seg2.text


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        mask_document(_doc(), _engine(), mode="scramble")


# -- rendering -----------------------------------------------------------

def test_markdown_fallback_formats_by_kind():
    res = mask_document(_doc(), _engine())
    md = res.to_markdown()
    assert md.startswith("# Quarterly Report")
    assert "[EMAIL_1]" in md
    assert "jane@acme.com" not in md


def test_json_fallback_schema():
    res = mask_document(_doc(), _engine())
    payload = res.to_json()
    assert payload["schema"] == "cloak.segmented-doc/v1"
    assert len(payload["segments"]) == 3
    assert payload["segments"][1]["bbox"] == [72.0, 700.0, 520.0, 712.0]
    assert "jane@acme.com" not in payload["segments"][1]["text"]


def test_docx_not_yet_implemented():
    res = mask_document(_doc(), _engine())
    with pytest.raises(NotImplementedError):
        res.to_docx()


def test_pdf_requires_pymupdf_or_real_source():
    # Either PyMuPDF is missing (clean ImportError) or it's present and the
    # synthetic source path doesn't exist (a fitz error) — never a silent pass.
    res = mask_document(_doc(), _engine())
    with pytest.raises(Exception):
        res.to_pdf()


def test_markdown_normalizes_docling_escaped_tokens():
    # docling's markdown exporter escapes "_" in prose, which would corrupt our
    # tokens and break restore. to_markdown must collapse them back.
    res = mask_document(_doc(), _engine())
    raw = "Reach [EMAIL\\_1] about [SSN\\_1] now."
    fixed = res._normalize_tokens(raw)
    assert fixed == "Reach [EMAIL_1] about [SSN_1] now."
    # And the cleaned token restores via the vault.
    assert "jane@acme.com" in res.vault.restore(fixed)


def test_by_type_counts():
    res = mask_document(_doc(), _engine())
    counts = res.by_type()
    assert counts["EMAIL"] == 2  # one per page
    assert counts["SSN"] == 1


# -- engine integration --------------------------------------------------

def test_engine_accepts_segmented_doc_directly():
    c = _engine()
    res = c.mask_document(_doc())
    assert isinstance(res, DocumentResult)
    ents = c.scan_document(_doc())
    assert any(e.type == "EMAIL" for e in ents)


# -- parser availability -------------------------------------------------

def test_parser_available_reflects_docling_presence():
    has_docling = importlib.util.find_spec("docling") is not None
    assert DoclingParser().available() is has_docling


def test_parser_parse_without_docling_is_clean():
    if importlib.util.find_spec("docling") is not None:
        pytest.skip("docling installed; the clean-ImportError path can't trigger")
    with pytest.raises(ImportError, match="cloak-llm\\[docling\\]"):
        DoclingParser().parse("whatever.pdf")


# -- opt-in: real docling parse ------------------------------------------

_SAMPLE_PDF = os.path.join(
    os.path.dirname(__file__), "..", "examples", "data", "kundenkartei.pdf"
)


@pytest.mark.skipif(
    not (os.environ.get("CLOAK_TEST_DOCLING") and importlib.util.find_spec("docling")),
    reason="set CLOAK_TEST_DOCLING=1 with docling installed to run",
)
@pytest.mark.skipif(not os.path.exists(_SAMPLE_PDF), reason="sample PDF not present")
def test_real_docling_pdf_roundtrip():
    # German customer-file sample (synthetic), regex tier only so the test
    # needs no NER model. Exercises the structured PII regex reliably catches.
    c = Cloak(CloakPolicy(detectors=["regex"]))
    res = c.mask_document(_SAMPLE_PDF)
    md = res.to_markdown()

    # Structured PII inside TABLES must be masked, not just loose text — this is
    # the table-cell-segment fix. All ten customer emails should be gone.
    assert "@example.de" not in md
    counts = res.by_type()
    assert counts.get("EMAIL", 0) == 10
    # Printed IBANs are space-grouped ("DE89 3704 0044 0532 0130 00"); they must
    # still be detected (the separator-tolerant IBAN pattern).
    assert counts.get("IBAN", 0) >= 1
    assert "DE89 3704 0044 0532 0130 00" not in md

    # Every detected original must be gone, and the vault must round-trip.
    for de in res.entities:
        assert de.entity.text not in md
    tok = res.vault.reversible_entries()[0]
    assert res.vault.restore(tok.token) == tok.original


@pytest.mark.skipif(
    not (os.environ.get("CLOAK_TEST_DOCLING") and importlib.util.find_spec("docling")),
    reason="set CLOAK_TEST_DOCLING=1 with docling installed to run",
)
@pytest.mark.skipif(not os.path.exists(_SAMPLE_PDF), reason="sample PDF not present")
def test_real_docling_pdf_redaction_removes_glyphs():
    import fitz  # PyMuPDF ships with the [docling] extra

    c = Cloak(CloakPolicy(detectors=["regex"]))
    res = c.mask_document(_SAMPLE_PDF, mode="redact")
    pdf_bytes = res.to_pdf()

    # Re-extract text from the redacted PDF: no detected original may survive
    # (apply_redactions removes glyphs, it doesn't just cover them).
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    extracted = "\n".join(page.get_text() for page in doc)
    doc.close()
    for de in res.entities:
        assert de.entity.text not in extracted


@pytest.mark.skipif(
    not (os.environ.get("CLOAK_TEST_DOCLING") and importlib.util.find_spec("docling")),
    reason="set CLOAK_TEST_DOCLING=1 with docling installed to run",
)
def test_real_docling_roundtrip(tmp_path):
    # A minimal HTML doc is the lightest thing docling can parse text-layer-only.
    src = tmp_path / "memo.html"
    src.write_text(
        "<html><body><h1>Memo</h1>"
        "<p>Reach Jane at jane@acme.com or SSN 123-45-6789.</p></body></html>",
        encoding="utf-8",
    )
    c = _engine()
    res = c.mask_document(str(src))
    md = res.to_markdown()
    assert "jane@acme.com" not in md and "123-45-6789" not in md
    assert "[EMAIL_1]" in md
