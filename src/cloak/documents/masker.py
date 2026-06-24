"""Mask / scan a :class:`SegmentedDoc` with one shared vault.

This module has no docling dependency — it operates on plain segments, so it is
fully exercisable on synthetic documents. Each segment is masked individually
(never the flattened export) so character offsets stay valid and coreference is
preserved across the whole document via a single shared :class:`Vault`.
"""

from __future__ import annotations

from dataclasses import replace

from ..engine import Cloak
from ..policy import STRATEGY_REDACT
from ..vault import Vault
from .types import DocEntity, DocumentResult, Segment, SegmentedDoc

MODE_MASK = "mask"
MODE_REDACT = "redact"


def scan_document(doc: SegmentedDoc, cloak: Cloak) -> list[DocEntity]:
    """Detect entities across every segment, tagged with page/bbox provenance."""
    out: list[DocEntity] = []
    for seg in doc.segments:
        for ent in cloak.scan(seg.text):
            out.append(
                DocEntity(
                    entity=ent, order=seg.order, page=seg.page, bbox=seg.bbox, kind=seg.kind
                )
            )
    return out


def mask_document(doc: SegmentedDoc, cloak: Cloak, *, mode: str = MODE_MASK) -> DocumentResult:
    """Mask (reversible) or redact (one-way) every segment, sharing one vault.

    In ``mask`` mode the policy's strategy is used and the vault is reversible —
    restore operates on the *text* of an LLM's answer, not the document. In
    ``redact`` mode the ``redact`` strategy is forced: PII is removed and nothing
    recoverable is stored.
    """
    if mode not in (MODE_MASK, MODE_REDACT):
        raise ValueError(f"mode must be {MODE_MASK!r} or {MODE_REDACT!r}, got {mode!r}")

    engine = cloak if mode == MODE_MASK else _redact_engine(cloak)
    vault = Vault(salt=engine._salt())

    masked: list[Segment] = []
    entities: list[DocEntity] = []
    for seg in doc.segments:
        res = engine.mask_text(seg.text, vault)  # shared vault -> coreference
        new_seg = replace(seg, text=res.text)
        # Write masked text back into the backing docling node (if any) so
        # structure-faithful exporters reflect the masked content.
        _writeback(seg.node, res.text)
        masked.append(new_seg)
        for ent in res.entities:
            entities.append(
                DocEntity(
                    entity=ent, order=seg.order, page=seg.page, bbox=seg.bbox, kind=seg.kind
                )
            )

    masked_doc = SegmentedDoc(
        segments=masked, source_path=doc.source_path, backend=doc.backend, raw=doc.raw
    )
    return DocumentResult(doc=masked_doc, vault=vault, entities=entities, mode=mode)


def _redact_engine(cloak: Cloak) -> Cloak:
    """A sibling engine that forces the one-way redact strategy."""
    policy = replace(cloak.policy, strategy=STRATEGY_REDACT, strategy_by_type={})
    return Cloak(policy)


def _writeback(node: object | None, text: str) -> None:
    if node is None:
        return
    try:
        node.text = text  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        pass  # node is read-only or not a text node; markdown still re-emits
