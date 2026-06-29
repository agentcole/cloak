"""Redaction strategy: irreversible scrub to a fixed label.

By default emits a typed label like ``[PERSON]`` (more useful to the model than
a bare block), or a custom label. Marked ``reversible = False`` so the vault
deliberately does not keep a mapping — redacted values cannot be restored.
"""

from __future__ import annotations

from ..types import Entity
from .base import Strategy


class RedactStrategy(Strategy):
    name = "redact"
    reversible = False

    def __init__(
        self, label: str | None = None, typed: bool = True, numbered: bool = False
    ) -> None:
        """
        Args:
            label: Fixed replacement text. If set, used for every entity.
            typed: When no ``label`` is given, emit ``[TYPE]`` instead of a
                generic ``[REDACTED]``.
            numbered: When typed, emit ``[TYPE_N]`` so coreferent mentions are
                visibly linked (still irreversible — no mapping is stored).
        """
        self.label = label
        self.typed = typed
        self.numbered = numbered

    def generate(self, entity: Entity, index: int, salt: str) -> str:
        if self.label is not None:
            return self.label
        if not self.typed:
            return "[REDACTED]"
        type_ = entity.type.upper()
        return f"[{type_}_{index}]" if self.numbered else f"[{type_}]"
