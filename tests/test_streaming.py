"""StreamRestorer must restore tokens even when split across chunk boundaries."""

from __future__ import annotations

import pytest

from cloak import Cloak, CloakPolicy
from cloak.proxy.streaming import StreamRestorer


def _stream(text: str, vault, size: int) -> str:
    sr = StreamRestorer(vault)
    out = "".join(sr.feed(text[i : i + size]) for i in range(0, len(text), size))
    return out + sr.flush()


@pytest.mark.parametrize("chunk", [1, 2, 3, 5, 7, 100])
def test_restore_survives_any_chunking(chunk):
    c = Cloak(CloakPolicy(detectors=["regex"]))
    original = "mail jane@acme.com and ip 10.0.0.1 done"
    res = c.mask_text(original)
    assert "[EMAIL_1]" in res.text
    assert _stream(res.text, res.vault, chunk) == original


def test_passthrough_when_nothing_to_restore():
    c = Cloak(CloakPolicy(detectors=["regex"]))
    res = c.mask_text("nothing sensitive here")
    assert _stream(res.text, res.vault, 2) == "nothing sensitive here"
