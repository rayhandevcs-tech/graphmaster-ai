"""The declarative achievement rule engine.

Rules arrive as JSON from seed data, so these tests are as much about what the
engine does with *bad* data as with good: a content-authoring mistake must not
be able to unlock everything, and must not be able to fail a submission.
"""

from __future__ import annotations

import pytest

from app.gamification.rules import (
    StudentStats,
    evaluate_rule,
    required_recent_window,
)


def stats(**overrides) -> StudentStats:
    base = {
        "gender": "female",
        "current_streak_days": 0,
        "scored_submissions": 0,
        "tier_counts": {},
        "best_final_score": 0.0,
        "distinct_graph_types": 0,
        "recent_vocabulary_percentages": (),
    }
    return StudentStats(**(base | overrides))


# ── Counting rules ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("done", "threshold", "satisfied"),
    [(0, 1, False), (1, 1, True), (9, 10, False), (10, 10, True), (11, 10, True)],
)
def test_submission_count_unlocks_at_the_threshold(done, threshold, satisfied):
    outcome = evaluate_rule(
        {"type": "submission_count", "threshold": threshold},
        stats(scored_submissions=done),
    )

    assert outcome.satisfied is satisfied
    assert outcome.progress == done
    assert outcome.target == threshold


def test_a_locked_achievement_still_reports_how_far_away_it_is():
    """A visible distance is what makes the catalogue motivating."""
    outcome = evaluate_rule(
        {"type": "submission_count", "threshold": 50}, stats(scored_submissions=37)
    )

    assert not outcome.satisfied
    assert (outcome.progress, outcome.target) == (37, 50)


def test_streak_days_reads_the_current_streak_not_the_longest():
    assert evaluate_rule({"type": "streak_days", "threshold": 7}, stats(current_streak_days=7))
    assert not evaluate_rule(
        {"type": "streak_days", "threshold": 7}, stats(current_streak_days=6)
    ).satisfied


def test_reward_tier_count_only_counts_the_named_tier():
    tiers = {"crown": 1, "flower": 12, "hammer": 3}

    assert evaluate_rule(
        {"type": "reward_tier_count", "tier": "crown", "threshold": 1}, stats(tier_counts=tiers)
    ).satisfied
    assert not evaluate_rule(
        {"type": "reward_tier_count", "tier": "steady", "threshold": 1}, stats(tier_counts=tiers)
    ).satisfied


def test_distinct_graph_types_needs_all_four():
    rule = {"type": "distinct_graph_types", "threshold": 4}

    assert not evaluate_rule(rule, stats(distinct_graph_types=3)).satisfied
    assert evaluate_rule(rule, stats(distinct_graph_types=4)).satisfied


# ── Gender gating ────────────────────────────────────────────────────────────


def test_a_gendered_rule_is_inapplicable_rather_than_merely_locked():
    """Graph King is not something a female student is 1 crown away from."""
    crowned = stats(gender="female", tier_counts={"crown": 5})

    king = evaluate_rule(
        {"type": "reward_tier_count", "tier": "crown", "threshold": 1, "gender": "male"}, crowned
    )
    queen = evaluate_rule(
        {"type": "reward_tier_count", "tier": "crown", "threshold": 1, "gender": "female"}, crowned
    )

    assert not king.applicable
    assert not king.satisfied
    assert queen.applicable
    assert queen.satisfied


# ── Score rules ──────────────────────────────────────────────────────────────


def test_a_perfect_score_rule_needs_the_full_hundred():
    rule = {"type": "final_score_threshold", "threshold": 100}

    assert not evaluate_rule(rule, stats(best_final_score=99.6)).satisfied
    assert evaluate_rule(rule, stats(best_final_score=100.0)).satisfied


def test_score_progress_is_truncated_rather_than_rounded_up():
    """99.6 shown as 100 beside a padlock that has not opened reads as a bug."""
    outcome = evaluate_rule(
        {"type": "final_score_threshold", "threshold": 100}, stats(best_final_score=99.6)
    )

    assert outcome.progress == 99


# ── Consecutive rules ────────────────────────────────────────────────────────


def test_consecutive_vocabulary_counts_the_run_from_the_newest_submission():
    rule = {"type": "vocabulary_percentage_threshold", "threshold": 90, "consecutive": 3}

    assert evaluate_rule(rule, stats(recent_vocabulary_percentages=(95.0, 92.0, 90.0))).satisfied


def test_one_weak_attempt_breaks_the_run():
    """ "In a row" has to mean in a row, or the achievement rewards a lucky one."""
    rule = {"type": "vocabulary_percentage_threshold", "threshold": 90, "consecutive": 3}

    outcome = evaluate_rule(rule, stats(recent_vocabulary_percentages=(95.0, 41.0, 99.0)))

    assert not outcome.satisfied
    assert outcome.progress == 1


def test_the_run_is_broken_by_the_most_recent_attempt_not_only_older_ones():
    rule = {"type": "vocabulary_percentage_threshold", "threshold": 90, "consecutive": 3}

    outcome = evaluate_rule(rule, stats(recent_vocabulary_percentages=(12.0, 95.0, 97.0)))

    assert not outcome.satisfied
    assert outcome.progress == 0


def test_a_student_with_no_history_satisfies_nothing():
    for rule in (
        {"type": "submission_count", "threshold": 1},
        {"type": "streak_days", "threshold": 7},
        {"type": "final_score_threshold", "threshold": 100},
        {"type": "vocabulary_percentage_threshold", "threshold": 90, "consecutive": 3},
        {"type": "distinct_graph_types", "threshold": 4},
    ):
        assert not evaluate_rule(rule, stats()).satisfied


# ── Malformed rules ──────────────────────────────────────────────────────────


def test_an_unknown_rule_type_is_inert_rather_than_fatal():
    """A typo in a seed row must not cost a student the submission that hit it."""
    outcome = evaluate_rule(
        {"type": "submisson_count", "threshold": 1}, stats(scored_submissions=9)
    )

    assert not outcome.satisfied
    assert not outcome.applicable


def test_a_rule_with_no_type_at_all_is_inert():
    assert not evaluate_rule({}, stats(scored_submissions=99)).satisfied


def test_a_non_numeric_threshold_falls_back_rather_than_raising():
    outcome = evaluate_rule(
        {"type": "submission_count", "threshold": "ten"}, stats(scored_submissions=4)
    )

    assert outcome.target == 1
    assert outcome.satisfied


def test_a_zero_threshold_is_raised_to_one():
    """Otherwise every student would hold it before ever submitting anything."""
    assert evaluate_rule({"type": "submission_count", "threshold": 0}, stats()).target == 1
    assert not evaluate_rule({"type": "submission_count", "threshold": 0}, stats()).satisfied


# ── Window derivation ────────────────────────────────────────────────────────


def test_the_recent_window_comes_from_the_catalogue():
    """Adding a five-in-a-row achievement must not leave the engine reading three."""
    catalogue = [
        {"type": "submission_count", "threshold": 10},
        {"type": "vocabulary_percentage_threshold", "threshold": 90, "consecutive": 3},
        {"type": "vocabulary_percentage_threshold", "threshold": 80, "consecutive": 5},
    ]

    assert required_recent_window(catalogue) == 5


def test_a_catalogue_with_no_consecutive_rules_still_asks_for_one_row():
    assert required_recent_window([{"type": "submission_count", "threshold": 3}]) == 1
