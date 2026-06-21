<div align="center"><pre>
   ██████╗██╗      ██████╗  █████╗ ██╗  ██╗
  ██╔════╝██║     ██╔═══██╗██╔══██╗██║ ██╔╝
  ██║     ██║     ██║   ██║███████║█████╔╝
  ██║     ██║     ██║   ██║██╔══██║██╔═██╗
  ╚██████╗███████╗╚██████╔╝██║  ██║██║  ██╗
   ╚═════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
   Reversible PII redaction for LLM prompts
</pre></div>

<p align="center"><strong>Local-first · reversible · pluggable strategies · library · CLI · MCP · round-trip proxy</strong></p>

**cloak** strips personally identifiable information out of text *before* it reaches a model, then puts it back in the response — so the model only ever sees `[PERSON_1]` while your user sees `Jane Doe`. Detection runs on your machine (regex + local NER, with an optional local LLM); nothing about *finding* PII requires a network call.

It is a sibling of [`headroom`](../headroom) and borrows its architecture (tiered detect → resolve → transform → reverse, a `Vault` that mirrors headroom's CCR reversibility, dependency-free core with optional extras). Where headroom *compresses* context, cloak *protects* it.

```
 your app ──prompt──▶  ┌─────────── cloak (local) ───────────┐ ──masked──▶ LLM provider
                       │ detect (regex│NER│local-LLM)         │
                       │   → resolve (overlaps, code-skip)    │
                       │   → replace (placeholder│pseudonym│  │
                       │              redact│hash)            │
 your app ◀─restored── │   ◀── restore from Vault ◀───────────│ ◀─response─ LLM provider
                       └─────────────────────────────────────┘
```

## Install

```bash
pip install "cloak-llm"          # core: regex detection + all 4 strategies, zero deps
pip install "cloak-llm[ner]"     # + local NER (GLiNER/ONNX) for names, orgs, places
pip install "cloak-llm[phone]"   # + validated, locale-aware phone detection
pip install "cloak-llm[faker]"   # + realistic pseudonyms
pip install "cloak-llm[mcp]"     # + MCP server
pip install "cloak-llm[proxy]"   # + round-trip reverse proxy
pip install "cloak-llm[llm]"     # + local/trusted-LLM tagging detector
pip install "cloak-llm[config]"  # + YAML config files
pip install "cloak-llm[all]"     # everything
```

## Library

```python
from cloak import Cloak, CloakPolicy

c = Cloak(CloakPolicy(strategy="placeholder"))          # or pseudonym | redact | hash
res = c.mask_text("Email Jane Doe at jane@acme.com about SSN 123-45-6789")
# res.text  -> "Email Jane Doe at [EMAIL_1] about SSN 123-45-6789"  (regex-only;
#              add detectors=["regex","ner"] to also catch the name)

answer = call_your_llm(res.text)
print(c.unmask_text(answer, res.vault))                 # originals restored
```

Chat messages share one vault, so the same value maps to the same token everywhere (coreference) and provider prefix-caches stay stable:

```python
res = c.mask_messages([
    {"role": "user", "content": "I'm jane@acme.com"},
    {"role": "assistant", "content": "Hi jane@acme.com"},
])  # both become [EMAIL_1]
```

## CLI

```bash
echo "call Jane at +1 415 555 0123" | cloak scan --detectors regex
cloak mask report.txt --strategy pseudonym --vault out.cloakvault > masked.txt
cloak unmask masked.txt --vault out.cloakvault
cloak serve-mcp                                  # MCP server over stdio
cloak proxy --port 8788 --upstream https://api.openai.com
```

## MCP

`cloak serve-mcp` exposes three tools to any MCP client:

| Tool | Purpose |
|------|---------|
| `cloak_scan(text, detectors)` | report detected entities |
| `cloak_mask(text, strategy, detectors)` | returns masked text + a `vault_id` |
| `cloak_unmask(text, vault_id)` | restore originals from a `vault_id` |

## Round-trip proxy

Point your LLM client's base URL at the proxy; it masks the request, forwards to `--upstream`, and restores PII in the response — including streamed SSE (tokens split across chunks are handled).

```bash
cloak proxy --port 8788 --upstream https://api.openai.com --strategy placeholder
# then: OPENAI_BASE_URL=http://127.0.0.1:8788/v1
```

### Docker

```bash
docker build -t cloak .
docker run -p 8788:8788 -e CLOAK_PROXY_UPSTREAM=https://api.openai.com cloak
```

Or a fully-local stack (cloak ↔ Ollama) with `docker compose up --build` — see
[`docker-compose.yml`](docker-compose.yml).

## Detection tiers

| Tier | Detector | Catches | Cost |
|------|----------|---------|------|
| 1 | `regex` (always on) | emails, phones, SSNs, credit cards (Luhn), IBANs (mod-97), IPs/MACs, URLs, **secrets** (private keys/PEM, AWS, GitHub, OpenAI, Stripe, SendGrid, Twilio, Google, Slack, npm, PyPI, JWT), crypto addresses, dates, **national IDs** (US SSN/EIN, UK NINO, Spain DNI, Italy codice, India PAN/Aadhaar, Brazil CPF, Germany Steuer-ID, France INSEE), **NPI**, **VIN**, geo-coordinates, ZIP+4, handles | free, deterministic |
| 2 | `ner` (`[ner]`) | PERSON, ORGANIZATION, LOCATION, ADDRESS, DATE | local model |
| 3 | `llm` (`[llm]`) | context-dependent / messy PII | local model, slower |

The LLM detector refuses any non-loopback endpoint unless `policy.llm_allow_remote=True` — detecting PII must not itself leak PII.

## Replacement strategies

| Strategy | Example | Reversible | Notes |
|----------|---------|:---:|-------|
| `placeholder` | `[PERSON_1]` | ✅ | default; clear & cache-friendly |
| `pseudonym` | `Aaron Wells` | ✅ (best-effort) | format-preserving fakes (Faker) |
| `redact` | `[PERSON]` | ❌ | one-way scrub |
| `hash` | `[PERSON_a1b2c3d4]` | ✅ | stable across runs for a fixed seed |

Pick globally (`strategy=...`) or per category (`strategy_by_type={"PERSON": "pseudonym"}`).

## Compliance profiles

Opinionated presets (starting points, not legal advice):

| Profile | Detectors | Strategy | Scope |
|---------|-----------|----------|-------|
| `gdpr` | regex + ner | pseudonym | all personal data (pseudonymisation, Art. 4(5)) |
| `hipaa` | regex + ner | placeholder | all 18 identifier classes, high recall |
| `pci` | regex | hash | cardholder data only (CREDIT_CARD, IBAN) |
| `secrets` | regex | redact | API keys / JWT / crypto addresses |
| `strict` | regex + ner | redact | everything, lowest threshold |

```python
c = Cloak(CloakPolicy.from_profile("pci"))           # or from_profile("gdpr", strategy="redact")
```
```bash
cloak scan report.txt --profile hipaa
```

## Config file & env

```python
CloakPolicy.from_file("policy.toml")   # .json / .toml / .yaml
CloakPolicy.from_env()                 # CLOAK_PROFILE, CLOAK_DETECTORS, CLOAK_STRATEGY, …
```
```toml
# policy.toml — base on a profile, then override
profile = "gdpr"
detectors = ["regex", "ner"]
min_score = 0.5
```
```bash
cloak mask notes.txt --config policy.toml --vault out.cloakvault
```

## Evaluate detection quality

`cloak` ships a span-level precision/recall/F1 harness so coverage is measured, not guessed:

```bash
cloak eval eval/gold.txt --detectors regex          # P/R/F1 per entity type
```

Gold corpora use an inline `[[TYPE|value]]` markup (no manual offsets). The bundled corpus regression-tests the regex tier at **1.00 precision / 1.00 recall** on every structured type.

## Reversibility & the vault

The `Vault` is the only thing needed to restore a response — and it holds the **raw PII**. Treat it as a secret. It serializes to JSON and can be encrypted at rest with a password (`Vault.save(path, password=...)`, requires `cryptography`).

## Design notes

- **Code-aware:** by default cloak does not mask inside fenced/inline code spans, so it won't corrupt identifiers and break agent tasks.
- **Overlap resolution:** when detectors disagree, the highest-confidence, longest span wins (a date-formatted string stays `DATE`, not `PHONE`).
- **Graceful degradation:** an optional detector whose dependency is missing is skipped with a warning, never a crash.

## License

Apache-2.0.
