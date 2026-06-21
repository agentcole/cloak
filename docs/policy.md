# Policy reference

`CloakPolicy` (in `cloak.policy`) controls *what* is detected, *how* it's
replaced, and *where* detection runs.

## Construction

```python
from cloak import CloakPolicy

CloakPolicy()                                   # safe defaults
CloakPolicy(strategy="pseudonym", min_score=0.6)
CloakPolicy.from_profile("hipaa")               # a compliance preset
CloakPolicy.from_profile("pci", strategy="redact")  # preset + override
CloakPolicy.from_file("policy.toml")            # .json / .toml / .yaml
CloakPolicy.from_env()                           # CLOAK_* env vars
```

## Fields

| Field | Default | Meaning |
|-------|---------|---------|
| `detectors` | `["regex","ner"]` | Tiers to run: `regex`, `phone`, `ner`, `llm`. (`regex` also runs phone.) |
| `strategy` | `"placeholder"` | Global replacement: `placeholder`/`pseudonym`/`redact`/`hash`. |
| `strategy_by_type` | `{}` | Per-type overrides, e.g. `{"PERSON":"pseudonym"}`. |
| `enabled_types` | `None` | If set, only mask these categories. `None` = all. |
| `disabled_types` | `set()` | Categories to never mask. |
| `min_score` | `0.5` | Drop detections below this confidence. |
| `skip_code_blocks` | `True` | Don't mask inside fenced/inline code. |
| `roles` | system/user/assistant/tool | Message roles scanned (for `mask_messages`). |
| `allowlist` / `denylist` | `[]` | Literals never / always masked. |
| `locale` | `"en_US"` | Faker locale for the pseudonym strategy. |
| `seed` | `None` | Deterministic salt for hash/pseudonym. |
| `phone_region` | `"US"` | Assumed region for national-format phone numbers. |
| `ner_backend` / `ner_model` | `gliner` / `gliner_multi_pii-v1` | NER backend + model. |
| `llm_endpoint` / `llm_model` | `localhost:11434` / `llama3.1` | Local LLM detector. |
| `llm_allow_remote` | `False` | Allow a non-loopback LLM endpoint (off = privacy guard). |
| `llm_timeout` | `60.0` | LLM detector request timeout (seconds). |

## Compliance profiles

| Profile | Detectors | Strategy | Scope |
|---------|-----------|----------|-------|
| `default` | regex + ner | placeholder | all |
| `gdpr` | regex + ner | pseudonym | all personal data |
| `hipaa` | regex + ner | placeholder | all, high recall |
| `pci` | regex | hash | CREDIT_CARD, IBAN |
| `secrets` | regex | redact | API_KEY, JWT, CRYPTO_ADDRESS (code spans included) |
| `strict` | regex + ner | redact | everything, lowest threshold |

## Entity types

Structured (regex tier): `EMAIL`, `PHONE`, `SSN`, `CREDIT_CARD`, `IBAN`, `EIN`,
`NATIONAL_ID`, `MEDICAL_ID`, `IP_ADDRESS`, `MAC_ADDRESS`, `URL`, `API_KEY`,
`JWT`, `PRIVATE_KEY`, `CRYPTO_ADDRESS`, `DATE`, `VIN`, `GEO_COORDINATE`,
`US_ZIP`, `HANDLE`.

Unstructured (NER/LLM tiers): `PERSON`, `ORGANIZATION`, `LOCATION`, `ADDRESS`,
plus whatever labels you configure for GLiNER.

Custom: `denylist` literals are emitted as `CUSTOM`.

## Config file example (`policy.toml`)

```toml
profile = "gdpr"        # optional base
detectors = ["regex", "ner"]
strategy = "pseudonym"
min_score = 0.5
enabled_types = ["PERSON", "EMAIL", "PHONE", "NATIONAL_ID"]
```
