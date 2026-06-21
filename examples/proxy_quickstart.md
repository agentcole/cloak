# Round-trip proxy quickstart

Run cloak as a reverse proxy in front of any OpenAI-compatible provider. It
masks PII in the request and restores it in the response (including streamed
SSE), so the provider only ever sees tokens.

## 1. Start the proxy

```bash
pip install "cloak-llm[proxy]"

# In front of OpenAI:
cloak proxy --port 8788 --upstream https://api.openai.com

# …or in front of a local Ollama (fully offline):
cloak proxy --port 8788 --upstream http://localhost:11434 --detectors regex
```

Useful flags: `--strategy pseudonym|redact|hash`, `--detectors regex,ner`,
`--no-restore` (mask only, don't restore responses).

## 2. Point your client at the proxy

Just change the base URL — no code changes otherwise.

```bash
# OpenAI Python SDK
export OPENAI_BASE_URL=http://127.0.0.1:8788/v1
export OPENAI_API_KEY=sk-...        # forwarded upstream as-is
```

```bash
# curl
curl http://127.0.0.1:8788/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Email jane@acme.com a summary."}]
      }'
```

The upstream provider receives `Email [EMAIL_1] a summary.`; your client gets the
real address back in the response.

## Notes

- Works for Anthropic-style payloads too (`system` + content blocks) — point a
  client at the proxy with `--upstream https://api.anthropic.com`.
- The vault lives only for the duration of each request; nothing is persisted.
- An unreachable upstream returns a clean `502` with a JSON error body.
