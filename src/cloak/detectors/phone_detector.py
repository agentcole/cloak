"""Phone-number detection.

Prefers the ``phonenumbers`` library (Google's libphonenumber port) which finds
*and validates* numbers with locale awareness — far fewer false positives than a
regex. Falls back to a regex when the optional ``[phone]`` extra isn't installed.

The fallback emits PHONE at a lower confidence (0.6) than the validated
phonenumbers path (0.95), so a higher ``min_score`` naturally prefers validated
matches.
"""

from __future__ import annotations

import importlib.util

from ..patterns import PHONE_FALLBACK
from ..policy import CloakPolicy
from ..types import Entity
from .base import Detector


class PhoneDetector(Detector):
    name = "phone"

    def __init__(self, policy: CloakPolicy) -> None:
        self.region = policy.phone_region
        self._has_lib = importlib.util.find_spec("phonenumbers") is not None

    def available(self) -> bool:
        return True  # regex fallback always works

    def detect(self, text: str, policy: CloakPolicy) -> list[Entity]:
        if self._has_lib:
            return self._detect_lib(text)
        return self._detect_regex(text)

    def _detect_lib(self, text: str) -> list[Entity]:
        import phonenumbers

        out: list[Entity] = []
        # region is the assumed country for numbers written in national format;
        # international (+...) numbers are matched regardless.
        for match in phonenumbers.PhoneNumberMatcher(text, self.region or "US"):
            out.append(
                Entity(
                    type="PHONE",
                    start=match.start,
                    end=match.end,
                    text=match.raw_string,
                    score=0.95,
                    source=self.name,
                )
            )
        return out

    def _detect_regex(self, text: str) -> list[Entity]:
        out: list[Entity] = []
        pat = PHONE_FALLBACK
        for m in pat.regex.finditer(text):
            value = m.group(0)
            if pat.validator is not None and not pat.validator(value):
                continue
            out.append(
                Entity(
                    type="PHONE",
                    start=m.start(),
                    end=m.end(),
                    text=value,
                    score=pat.score,
                    source=self.name,
                )
            )
        return out
