"""Deterministic regex patterns for structured PII and secrets.

Each :class:`PiiPattern` pairs a compiled regex with an optional validator so we
can keep false positives low (e.g. a 16-digit number is only a credit card if it
passes the Luhn checksum). Patterns are the dependency-free Tier-1 detector.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass


def luhn_valid(number: str) -> bool:
    """Return True if ``number`` passes the Luhn checksum (credit cards)."""
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def iban_valid(candidate: str) -> bool:
    """Validate an IBAN via the ISO 7064 mod-97 check."""
    s = candidate.replace(" ", "").upper()
    if len(s) < 15 or len(s) > 34:
        return False
    rearranged = s[4:] + s[:4]
    digits = "".join(str(int(c, 36)) if c.isalpha() else c for c in rearranged)
    try:
        return int(digits) % 97 == 1
    except ValueError:
        return False


@dataclass
class PiiPattern:
    """A regex-based PII recognizer.

    Attributes:
        type: Entity category emitted on a match.
        regex: Compiled pattern. Group ``value`` is used as the span if present,
            else the whole match.
        score: Confidence assigned to matches.
        validator: Optional predicate over the matched value; matches that fail
            it are discarded.
    """

    type: str
    regex: re.Pattern[str]
    score: float = 0.95
    validator: Callable[[str], bool] | None = None


_C = re.compile

# Order matters: more specific / higher-value patterns first so the resolver
# prefers them when spans overlap.
PATTERNS: list[PiiPattern] = [
    # --- Secrets & API keys (high value, very specific) ---
    PiiPattern("API_KEY", _C(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"), 0.99),
    PiiPattern("API_KEY", _C(r"\bsk-[A-Za-z0-9]{20,}\b"), 0.97),
    PiiPattern("API_KEY", _C(r"\bAKIA[0-9A-Z]{16}\b"), 0.99),
    PiiPattern("API_KEY", _C(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), 0.99),
    PiiPattern("API_KEY", _C(r"\bAIza[0-9A-Za-z_\-]{35}\b"), 0.98),
    PiiPattern("API_KEY", _C(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), 0.98),
    PiiPattern(
        "JWT",
        _C(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"),
        0.95,
    ),
    # --- Financial ---
    PiiPattern(
        "CREDIT_CARD",
        _C(r"\b(?:\d[ -]?){13,19}\b"),
        0.9,
        validator=luhn_valid,
    ),
    PiiPattern(
        "IBAN",
        _C(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
        0.95,
        validator=iban_valid,
    ),
    # --- Government IDs ---
    PiiPattern("SSN", _C(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"), 0.9),
    # --- Contact ---
    PiiPattern(
        "EMAIL",
        _C(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        0.98,
    ),
    # --- Network ---
    PiiPattern(
        "IP_ADDRESS",
        _C(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"),
        0.9,
    ),
    PiiPattern(
        "IP_ADDRESS",
        _C(r"\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b"),
        0.9,
    ),
    PiiPattern("MAC_ADDRESS", _C(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b"), 0.95),
    PiiPattern(
        "URL",
        _C(r"\bhttps?://[^\s<>\"')]+", re.IGNORECASE),
        0.9,
    ),
    # --- Crypto wallets ---
    PiiPattern("CRYPTO_ADDRESS", _C(r"\b0x[a-fA-F0-9]{40}\b"), 0.9),  # ETH
    PiiPattern("CRYPTO_ADDRESS", _C(r"\b(?:bc1|[13])[a-km-zA-HJ-NP-Z1-9]{25,39}\b"), 0.7),  # BTC
    # --- Dates / birthdays (numeric formats; NER catches written dates) ---
    PiiPattern(
        "DATE",
        _C(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})\b"),
        0.7,  # above PHONE so date-formatted strings win overlap resolution
    ),
]

# Regex fallback for phone numbers, used by PhoneDetector when the optional
# ``phonenumbers`` library isn't installed. Noisier than phonenumbers (no real
# validation or locale), hence the lower score.
PHONE_FALLBACK = PiiPattern(
    "PHONE",
    _C(r"(?<!\w)(?:\+\d{1,3}[\s.\-]?)?\(?\d{2,4}\)?(?:[\s.\-]\d{2,4}){1,4}(?!\w)"),
    0.6,
    validator=lambda v: 7 <= sum(c.isdigit() for c in v) <= 15,
)

# Canonical category set, for documentation / CLI help.
STRUCTURED_TYPES: tuple[str, ...] = tuple(dict.fromkeys(p.type for p in PATTERNS)) + ("PHONE",)
