"""Leaderboard period windows."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.gamification.periods import (
    ALL_TIME_END,
    ALL_TIME_START,
    period_window,
    platform_today,
)
from app.models.enums import LeaderboardScope


@pytest.mark.parametrize(
    ("today", "expected_start", "expected_end"),
    [
        # A Monday is the start of its own week, not the end of the previous one.
        (date(2026, 8, 24), date(2026, 8, 24), date(2026, 8, 30)),
        (date(2026, 8, 27), date(2026, 8, 24), date(2026, 8, 30)),
        (date(2026, 8, 30), date(2026, 8, 24), date(2026, 8, 30)),
    ],
)
def test_the_weekly_window_is_the_iso_week(today, expected_start, expected_end):
    assert period_window(LeaderboardScope.WEEKLY, today=today) == (expected_start, expected_end)


@pytest.mark.parametrize(
    ("today", "expected_end"),
    [
        (date(2026, 2, 14), date(2026, 2, 28)),
        (date(2024, 2, 14), date(2024, 2, 29)),  # a leap year
        (date(2026, 12, 3), date(2026, 12, 31)),  # rolls over the year
        (date(2026, 4, 30), date(2026, 4, 30)),
    ],
)
def test_the_monthly_window_ends_on_the_last_day_of_the_month(today, expected_end):
    start, end = period_window(LeaderboardScope.MONTHLY, today=today)

    assert start == today.replace(day=1)
    assert end == expected_end


@pytest.mark.parametrize("scope", [LeaderboardScope.GLOBAL, LeaderboardScope.CLASS])
def test_all_time_scopes_use_the_sentinel_window(scope):
    """They still need a period, because it is part of a row's identity."""
    assert period_window(scope, today=date(2026, 8, 24)) == (ALL_TIME_START, ALL_TIME_END)


@pytest.mark.parametrize("timezone", ["UTC", "Asia/Dhaka", "Pacific/Kiritimati", "America/Lima"])
def test_the_platform_timezone_decides_which_day_it_is(timezone):
    """Not the server's locale, and not UTC unless that is what was configured.

    A cohort in Dhaka rolls over at Dhaka midnight; a streak measured in UTC
    would break for anyone practising in the evening.
    """
    assert platform_today(timezone) == datetime.now(UTC).astimezone(ZoneInfo(timezone)).date()
