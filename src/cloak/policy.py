"""Configuration for a cloaking session.

A :class:`CloakPolicy` is the single knob bag that controls *what* is detected,
*how* it is replaced, and *where* detection runs. Everything has a sensible,
privacy-leaning default so ``CloakPolicy()`` is a safe starting point.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from typing import Any

# Fields that accept a set but are naturally written as a list in config files.
_SET_FIELDS = {"enabled_types", "disabled_types", "roles"}

# Replacement strategy names (see cloak.strategies).
STRATEGY_PLACEHOLDER = "placeholder"
STRATEGY_PSEUDONYM = "pseudonym"
STRATEGY_REDACT = "redact"
STRATEGY_HASH = "hash"

# Detector names (see cloak.detectors).
DETECTOR_REGEX = "regex"
DETECTOR_PHONE = "phone"
DETECTOR_NER = "ner"
DETECTOR_LLM = "llm"


@dataclass
class CloakPolicy:
    """Controls detection and replacement behaviour.

    Args:
        detectors: Ordered detectors to run. ``regex`` is dependency-free;
            ``ner`` and ``llm`` require optional extras and degrade gracefully
            (a warning) if their dependencies are missing.
        strategy: Default replacement strategy applied to every entity type.
        strategy_by_type: Per-type overrides, e.g. ``{"PERSON": "pseudonym"}``.
        enabled_types: If set, only these entity types are masked (allow-list of
            categories). ``None`` means "all detected types".
        disabled_types: Entity types to never mask (deny-list of categories).
        min_score: Drop detections below this confidence.
        skip_code_blocks: Do not mask inside fenced/inline code spans — avoids
            corrupting identifiers and breaking agent tasks.
        roles: Message roles whose content is scanned (for message inputs).
        allowlist: Literal strings that must never be masked even if detected.
        denylist: Literal strings that are always masked (type ``CUSTOM``).
        locale: Faker locale for the pseudonym strategy.
        seed: Optional deterministic seed for hash/pseudonym strategies. ``None``
            derives a per-vault random salt.
        ner_backend: ``gliner`` or ``spacy``.
        ner_model: Model id for the chosen NER backend.
        ner_labels: Entity labels the NER model should look for.
        llm_endpoint: Base URL of a *local/trusted* OpenAI-compatible or Ollama
            server. Cloak refuses to call non-loopback hosts unless
            ``llm_allow_remote`` is explicitly set.
        llm_model: Model name for the local LLM detector.
        llm_allow_remote: Opt-in escape hatch to allow a non-loopback endpoint.
    """

    detectors: list[str] = field(default_factory=lambda: [DETECTOR_REGEX, DETECTOR_NER])
    strategy: str = STRATEGY_PLACEHOLDER
    strategy_by_type: dict[str, str] = field(default_factory=dict)

    enabled_types: set[str] | None = None
    disabled_types: set[str] = field(default_factory=set)
    min_score: float = 0.5

    skip_code_blocks: bool = True
    roles: set[str] = field(default_factory=lambda: {"system", "user", "assistant", "tool"})

    allowlist: list[str] = field(default_factory=list)
    denylist: list[str] = field(default_factory=list)

    # Pseudonym / hash
    locale: str = "en_US"
    seed: int | None = None

    # Phone detection: assumed region for nationally-formatted numbers
    # (the optional ``phonenumbers`` library). International numbers match
    # regardless.
    phone_region: str = "US"

    # NER detector
    ner_backend: str = "gliner"
    ner_model: str = "urchade/gliner_multi_pii-v1"
    ner_labels: list[str] = field(
        default_factory=lambda: [
            "person",
            "organization",
            "location",
            "date",
            "address",
        ]
    )

    # Local/trusted LLM detector
    llm_endpoint: str = "http://localhost:11434"
    llm_model: str = "llama3.1"
    llm_allow_remote: bool = False
    llm_timeout: float = 60.0

    def strategy_for(self, entity_type: str) -> str:
        """Resolve the strategy name for a given entity type."""
        return self.strategy_by_type.get(entity_type, self.strategy)

    def is_type_enabled(self, entity_type: str) -> bool:
        if entity_type in self.disabled_types:
            return False
        if self.enabled_types is not None:
            return entity_type in self.enabled_types
        return True

    # -- constructors -----------------------------------------------------

    @classmethod
    def from_profile(cls, name: str, **overrides: Any) -> CloakPolicy:
        """Build a policy from a named compliance profile, with optional overrides."""
        from .profiles import get_profile

        return cls(**{**get_profile(name), **overrides})

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> CloakPolicy:
        """Build a policy from a plain dict (e.g. parsed JSON/TOML/YAML).

        Supports a ``profile`` key to base the policy on a profile, with the
        remaining keys applied as overrides. ``enabled_types`` etc. may be given
        as lists. Unknown keys raise a clear error.
        """
        data = dict(data)
        profile = data.pop("profile", None)

        valid = {f.name for f in fields(cls)}
        unknown = set(data) - valid
        if unknown:
            raise ValueError(
                f"Unknown policy keys: {', '.join(sorted(unknown))}. "
                f"Valid keys: {', '.join(sorted(valid))}"
            )

        for key in _SET_FIELDS:
            if isinstance(data.get(key), list):
                data[key] = set(data[key])

        if profile is not None:
            return cls.from_profile(profile, **data)
        return cls(**data)

    @classmethod
    def from_file(cls, path: str) -> CloakPolicy:
        """Load a policy from a JSON, TOML, or YAML file (by extension)."""
        return cls.from_mapping(_load_mapping(path))

    @classmethod
    def from_env(cls, prefix: str = "CLOAK_") -> CloakPolicy:
        """Build a policy from ``CLOAK_*`` environment variables.

        Recognized: ``PROFILE``, ``DETECTORS`` (comma), ``STRATEGY``,
        ``MIN_SCORE``, ``LOCALE``, ``PHONE_REGION``, ``SEED``,
        ``ENABLED_TYPES`` (comma).
        """
        data: dict[str, Any] = {}
        env = os.environ

        def _get(name: str) -> str | None:
            return env.get(prefix + name)

        if (v := _get("PROFILE")) is not None:
            data["profile"] = v
        if (v := _get("DETECTORS")) is not None:
            data["detectors"] = [d.strip() for d in v.split(",") if d.strip()]
        if (v := _get("STRATEGY")) is not None:
            data["strategy"] = v
        if (v := _get("MIN_SCORE")) is not None:
            data["min_score"] = float(v)
        if (v := _get("LOCALE")) is not None:
            data["locale"] = v
        if (v := _get("PHONE_REGION")) is not None:
            data["phone_region"] = v
        if (v := _get("SEED")) is not None:
            data["seed"] = int(v)
        if (v := _get("ENABLED_TYPES")) is not None:
            data["enabled_types"] = {t.strip().upper() for t in v.split(",") if t.strip()}
        return cls.from_mapping(data)


def _load_mapping(path: str) -> dict[str, Any]:
    """Parse a config file into a dict, choosing the parser by extension."""
    import json

    lower = path.lower()
    with open(path, "rb") as fh:
        raw = fh.read()

    if lower.endswith(".json"):
        return json.loads(raw.decode("utf-8"))
    if lower.endswith((".toml",)):
        try:
            import tomllib  # Python 3.11+
        except ModuleNotFoundError:  # pragma: no cover - 3.10 fallback
            import tomli as tomllib
        return tomllib.loads(raw.decode("utf-8"))
    if lower.endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                'YAML config requires PyYAML: pip install "cloak-llm[config]"'
            ) from exc
        return yaml.safe_load(raw.decode("utf-8")) or {}
    raise ValueError(f"Unsupported config extension for {path!r} (use .json/.toml/.yaml)")
