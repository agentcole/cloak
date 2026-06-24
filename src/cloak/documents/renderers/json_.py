"""JSON rendering of a masked document.

When the masked ``DoclingDocument`` is present, emit its full structured export
(``export_to_dict``) — machine-readable and re-convertible to any docling
output. Otherwise emit a simple, stable segment-list document so JSON output
works without docling (and for synthetic documents in tests).
"""

from __future__ import annotations

from typing import Any

from ..types import SegmentedDoc


def render_json(doc: SegmentedDoc) -> dict[str, Any]:
    if doc.raw is not None:
        try:
            return doc.raw.export_to_dict()
        except Exception:  # noqa: BLE001 — fall back to segment list
            pass
    return {
        "schema": "cloak.segmented-doc/v1",
        "source_path": doc.source_path,
        "backend": doc.backend,
        "segments": [
            {
                "order": s.order,
                "kind": s.kind,
                "page": s.page,
                "bbox": list(s.bbox) if s.bbox else None,
                "text": s.text,
            }
            for s in sorted(doc.segments, key=lambda s: s.order)
        ],
    }
