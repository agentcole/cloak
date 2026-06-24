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
| A5 | ~~Thin detection coverage~~ — **expanded**: PEM private keys; Stripe/SendGrid/Twilio/Google/GitHub-PAT/OpenAI-proj/npm/PyPI secrets; national IDs (UK NINO, Spain DNI, Italy codice, India PAN/Aadhaar, Brazil CPF, Germany Steuer-ID, France INSEE) + US EIN/NPI; Canada SIN; US street addresses; VIN, geo-coordinates, ZIP+4, handles — all checksum/format-validated, regression-tested in `eval/gold.txt` at 1.00 precision. (Remaining: passports, driver's licenses, non-US postal formats, more locales.) | ✅ |
| A6 | ~~Proxy hardening~~ — **done**: Anthropic `system`+content-block masking (tested), bounded connect/write timeouts (read unbounded for streams), clean 502 on unreachable upstream, masking offloaded to a threadpool, thread-safe pseudonym strategy, guaranteed upstream close, bounded MCP vault store. | ✅ |
| A7 | ~~double-masking/idempotency~~ — **fixed**: token-collision protection (`Vault.reserve`) so a real value never reuses a token literal already in the input; masked output isn't re-masked; restore is idempotent. (Pseudonym restore remains best-effort by design — see threat model.) | ✅ |
| A8 | ~~Vault security~~ — **hardened**: `Vault.clear()` zeroization, context-manager auto-wipe, PII-safe `__repr__`/`VaultEntry` repr, warning on unencrypted save. (Encryption was already available via `save(password=...)`.) | ✅ |

## B. Capabilities (in scope for a solid standalone tool)

| ID | Item | Status |
|----|------|:--:|
| B1 | ~~PII eval harness~~ — **done**: `cloak eval` + `cloak.evaluate` give span-level P/R/F1 per type over a markup gold corpus; regex tier regression-tested at 1.00/1.00 on structured types. | ✅ |
| B2 | ~~Compliance profiles~~ — **done**: `gdpr` / `hipaa` / `pci` / `strict` / `secrets` via `CloakPolicy.from_profile` / `--profile`. | ✅ |
| B3 | ~~Config-file loading~~ — **done**: `CloakPolicy.from_file` (JSON/TOML/YAML), `.from_mapping`, `.from_env`; `--config`. | ✅ |
| B4 | ~~Examples~~ — **done**: `examples/` quickstart, strategies+profiles, OpenAI-SDK wrap (runs against local Ollama), proxy + MCP guides. | ✅ |
| B5 | ~~Dockerized proxy~~ — **done**: `Dockerfile` (runs `cloak proxy`, unprivileged) + `docker-compose.yml` (cloak ↔ Ollama); proxy command validated live against Ollama. | ✅ |
| B6 | ~~CI~~ — **done**: `ci.yml` runs ruff check/format + mypy + pytest on Python 3.10–3.13 and builds the wheel; `publish.yml` does PyPI Trusted Publishing on version tags. | ✅ |
| B7 | ~~Docs~~ — **done**: `docs/architecture.md`, `docs/policy.md` (field/profile/type reference), `docs/threat-model.md`, and `llms.txt`. | ✅ |
| B8 | **Project hygiene** — **mostly done**: CHANGELOG, CONTRIBUTING, SECURITY.md added; identity = symbolicinterfaces.com. (Full Apache LICENSE body still the short reference form.) | 🚧 |
| B9 | **Document support (docling)** — **in progress**: library `scan_document`/`mask_document` with shared-vault coreference, reversible `mask` vs one-way `redact`, table-cell-aware parsing, markdown/JSON renderers, and **in-place PDF redaction** (PyMuPDF `apply_redactions` — glyphs removed, metadata scrubbed). Validated end-to-end on a real 3-page PDF (`examples/data/kundenkartei.pdf`). Optional `[docling]` extra, lazy-imported (core stays zero-dep). Remaining: DOCX render, OCR validation (RapidOCR model issue in some envs), CLI/MCP/proxy wiring. Plan: `docs/documents-plan.md`. | 🚧 |

## C. Explicitly deferred (parity with headroom, not pursued now)

| ID | Item | Status |
|----|------|:--:|
| C1 | TypeScript/npm SDK (MCP + proxy are already language-agnostic). | ❄️ |
| C2 | `cloak wrap <agent>` agent wrappers + `.claude-plugin` marketplace. | ❄️ |
| C3 | Full docs website (mkdocs/next). | ❄️ |

## Done so far
A1–A6 (all shipped defects, proxy hardening, detection breadth); B1–B7 (eval,
profiles, config, examples, Docker, CI, docs); B8 hygiene + identity.

## Next up
**B9 — document support (docling):** the next pillar. Whole-document parse →
scan / reversible mask / one-way redact, with markdown/JSON/PDF/DOCX output and
optional OCR, behind an optional `[docling]` extra. See `docs/documents-plan.md`
for the full design and build order.

Optional future tail: passports / driver's licenses (need contextual cues to
stay precise), non-US postal-address formats, and more phone/ID locales.
Deferred by decision: C1–C3.
