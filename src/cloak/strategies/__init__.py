"""Replacement strategies and a small factory keyed by policy."""

from __future__ import annotations

from ..policy import (
    STRATEGY_HASH,
    STRATEGY_PLACEHOLDER,
    STRATEGY_PSEUDONYM,
    STRATEGY_REDACT,
    CloakPolicy,
)
from .base import Strategy
from .hash_strategy import HashStrategy
from .placeholder import PlaceholderStrategy
from .pseudonym import PseudonymStrategy
from .redact import RedactStrategy

__all__ = [
    "Strategy",
    "PlaceholderStrategy",
    "PseudonymStrategy",
    "RedactStrategy",
    "HashStrategy",
    "build_strategy",
    "build_strategy_map",
]


def build_strategy(name: str, policy: CloakPolicy) -> Strategy:
    """Instantiate a strategy by name using settings from ``policy``."""
    if name == STRATEGY_PLACEHOLDER:
        return PlaceholderStrategy()
    if name == STRATEGY_HASH:
        return HashStrategy()
    if name == STRATEGY_REDACT:
        return RedactStrategy(numbered=policy.redact_numbered)
    if name == STRATEGY_PSEUDONYM:
        return PseudonymStrategy(locale=policy.locale)
    raise ValueError(f"Unknown replacement strategy: {name!r}")


def build_strategy_map(policy: CloakPolicy) -> dict[str, Strategy]:
    """Build the set of strategy instances referenced by a policy.

    Returns a map of strategy-name → instance covering the global default plus
    every per-type override, so each is constructed at most once.
    """
    names = {policy.strategy, *policy.strategy_by_type.values()}
    return {name: build_strategy(name, policy) for name in names}
