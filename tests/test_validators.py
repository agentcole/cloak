"""Checksum/format validators and the A5 breadth recognizers."""

from __future__ import annotations

import pytest

from cloak import validators as V
from cloak.detectors.regex_detector import RegexDetector
from cloak.policy import CloakPolicy

# --- validators: a known-valid passes, a tampered one fails ----------------


@pytest.mark.parametrize(
    "fn,valid,invalid",
    [
        (V.spain_dni_valid, "12345678Z", "12345678A"),
        (V.cpf_valid, "111.444.777-35", "111.444.777-36"),
        (V.german_taxid_valid, "86095742719", "86095742718"),
        (V.france_insee_valid, "184127645108154", "184127645108155"),
        (V.npi_valid, "1234567893", "1234567894"),
        (V.aadhaar_valid, "234123456783", "234123456784"),
        (V.vin_valid, "1HGBH41JXMN109186", "1HGBH41JXMN109187"),
        (V.canada_sin_valid, "130692544", "130692545"),
    ],
)
def test_validator_accepts_valid_rejects_tampered(fn, valid, invalid):
    assert fn(valid) is True
    assert fn(invalid) is False


def test_validators_reject_wrong_length():
    assert V.german_taxid_valid("123") is False
    assert V.vin_valid("TOO-SHORT") is False
    assert V.aadhaar_valid("12") is False


def test_aadhaar_rejects_leading_0_or_1():
    # Aadhaar never starts with 0 or 1, regardless of checksum.
    assert V.aadhaar_valid("034123456783") is False


# --- recognizers fire on representative inputs -----------------------------


@pytest.fixture
def detect():
    det = RegexDetector()
    pol = CloakPolicy()

    def _run(text: str) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for e in det.detect(text, pol):
            out.setdefault(e.type, []).append(e.text)
        return out

    return _run


@pytest.mark.parametrize(
    "text,etype,value",
    [
        ("key sk-proj-abcdefghijklmnopqrst here", "API_KEY", "sk-proj-abcdefghijklmnopqrst"),
        ("stripe sk_live_abcdefghij1234567890 x", "API_KEY", "sk_live_abcdefghij1234567890"),
        ("pan ABCDE1234F ok", "NATIONAL_ID", "ABCDE1234F"),
        ("dni 12345678Z ok", "NATIONAL_ID", "12345678Z"),
        ("cpf 111.444.777-35 ok", "NATIONAL_ID", "111.444.777-35"),
        ("ein 12-3456789 ok", "EIN", "12-3456789"),
        ("vin 1HGBH41JXMN109186 ok", "VIN", "1HGBH41JXMN109186"),
        ("zip 90210-1234 ok", "US_ZIP", "90210-1234"),
        ("at 37.7749, -122.4194 ok", "GEO_COORDINATE", "37.7749, -122.4194"),
        ("ship to 1600 Pennsylvania Avenue today", "ADDRESS", "1600 Pennsylvania Avenue"),
        ("sin 130 692 544 ok", "NATIONAL_ID", "130 692 544"),
    ],
)
def test_recognizes(detect, text, etype, value):
    found = detect(text)
    assert etype in found, f"{etype} not in {found}"
    assert value in found[etype]


def test_runtime_built_secrets_recognized(detect):
    # Built at runtime so no secret-shaped literal is committed to the repo
    # (push-protection scanners flag even fake SendGrid/Twilio keys).
    sendgrid = "SG." + "a" * 22 + "." + "b" * 43
    twilio = "AC" + "0" * 32
    assert "API_KEY" in detect(f"key {sendgrid} here")
    assert "API_KEY" in detect(f"sid {twilio} here")


def test_private_key_block_detected(detect):
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIBdummy\n-----END RSA PRIVATE KEY-----"
    found = detect(f"leaked:\n{pem}\ndone")
    assert "PRIVATE_KEY" in found


def test_handle_off_by_default_on_at_threshold(detect):
    # HANDLE scores 0.4, below the default 0.5 min_score, so scan drops it.
    from cloak import Cloak

    c = Cloak(CloakPolicy(detectors=["regex"]))
    assert "[HANDLE" not in c.mask_text("follow @janedoe today").text
    # Lowering the threshold enables it.
    c2 = Cloak(CloakPolicy(detectors=["regex"], min_score=0.4))
    assert "[HANDLE_1]" in c2.mask_text("follow @janedoe today").text


def test_handle_does_not_match_email_local_part(detect):
    assert "HANDLE" not in detect("mail jane@acme.com")
