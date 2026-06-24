"""Document support — parse whole documents (PDF/DOCX/PPTX/HTML/images) for
scan, reversible masking, and one-way redaction.

The value types, masker, and renderers are dependency-free; only the docling
parser needs the optional ``cloak-llm[docling]`` extra. See
``docs/documents-plan.md`` for the design and roadmap.
"""

from __future__ import annotations

from .masker import MODE_MASK, MODE_REDACT, mask_document, scan_document
from .parser import DoclingParser, DocumentParser, get_parser
from .types import BBox, DocEntity, DocumentResult, Segment, SegmentedDoc

__all__ = [
    "Segment",
    "SegmentedDoc",
    "DocEntity",
    "DocumentResult",
    "BBox",
    "DocumentParser",
    "DoclingParser",
    "get_parser",
    "scan_document",
    "mask_document",
    "MODE_MASK",
    "MODE_REDACT",
]
