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
| A5 | ~~Thin detection coverage~~ — **expanded**: PEM private keys; Stripe/SendGrid/Twilio/Google/GitHub-PAT/OpenAI-proj/npm/PyPI secrets; national IDs (UK NINO, Spain DNI, Italy codice, India PAN/Aadhaar, Brazil CPF, Germany Steuer-ID, France INSEE) + US EIN/NPI; VIN, geo-coordinates, ZIP+4, handles — all checksum/format-validated, regression-tested in `eval/gold.txt` at 1.00 precision. (Remaining: passports/driver's-licenses, postal addresses, more locales.) | ✅ |
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
| B6 | ~~CI~~ — **done**: `ci.yml` runs ruff check/format + mypy + pytest on Python 3.10–3.13 and builds the wheel; `publish.yml` does PyPI Trusted Publishing on version tags. | ✅ |
| B7 | **Docs** — architecture, policy reference, compliance profiles, threat model; `llms.txt`. | ⬜ |
| B8 | **Project hygiene** — **mostly done**: CHANGELOG, CONTRIBUTING, SECURITY.md added; identity = symbolicinterfaces.com. (Full Apache LICENSE body still the short reference form.) | 🚧 |

## C. Explicitly deferred (parity with headroom, not pursued now)

| ID | Item | Status |
|----|------|:--:|
| C1 | TypeScript/npm SDK (MCP + proxy are already language-agnostic). | ❄️ |
| C2 | `cloak wrap <agent>` agent wrappers + `.claude-plugin` marketplace. | ❄️ |
| C3 | Full docs website (mkdocs/next). | ❄️ |

## Done so far
A1–A4, A6 (all shipped defects + proxy hardening); B1–B3 (eval, profiles, config);
B6 (CI) + B8 hygiene + identity.

## Next up
A5 (detection breadth — passports/PHI/addresses/locales, secret formats, private
keys), then B4/B5/B7 (examples, Dockerized proxy, docs). A7/A8 (pseudonym
idempotency, vault security) as polish.
