"""Tier-2 detector: local NER for unstructured PII (names, orgs, places, dates).

Two backends, both fully local:

* ``gliner`` (default) — a small zero-shot NER model; pick the labels you want
  at runtime. Runs on the ONNX/transformers stack. Extra: ``cloak-llm[ner]``.
* ``spacy`` — classic statistical NER. Extra: ``cloak-llm[spacy]`` plus a model
  (e.g. ``python -m spacy download en_core_web_sm``).

The model is loaded lazily on first :meth:`detect` and cached. If the backend
isn't installed, :meth:`available` returns ``False`` and the engine skips it
with a warning rather than crashing.
"""

from __future__ import annotations

import importlib.util
import logging
from typing import Any

from ..policy import CloakPolicy
from ..types import Entity
from .base import Detector

logger = logging.getLogger("cloak")

# Normalize spaCy's label set to cloak's canonical entity types.
_SPACY_MAP = {
    "PERSON": "PERSON",
    "PER": "PERSON",
    "ORG": "ORGANIZATION",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "FAC": "LOCATION",
    "DATE": "DATE",
    "NORP": "ORGANIZATION",
}


class NerDetector(Detector):
    name = "ner"

    def __init__(self, policy: CloakPolicy) -> None:
        self.backend = policy.ner_backend
        self.model_name = policy.ner_model
        self.labels = policy.ner_labels
        self._model: Any = None  # lazily loaded model (GLiNER or spaCy Language)

    def available(self) -> bool:
        if self.backend == "gliner":
            return importlib.util.find_spec("gliner") is not None
        if self.backend == "spacy":
            return importlib.util.find_spec("spacy") is not None
        return False

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        if self.backend == "gliner":
            from gliner import GLiNER

            self._model = GLiNER.from_pretrained(self.model_name)
        elif self.backend == "spacy":
            import spacy

            self._model = spacy.load(self.model_name)
        else:  # pragma: no cover
            raise ValueError(f"Unknown NER backend: {self.backend!r}")

    def detect(self, text: str, policy: CloakPolicy) -> list[Entity]:
        if not self.available():
            return []
        try:
            self._ensure_model()
        except Exception as exc:
            logger.warning("Could not load NER model %s: %s", self.model_name, exc)
            return []

        if self.backend == "gliner":
            return self._detect_gliner(text, policy)
        return self._detect_spacy(text)

    def _detect_gliner(self, text: str, policy: CloakPolicy) -> list[Entity]:
        assert self._model is not None
        threshold = max(0.0, policy.min_score)
        raw = self._model.predict_entities(text, self.labels, threshold=threshold)
        out: list[Entity] = []
        for r in raw:
            out.append(
                Entity(
                    type=str(r["label"]).upper().replace(" ", "_"),
                    start=int(r["start"]),
                    end=int(r["end"]),
                    text=r["text"],
                    score=float(r.get("score", 0.8)),
                    source=self.name,
                )
            )
        return out

    def _detect_spacy(self, text: str) -> list[Entity]:
        assert self._model is not None
        doc = self._model(text)
        out: list[Entity] = []
        for ent in doc.ents:
            mapped = _SPACY_MAP.get(ent.label_)
            if mapped is None:
                continue
            out.append(
                Entity(
                    type=mapped,
                    start=ent.start_char,
                    end=ent.end_char,
                    text=ent.text,
                    score=0.85,  # spaCy doesn't expose per-entity confidence
                    source=self.name,
                )
            )
        return out
