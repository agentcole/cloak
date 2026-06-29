"""Tier-1 detector: deterministic regex + validators for structured PII.

Dependency-free and fast. Catches emails, phone numbers, SSNs, credit cards,
IBANs, IPs/MACs, URLs, crypto addresses, secrets/API keys and numeric dates.
"""

from __future__ import annotations

from ..patterns import (
    IBAN_FRAGMENT_TYPES,
    PATTERNS,
    PiiPattern,
    iban_structural_spans,
)
from ..policy import CloakPolicy
from ..types import Entity
from .base import Detector


class RegexDetector(Detector):
    name = "regex"

    def __init__(self, patterns: list[PiiPattern] | None = None) -> None:
        self.patterns = patterns if patterns is not None else PATTERNS

    def available(self) -> bool:
        return True

    def detect(self, text: str, policy: CloakPolicy) -> list[Entity]:
        entities: list[Entity] = []
        for pat in self.patterns:
            for m in pat.regex.finditer(text):
                # Prefer a named ``value`` group when the pattern defines one.
                if "value" in pat.regex.groupindex:
                    value = m.group("value")
                    start, end = m.span("value")
                else:
                    value = m.group(0)
                    start, end = m.span(0)
                # Trim surrounding whitespace while keeping span aligned to the
                # exact substring we store — this keeps round-trip restore exact.
                lead = len(value) - len(value.lstrip())
                trail = len(value) - len(value.rstrip())
                start += lead
                end -= trail
                value = text[start:end]
                if not value:
                    continue
                if pat.validator is not None and not pat.validator(value):
                    continue
                entities.append(
                    Entity(
                        type=pat.type,
                        start=start,
                        end=end,
                        text=value,
                        score=pat.score,
                        source=self.name,
                    )
                )
        return self._suppress_iban_fragments(entities, text)

    @staticmethod
    def _suppress_iban_fragments(entities: list[Entity], text: str) -> list[Entity]:
        """Drop fragmenting numeric matches that sit inside an IBAN-shaped run.

        A checksum-invalid IBAN emits no IBAN token, but an interior Luhn or
        tax-id run would otherwise survive and half-mask the field (leaking the
        rest of the account number). Suppress those fragments so the IBAN is
        either fully tokenized or left wholly intact — never partially masked.
        """
        zones = iban_structural_spans(text)
        if not zones:
            return entities
        return [
            e
            for e in entities
            if not (
                e.type in IBAN_FRAGMENT_TYPES
                and any(zs <= e.start and e.end <= ze for zs, ze in zones)
            )
        ]
