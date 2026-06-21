"""Wrap the OpenAI SDK so PII is masked outbound and restored in the reply.

The provider only ever sees tokens like [EMAIL_1]; your code gets the real
values back. Works with any OpenAI-compatible endpoint.

By default it targets a local Ollama (http://localhost:11434/v1) so it runs with
no API key. To use real OpenAI instead, set OPENAI_API_KEY (and unset
CLOAK_DEMO_BASE_URL).

    # against local Ollama (default):
    python examples/wrap_openai.py
    # against OpenAI:
    OPENAI_API_KEY=sk-... CLOAK_DEMO_BASE_URL= CLOAK_DEMO_MODEL=gpt-4o-mini \
        python examples/wrap_openai.py

Requires: pip install "cloak-llm" openai
"""

from __future__ import annotations

import os

from cloak import Cloak, CloakPolicy


class CloakedChat:
    """Thin wrapper that masks request messages and restores the response."""

    def __init__(self, client, cloak: Cloak) -> None:
        self._client = client
        self._cloak = cloak

    def create(self, *, model: str, messages: list[dict], **kwargs):
        masked = self._cloak.mask_messages(messages)
        resp = self._client.chat.completions.create(model=model, messages=masked.messages, **kwargs)
        content = resp.choices[0].message.content or ""
        restored = self._cloak.unmask_text(content, masked.vault)
        return restored, masked  # masked.messages shows what the provider saw


def main() -> None:
    from openai import OpenAI

    base_url = os.environ.get("CLOAK_DEMO_BASE_URL", "http://localhost:11434/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "ollama")
    model = os.environ.get("CLOAK_DEMO_MODEL", "qwen2:0.5b")

    client = OpenAI(base_url=base_url or None, api_key=api_key)
    chat = CloakedChat(client, Cloak(CloakPolicy(detectors=["regex"], strategy="placeholder")))

    messages = [
        {"role": "system", "content": "You are a terse assistant."},
        {"role": "user", "content": "Draft a one-line reply confirming I'll email jane@acme.com."},
    ]

    answer, masked = chat.create(model=model, messages=messages)
    print("PROVIDER SAW (user msg):", masked.messages[-1]["content"])
    print("ANSWER (restored)      :", answer)


if __name__ == "__main__":
    main()
