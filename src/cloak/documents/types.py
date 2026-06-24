"""Document value types — the bridge between docling's structured documents and
cloak's flat-string pipeline.

These are intentionally dependency-free dataclasses (no docling import) so the
masker and renderers can be exercised on synthetic segments without the heavy
``[docling]`` extra installed. A :class:`Segment` may optionally carry a
reference to its backing docling node, which the masker writes masked text back
into so structure-faithful exporters (JSON, structure-aware markdown) reflect
the masked content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..types import Entity

if TYPE_CHECKING:
    from ..vault import Vault

# A bounding box in PDF points: (x0, y0, x1, y1).
BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class Segment:
    """One unit of text in a parsed document, with its provenance.

    The ``text`` is what cloak masks. ``page``/``bbox`` are the provenance an
    in-place PDF redactor needs; they are ``None`` for non-paginated inputs
    (HTML) or when a backend does not expose layout. ``node`` is the underlying
    docling item (if any) so the masker can write masked text back for
    structure-faithful re-export — it is excluded from equality and repr because
    it is a heavy, opaque object.
    """

    text: str
    order: int
    node_id: str | None = None
    page: int | None = None
    bbox: BBox | None = None
    kind: str = "text"  # text | heading | list_item | table_cell | caption | ...
    node: Any = field(default=None, repr=False, compare=False)


@dataclass
class SegmentedDoc:
    """An ordered, provenance-carrying view of a parsed document."""

    segments: list[Segment]
    source_path: str | None = None
    backend: str = "docling"
    raw: Any = None  # the underlying DoclingDocument, when a docling backend ran


@dataclass(frozen=True)
class DocEntity:
    """A detected entity plus the document location it was found at.

    ``entity`` offsets are local to its segment's text (not the whole document),
    mirroring how the engine reports spans per masked string.
    """

    entity: Entity
    order: int  # the segment's reading-order index
    page: int | None = None
    bbox: BBox | None = None
    kind: str = "text"

    @property
    def type(self) -> str:
        return self.entity.type

    @property
    def text(self) -> str:
        return self.entity.text

    @property
    def score(self) -> float:
        return self.entity.score


@dataclass
class DocumentResult:
    """Result of masking a document.

    ``doc`` is the masked :class:`SegmentedDoc`; ``vault`` restores the *text*
    of an LLM's answer (never the binary file); ``entities`` carry page/bbox
    provenance for reporting and in-place redaction.
    """

    doc: SegmentedDoc
    vault: Vault
    entities: list[DocEntity] = field(default_factory=list)
    mode: str = "mask"  # "mask" (reversible) | "redact" (one-way)

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    def by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.entities:
            counts[e.type] = counts.get(e.type, 0) + 1
        return counts

    # -- rendering (lazy imports keep heavy deps optional) ----------------

    def to_markdown(self) -> str:
        """Render the masked document as markdown.

        docling's markdown exporter escapes markdown metacharacters (notably
        ``_`` → ``\\_``) in prose, which would corrupt our tokens (``[EMAIL_1]``
        → ``[EMAIL\\_1]``) and break ``vault.restore`` on the response. We
        normalize every known token literal back to its clean form so the
        reversible round trip holds.
        """
        from .renderers.markdown import render_markdown

        return self._normalize_tokens(render_markdown(self.doc))

    def _normalize_tokens(self, md: str) -> str:
        import re

        if self.vault is None:
            return md
        for entry in self.vault.entries:
            tok = entry.token
            # Match the token with an optional backslash before any character,
            # so an escaped rendering (``[EMAIL\_1]``) collapses back to ``tok``.
            pattern = "".join("\\\\?" + re.escape(ch) for ch in tok)
            md = re.sub(pattern, lambda _m, t=tok: t, md)
        return md

    def to_json(self) -> dict[str, Any]:
        """Render the masked document as a JSON-able dict."""
        from .renderers.json_ import render_json

        return render_json(self.doc)

    def to_text(self) -> str:
        """Plain-text rendering (markdown without the table/heading pipes is fine
        as text; this returns the masked markdown, readable as a text file)."""
        return self.to_markdown()

    def to_pdf(self) -> bytes:
        """Render an in-place **redacted** PDF (PyMuPDF) from the original file.

        True redaction: detected PII is located and its glyphs removed, then
        metadata is scrubbed. One-way — the vault does not restore the file.
        Requires the source path on ``self.doc`` and the ``[docling]`` extra.
        """
        from .renderers.pdf import render_pdf

        return render_pdf(self)

    def to_docx(self, *, render: str = "in-place") -> bytes:
        """Render a masked/redacted DOCX (B9 step 3–4 — not yet implemented)."""
        raise NotImplementedError(
            "DOCX rendering lands in a later step (see docs/documents-plan.md). "
            "Use to_markdown()/to_json() for now."
        )
