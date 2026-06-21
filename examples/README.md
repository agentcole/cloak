# cloak examples

| Example | What it shows | Runs offline? |
|---------|---------------|:---:|
| [`quickstart.py`](quickstart.py) | mask → (send) → restore round trip | ✅ |
| [`strategies_and_profiles.py`](strategies_and_profiles.py) | the 4 strategies + compliance profiles side by side | ✅ |
| [`wrap_openai.py`](wrap_openai.py) | wrap the OpenAI SDK; provider sees only tokens | ✅ (via local Ollama) |
| [`proxy_quickstart.md`](proxy_quickstart.md) | run the round-trip reverse proxy | — |
| [`mcp_usage.md`](mcp_usage.md) | use cloak as an MCP server | — |

## Run

```bash
pip install -e ".[faker]"          # quickstart/strategies need nothing; faker enables pseudonyms
python examples/quickstart.py
python examples/strategies_and_profiles.py

# wrap_openai.py talks to a local Ollama by default (no API key):
pip install openai
python examples/wrap_openai.py
```

`wrap_openai.py` defaults to `http://localhost:11434/v1` (Ollama). Point it at
real OpenAI with `OPENAI_API_KEY=sk-... CLOAK_DEMO_BASE_URL= CLOAK_DEMO_MODEL=gpt-4o-mini`.
