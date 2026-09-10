"""Pure aggregation math for the admin dashboard, kept separate from the DB-touching
endpoint code in app/routers/admin.py so it's directly unit-testable."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvaluationStats:
    total_searches: int
    total_evaluations: int
    helpful_rate: float | None
    resolved_rate: float | None


def _rate(flags: list[bool]) -> float | None:
    if not flags:
        return None
    return sum(1 for f in flags if f) / len(flags)


def compute_evaluation_stats(
    total_searches: int, helpful_flags: list[bool], resolved_flags: list[bool]
) -> EvaluationStats:
    return EvaluationStats(
        total_searches=total_searches,
        total_evaluations=max(len(helpful_flags), len(resolved_flags)),
        helpful_rate=_rate(helpful_flags),
        resolved_rate=_rate(resolved_flags),
    )
