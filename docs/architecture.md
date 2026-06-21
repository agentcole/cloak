# Architecture

cloak is a pipeline: **detect → resolve → replace → restore**. Everything runs
locally; the only thing that crosses a network boundary is the masked text you
choose to send to an LLM.

```
 text / chat messages
        │
        ▼
  ┌───────────────────────────────────────────── Cloak.scan ─────────────┐
  │  Detectors (tiered, run in order, results unioned)                    │
  │    • RegexDetector   structured PII + secrets        (cloak/patterns) │
  │    • PhoneDetector   libphonenumber / regex fallback                  │
  │    • NerDetector     GLiNER / spaCy        (optional [ner])           │
  │    • LlmDetector     local Ollama / OpenAI-compatible (optional [llm])│
  │              │                                                        │
  │              ▼                                                        │
  │  Resolver  — drop low-confidence; skip code spans; allow/deny;        │
  │              merge overlaps (highest score, longest span wins)        │
  └──────────────────────────────┬───────────────────────────────────────┘
                                 ▼  resolved entities
  ┌──────────────────────── Cloak.mask_* ────────────────────────────────┐
  │  For each entity: Strategy.generate → token, recorded in the Vault    │
  │    placeholder | pseudonym | redact | hash   (per-type selectable)    │
  │  Replace spans right-to-left so offsets stay valid                    │
  └──────────────────────────────┬───────────────────────────────────────┘
                                 ▼  masked text  +  Vault
                          send to the LLM
                                 ▼  response (may echo tokens)
  ┌──────────────────────── Vault.restore ───────────────────────────────┐
  │  Replace each reversible token with its original (longest-first)      │
  └───────────────────────────────────────────────────────────────────────┘
```

## Components

| Module | Role |
|--------|------|
| `cloak.engine.Cloak` | Orchestrator: builds detectors/strategies, runs the pipeline. |
| `cloak.policy.CloakPolicy` | All configuration; profile/file/env constructors. |
| `cloak.detectors.*` | `RegexDetector`, `PhoneDetector`, `NerDetector`, `LlmDetector`. |
| `cloak.patterns` / `cloak.validators` | Regexes + checksum validators (Luhn, IBAN, VIN, CPF, Verhoeff, …). |
| `cloak.resolver.Resolver` | Filtering, code-span skipping, overlap resolution. |
| `cloak.strategies.*` | The four replacement strategies. |
| `cloak.vault.Vault` | original ↔ token map (coreference), restore, (encrypted) persistence. |
| `cloak.evaluate` | Span-level precision/recall/F1 over a gold corpus. |
| `cloak.proxy.server` | Round-trip reverse proxy. |
| `cloak.mcp_server` | MCP server exposing scan/mask/unmask. |

## Key design choices

- **Reversibility lives in the Vault.** Restoration is token-string replacement,
  which is format-agnostic — it works for any provider's JSON and for streamed
  SSE (the proxy buffers partial tokens across chunk boundaries; see
  `cloak.proxy.streaming.StreamRestorer`).
- **Coreference.** One Vault per request maps the same value to the same token
  everywhere — readable for the model and stable for provider prefix caches.
- **Graceful degradation.** Optional detectors whose dependency is missing are
  skipped with a warning, never a crash. Core has zero required dependencies.
- **Precision via validators.** Bare-digit identifiers only emit when they pass
  the relevant checksum, keeping the regex tier's false-positive rate low.
