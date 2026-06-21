"""Core value types shared across cloak.

These are intentionally dependency-free dataclasses so the core engine can run
on the standard library alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Entity:
    """A detected span of sensitive content in a piece of text.

    Attributes:
        type: Entity category, e.g. ``PERSON``, ``EMAIL``, ``CREDIT_CARD``.
        start: Inclusive start offset into the source text.
        end: Exclusive end offset into the source text.
        text: The exact substring ``source[start:end]``.
        score: Detector confidence in ``[0.0, 1.0]``.
        source: Which detector produced this entity (``regex``/``ner``/``llm``/``denylist``).
    """

    type: str
    start: int
    end: int
    text: str
    score: float = 1.0
    source: str = "regex"

    def __len__(self) -> int:
        return self.end - self.start

    @property
    def span(self) -> tuple[int, int]:
        return (self.start, self.end)

    def overlaps(self, other: Entity) -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(repr=False)
class VaultEntry:
    """A single reversible mapping between an original value and its token."""

    token: str
    original: str
    type: str
    reversible: bool = True

    def __repr__(self) -> str:
        # Mask the original — a VaultEntry holds raw PII.
        shown = (self.original[:1] + "…") if self.original else ""
        return f"VaultEntry(token={self.token!r}, type={self.type!r}, original='{shown}')"


@dataclass
class CloakResult:
    """Result of a mask operation.

    Exactly one of :attr:`text` or :attr:`messages` is populated, mirroring the
    shape of the input that was masked.
    """

    text: str | None = None
    messages: list[dict[str, Any]] | None = None
    vault: Any = None  # cloak.vault.Vault — Any to avoid an import cycle.
    entities: list[Entity] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    def by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.entities:
            counts[e.type] = counts.get(e.type, 0) + 1
        return counts
