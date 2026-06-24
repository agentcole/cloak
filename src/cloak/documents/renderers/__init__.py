"""Renderers turn a masked :class:`~cloak.documents.types.SegmentedDoc` into an
output format. markdown and JSON ship first (reversible, no PDF-render risk);
PDF/DOCX land in later steps (see ``docs/documents-plan.md``).
"""

from __future__ import annotations

from .json_ import render_json
from .markdown import render_markdown

__all__ = ["render_markdown", "render_json"]
