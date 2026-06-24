"""Markdown rendering of a masked document.

Two paths:

* **Structure-faithful** — when the masked ``DoclingDocument`` is present (its
  text nodes were updated in place by the masker), use docling's own
  ``export_to_markdown`` so tables/headings/lists render exactly.
* **Fallback** — re-emit from the masked :class:`Segment` list, so markdown
  works with no docling installed (and for synthetic documents in tests).
"""

from __future__ import annotations

from ..types import Segment, SegmentedDoc

# Heading-ish kinds get an ATX prefix; list items a bullet. Anything else is a
# plain paragraph. Kept deliberately small — the faithful path handles the rest.
_HEADINGS = {"title", "section_header", "heading", "subtitle"}
_LIST = {"list_item", "list"}


def render_markdown(doc: SegmentedDoc) -> str:
    if doc.raw is not None:
        try:
            return doc.raw.export_to_markdown()
        except Exception:  # noqa: BLE001 — fall back to segment re-emit
            pass
    return _from_segments(doc.segments)


def _from_segments(segments: list[Segment]) -> str:
    blocks: list[str] = []
    for seg in sorted(segments, key=lambda s: s.order):
        text = seg.text.strip()
        if not text:
            continue
        kind = (seg.kind or "text").lower()
        if kind in _HEADINGS:
            blocks.append(f"# {text}")
        elif kind in _LIST:
            blocks.append(f"- {text}")
        else:
            blocks.append(text)
    return "\n\n".join(blocks) + ("\n" if blocks else "")
