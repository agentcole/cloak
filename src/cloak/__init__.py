"""cloak — local-first, reversible PII redaction for LLM prompts.

Quick start::

    from cloak import Cloak, CloakPolicy

    c = Cloak(CloakPolicy(strategy="placeholder"))
    res = c.mask_text("Call Jane Doe at +1 415 555 0123")
    # res.text  -> "Call [PERSON_1] at [PHONE_1]"
    original = c.unmask_text(res.text, res.vault)
"""

from __future__ import annotations

from ._version import __version__
from .engine import Cloak, mask, scan, unmask
from .policy import (
    DETECTOR_LLM,
    DETECTOR_NER,
    DETECTOR_REGEX,
    STRATEGY_HASH,
    STRATEGY_PLACEHOLDER,
    STRATEGY_PSEUDONYM,
    STRATEGY_REDACT,
    CloakPolicy,
)
from .profiles import PROFILES, profile_names
from .types import CloakResult, Entity, VaultEntry
from .vault import Vault

__all__ = [
    "__version__",
    "Cloak",
    "CloakPolicy",
    "CloakResult",
    "Entity",
    "VaultEntry",
    "Vault",
    "mask",
    "unmask",
    "scan",
    "PROFILES",
    "profile_names",
    "STRATEGY_PLACEHOLDER",
    "STRATEGY_PSEUDONYM",
    "STRATEGY_REDACT",
    "STRATEGY_HASH",
    "DETECTOR_REGEX",
    "DETECTOR_NER",
    "DETECTOR_LLM",
]
