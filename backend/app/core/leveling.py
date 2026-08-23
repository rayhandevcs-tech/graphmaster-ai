"""Level curve.

Levels are derived deterministically from total XP:

    xp_required_to_reach(n) = 25 x (n - 1) x n

Quadratic rather than exponential. An exponential curve makes the first levels
trivial and everything past roughly level 20 unreachable within a semester;
this one keeps level 5 achievable in a first session while leaving the upper
range meaningful across a full course.

    Level   2 ->        50 XP
    Level   5 ->       500 XP
    Level  10 ->     2,250 XP
    Level  25 ->    15,000 XP
    Level 100 ->   247,500 XP
"""

from __future__ import annotations

from dataclasses import dataclass

LEVEL_COEFFICIENT = 25


def xp_required_for_level(level: int) -> int:
    """Cumulative XP needed to reach ``level``. Level 1 requires none."""
    if level <= 1:
        return 0
    return LEVEL_COEFFICIENT * (level - 1) * level


def level_for_xp(total_xp: int, *, max_level: int = 100) -> int:
    """The highest level fully paid for by ``total_xp``.

    Solved directly rather than by looping: for a curve this shape the closed
    form is exact, and a loop would run up to `max_level` times on every XP
    write and every profile read.

        xp = 25(n-1)n  ->  n = (1 + sqrt(1 + 4*xp/25)) / 2
    """
    if total_xp <= 0:
        return 1

    level = int((1 + (1 + 4 * total_xp / LEVEL_COEFFICIENT) ** 0.5) / 2)
    level = max(1, min(level, max_level))

    # Correct for float error at the boundaries rather than trusting sqrt: an
    # off-by-one here would show a student the wrong level after a level-up.
    while level < max_level and xp_required_for_level(level + 1) <= total_xp:
        level += 1
    while level > 1 and xp_required_for_level(level) > total_xp:
        level -= 1

    return level


@dataclass(frozen=True)
class LevelProgress:
    current_level: int
    total_xp: int
    xp_into_level: int
    xp_for_next_level: int
    progress_percent: float
    is_max_level: bool


def level_progress(total_xp: int, *, max_level: int = 100) -> LevelProgress:
    """Where ``total_xp`` sits within its current level."""
    total_xp = max(0, total_xp)
    level = level_for_xp(total_xp, max_level=max_level)

    floor_xp = xp_required_for_level(level)

    if level >= max_level:
        return LevelProgress(
            current_level=level,
            total_xp=total_xp,
            xp_into_level=total_xp - floor_xp,
            xp_for_next_level=0,
            progress_percent=100.0,
            is_max_level=True,
        )

    ceiling_xp = xp_required_for_level(level + 1)
    span = ceiling_xp - floor_xp
    into = total_xp - floor_xp

    return LevelProgress(
        current_level=level,
        total_xp=total_xp,
        xp_into_level=into,
        xp_for_next_level=span,
        progress_percent=round(into / span * 100, 2) if span else 100.0,
        is_max_level=False,
    )
