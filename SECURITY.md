# Security Policy

## Reporting a vulnerability

Please report security issues privately to **security@symbolicinterfaces.com**.
Do not open a public issue for vulnerabilities. We aim to acknowledge reports
within a few business days.

## Handling sensitive data

cloak exists to keep PII away from third-party LLMs, but a few artifacts contain
the original sensitive data and must be treated as secrets:

- **Vaults** (`*.cloakvault`, the in-memory `Vault`, MCP `vault_id` stores) hold
  the original ↔ token mapping — i.e. the raw PII. Never commit them, log them,
  or send them to a remote service. Use `Vault.save(path, password=...)` to
  encrypt at rest.
- **The local-LLM detector** (`detectors=["llm"]`) refuses non-loopback
  endpoints unless `policy.llm_allow_remote=True`. Do not enable remote
  endpoints with real PII unless you fully trust and control the endpoint.
- **Redaction is best-effort, not a guarantee.** Detector recall is not 100%
  (see `cloak eval`); validate coverage for your data and threat model before
  relying on it for compliance.

## Supported versions

This is pre-1.0 software; only the latest released version receives fixes.
