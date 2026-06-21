"""Local-LLM detector: deterministic units + an opt-in live Ollama test."""

from __future__ import annotations

import importlib.util
import os
import socket

import pytest

from cloak.detectors.llm_detector import LlmDetector, _extract_items
from cloak.policy import CloakPolicy

_HAS_HTTPX = importlib.util.find_spec("httpx") is not None


# --- shape-tolerant extraction (no network) --------------------------------


def test_extract_items_wrapped():
    assert _extract_items({"entities": [{"text": "x"}]}) == [{"text": "x"}]


def test_extract_items_bare_list():
    assert _extract_items([{"text": "x"}]) == [{"text": "x"}]


def test_extract_items_renamed_key():
    assert _extract_items({"results": [{"text": "x"}]}) == [{"text": "x"}]


def test_extract_items_garbage():
    assert _extract_items("nope") == []
    assert _extract_items({"a": 1}) == []


# --- privacy guard: refuse non-loopback unless opted in --------------------


@pytest.mark.skipif(not _HAS_HTTPX, reason="httpx not installed")
def test_remote_endpoint_refused_by_default():
    det = LlmDetector(CloakPolicy(llm_endpoint="http://evil.example.com:11434"))
    assert det._is_loopback() is False
    assert det.available() is False


@pytest.mark.skipif(not _HAS_HTTPX, reason="httpx not installed")
def test_remote_endpoint_allowed_when_opted_in():
    det = LlmDetector(
        CloakPolicy(llm_endpoint="http://evil.example.com:11434", llm_allow_remote=True)
    )
    assert det.available() is True


# --- detect() parse + span location, with the network call mocked ----------


@pytest.mark.skipif(not _HAS_HTTPX, reason="httpx not installed")
def test_detect_locates_spans_from_mocked_response(monkeypatch):
    pol = CloakPolicy()
    det = LlmDetector(pol)
    monkeypatch.setattr(
        det,
        "_call",
        lambda text: '{"entities":[{"text":"Sarah Chen","type":"PERSON"},'
        '{"text":"sarah@x.com","type":"EMAIL"}]}',
    )
    text = "Email Sarah Chen at sarah@x.com please"
    ents = {(e.type, e.text) for e in det.detect(text, pol)}
    assert ("PERSON", "Sarah Chen") in ents
    assert ("EMAIL", "sarah@x.com") in ents
    # Spans must be exact so round-trip restore works.
    for e in det.detect(text, pol):
        assert text[e.start : e.end] == e.text


# --- live Ollama (opt-in; skipped unless reachable + CLOAK_TEST_OLLAMA) -----


def _ollama_up(host: str = "127.0.0.1", port: int = 11434) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


_RUN_OLLAMA = bool(os.environ.get("CLOAK_TEST_OLLAMA")) and _HAS_HTTPX and _ollama_up()


@pytest.mark.skipif(not _RUN_OLLAMA, reason="set CLOAK_TEST_OLLAMA=1 with Ollama running")
def test_live_ollama_detection_and_roundtrip():
    from cloak import Cloak

    pol = CloakPolicy(detectors=["llm"], llm_model=os.environ.get("CLOAK_OLLAMA_MODEL", "llama3.1"))
    cloak = Cloak(pol)
    text = "I'm Sarah Chen, email sarah.chen@mercy.org."
    res = cloak.mask_text(text)
    assert res.entity_count >= 1
    assert cloak.unmask_text(res.text, res.vault) == text
