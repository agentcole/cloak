"""In-place PDF redaction with PyMuPDF (fitz).

This is *true* redaction: each detected PII string is located on its page and
covered with a redaction annotation, then ``apply_redactions()`` removes the
underlying glyphs from the content stream (not merely drawing a box over them),
and ``scrub()`` strips metadata. The result is a one-way sanitized PDF — the
vault is irrelevant to it.

PyMuPDF is AGPL-3.0 and an optional ``[docling]`` extra; this is the only module
that imports it, so cloak's core stays Apache-2.0 and dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import DocumentResult

_BLACK = (0.0, 0.0, 0.0)


@dataclass
class RedactionStats:
    """How many detected spans were located and redacted vs not found on-page."""

    redacted: int = 0
    not_found: int = 0


def render_pdf(result: DocumentResult) -> bytes:
    """Return PDF bytes with every detected entity redacted in place.

    Requires the source path (the original file) on ``result.doc``. Raises
    ``ImportError`` with a clean hint if PyMuPDF isn't installed.
    """
    data, _ = render_pdf_with_stats(result)
    return data


def render_pdf_with_stats(result: DocumentResult) -> tuple[bytes, RedactionStats]:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            'PDF redaction needs PyMuPDF; install it with: pip install "cloak-llm[docling]"'
        ) from exc

    source = result.doc.source_path
    if not source:
        raise ValueError("cannot render a PDF without the original source path")

    stats = RedactionStats()
    pdf = fitz.open(source)
    try:
        # Unique (page, original) targets — a value repeats across cells/pages.
        targets: dict[int | None, set[str]] = {}
        for de in result.entities:
            targets.setdefault(de.page, set()).add(de.entity.text)

        for page_no, originals in targets.items():
            pages = (
                [pdf[page_no - 1]]
                if page_no is not None and 0 < page_no <= pdf.page_count
                else list(pdf)  # page unknown -> search the whole document
            )
            for page in pages:
                for original in originals:
                    rects = page.search_for(original)
                    if not rects:
                        stats.not_found += 1
                        continue
                    for rect in rects:
                        page.add_redact_annot(rect, fill=_BLACK)
                    stats.redacted += 1

        for page in pdf:
            page.apply_redactions()  # actually deletes the covered glyphs
        try:
            pdf.scrub()  # strip metadata, hidden text, embedded files
        except Exception:  # noqa: BLE001 - scrub is best-effort across versions
            pass
        return pdf.tobytes(), stats
    finally:
        pdf.close()
