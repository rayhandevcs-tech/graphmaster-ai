"""Gamification engine.

Pure, dependency-free rules — periods, streaks and achievement conditions —
kept apart from the service that persists their results, for the same reason
``app/nlp`` is separate from ``AnalysisService``: the interesting logic is then
testable without a database, and the service is left doing nothing but reading,
writing and ordering.
"""

from app.gamification.periods import (
    ALL_TIME_END,
    ALL_TIME_START,
    period_window,
    platform_today,
)
from app.gamification.rules import RuleOutcome, StudentStats, evaluate_rule
from app.gamification.streaks import StreakOutcome, advance_streak

__all__ = [
    "ALL_TIME_END",
    "ALL_TIME_START",
    "RuleOutcome",
    "StreakOutcome",
    "StudentStats",
    "advance_streak",
    "evaluate_rule",
    "period_window",
    "platform_today",
]
