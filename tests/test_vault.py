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


def test_reserve_avoids_colliding_with_input_literal():
    v = Vault(salt="s")
    v.reserve("text containing a [EMAIL_1] literal")
    token = v.allocate(_ent("EMAIL", "new@x.com"), PlaceholderStrategy())
    assert token != "[EMAIL_1]"
    assert v.restore(f"{token}") == "new@x.com"


def test_clear_zeroizes():
    v = Vault(salt="s")
    v.allocate(_ent("EMAIL", "x@y.com"), PlaceholderStrategy())
    v.clear()
    assert len(v) == 0
    assert v.restore("[EMAIL_1]") == "[EMAIL_1]"  # nothing to restore


def test_context_manager_clears_on_exit():
    v = Vault(salt="s")
    with v as inner:
        inner.allocate(_ent("EMAIL", "x@y.com"), PlaceholderStrategy())
        assert len(inner) == 1
    assert len(v) == 0


def test_repr_does_not_leak_pii():
    v = Vault(salt="s")
    v.allocate(_ent("EMAIL", "secret@example.com"), PlaceholderStrategy())
    assert "secret@example.com" not in repr(v)
    assert "secret@example.com" not in repr(v.entries[0])
    assert "secret@example.com" not in str(v)


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
