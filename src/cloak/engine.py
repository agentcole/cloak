"""The :class:`Cloak` engine — orchestrates detect → resolve → replace → restore.

Typical use::

    from cloak import Cloak, CloakPolicy

    c = Cloak(CloakPolicy(strategy="pseudonym"))
    res = c.mask_text("Email jane@acme.com about the Q3 report")
    send_to_llm(res.text)
    answer = c.unmask_text(llm_reply, res.vault)
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any

from .detectors.base import Detector
from .detectors.phone_detector import PhoneDetector
from .detectors.regex_detector import RegexDetector
from .policy import (
    DETECTOR_LLM,
    DETECTOR_NER,
    DETECTOR_PHONE,
    DETECTOR_REGEX,
    CloakPolicy,
)
from .resolver import Resolver
from .strategies import build_strategy_map
from .strategies.base import Strategy
from .types import CloakResult, Entity
from .vault import Vault

logger = logging.getLogger("cloak")


class Cloak:
    """Reversible PII masking engine bound to a :class:`CloakPolicy`."""

    def __init__(self, policy: CloakPolicy | None = None) -> None:
        self.policy = policy or CloakPolicy()
        self.resolver = Resolver(self.policy)
        self._strategies = build_strategy_map(self.policy)
        self._detectors = self._build_detectors()

    # -- setup ------------------------------------------------------------

    def _build_detectors(self) -> list[Detector]:
        detectors: list[Detector] = []
        for name in self.policy.detectors:
            if name == DETECTOR_REGEX:
                # The regex tier covers structured PII + phone numbers (the
                # latter via phonenumbers when installed, else a regex fallback).
                detectors.append(RegexDetector())
                detectors.append(PhoneDetector(self.policy))
            elif name == DETECTOR_PHONE:
                detectors.append(PhoneDetector(self.policy))
            elif name == DETECTOR_NER:
                from .detectors.ner_detector import NerDetector

                det = NerDetector(self.policy)
                if det.available():
                    detectors.append(det)
                else:
                    logger.warning(
                        "NER detector requested but unavailable "
                        '(install with: pip install "cloak-llm[ner]"); skipping'
                    )
            elif name == DETECTOR_LLM:
                from .detectors.llm_detector import LlmDetector

                detectors.append(LlmDetector(self.policy))
            else:
                logger.warning("Unknown detector %r in policy; skipping", name)
        return detectors

    def _salt(self) -> str | None:
        return str(self.policy.seed) if self.policy.seed is not None else None

    def _strategy_for(self, entity_type: str) -> Strategy:
        return self._strategies[self.policy.strategy_for(entity_type)]

    # -- detection --------------------------------------------------------

    def _denylist_entities(self, text: str) -> list[Entity]:
        out: list[Entity] = []
        for literal in self.policy.denylist:
            if not literal:
                continue
            for m in re.finditer(re.escape(literal), text):
                out.append(
                    Entity(
                        type="CUSTOM",
                        start=m.start(),
                        end=m.end(),
                        text=m.group(0),
                        score=1.0,
                        source="denylist",
                    )
                )
        return out

    def scan(self, text: str) -> list[Entity]:
        """Detect and resolve sensitive spans in ``text`` (no replacement)."""
        found: list[Entity] = []
        for detector in self._detectors:
            try:
                found.extend(detector.detect(text, self.policy))
            except Exception as exc:  # detectors must never break the pipeline
                logger.warning("Detector %s failed: %s", detector.name, exc)
        found.extend(self._denylist_entities(text))
        return self.resolver.resolve(found, text)

    # -- masking ----------------------------------------------------------

    def _replace(self, text: str, entities: list[Entity], vault: Vault) -> str:
        spans: list[tuple[int, int, str]] = []
        for e in entities:
            token = vault.allocate(e, self._strategy_for(e.type))
            spans.append((e.start, e.end, token))
        # Apply right-to-left so earlier offsets stay valid.
        for start, end, token in sorted(spans, key=lambda s: s[0], reverse=True):
            text = text[:start] + token + text[end:]
        return text

    def mask_text(self, text: str, vault: Vault | None = None) -> CloakResult:
        """Mask a single string, returning the masked text and its vault."""
        vault = vault if vault is not None else Vault(salt=self._salt())
        vault.reserve(text)  # don't reuse a token literal already in the input
        entities = self.scan(text)
        masked = self._replace(text, entities, vault)
        return CloakResult(
            text=masked,
            vault=vault,
            entities=entities,
            stats={"entities": len(entities), "by_type": _count(entities)},
        )

    def unmask_text(self, text: str, vault: Vault) -> str:
        """Restore originals in ``text`` using ``vault`` (the response path)."""
        return vault.restore(text)

    # -- masking: chat messages ------------------------------------------

    def mask_messages(
        self, messages: list[dict[str, Any]], vault: Vault | None = None
    ) -> CloakResult:
        """Mask the content of chat messages, sharing one vault for coreference.

        Handles string content and OpenAI/Anthropic-style block lists
        (``[{"type": "text", "text": ...}]``). Only roles in ``policy.roles``
        are scanned.
        """
        vault = vault if vault is not None else Vault(salt=self._salt())
        out = copy.deepcopy(messages)
        entities: list[Entity] = []
        for msg in out:
            if msg.get("role") not in self.policy.roles:
                continue
            msg["content"] = self._mask_content(msg.get("content"), vault, entities)
        return CloakResult(
            messages=out,
            vault=vault,
            entities=entities,
            stats={"entities": len(entities), "by_type": _count(entities)},
        )

    def _mask_content(self, content: Any, vault: Vault, acc: list[Entity]) -> Any:
        if isinstance(content, str):
            res = self.mask_text(content, vault)
            acc.extend(res.entities)
            return res.text
        if isinstance(content, list):
            return [self._mask_content(block, vault, acc) for block in content]
        if isinstance(content, dict):
            block = dict(content)
            if isinstance(block.get("text"), str):
                res = self.mask_text(block["text"], vault)
                acc.extend(res.entities)
                block["text"] = res.text
            elif "content" in block:
                block["content"] = self._mask_content(block["content"], vault, acc)
            return block
        return content

    # -- masking: documents ----------------------------------------------

    def scan_document(self, source: Any, *, ocr: bool = False) -> list[Any]:
        """Detect PII across a document, tagged with page/bbox provenance.

        ``source`` is a file path (parsed via the optional ``[docling]`` extra)
        or an already-parsed ``SegmentedDoc``. Returns ``DocEntity`` objects.
        """
        from .documents import scan_document as _scan_document

        return _scan_document(self._as_segmented(source, ocr=ocr), self)

    def mask_document(self, source: Any, *, ocr: bool = False, mode: str = "mask") -> Any:
        """Mask (reversible) or redact (one-way) a whole document.

        ``source`` is a file path or a ``SegmentedDoc``. Returns a
        ``DocumentResult`` whose ``.to_markdown()`` / ``.to_json()`` render the
        masked content and whose ``.vault`` restores an LLM answer's *text*.
        """
        from .documents import mask_document as _mask_document

        return _mask_document(self._as_segmented(source, ocr=ocr), self, mode=mode)

    @staticmethod
    def _as_segmented(source: Any, *, ocr: bool) -> Any:
        from .documents import SegmentedDoc
        from .documents.parser import get_parser

        if isinstance(source, SegmentedDoc):
            return source
        return get_parser().parse(source, ocr=ocr)

    def unmask_messages(self, messages: list[dict[str, Any]], vault: Vault) -> list[dict[str, Any]]:
        """Restore originals across a list of messages."""
        out = copy.deepcopy(messages)
        for msg in out:
            msg["content"] = self._unmask_content(msg.get("content"), vault)
        return out

    def _unmask_content(self, content: Any, vault: Vault) -> Any:
        if isinstance(content, str):
            return vault.restore(content)
        if isinstance(content, list):
            return [self._unmask_content(b, vault) for b in content]
        if isinstance(content, dict):
            block = dict(content)
            if isinstance(block.get("text"), str):
                block["text"] = vault.restore(block["text"])
            elif "content" in block:
                block["content"] = self._unmask_content(block["content"], vault)
            return block
        return content


def _count(entities: list[Entity]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in entities:
        counts[e.type] = counts.get(e.type, 0) + 1
    return counts


# -- module-level convenience -------------------------------------------

_default: Cloak | None = None


def _get_default() -> Cloak:
    global _default
    if _default is None:
        _default = Cloak()
    return _default


def mask(text: str) -> CloakResult:
    """Mask ``text`` with a default (placeholder + regex + NER) policy."""
    return _get_default().mask_text(text)


def unmask(text: str, vault: Vault) -> str:
    """Restore ``text`` using ``vault``."""
    return vault.restore(text)


def scan(text: str) -> list[Entity]:
    """Detect sensitive spans in ``text`` with the default policy."""
    return _get_default().scan(text)
