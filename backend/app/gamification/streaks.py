"""Practice-streak transitions.

Pure arithmetic over dates, kept separate from the service so the awkward cases
— the first ever submission, a second submission on the same day, a missed day,
a clock that appears to move backwards — are testable without writing a row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class StreakOutcome:
    current_streak_days: int
    longest_streak_days: int
    is_new_day: bool
    """Whether this submission is the first of its calendar day."""
    continued: bool
    """Whether it extended a streak that was already running."""


def advance_streak(
    *,
    today: date,
    last_activity_date: date | None,
    current_streak_days: int,
    longest_streak_days: int,
) -> StreakOutcome:
    """Apply one qualifying submission to a student's streak counters.

    Four cases, and the third is the one worth stating plainly:

    * **No history** — the streak starts at 1.
    * **Already practised today** — nothing changes. The counters are per day,
      so a second submission neither extends nor resets them.
    * **Practised yesterday** — the streak extends.
    * **A day was missed** — the streak restarts at 1, not at 0. The student
      *is* practising today, and showing them a zero on the day they came back
      would be both wrong and discouraging.

    ``last_activity_date`` in the future is treated as "already practised
    today". It should be unreachable, but a timezone reconfiguration can move
    the boundary backwards over rows already written, and the alternative —
    silently resetting a streak the student earned — is the worse failure.
    """
    if last_activity_date is None:
        streak = 1
        is_new_day = True
        continued = False
    elif last_activity_date >= today:
        streak = max(current_streak_days, 1)
        is_new_day = False
        continued = False
    elif last_activity_date == today - timedelta(days=1):
        streak = max(current_streak_days, 0) + 1
        is_new_day = True
        continued = True
    else:
        streak = 1
        is_new_day = True
        continued = False

    return StreakOutcome(
        current_streak_days=streak,
        longest_streak_days=max(longest_streak_days, streak),
        is_new_day=is_new_day,
        continued=continued,
    )
