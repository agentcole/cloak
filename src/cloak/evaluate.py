"""Span-level precision/recall/F1 for cloak's detectors.

This is the credibility metric: how well does a given policy actually find PII?
You feed it a *gold* corpus (text + labeled spans) and it reports per-type and
overall precision/recall/F1.

Gold corpus format — an inline markup that keeps offsets out of human hands::

    Please email [[EMAIL|jane@acme.com]] today.

The loader strips ``[[TYPE|value]]`` to recover plain text plus the gold span.
Lines that are blank or start with ``#`` are ignored; lines with no markup are
negatives (any detection on them is a false positive).

Matching: a predicted entity is a true positive if a gold entity of the *same
type* overlaps it (greedy, each gold matched at most once). Overlap (vs exact)
tolerates boundary differences between detectors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .engine import Cloak
from .types import Entity

_MARKUP = re.compile(r"\[\[([A-Z_]+)\|(.+?)\]\]")

# A parsed gold example: plain text + its labeled spans.
GoldEntity = dict  # {"type": str, "start": int, "end": int, "text": str}
Example = tuple  # (text: str, list[GoldEntity])


def parse_markup(line: str) -> Example:
    """Turn one ``[[TYPE|value]]``-annotated line into (text, gold_entities)."""
    text_parts: list[str] = []
    entities: list[GoldEntity] = []
    pos = 0
    cursor = 0
    for m in _MARKUP.finditer(line):
        prefix = line[pos : m.start()]
        text_parts.append(prefix)
        cursor += len(prefix)
        value = m.group(2)
        entities.append(
            {"type": m.group(1), "start": cursor, "end": cursor + len(value), "text": value}
        )
        text_parts.append(value)
        cursor += len(value)
        pos = m.end()
    text_parts.append(line[pos:])
    return "".join(text_parts), entities


def load_corpus(path: str) -> list[Example]:
    """Load a gold corpus file (markup format). Skips blanks and ``#`` comments."""
    examples: list[Example] = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            examples.append(parse_markup(line))
    return examples


@dataclass
class Metrics:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 1.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


@dataclass
class EvalReport:
    by_type: dict[str, Metrics] = field(default_factory=dict)
    overall: Metrics = field(default_factory=Metrics)

    def format_table(self) -> str:
        rows = [f"{'TYPE':<16}{'TP':>5}{'FP':>5}{'FN':>5}{'P':>8}{'R':>8}{'F1':>8}"]
        rows.append("-" * 57)
        for etype in sorted(self.by_type):
            m = self.by_type[etype]
            rows.append(
                f"{etype:<16}{m.tp:>5}{m.fp:>5}{m.fn:>5}"
                f"{m.precision:>8.2f}{m.recall:>8.2f}{m.f1:>8.2f}"
            )
        rows.append("-" * 57)
        o = self.overall
        rows.append(
            f"{'OVERALL':<16}{o.tp:>5}{o.fp:>5}{o.fn:>5}"
            f"{o.precision:>8.2f}{o.recall:>8.2f}{o.f1:>8.2f}"
        )
        return "\n".join(rows)


def _overlaps(pred: Entity, gold: GoldEntity) -> bool:
    return pred.start < gold["end"] and gold["start"] < pred.end


def evaluate(cloak: Cloak, examples: list[Example]) -> EvalReport:
    """Run ``cloak`` over ``examples`` and compute span-level metrics."""
    report = EvalReport()

    def bucket(etype: str) -> Metrics:
        return report.by_type.setdefault(etype, Metrics())

    for text, gold in examples:
        preds = cloak.scan(text)
        matched: set[int] = set()
        for p in preds:
            hit = next(
                (
                    gi
                    for gi, g in enumerate(gold)
                    if gi not in matched and g["type"] == p.type and _overlaps(p, g)
                ),
                None,
            )
            if hit is None:
                bucket(p.type).fp += 1
                report.overall.fp += 1
            else:
                matched.add(hit)
                bucket(p.type).tp += 1
                report.overall.tp += 1
        for gi, g in enumerate(gold):
            if gi not in matched:
                bucket(g["type"]).fn += 1
                report.overall.fn += 1
    return report
