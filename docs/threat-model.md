# Threat model

## What cloak is for

Keeping personally identifiable information out of prompts sent to **third-party
LLM providers**, while staying usable: detection runs locally and the original
values are restored in the response so your users still see real data.

## Trust boundaries

- **Detection is local.** The regex, phone, and NER tiers never touch the
  network. The optional LLM detector refuses any non-loopback endpoint unless
  `llm_allow_remote=True` — detecting PII must not itself leak PII.
- **The masked text is what you trust to the provider.** Only tokens like
  `[EMAIL_1]` leave your machine (assuming recall caught the PII — see limits).
- **The Vault is a secret.** It holds the original ↔ token mapping, i.e. the raw
  PII. Anyone with the vault can de-mask. Never commit, log, or transmit it.
  Encrypt at rest with `Vault.save(path, password=...)`.

## Limitations (read these)

- **Recall is not 100%.** Regex/NER/LLM detectors miss things. Measure coverage
  for *your* data with `cloak eval` before relying on it. cloak is a strong
  control, not a guarantee — don't make it your sole compliance mechanism.
- **Checksum-gated generic IDs can false-positive.** Bare-digit identifiers
  (German tax ID, NPI, Aadhaar, INSEE) are validated only by a checksum, so on
  number-heavy text some random values may match. They carry a low score (0.55);
  raise `min_score` to 0.6 to drop them.
- **Code spans are skipped by default.** `skip_code_blocks=True` means PII (or
  secrets) inside fenced/inline code isn't masked. Set it `False` (the `secrets`
  profile does) to scan code too.
- **Pseudonyms restore best-effort.** A generated fake that also appears
  verbatim in the model's prose could be over-restored. Use `placeholder`/`hash`
  for guaranteed-unique tokens.
- **`redact` is irreversible** by design — redacted values cannot be restored.
- **The proxy trusts its upstream.** It forwards your auth headers to whatever
  `--upstream` you configure; point it only at providers you trust.
- **NER/LLM add latency** and, for the LLM tier, depend on a local model's
  quality.

## Recommendations

- Pin a profile (`gdpr`/`hipaa`/`pci`) and verify it with `cloak eval`.
- Encrypt vaults; treat them like credentials.
- Keep the LLM detector local; never set `llm_allow_remote` with real PII unless
  you fully control the endpoint.
- Tune `min_score` to your precision/recall needs and re-measure.
