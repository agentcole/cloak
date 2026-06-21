"""PhoneDetector — phonenumbers when available, regex fallback otherwise."""

from __future__ import annotations

import importlib.util

import pytest

from cloak.detectors.phone_detector import PhoneDetector
from cloak.policy import CloakPolicy

_HAS_PHONENUMBERS = importlib.util.find_spec("phonenumbers") is not None


@pytest.fixture
def detect():
    det = PhoneDetector(CloakPolicy())

    def _run(text: str) -> list[str]:
        return [e.text for e in det.detect(text, CloakPolicy())]

    return _run


@pytest.mark.parametrize(
    "text",
    ["+1 415 555 0123", "(415) 555-0123", "415-555-0123", "+44 20 7946 0958"],
)
def test_detects_common_formats(detect, text):
    assert detect(text), f"no phone found in {text!r}"


def test_short_number_is_not_a_phone(detect):
    assert detect("only 12-34") == []


def test_always_available():
    assert PhoneDetector(CloakPolicy()).available() is True


@pytest.mark.skipif(not _HAS_PHONENUMBERS, reason="phonenumbers not installed")
def test_phonenumbers_path_validates_and_scores_high():
    det = PhoneDetector(CloakPolicy())
    ents = det.detect("reach me at +1 415 555 0123 today", CloakPolicy())
    assert ents and ents[0].type == "PHONE"
    assert ents[0].score == 0.95  # validated path is high-confidence
    # An invalid-looking grouping should not validate via libphonenumber.
    assert det.detect("ref 1234 5678", CloakPolicy()) == []
