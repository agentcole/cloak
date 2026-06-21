# cloak — roadmap & gap analysis

`cloak` v0.1 ships a working core (tiered detection → resolve → pluggable
replacement → reversible vault) across four surfaces (library, CLI, MCP server,
round-trip proxy) with 51 tests passing.

**Direction:** a *solid standalone tool* — excellent library + CLI + MCP + proxy,
well-tested and documented. Explicitly **out of scope**: a TypeScript SDK,
multi-agent `wrap` commands, and a full docs-site/plugin-marketplace sprawl.

Legend: ✅ done · 🚧 in progress · ⬜ planned · ❄️ deferred (out of current scope)

## A. Defects / risks in the shipped code (highest priority)

| ID | Gap | Status |
|----|-----|:--:|
| A1 | **GLiNER default backend never run** — `ner_backend="gliner"` is unvalidated; only the spaCy path was exercised. The default `[ner]` install may not work out of the box. | 🚧 |
| A2 | **`[phone]` extra is dead** — `phonenumbers` is declared but never used; phone detection is pure regex (noisy, no validation/locale). | 🚧 |
| A3 | **`mypy` never run; no `py.typed`** — types unchecked and not shipped to consumers. | 🚧 |
| A4 | **LLM detector never run against a real model** — Tier-3 request/parse path is import-guarded only. | ⬜ |
| A5 | **Thin detection coverage** — missing passports, driver's licenses, non-US national IDs, PHI/medical, postal addresses, dates-in-prose, handles, plates; no locale awareness. | ⬜ |
| A6 | **Proxy hardening** — Anthropic response shapes, timeouts/retries, sync masking blocks the async loop, Faker not thread-safe under concurrency, vault has no TTL/eviction/persistence. | ⬜ |
| A7 | **Pseudonym round-trip is best-effort**; double-masking/idempotency undefined. | ⬜ |
| A8 | **Vault security** — holds raw PII; encryption opt-in, no zeroization, plaintext-by-default on disk. | ⬜ |

## B. Capabilities (in scope for a solid standalone tool)

| ID | Item | Status |
|----|------|:--:|
| B1 | **PII eval harness** — labeled gold corpus + span-level precision/recall/F1 per type; regression thresholds. The credibility metric. | 🚧 |
| B2 | **Compliance profiles** — `gdpr` / `hipaa` / `pci` / `strict` presets selecting detectors, types, strategy, thresholds. | 🚧 |
| B3 | **Config-file loading** — policy from JSON/TOML/YAML + env. | 🚧 |
| B4 | **Examples** — OpenAI/Anthropic SDK wrap, LangChain callback, proxy quickstart, a before/after notebook. | ⬜ |
| B5 | **Dockerized proxy** — Dockerfile + compose (cloak ↔ Ollama ↔ app). | ⬜ |
| B6 | **CI** — GitHub Actions: pytest + ruff + mypy across 3.10–3.13; PyPI publish. | ⬜ |
| B7 | **Docs** — architecture, policy reference, compliance profiles, threat model; `llms.txt`. | ⬜ |
| B8 | **Project hygiene** — CHANGELOG, CONTRIBUTING, SECURITY.md, full Apache LICENSE text. | ⬜ |

## C. Explicitly deferred (parity with headroom, not pursued now)

| ID | Item | Status |
|----|------|:--:|
| C1 | TypeScript/npm SDK (MCP + proxy are already language-agnostic). | ❄️ |
| C2 | `cloak wrap <agent>` agent wrappers + `.claude-plugin` marketplace. | ❄️ |
| C3 | Full docs website (mkdocs/next). | ❄️ |

## Current focus
A1–A3 (fix shipped defects) → B1 (eval harness) → B2+B3 (profiles + config).
