# cloak examples

| Example | What it shows | Runs offline? |
|---------|---------------|:---:|
| [`quickstart.py`](quickstart.py) | mask → (send) → restore round trip | ✅ |
| [`strategies_and_profiles.py`](strategies_and_profiles.py) | the 4 strategies + compliance profiles side by side | ✅ |
| [`mask_document.py`](mask_document.py) | scan / mask / redact a whole document, page-aware | ✅ (synthetic; real files need `[docling]`) |
| [`wrap_openai.py`](wrap_openai.py) | wrap the OpenAI SDK; provider sees only tokens | ✅ (via local Ollama) |
| [`proxy_quickstart.md`](proxy_quickstart.md) | run the round-trip reverse proxy | — |
| [`mcp_usage.md`](mcp_usage.md) | use cloak as an MCP server | — |

## Run

```bash
pip install -e ".[faker]"          # quickstart/strategies need nothing; faker enables pseudonyms
python examples/quickstart.py
python examples/strategies_and_profiles.py
python examples/mask_document.py              # offline; add a PDF path + [docling] for real files

# wrap_openai.py talks to a local Ollama by default (no API key):
pip install openai
python examples/wrap_openai.py
```

`wrap_openai.py` defaults to `http://localhost:11434/v1` (Ollama). Point it at
real OpenAI with `OPENAI_API_KEY=sk-... CLOAK_DEMO_BASE_URL= CLOAK_DEMO_MODEL=gpt-4o-mini`.

## Documents (`[docling]`)

`mask_document.py` runs offline on a synthetic doc. Point it at a real PDF to
parse + redact it (needs `pip install "cloak-llm[docling]"`):

```bash
python examples/mask_document.py examples/data/kundenkartei.pdf
```

That writes two artifacts next to the input (checked in for reference):

- `data/kundenkartei.redacted.txt` — masked markdown (tables preserved, `[TYPE]` tokens)
- `data/kundenkartei.redacted.pdf` — a true in-place redacted PDF: PII glyphs are
  removed (not just covered) via PyMuPDF `apply_redactions`, and metadata is scrubbed

`data/kundenkartei.pdf` is synthetic German customer data (all values fabricated).
