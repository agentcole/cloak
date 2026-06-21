"""Labeled-placeholder strategy: ``[PERSON_1]``, ``[EMAIL_2]``, …

Fully reversible and cache-friendly (same value → same token). The LLM can see
the type and that the value is a placeholder, which helps it reason without
leaking the original.
"""

from __future__ import annotations

from ..types import Entity
from .base import Strategy


class PlaceholderStrategy(Strategy):
    name = "placeholder"
    reversible = True

    def generate(self, entity: Entity, index: int, salt: str) -> str:
        return f"[{entity.type.upper()}_{index}]"
