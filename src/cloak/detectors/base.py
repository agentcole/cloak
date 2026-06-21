"""Detector interface.

A detector turns raw text into a list of :class:`~cloak.types.Entity` spans. The
engine runs one or more detectors (tiered: regex → NER → LLM) and hands the
union to the resolver for overlap merging.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..policy import CloakPolicy
from ..types import Entity


class Detector(ABC):
    """Abstract base class for PII detectors."""

    name: str = "base"

    @abstractmethod
    def detect(self, text: str, policy: CloakPolicy) -> list[Entity]:
        """Return all sensitive spans found in ``text``.

        Implementations must return offsets into the *given* ``text`` and should
        never raise on ordinary input — a detector that cannot run (missing
        optional dependency, unreachable model) should return ``[]`` and warn.
        """
        raise NotImplementedError

    def available(self) -> bool:
        """Whether this detector can actually run (deps present, model reachable)."""
        return True
