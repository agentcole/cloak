"""Engine-level masking, coreference, scope, and round-trip restore."""

from __future__ import annotations

import pytest

from cloak import Cloak, CloakPolicy


def _engine(**kw) -> Cloak:
    kw.setdefault("detectors", ["regex"])
    return Cloak(CloakPolicy(**kw))


def test_placeholder_roundtrip_is_identity():
    c = _engine(strategy="placeholder")
    text = "Email jane@acme.com or call +1 415 555 0123 about SSN 123-45-6789."
    res = c.mask_text(text)
    assert "jane@acme.com" not in res.text
    assert c.unmask_text(res.text, res.vault) == text


def test_hash_roundtrip_is_identity():
    c = _engine(strategy="hash", seed=7)
    text = "ip 10.0.0.1 and mail x@y.com"
    res = c.mask_text(text)
    assert c.unmask_text(res.text, res.vault) == text


def test_coreference_same_value_same_token():
    c = _engine()
    res = c.mask_text("mail a@b.com, again a@b.com, but c@d.com")
    # Two distinct emails -> two tokens; the repeat reuses the first.
    assert res.text.count("[EMAIL_1]") == 2
    assert "[EMAIL_2]" in res.text


def test_code_blocks_are_skipped():
    c = _engine(skip_code_blocks=True)
    res = c.mask_text("real a@b.com but `keep b@c.com` and ```\nx@y.com\n```")
    assert "[EMAIL_1]" in res.text
    assert "b@c.com" in res.text  # inline code preserved
    assert "x@y.com" in res.text  # fenced code preserved


def test_redact_is_irreversible():
    c = _engine(strategy="redact")
    res = c.mask_text("mail a@b.com and c@d.com")
    assert res.text == "mail [EMAIL] and [EMAIL]"
    # Nothing reversible was stored, so restore is a no-op.
    assert c.unmask_text(res.text, res.vault) == res.text


def test_enabled_types_filter():
    c = _engine(enabled_types={"EMAIL"})
    res = c.mask_text("mail a@b.com ip 10.0.0.1")
    assert "[EMAIL_1]" in res.text
    assert "10.0.0.1" in res.text  # IP not in enabled set


def test_allowlist_and_denylist():
    c = _engine(allowlist=["a@b.com"], denylist=["ProjectFalcon"])
    res = c.mask_text("a@b.com works on ProjectFalcon")
    assert "a@b.com" in res.text  # allow-listed -> never masked
    assert "ProjectFalcon" not in res.text  # deny-listed -> masked
    assert "[CUSTOM_1]" in res.text


def test_messages_share_vault_for_coreference():
    c = _engine()
    msgs = [
        {"role": "user", "content": "I am a@b.com"},
        {"role": "assistant", "content": [{"type": "text", "text": "you are a@b.com"}]},
        {"role": "tool", "content": "ignore"},
    ]
    res = c.mask_messages(msgs)
    assert res.messages[0]["content"] == "I am [EMAIL_1]"
    assert res.messages[1]["content"][0]["text"] == "you are [EMAIL_1]"


def test_non_scanned_roles_untouched():
    c = _engine(roles={"user"})
    msgs = [
        {"role": "user", "content": "a@b.com"},
        {"role": "assistant", "content": "c@d.com"},
    ]
    res = c.mask_messages(msgs)
    assert res.messages[0]["content"] == "[EMAIL_1]"
    assert res.messages[1]["content"] == "c@d.com"


@pytest.mark.parametrize("strategy", ["placeholder", "hash"])
def test_min_score_threshold_drops_low_confidence(strategy):
    # DATE scores 0.7; a 0.8 threshold should drop it (backend-agnostic).
    c = _engine(strategy=strategy, min_score=0.8)
    res = c.mask_text("met on 01/15/2024")
    assert "01/15/2024" in res.text
