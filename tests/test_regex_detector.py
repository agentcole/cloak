"""Golden tests for the structured-PII regex detector."""

from __future__ import annotations

import pytest

from cloak.detectors.regex_detector import RegexDetector
from cloak.policy import CloakPolicy


@pytest.fixture
def detect():
    det = RegexDetector()
    policy = CloakPolicy()

    def _run(text: str) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for e in det.detect(text, policy):
            out.setdefault(e.type, []).append(e.text)
        return out

    return _run


@pytest.mark.parametrize(
    "text,etype,value",
    [
        ("write to jane.doe@acme.co.uk please", "EMAIL", "jane.doe@acme.co.uk"),
        ("ssn is 123-45-6789 ok", "SSN", "123-45-6789"),
        ("ip 192.168.1.254 here", "IP_ADDRESS", "192.168.1.254"),
        ("mac 00:1A:2B:3C:4D:5E", "MAC_ADDRESS", "00:1A:2B:3C:4D:5E"),
        ("visit https://example.com/x?y=1 now", "URL", "https://example.com/x?y=1"),
        ("key sk-ant-abcdefghij0123456789XYZ", "API_KEY", "sk-ant-abcdefghij0123456789XYZ"),
        ("aws AKIAIOSFODNN7EXAMPLE rotated", "API_KEY", "AKIAIOSFODNN7EXAMPLE"),
        (
            "eth 0x52908400098527886E0F7030069857D2E4169EE7",
            "CRYPTO_ADDRESS",
            "0x52908400098527886E0F7030069857D2E4169EE7",
        ),
    ],
)
def test_detects_structured(detect, text, etype, value):
    found = detect(text)
    assert etype in found, f"{etype} not found in {found}"
    assert value in found[etype]


def test_credit_card_requires_luhn(detect):
    assert "CREDIT_CARD" in detect("card 4111 1111 1111 1111")  # valid Luhn
    assert "CREDIT_CARD" not in detect("num 4111 1111 1111 1112")  # bad checksum


def test_iban_mod97(detect):
    assert "IBAN" in detect("acct GB82WEST12345698765432")  # valid
    assert "IBAN" not in detect("acct GB00WEST12345698765432")  # invalid checksum


def test_iban_space_grouped(detect):
    # Printed IBANs are grouped in fours; the whole span must be captured.
    found = detect("IBAN (Test): DE89 3704 0044 0532 0130 00 thanks")
    assert "DE89 3704 0044 0532 0130 00" in found.get("IBAN", [])


def test_regex_detector_does_not_emit_phone(detect):
    # Phone detection moved to PhoneDetector; RegexDetector should not emit it.
    assert "PHONE" not in detect("call 415-555-0123")


def test_invalid_iban_leaves_no_fragment(detect):
    # A checksum-invalid IBAN must not be HALF-masked: the interior numeric runs
    # (a 16-digit Luhn span, an 11-digit tax-id span) that would otherwise match
    # CREDIT_CARD / NATIONAL_ID are suppressed inside the IBAN-shaped run.
    found = detect("IBAN (Test): DE49 5505 0120 0200 3456 78 end")
    assert "IBAN" not in found  # bad checksum -> not tokenized
    assert "CREDIT_CARD" not in found
    assert "NATIONAL_ID" not in found


def test_iban_suppression_does_not_swallow_standalone_numbers(detect):
    # The exclusion zone is scoped to IBAN-shaped runs only; a real credit card
    # or tax id elsewhere in the text must still be detected.
    found = detect("Card 4111 1111 1111 1111 and IBAN DE49 5505 0120 0200 3456 78")
    assert "4111 1111 1111 1111" in found.get("CREDIT_CARD", [])


@pytest.mark.parametrize(
    "addr",
    [
        "Lindenstraße 14, 80335 München",
        "Am Marktplatz 22, 50667 Köln",
        "Rosenheimer Str. 103, 81669 München",
        "Schillerstraße 31, 60313 Frankfurt am Main",
        "Kirchgasse 18, 55116 Mainz",
    ],
)
def test_german_street_address(detect, addr):
    assert addr in detect(addr).get("ADDRESS", [])
