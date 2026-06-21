"""Configuration for a cloaking session.

A :class:`CloakPolicy` is the single knob bag that controls *what* is detected,
*how* it is replaced, and *where* detection runs. Everything has a sensible,
privacy-leaning default so ``CloakPolicy()`` is a safe starting point.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Replacement strategy names (see cloak.strategies).
STRATEGY_PLACEHOLDER = "placeholder"
STRATEGY_PSEUDONYM = "pseudonym"
STRATEGY_REDACT = "redact"
STRATEGY_HASH = "hash"

# Detector names (see cloak.detectors).
DETECTOR_REGEX = "regex"
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

    def strategy_for(self, entity_type: str) -> str:
        """Resolve the strategy name for a given entity type."""
        return self.strategy_by_type.get(entity_type, self.strategy)

    def is_type_enabled(self, entity_type: str) -> bool:
        if entity_type in self.disabled_types:
            return False
        if self.enabled_types is not None:
            return entity_type in self.enabled_types
        return True
