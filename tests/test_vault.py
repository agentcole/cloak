"""Vault allocation, coreference, collision handling, and serialization."""

from __future__ import annotations

from cloak.strategies.placeholder import PlaceholderStrategy
from cloak.strategies.redact import RedactStrategy
from cloak.types import Entity
from cloak.vault import Vault


def _ent(t, text, start=0):
    return Entity(type=t, start=start, end=start + len(text), text=text)


def test_allocate_is_stable_and_coreferent():
    v = Vault(salt="s")
    strat = PlaceholderStrategy()
    a = v.allocate(_ent("EMAIL", "x@y.com"), strat)
    b = v.allocate(_ent("EMAIL", "x@y.com", 20), strat)
    c = v.allocate(_ent("EMAIL", "z@y.com", 40), strat)
    assert a == b == "[EMAIL_1]"
    assert c == "[EMAIL_2]"


def test_restore_replaces_tokens():
    v = Vault(salt="s")
    strat = PlaceholderStrategy()
    tok = v.allocate(_ent("PERSON", "Jane Doe"), strat)
    assert v.restore(f"hello {tok}") == "hello Jane Doe"


def test_redacted_entries_not_reversible():
    v = Vault(salt="s")
    strat = RedactStrategy()
    tok = v.allocate(_ent("EMAIL", "x@y.com"), strat)
    assert tok == "[EMAIL]"
    # Not stored reversibly -> restore leaves it as-is.
    assert v.restore("a [EMAIL] b") == "a [EMAIL] b"
    assert v.reversible_entries() == []


def test_serialization_roundtrip():
    v = Vault(salt="s")
    strat = PlaceholderStrategy()
    v.allocate(_ent("EMAIL", "x@y.com"), strat)
    v.allocate(_ent("IP_ADDRESS", "10.0.0.1"), strat)
    restored = Vault.from_dict(v.to_dict())
    assert restored.restore("[EMAIL_1] / [IP_ADDRESS_1]") == "x@y.com / 10.0.0.1"
    # Coreference index survives so further allocations continue the sequence.
    nxt = restored.allocate(_ent("EMAIL", "new@y.com"), strat)
    assert nxt == "[EMAIL_2]"


def test_longest_token_restored_first():
    # Ensure a token that is a substring of another restores correctly.
    v = Vault(salt="s")
    v._entries.clear()
    from cloak.types import VaultEntry

    v._entries.append(VaultEntry("[X_1]", "AAA", "X"))
    v._entries.append(VaultEntry("[X_12]", "BBB", "X"))
    v._original_by_token["[X_1]"] = "AAA"
    v._original_by_token["[X_12]"] = "BBB"
    assert v.restore("[X_12]") == "BBB"
