"""Opinionated compliance presets.

A profile is a bundle of :class:`~cloak.policy.CloakPolicy` field overrides tuned
for a regulatory context. They are *starting points*, not legal guarantees —
review against your obligations.

Use via ``CloakPolicy.from_profile("gdpr")`` or the CLI ``--profile gdpr``.
"""

from __future__ import annotations

from typing import Any

# Each profile maps to CloakPolicy keyword overrides. ``enabled_types=None``
# means "mask everything detected".
PROFILES: dict[str, dict[str, Any]] = {
    # Baseline defaults (regex + NER, labeled placeholders).
    "default": {},
    # GDPR: pseudonymisation is explicitly favoured (Art. 4(5)) — replace
    # personal data with realistic fakes so downstream stays usable while
    # de-identified. Broad detection.
    "gdpr": {
        "detectors": ["regex", "ner"],
        "strategy": "pseudonym",
        "enabled_types": None,
        "min_score": 0.45,
    },
    # HIPAA Safe Harbor: scrub the 18 identifier classes. High recall, labeled
    # placeholders so clinicians/devs can still follow the text.
    "hipaa": {
        "detectors": ["regex", "ner"],
        "strategy": "placeholder",
        "enabled_types": None,
        "min_score": 0.4,
    },
    # PCI DSS: cardholder data. Tokenize (stable hash) so the same PAN
    # correlates across records without exposing it.
    "pci": {
        "detectors": ["regex"],
        "strategy": "hash",
        "enabled_types": {"CREDIT_CARD", "IBAN"},
        "min_score": 0.5,
    },
    # Maximum redaction: everything, lowest threshold, irreversible scrub.
    "strict": {
        "detectors": ["regex", "ner"],
        "strategy": "redact",
        "enabled_types": None,
        "min_score": 0.3,
        "skip_code_blocks": False,
    },
    # Secrets/credentials hygiene for logs and tool output.
    "secrets": {
        "detectors": ["regex"],
        "strategy": "redact",
        "enabled_types": {"API_KEY", "JWT", "CRYPTO_ADDRESS"},
        "min_score": 0.5,
    },
}


def profile_names() -> list[str]:
    return sorted(PROFILES)


def get_profile(name: str) -> dict[str, Any]:
    try:
        return dict(PROFILES[name])
    except KeyError:
        raise ValueError(
            f"Unknown profile {name!r}. Available: {', '.join(profile_names())}"
        ) from None
