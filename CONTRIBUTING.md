# Contributing to cloak

Thanks for your interest! cloak is a local-first, reversible PII-redaction layer
for LLM prompts.

## Development setup

cloak uses [uv](https://github.com/astral-sh/uv).

```bash
uv venv
uv pip install -e ".[dev,proxy,phone,config]"   # core + the lightweight extras
```

Heavier, optional extras (only needed for their detectors):

```bash
uv pip install -e ".[ner]"     # GLiNER NER (downloads a model on first use)
uv pip install -e ".[faker]"   # pseudonym strategy
uv pip install -e ".[mcp]"     # MCP server
uv pip install -e ".[llm]"     # local-LLM detector
```

> Note: with a `uv` venv, prefer `uv pip install --python .venv/bin/python ...`
> if another environment (e.g. conda) is active — plain `uv pip install` targets
> the active environment.

## Checks (all must pass)

```bash
uv run pytest          # tests
uv run ruff check .    # lint
uv run ruff format .   # format
uv run mypy src/cloak  # types
```

Optional, model/endpoint-gated tests are opt-in:

```bash
CLOAK_TEST_GLINER=1 uv run pytest tests/test_ner_detector.py   # needs gliner + model
CLOAK_TEST_OLLAMA=1 uv run pytest tests/test_llm_detector.py   # needs Ollama running
```

## Guidelines

- Keep the **core dependency-free** — new third-party deps go behind an extra
  and import lazily, degrading gracefully when absent.
- Add or update **tests** for any behaviour change; for new detector coverage,
  extend `eval/gold.txt` and keep `cloak eval` green.
- Conventional Commit messages (`feat:`, `fix:`, `docs:`, `test:`, …).
- Never commit a vault or any file containing real PII.

## Reporting security issues

See [SECURITY.md](SECURITY.md) — report privately, do not open a public issue.
