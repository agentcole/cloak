# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Core engine: tiered detection (regex → local NER → local LLM) → overlap
  resolution (code-block skip, allow/deny) → pluggable replacement strategies
  (placeholder / pseudonym / redact / hash) → reversible `Vault` with full
  round-trip restore.
- Surfaces: Python library, CLI (`scan`/`mask`/`unmask`/`eval`/`serve-mcp`/
  `proxy`), MCP server, and a round-trip reverse proxy with streamed-SSE
  restoration.
- Phone detection via `phonenumbers` (validated, locale-aware) with a regex
  fallback.
- Local-LLM detector validated against Ollama; configurable timeout, robust
  JSON parsing, non-loopback refusal.
- PII evaluation harness: `cloak eval` + `cloak.evaluate` (span-level
  precision/recall/F1) over an inline-markup gold corpus.
- Compliance profiles (`gdpr` / `hipaa` / `pci` / `strict` / `secrets`) and
  config loading from JSON/TOML/YAML/env (`CloakPolicy.from_profile` /
  `from_file` / `from_env`; `--profile` / `--config`).
- Proxy hardening: Anthropic `system`+block masking, bounded timeouts, clean
  502s, threadpool offload, thread-safe pseudonyms, bounded MCP vault store.
- `py.typed` marker; mypy-clean.

[Unreleased]: https://symbolicinterfaces.com
