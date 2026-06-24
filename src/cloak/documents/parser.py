"""Document parsing — turn a file into a :class:`SegmentedDoc`.

The only backend today is docling (PDF/DOCX/PPTX/HTML/images). It is imported
lazily so the dependency-free core is untouched; a missing extra yields a clean
"install cloak-llm[docling]" message rather than an ImportError traceback.
"""

from __future__ import annotations

import importlib.util
import logging
from typing import Any, Protocol, runtime_checkable

from .types import BBox, Segment, SegmentedDoc

logger = logging.getLogger("cloak")

_DOCLING_HINT = (
    "document parsing needs the optional docling backend; "
    'install it with: pip install "cloak-llm[docling]"'
)


@runtime_checkable
class DocumentParser(Protocol):
    """Parses a document path into ordered, provenance-carrying segments."""

    def parse(self, path: str, *, ocr: bool = False) -> SegmentedDoc: ...

    def available(self) -> bool: ...


class DoclingParser:
    """docling-backed parser. Heavy deps (torch, models) load lazily on first use."""

    name = "docling"

    def available(self) -> bool:
        return importlib.util.find_spec("docling") is not None

    def parse(self, path: str, *, ocr: bool = False) -> SegmentedDoc:
        if not self.available():
            raise ImportError(_DOCLING_HINT)
        converter = self._build_converter(ocr=ocr)
        result = converter.convert(path)
        document = result.document
        segments = list(self._iter_segments(document))
        return SegmentedDoc(
            segments=segments, source_path=path, backend=self.name, raw=document
        )

    # -- internals --------------------------------------------------------

    def _build_converter(self, *, ocr: bool) -> Any:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        pipeline = PdfPipelineOptions()
        pipeline.do_ocr = ocr  # scanned/image PDFs need OCR to surface text
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline)
            }
        )

    def _iter_segments(self, document: Any):
        """Walk the DoclingDocument in reading order, emitting text segments.

        Carries each item's first provenance (page + bbox) and a back-reference
        to the node so the masker can write masked text in place. Tables are a
        special case: their text lives in ``data.table_cells``, not ``.text`` —
        each non-empty cell becomes its own segment (with the cell as the
        writeback node) so PII inside tables is masked too.
        """
        order = 0
        for item, _level in document.iterate_items():
            cells = self._table_cells(item)
            if cells is not None:
                page, _ = self._provenance(item)
                ref = getattr(item, "self_ref", None)
                for cell in cells:
                    ctext = getattr(cell, "text", None)
                    if not ctext or not ctext.strip():
                        continue
                    yield Segment(
                        text=ctext,
                        order=order,
                        node_id=ref,
                        page=page,
                        bbox=self._bbox_of(getattr(cell, "bbox", None)),
                        kind="table_cell",
                        node=cell,
                    )
                    order += 1
                continue

            text = getattr(item, "text", None)
            if not text or not text.strip():
                continue
            page, bbox = self._provenance(item)
            yield Segment(
                text=text,
                order=order,
                node_id=getattr(item, "self_ref", None),
                page=page,
                bbox=bbox,
                kind=self._kind(item),
                node=item,
            )
            order += 1

    @staticmethod
    def _table_cells(item: Any) -> list[Any] | None:
        """Return a table item's cells, or ``None`` if it isn't a table."""
        data = getattr(item, "data", None)
        cells = getattr(data, "table_cells", None)
        return cells if cells else None

    @classmethod
    def _provenance(cls, item: Any) -> tuple[int | None, BBox | None]:
        prov = getattr(item, "prov", None)
        if not prov:
            return None, None
        first = prov[0]
        return getattr(first, "page_no", None), cls._bbox_of(getattr(first, "bbox", None))

    @staticmethod
    def _bbox_of(raw_bbox: Any) -> BBox | None:
        if raw_bbox is None:
            return None
        try:
            return (
                float(raw_bbox.l),
                float(raw_bbox.t),
                float(raw_bbox.r),
                float(raw_bbox.b),
            )
        except (AttributeError, TypeError, ValueError):
            return None

    @staticmethod
    def _kind(item: Any) -> str:
        label = getattr(item, "label", None)
        return str(getattr(label, "value", label) or "text")


def get_parser(backend: str = "docling") -> DocumentParser:
    """Return a parser for ``backend`` (only ``docling`` today)."""
    if backend == "docling":
        return DoclingParser()
    raise ValueError(f"unknown document backend {backend!r}")
