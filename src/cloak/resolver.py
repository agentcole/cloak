"""Turn raw, possibly-overlapping detections into a clean replacement set.

Steps: drop low-confidence/disabled/allow-listed spans, drop anything inside a
code span (when configured), then resolve overlaps by keeping the highest
-confidence, longest span.
"""

from __future__ import annotations

import re

from .policy import CloakPolicy
from .types import Entity

# Fenced ```code``` blocks (incl. language tag) and inline `code`.
_FENCED = re.compile(r"```.*?```", re.DOTALL)
_INLINE = re.compile(r"`[^`\n]+`")


def _code_ranges(text: str) -> list[tuple[int, int]]:
    ranges = [m.span() for m in _FENCED.finditer(text)]
    for m in _INLINE.finditer(text):
        s, e = m.span()
        if not any(s >= a and e <= b for a, b in ranges):
            ranges.append((s, e))
    return ranges


def _in_any_range(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start < b and a < end for a, b in ranges)


class Resolver:
    def __init__(self, policy: CloakPolicy) -> None:
        self.policy = policy

    def resolve(self, entities: list[Entity], text: str) -> list[Entity]:
        policy = self.policy
        allow = set(policy.allowlist)

        protected: list[tuple[int, int]] = _code_ranges(text) if policy.skip_code_blocks else []

        candidates: list[Entity] = []
        for e in entities:
            if e.score < policy.min_score:
                continue
            if not policy.is_type_enabled(e.type):
                continue
            if e.text in allow:
                continue
            if protected and _in_any_range(e.start, e.end, protected):
                continue
            candidates.append(e)

        # Highest confidence first, then longest; greedily drop overlaps.
        accepted: list[Entity] = []
        for e in sorted(candidates, key=lambda x: (x.score, len(x)), reverse=True):
            if any(e.overlaps(a) for a in accepted):
                continue
            accepted.append(e)

        accepted.sort(key=lambda x: x.start)
        return accepted
