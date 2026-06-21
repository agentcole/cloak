"""The vault: the original ↔ token map that makes cloaking reversible.

One vault is shared across all content in a single request so the *same* value
gets the *same* token everywhere (coreference) — which both reads naturally to
the model and keeps provider prefix caches stable.

The vault is the only thing needed to restore a response, so treat it as
sensitive: it contains the original PII. It can be serialized for cross-process
surfaces (CLI, MCP, proxy) and optionally encrypted at rest.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import TYPE_CHECKING, Any

from .types import VaultEntry

if TYPE_CHECKING:
    from .strategies.base import Strategy

logger = logging.getLogger("cloak")

# Shape of a cloak token already present in input (placeholder/redact/hash), so
# we don't generate a colliding one. Allows lowercase for hash suffixes.
_TOKEN_RE = re.compile(r"\[[A-Z][A-Za-z0-9_]*\]")


def _random_salt() -> str:
    return os.urandom(8).hex()


def _suffix(token: str, n: int) -> str:
    """Append a disambiguator, keeping the trailing ``]`` if present."""
    return f"{token[:-1]}.{n}]" if token.endswith("]") else f"{token}.{n}"


class Vault:
    def __init__(self, salt: str | None = None) -> None:
        self.salt = salt or _random_salt()
        self._token_by_key: dict[tuple[str, str], str] = {}
        self._original_by_token: dict[str, str] = {}
        self._counter: dict[str, int] = {}
        self._entries: list[VaultEntry] = []
        # Token literals already present in the input — never generate these,
        # or restore would corrupt the pre-existing literal (idempotency / A7).
        self._reserved: set[str] = set()

    # -- allocation -------------------------------------------------------

    def reserve(self, text: str) -> None:
        """Record cloak-shaped token literals already in ``text`` as off-limits.

        Call before masking so a real value can't be assigned a token that
        already appears verbatim in the input.
        """
        self._reserved.update(_TOKEN_RE.findall(text))

    def _token_taken(self, token: str, original: str) -> bool:
        if token in self._reserved:
            return True
        owner = self._original_by_token.get(token)
        return owner is not None and owner != original

    def allocate(self, entity: Any, strategy: Strategy) -> str:
        """Return the token for ``entity``, creating one if needed.

        Coreference: a repeat of the same (type, text) returns the existing
        token. Token collisions — with a different original, or with a literal
        already present in the input — are broken by re-salting, then a suffix.
        """
        key = (entity.type, entity.text)
        existing = self._token_by_key.get(key)
        if existing is not None:
            return existing

        idx = self._counter.get(entity.type, 0) + 1
        self._counter[entity.type] = idx

        token = strategy.generate(entity, idx, self.salt)
        if strategy.reversible and self._token_taken(token, entity.text):
            base = token
            n = 1
            while self._token_taken(token, entity.text):
                n += 1
                # Re-salting varies hash/pseudonym output; placeholder ignores
                # the salt, so fall back to a readable suffix.
                resalted = strategy.generate(entity, idx, f"{self.salt}:{n}")
                token = resalted if resalted != base else _suffix(base, n)
                if n > 1000:
                    token = _suffix(base, idx)
                    break

        self._token_by_key[key] = token
        self._entries.append(
            VaultEntry(
                token=token, original=entity.text, type=entity.type, reversible=strategy.reversible
            )
        )
        if strategy.reversible:
            self._original_by_token[token] = entity.text
        return token

    # -- restoration ------------------------------------------------------

    def reversible_entries(self) -> list[VaultEntry]:
        """Reversible entries, longest token first.

        Longest-first avoids a shorter token being a prefix/substring of a
        longer one during naive string replacement on restore.
        """
        entries = [e for e in self._entries if e.reversible]
        entries.sort(key=lambda e: len(e.token), reverse=True)
        return entries

    def restore(self, text: str) -> str:
        """Replace every reversible token in ``text`` with its original."""
        for entry in self.reversible_entries():
            if entry.token in text:
                text = text.replace(entry.token, entry.original)
        return text

    # -- introspection ----------------------------------------------------

    @property
    def entries(self) -> list[VaultEntry]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __bool__(self) -> bool:
        return bool(self._entries)

    def __repr__(self) -> str:
        # Never include originals/tokens — a vault holds raw PII and may be
        # logged accidentally.
        return f"<Vault entries={len(self._entries)} (contents hidden)>"

    __str__ = __repr__

    def clear(self) -> None:
        """Wipe all mappings (zeroize). The vault can no longer restore."""
        self._token_by_key.clear()
        self._original_by_token.clear()
        self._counter.clear()
        self._entries.clear()
        self._reserved.clear()

    def __enter__(self) -> Vault:
        return self

    def __exit__(self, *exc: object) -> None:
        # Auto-wipe PII when used as a context manager:
        #   with cloak.mask_text(t).vault as v: ... (cleared on exit)
        self.clear()

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "salt": self.salt,
            "counter": dict(self._counter),
            "entries": [
                {
                    "token": e.token,
                    "original": e.original,
                    "type": e.type,
                    "reversible": e.reversible,
                }
                for e in self._entries
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Vault:
        vault = cls(salt=data.get("salt"))
        vault._counter = {k: int(v) for k, v in data.get("counter", {}).items()}
        for raw in data.get("entries", []):
            entry = VaultEntry(
                token=raw["token"],
                original=raw["original"],
                type=raw["type"],
                reversible=raw.get("reversible", True),
            )
            vault._entries.append(entry)
            vault._token_by_key[(entry.type, entry.original)] = entry.token
            if entry.reversible:
                vault._original_by_token[entry.token] = entry.original
        return vault

    def save(self, path: str, password: str | None = None) -> None:
        """Persist the vault as JSON, optionally encrypted with ``password``.

        Encryption uses Fernet (AES-128-CBC + HMAC) via the optional
        ``cryptography`` package. Without a password the vault is written as
        plaintext JSON — fine for ephemeral local use, but it contains raw PII.
        """
        payload = json.dumps(self.to_dict()).encode()
        if password is not None:
            payload = _encrypt(payload, password)
        elif self._entries:
            logger.warning(
                "Vault.save(%s) is writing UNENCRYPTED raw PII; pass password=... "
                "to encrypt at rest.",
                path,
            )
        with open(path, "wb") as fh:
            fh.write(payload)

    @classmethod
    def load(cls, path: str, password: str | None = None) -> Vault:
        with open(path, "rb") as fh:
            raw = fh.read()
        if password is not None:
            raw = _decrypt(raw, password)
        return cls.from_dict(json.loads(raw.decode()))


# -- optional at-rest encryption -----------------------------------------


def _fernet(password: str) -> Any:
    import base64
    import hashlib

    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Encrypted vaults require the 'cryptography' package. "
            "Install it with: pip install cryptography"
        ) from exc
    key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
    return Fernet(key)


def _encrypt(data: bytes, password: str) -> bytes:
    return _fernet(password).encrypt(data)


def _decrypt(data: bytes, password: str) -> bytes:
    return _fernet(password).decrypt(data)
