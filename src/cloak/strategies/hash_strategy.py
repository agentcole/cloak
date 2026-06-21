"""Deterministic-hash strategy: ``[EMAIL_a1b2c3d4]``.

Reversible via the vault, stable across runs for a fixed salt (good for
correlating the same value across requests), and opaque to the model.
"""

from __future__ import annotations

import hashlib

from ..types import Entity
from .base import Strategy


class HashStrategy(Strategy):
    name = "hash"
    reversible = True

    def __init__(self, length: int = 8) -> None:
        self.length = length

    def generate(self, entity: Entity, index: int, salt: str) -> str:
        digest = hashlib.sha256(f"{salt}:{entity.type}:{entity.text}".encode()).hexdigest()
        return f"[{entity.type.upper()}_{digest[: self.length]}]"
