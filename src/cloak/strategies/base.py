"""Replacement strategy interface.

A strategy turns a detected :class:`~cloak.types.Entity` into the token that
takes its place in the outgoing text. Strategies are *pluggable* — the policy
selects one globally and/or per entity type.

``reversible`` declares whether the produced token uniquely identifies the
original (so the vault can restore it on the response path). Redaction is the
one built-in irreversible strategy.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import Entity


class Strategy(ABC):
    name: str = "base"
    reversible: bool = True

    @abstractmethod
    def generate(self, entity: Entity, index: int, salt: str) -> str:
        """Produce the replacement token for ``entity``.

        Args:
            entity: The detected entity being replaced.
            index: 1-based per-type counter (``PERSON`` #1, #2, …). Used by the
                placeholder strategy and as a uniqueness hint elsewhere.
            salt: Per-vault salt (optionally suffixed on retry to break a token
                collision deterministically).
        """
        raise NotImplementedError
