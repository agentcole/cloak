"""Tier-3 detector: tag PII with a *local/trusted* LLM.

Highest recall on messy / context-dependent text, but slower. Off by default.

Privacy guard: detecting PII by shipping text to a *remote* model would defeat
the purpose, so this detector refuses any non-loopback ``llm_endpoint`` unless
``policy.llm_allow_remote`` is explicitly set. The default endpoint is a local
Ollama server.

Supports two local API shapes, chosen by the endpoint:
* Ollama native (``/api/chat``) — default for ``http://localhost:11434``.
* OpenAI-compatible (``/v1/chat/completions``) — when the endpoint path ends in
  ``/v1`` (e.g. llama.cpp, LM Studio, vLLM).

Extra: ``cloak-llm[llm]``.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import re
from urllib.parse import urlparse

from ..policy import CloakPolicy
from ..types import Entity
from .base import Detector

logger = logging.getLogger("cloak")

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

_SYSTEM_PROMPT = (
    "You are a precise PII detection engine. Find every piece of personally "
    "identifiable or sensitive information in the user's text. Respond with ONLY "
    'a JSON object of the form {"entities": [{"text": <exact substring>, "type": '
    "<category>}]}. Categories: PERSON, ORGANIZATION, LOCATION, ADDRESS, DATE, "
    "EMAIL, PHONE, SSN, CREDIT_CARD, ID, API_KEY, OTHER. Copy 'text' verbatim "
    "from the input. If there is no PII, return an empty list."
)


class LlmDetector(Detector):
    name = "llm"

    def __init__(self, policy: CloakPolicy) -> None:
        self.endpoint = policy.llm_endpoint.rstrip("/")
        self.model = policy.llm_model
        self.allow_remote = policy.llm_allow_remote

    def _is_loopback(self) -> bool:
        host = (urlparse(self.endpoint).hostname or "").lower()
        return host in _LOOPBACK_HOSTS

    def available(self) -> bool:
        if importlib.util.find_spec("httpx") is None:
            return False
        if not self._is_loopback() and not self.allow_remote:
            logger.warning(
                "LLM detector endpoint %s is not loopback; refusing without "
                "policy.llm_allow_remote=True",
                self.endpoint,
            )
            return False
        return True

    def _is_openai_style(self) -> bool:
        return urlparse(self.endpoint).path.rstrip("/").endswith("/v1")

    def _call(self, text: str) -> str:
        import httpx

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]
        if self._is_openai_style():
            url = f"{self.endpoint}/chat/completions"
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0,
                "response_format": {"type": "json_object"},
            }
            data = httpx.post(url, json=payload, timeout=60.0).json()
            return data["choices"][0]["message"]["content"]
        # Ollama native
        url = f"{self.endpoint}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        data = httpx.post(url, json=payload, timeout=60.0).json()
        return data["message"]["content"]

    def detect(self, text: str, policy: CloakPolicy) -> list[Entity]:
        if not self.available():
            return []
        try:
            raw = self._call(text)
            parsed = json.loads(raw)
        except Exception as exc:
            logger.warning("LLM detector call/parse failed: %s", exc)
            return []

        items = parsed.get("entities", []) if isinstance(parsed, dict) else []
        score = max(policy.min_score, 0.9)
        out: list[Entity] = []
        seen: set[tuple[int, int]] = set()
        for item in items:
            value = (item or {}).get("text")
            etype = (item or {}).get("type", "OTHER")
            if not isinstance(value, str) or not value.strip():
                continue
            # The model doesn't return offsets reliably; locate verbatim spans.
            for m in re.finditer(re.escape(value), text):
                span = (m.start(), m.end())
                if span in seen:
                    continue
                seen.add(span)
                out.append(
                    Entity(
                        type=str(etype).upper().replace(" ", "_"),
                        start=m.start(),
                        end=m.end(),
                        text=value,
                        score=score,
                        source=self.name,
                    )
                )
        return out
