"""cloak document masking — scan / mask / redact a whole document.

Runs fully offline against a synthetic in-memory document (regex tier only, no
docling needed). Pass a real file to parse it with the optional [docling] extra:

    python examples/mask_document.py                              # offline synthetic demo
    python examples/mask_document.py examples/data/kundenkartei.pdf   # real PDF; needs [docling]

Masking is reversible (a vault restores the LLM's *text* answer); redaction is
one-way (PII removed, nothing recoverable). See docs/documents-plan.md.
"""

from __future__ import annotations

import sys

from cloak import Cloak, CloakPolicy
from cloak.documents import Segment, SegmentedDoc


def _synthetic_doc() -> SegmentedDoc:
    """A tiny two-page document with page/bbox provenance, as a parser would emit."""
    return SegmentedDoc(
        segments=[
            Segment(text="Quarterly Customer Report", order=0, kind="section_header", page=1),
            Segment(
                text="Primary contact: Jane Doe, jane@acme.com, +1 415 555 0123.",
                order=1, page=1, bbox=(72.0, 700.0, 520.0, 712.0),
            ),
            Segment(text="Account SSN on file: 123-45-6789.", order=2, page=1),
            Segment(text="For escalations, email jane@acme.com.", order=3, page=2),
        ],
        source_path="<synthetic>",
    )


def main() -> None:
    cloak = Cloak(CloakPolicy(detectors=["regex"], strategy="placeholder"))

    # Parse a real document if given a path; otherwise use the offline demo doc.
    source = sys.argv[1] if len(sys.argv) > 1 else _synthetic_doc()

    # 1) Detect-and-report: where is the PII?
    print("=== scan ===")
    for e in cloak.scan_document(source):
        where = f"page {e.page}" if e.page is not None else "?"
        print(f"  {e.type:<8} {where:<8} {e.text!r}")

    # 2) Reversible mask — this is what a model would see.
    masked = cloak.mask_document(source, mode="mask")
    print("\n=== masked markdown ===")
    print(masked.to_markdown())

    # 3) The vault restores the model's *text* answer (not the file).
    llm_reply = "I've flagged [EMAIL_1] and [PHONE_1] for follow-up."
    print("=== restore an answer ===")
    print("  LLM saw  :", llm_reply)
    print("  user sees:", masked.vault.restore(llm_reply))

    # 4) One-way redaction — produce a sanitized artifact, nothing recoverable.
    redacted = cloak.mask_document(source, mode="redact")
    print("\n=== redacted markdown (one-way) ===")
    print(redacted.to_markdown())

    # 5) When run on a real PDF, also write redacted artifacts next to it:
    #    a true in-place redacted PDF (PII glyphs removed) + a text version.
    if isinstance(source, str) and source.lower().endswith(".pdf"):
        stem = source[: -len(".pdf")]
        with open(f"{stem}.redacted.txt", "w", encoding="utf-8") as fh:
            fh.write(redacted.to_text())
        with open(f"{stem}.redacted.pdf", "wb") as fh:
            fh.write(redacted.to_pdf())
        print(f"\n[wrote {stem}.redacted.pdf and {stem}.redacted.txt]")


if __name__ == "__main__":
    main()
