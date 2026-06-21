"""Replacement strategy behaviour and the factory."""

from __future__ import annotations

import pytest

from cloak.policy import CloakPolicy
from cloak.strategies import build_strategy, build_strategy_map
from cloak.strategies.hash_strategy import HashStrategy
from cloak.strategies.placeholder import PlaceholderStrategy
from cloak.types import Entity


def _ent(t="EMAIL", text="x@y.com"):
    return Entity(type=t, start=0, end=len(text), text=text)


def test_placeholder_format():
    assert PlaceholderStrategy().generate(_ent(), 3, "salt") == "[EMAIL_3]"


def test_hash_is_deterministic_for_fixed_salt():
    s = HashStrategy()
    a = s.generate(_ent(), 1, "salt")
    b = s.generate(_ent(), 9, "salt")  # index must not affect the hash
    assert a == b
    assert a.startswith("[EMAIL_") and a.endswith("]")


def test_hash_varies_with_salt():
    s = HashStrategy()
    assert s.generate(_ent(), 1, "salt-a") != s.generate(_ent(), 1, "salt-b")


def test_build_strategy_unknown_raises():
    with pytest.raises(ValueError):
        build_strategy("nope", CloakPolicy())


def test_build_strategy_map_covers_overrides():
    policy = CloakPolicy(strategy="placeholder", strategy_by_type={"PERSON": "hash"})
    smap = build_strategy_map(policy)
    assert set(smap) == {"placeholder", "hash"}
