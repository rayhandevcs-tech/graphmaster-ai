"""Streak transitions.

The cases that matter are the awkward ones: the first ever submission, a second
on the same day, a missed day, and a clock that appears to have moved backwards.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.gamification.streaks import advance_streak

TODAY = date(2026, 8, 24)
YESTERDAY = TODAY - timedelta(days=1)


def advance(**overrides):
    kwargs = {
        "today": TODAY,
        "last_activity_date": None,
        "current_streak_days": 0,
        "longest_streak_days": 0,
    }
    return advance_streak(**(kwargs | overrides))


def test_a_first_submission_starts_the_streak_at_one():
    outcome = advance()

    assert outcome.current_streak_days == 1
    assert outcome.longest_streak_days == 1
    assert outcome.is_new_day
    # Nothing was continued — there was no streak to continue. This is what
    # keeps the daily bonus from paying out on a student's very first attempt.
    assert not outcome.continued


def test_practising_yesterday_extends_the_streak():
    outcome = advance(last_activity_date=YESTERDAY, current_streak_days=4, longest_streak_days=9)

    assert outcome.current_streak_days == 5
    assert outcome.continued
    assert outcome.is_new_day


def test_a_second_submission_the_same_day_changes_nothing():
    outcome = advance(last_activity_date=TODAY, current_streak_days=3, longest_streak_days=7)

    assert outcome.current_streak_days == 3
    assert outcome.longest_streak_days == 7
    assert not outcome.is_new_day
    assert not outcome.continued


@pytest.mark.parametrize("gap", [2, 3, 30, 400])
def test_a_missed_day_restarts_at_one_not_zero(gap):
    """The student is practising today; showing them a zero would be wrong."""
    outcome = advance(
        last_activity_date=TODAY - timedelta(days=gap),
        current_streak_days=12,
        longest_streak_days=12,
    )

    assert outcome.current_streak_days == 1
    assert not outcome.continued
    # The record survives the break. A profile that forgot a student's best
    # streak the moment they missed a day would be erasing an achievement.
    assert outcome.longest_streak_days == 12


def test_the_longest_streak_only_ever_grows():
    outcome = advance(last_activity_date=YESTERDAY, current_streak_days=9, longest_streak_days=9)

    assert outcome.current_streak_days == 10
    assert outcome.longest_streak_days == 10


def test_a_last_activity_date_in_the_future_does_not_reset_the_streak():
    """Reconfiguring the platform timezone can move the boundary backwards.

    Treating that as "already practised today" keeps a streak the student
    genuinely earned; treating it as a gap would silently destroy it.
    """
    outcome = advance(
        last_activity_date=TODAY + timedelta(days=1),
        current_streak_days=6,
        longest_streak_days=6,
    )

    assert outcome.current_streak_days == 6
    assert not outcome.is_new_day
    assert not outcome.continued
