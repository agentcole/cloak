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

    def __init__(self, label: str | None = None, typed: bool = True) -> None:
        """
        Args:
            label: Fixed replacement text. If set, used for every entity.
            typed: When no ``label`` is given, emit ``[TYPE]`` instead of a
                generic ``[REDACTED]``.
        """
        self.label = label
        self.typed = typed

    def generate(self, entity: Entity, index: int, salt: str) -> str:
        if self.label is not None:
            return self.label
        return f"[{entity.type.upper()}]" if self.typed else "[REDACTED]"
