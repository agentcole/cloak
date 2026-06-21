"""Pseudonym strategy: replace with realistic, format-preserving fake values.

Turns ``Jane Doe`` into e.g. ``Aaron Wells`` and ``jane@acme.com`` into a
plausible fake email. The model reasons over natural-looking text; the vault
restores the originals on the way back.

Determinism: each value is seeded from ``salt + type + text`` so the same input
always maps to the same fake. Reversible best-effort — restoration is by token
string match, so in the rare case a generated pseudonym also appears verbatim in
the model's own prose it could be over-restored. Use placeholder/hash if you
need guaranteed-unique tokens.

Requires the ``faker`` extra: ``pip install "cloak-llm[faker]"``.
"""

from __future__ import annotations

import hashlib
import threading

from ..types import Entity
from .base import Strategy


def _seed_int(salt: str, entity: Entity) -> int:
    digest = hashlib.sha256(f"{salt}:{entity.type}:{entity.text}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


class PseudonymStrategy(Strategy):
    name = "pseudonym"
    reversible = True

    def __init__(self, locale: str = "en_US") -> None:
        try:
            from faker import Faker
        except ImportError as exc:  # pragma: no cover - exercised only without extra
            raise ImportError(
                "The 'pseudonym' strategy requires Faker. "
                'Install it with: pip install "cloak-llm[faker]"'
            ) from exc
        self._faker = Faker(locale)
        # Faker.seed_instance mutates shared RNG state; guard so concurrent
        # requests (e.g. in the threaded proxy) can't interleave seed→generate.
        self._lock = threading.Lock()

    def _fake_for(self, entity: Entity) -> str:
        f = self._faker
        t = entity.type.upper()
        # Map entity categories to format-preserving Faker providers.
        mapping = {
            "PERSON": f.name,
            "EMAIL": f.email,
            "PHONE": f.phone_number,
            "ORGANIZATION": f.company,
            "ORG": f.company,
            "LOCATION": f.city,
            "GPE": f.city,
            "ADDRESS": f.address,
            "DATE": lambda: f.date(),
            "CREDIT_CARD": f.credit_card_number,
            "IBAN": f.iban,
            "SSN": f.ssn,
            "IP_ADDRESS": f.ipv4,
            "MAC_ADDRESS": f.mac_address,
            "URL": f.url,
        }
        provider = mapping.get(t)
        if provider is None:
            # Fallback for unmapped categories: a stable opaque-ish token.
            return f.lexify(text="????????")
        return str(provider())

    def generate(self, entity: Entity, index: int, salt: str) -> str:
        with self._lock:
            self._faker.seed_instance(_seed_int(salt, entity))
            return self._fake_for(entity)
