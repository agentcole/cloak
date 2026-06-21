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
| A1 | ~~GLiNER default backend never run~~ — **validated**: default `gliner` + `gliner_multi_pii-v1` detects PERSON/ORG/LOCATION end-to-end; opt-in test (`CLOAK_TEST_GLINER=1`). | ✅ |
| A2 | ~~`[phone]` extra is dead~~ — **fixed**: dedicated `PhoneDetector` uses libphonenumber (validated, locale-aware, 0.95) with a regex fallback (0.6). | ✅ |
| A3 | ~~`mypy` never run; no `py.typed`~~ — **fixed**: `py.typed` shipped; `mypy` clean on 25 files. | ✅ |
| A4 | ~~LLM detector never run against a real model~~ — **validated** against live Ollama (llama3.1); hardened with configurable timeout, `raise_for_status`, shape-tolerant JSON parsing, and a tested non-loopback refusal. Opt-in live test (`CLOAK_TEST_OLLAMA=1`). | ✅ |
| A5 | **Thin detection coverage** — missing passports, driver's licenses, non-US national IDs, PHI/medical, postal addresses, dates-in-prose, handles, plates; no locale awareness. | ⬜ |
| A6 | ~~Proxy hardening~~ — **done**: Anthropic `system`+content-block masking (tested), bounded connect/write timeouts (read unbounded for streams), clean 502 on unreachable upstream, masking offloaded to a threadpool, thread-safe pseudonym strategy, guaranteed upstream close, bounded MCP vault store. | ✅ |
| A7 | **Pseudonym round-trip is best-effort**; double-masking/idempotency undefined. | ⬜ |
| A8 | **Vault security** — holds raw PII; encryption opt-in, no zeroization, plaintext-by-default on disk. | ⬜ |

## B. Capabilities (in scope for a solid standalone tool)

| ID | Item | Status |
|----|------|:--:|
| B1 | ~~PII eval harness~~ — **done**: `cloak eval` + `cloak.evaluate` give span-level P/R/F1 per type over a markup gold corpus; regex tier regression-tested at 1.00/1.00 on structured types. | ✅ |
| B2 | ~~Compliance profiles~~ — **done**: `gdpr` / `hipaa` / `pci` / `strict` / `secrets` via `CloakPolicy.from_profile` / `--profile`. | ✅ |
| B3 | ~~Config-file loading~~ — **done**: `CloakPolicy.from_file` (JSON/TOML/YAML), `.from_mapping`, `.from_env`; `--config`. | ✅ |
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
