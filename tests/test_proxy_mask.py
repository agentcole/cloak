"""Request-body masking used by the proxy (no network / no fastapi needed)."""

from __future__ import annotations

import json

from cloak import Cloak, CloakPolicy
from cloak.proxy.server import _mask_body


def _cloak():
    return Cloak(CloakPolicy(detectors=["regex"]))


def test_masks_chat_messages_and_is_restorable():
    body = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": "You help."},
            {"role": "user", "content": "email jane@acme.com"},
        ],
    }
    masked, vault = _mask_body(_cloak(), json.dumps(body).encode(), "application/json")
    out = json.loads(masked)
    assert out["messages"][1]["content"] == "email [EMAIL_1]"
    assert vault.restore(out["messages"][1]["content"]) == "email jane@acme.com"


def test_masks_anthropic_system_and_prompt_fields():
    body = {"system": "contact a@b.com", "prompt": "ip 10.0.0.1"}
    masked, _ = _mask_body(_cloak(), json.dumps(body).encode(), "application/json")
    out = json.loads(masked)
    assert out["system"] == "contact [EMAIL_1]"
    assert out["prompt"] == "ip [IP_ADDRESS_1]"


def test_non_json_body_passes_through():
    raw = b"\x00\x01binary"
    masked, vault = _mask_body(_cloak(), raw, "application/octet-stream")
    assert masked == raw
    assert len(vault) == 0
