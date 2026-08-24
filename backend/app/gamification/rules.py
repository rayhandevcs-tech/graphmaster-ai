"""The declarative achievement rule engine (FR-8.9).

Each achievement stores its unlock condition as JSON, so adding one is a seed
row rather than a code change. This module turns such a rule plus a snapshot of
a student's history into an answer, and is deliberately pure: no session, no
repositories, no clock.

Every rule reports *progress* as well as satisfaction, because the achievements
screen shows "7 / 10 submissions" rather than a locked padlock — a visible
distance to the next unlock is what makes the catalogue motivating instead of
merely decorative.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class StudentStats:
    """Everything the catalogue's rules can ask about one student.

    Assembled once per evaluation and passed to every rule, so scoring a
    submission costs one batch of aggregate queries rather than one per
    achievement.
    """

    gender: str
    current_streak_days: int = 0
    scored_submissions: int = 0
    tier_counts: Mapping[str, int] = field(default_factory=dict)
    best_final_score: float = 0.0
    distinct_graph_types: int = 0

    # Most recent first. Only as long as the longest ``consecutive`` run any
    # achievement in the catalogue asks for — a full history would be read on
    # every submission to answer a question about the last three.
    recent_vocabulary_percentages: Sequence[float] = ()


@dataclass(frozen=True)
class RuleOutcome:
    satisfied: bool
    progress: int
    target: int
    applicable: bool = True
    """False when the rule can never apply to this student — the gendered
    crown achievements. An inapplicable rule is hidden from their catalogue
    rather than shown as permanently locked."""


def evaluate_rule(rule: Mapping[str, Any], stats: StudentStats) -> RuleOutcome:
    """Evaluate one achievement rule against a student's history."""
    rule_type = rule.get("type")
    handler = _HANDLERS.get(str(rule_type))

    if handler is None:
        # A typo in a seed row must not unlock anything, and must not take the
        # scoring path down with it: a student mid-submission would lose their
        # work over a content-authoring mistake. Unknown rules are inert and
        # logged so the misconfiguration is still visible.
        logger.warning("Ignoring achievement rule with unknown type %r", rule_type)
        return RuleOutcome(satisfied=False, progress=0, target=0, applicable=False)

    gender = rule.get("gender")
    if gender is not None and gender != stats.gender:
        # The crown achievements are gender-gated so each student has exactly
        # one reachable one, matching the Graph King / Graph Queen titles in
        # FR-7.2 without awarding two achievements for one accomplishment.
        return RuleOutcome(satisfied=False, progress=0, target=0, applicable=False)

    return handler(rule, stats)


def _threshold(rule: Mapping[str, Any], default: int = 1) -> int:
    try:
        return max(1, int(rule.get("threshold", default)))
    except (TypeError, ValueError):
        return default


def _counted(progress: int, target: int) -> RuleOutcome:
    return RuleOutcome(satisfied=progress >= target, progress=progress, target=target)


def _submission_count(rule: Mapping[str, Any], stats: StudentStats) -> RuleOutcome:
    return _counted(stats.scored_submissions, _threshold(rule))


def _streak_days(rule: Mapping[str, Any], stats: StudentStats) -> RuleOutcome:
    return _counted(stats.current_streak_days, _threshold(rule))


def _reward_tier_count(rule: Mapping[str, Any], stats: StudentStats) -> RuleOutcome:
    tier = str(rule.get("tier", ""))
    return _counted(stats.tier_counts.get(tier, 0), _threshold(rule))


def _distinct_graph_types(rule: Mapping[str, Any], stats: StudentStats) -> RuleOutcome:
    return _counted(stats.distinct_graph_types, _threshold(rule))


def _final_score_threshold(rule: Mapping[str, Any], stats: StudentStats) -> RuleOutcome:
    target = _threshold(rule, default=100)
    # Compared as a float and reported as an int: "Perfect Score" is 100 and a
    # student sitting on 99.4 should see 99, not a rounded-up 100 next to a
    # padlock that has not opened.
    return RuleOutcome(
        satisfied=stats.best_final_score >= target,
        progress=int(stats.best_final_score),
        target=target,
    )


def _vocabulary_percentage_threshold(rule: Mapping[str, Any], stats: StudentStats) -> RuleOutcome:
    threshold = float(_threshold(rule, default=90))
    required = max(1, int(rule.get("consecutive", 1) or 1))

    # The run is counted from the most recent submission backwards, so a single
    # weak attempt breaks it. That is the point of "in a row": the achievement
    # rewards sustained accuracy, and counting the best three of the last ten
    # would reward a lucky one instead.
    run = 0
    for percentage in stats.recent_vocabulary_percentages:
        if percentage < threshold:
            break
        run += 1

    return _counted(min(run, required), required)


_HANDLERS = {
    "submission_count": _submission_count,
    "streak_days": _streak_days,
    "reward_tier_count": _reward_tier_count,
    "distinct_graph_types": _distinct_graph_types,
    "final_score_threshold": _final_score_threshold,
    "vocabulary_percentage_threshold": _vocabulary_percentage_threshold,
}


def required_recent_window(rules: Sequence[Mapping[str, Any]]) -> int:
    """How much recent history the catalogue's ``consecutive`` rules need.

    Derived from the catalogue rather than fixed, so adding a "five in a row"
    achievement does not silently keep evaluating against three.
    """
    windows = [
        int(rule.get("consecutive", 1) or 1)
        for rule in rules
        if rule.get("type") == "vocabulary_percentage_threshold"
    ]
    return max(windows, default=1)
