"""Leaderboard period windows and the platform's idea of "today".

Day boundaries are a product decision, not a technical one. A cohort whose
students roll over at different moments would see the streak counter and the
weekly board disagree with each other, so every date in the gamification
engine is derived from one configured timezone rather than from the server's
locale or the caller's browser.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.enums import LeaderboardScope

# The all-time scopes still have to name a period, because the uniqueness of a
# leaderboard row is (scope, class, period_start, user). These sentinels give
# them one without special-casing the column as nullable — which would have
# made the unique constraint stop working, since NULLs do not compare equal.
ALL_TIME_START = date(1970, 1, 1)
ALL_TIME_END = date(9999, 12, 31)


def platform_now(timezone: str) -> datetime:
    """The current moment in the configured platform timezone."""
    return datetime.now(ZoneInfo(timezone))


def platform_today(timezone: str) -> date:
    """The calendar day a submission arriving now belongs to."""
    return platform_now(timezone).date()


def period_window(scope: LeaderboardScope, *, today: date) -> tuple[date, date]:
    """The inclusive window a scope covers on ``today``.

    ``weekly`` is the ISO week — Monday to Sunday — rather than a rolling seven
    days: a rolling window drops a student's earliest submission at an
    unpredictable moment, so their rank falls with no visible cause.
    """
    if scope is LeaderboardScope.WEEKLY:
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)

    if scope is LeaderboardScope.MONTHLY:
        start = today.replace(day=1)
        # The last day of the month, found by stepping into the next month and
        # back a day; calendar.monthrange would do, but this needs no import
        # and handles December's year rollover in the same expression.
        next_month = (start + timedelta(days=32)).replace(day=1)
        return start, next_month - timedelta(days=1)

    return ALL_TIME_START, ALL_TIME_END
