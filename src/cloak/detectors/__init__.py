"""PII detectors (tiered): regex (Tier 1), NER (Tier 2), local LLM (Tier 3)."""

from __future__ import annotations

from .base import Detector
from .regex_detector import RegexDetector

__all__ = ["Detector", "RegexDetector", "NerDetector", "LlmDetector"]


def __getattr__(name: str):  # lazy: avoid importing optional-dep modules eagerly
    if name == "NerDetector":
        from .ner_detector import NerDetector

        return NerDetector
    if name == "LlmDetector":
        from .llm_detector import LlmDetector

        return LlmDetector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
