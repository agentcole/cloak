"""Compliance profiles and config-file / env policy loading."""

from __future__ import annotations

import json
import sys

import pytest

from cloak import Cloak, CloakPolicy
from cloak.profiles import profile_names


def test_profile_names_present():
    assert {"default", "gdpr", "hipaa", "pci", "strict", "secrets"} <= set(profile_names())


def test_from_profile_pci_tokenizes_only_financial():
    p = CloakPolicy.from_profile("pci")
    assert p.strategy == "hash"
    assert p.enabled_types == {"CREDIT_CARD", "IBAN"}
    c = Cloak(p)
    res = c.mask_text("card 4111 1111 1111 1111 email a@b.com")
    assert "[CREDIT_CARD_" in res.text  # hashed token
    assert "a@b.com" in res.text  # email not in PCI scope -> untouched


def test_from_profile_strict_redacts_everything():
    p = CloakPolicy.from_profile("strict")
    assert p.strategy == "redact" and p.enabled_types is None
    res = Cloak(p).mask_text("mail a@b.com")
    assert res.text == "mail [EMAIL]"


def test_from_profile_override():
    p = CloakPolicy.from_profile("pci", strategy="redact")
    assert p.strategy == "redact"


def test_from_profile_unknown_raises():
    with pytest.raises(ValueError, match="Unknown profile"):
        CloakPolicy.from_profile("nope")


def test_from_mapping_lists_become_sets_and_unknown_keys_error():
    p = CloakPolicy.from_mapping({"enabled_types": ["EMAIL", "PHONE"], "strategy": "hash"})
    assert p.enabled_types == {"EMAIL", "PHONE"}
    with pytest.raises(ValueError, match="Unknown policy keys"):
        CloakPolicy.from_mapping({"bogus": 1})


def test_from_mapping_with_profile_base():
    p = CloakPolicy.from_mapping({"profile": "pci", "min_score": 0.9})
    assert p.strategy == "hash"  # from profile
    assert p.min_score == 0.9  # override


def test_from_file_json(tmp_path):
    cfg = tmp_path / "policy.json"
    cfg.write_text(
        json.dumps({"profile": "gdpr", "detectors": ["regex"], "strategy": "placeholder"})
    )
    p = CloakPolicy.from_file(str(cfg))
    assert p.detectors == ["regex"]
    assert p.strategy == "placeholder"


@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib needs 3.11+")
def test_from_file_toml(tmp_path):
    cfg = tmp_path / "policy.toml"
    cfg.write_text('strategy = "hash"\ndetectors = ["regex"]\nmin_score = 0.6\n')
    p = CloakPolicy.from_file(str(cfg))
    assert p.strategy == "hash" and p.min_score == 0.6


def test_from_file_unsupported_extension(tmp_path):
    cfg = tmp_path / "policy.ini"
    cfg.write_text("nope")
    with pytest.raises(ValueError, match="Unsupported config extension"):
        CloakPolicy.from_file(str(cfg))


def test_from_env(monkeypatch):
    monkeypatch.setenv("CLOAK_PROFILE", "pci")
    monkeypatch.setenv("CLOAK_MIN_SCORE", "0.7")
    monkeypatch.setenv("CLOAK_ENABLED_TYPES", "credit_card,iban")
    p = CloakPolicy.from_env()
    assert p.strategy == "hash"  # from pci profile
    assert p.min_score == 0.7
    assert p.enabled_types == {"CREDIT_CARD", "IBAN"}
