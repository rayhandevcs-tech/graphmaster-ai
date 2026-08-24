"""Level curve."""

from __future__ import annotations

import pytest

from app.core.leveling import level_for_xp, level_progress, xp_required_for_level


class TestThresholds:
    @pytest.mark.parametrize(
        "level,expected",
        [(1, 0), (2, 50), (3, 150), (5, 500), (10, 2_250), (25, 15_000), (100, 247_500)],
    )
    def test_documented_thresholds(self, level: int, expected: int):
        # These values are published in docs/PROJECT_PLAN.md §5 and in the
        # gamification architecture; changing the curve silently would make
        # both wrong.
        assert xp_required_for_level(level) == expected

    def test_level_one_is_free(self):
        assert xp_required_for_level(1) == 0
        assert xp_required_for_level(0) == 0

    def test_thresholds_increase_monotonically(self):
        values = [xp_required_for_level(n) for n in range(1, 101)]
        assert values == sorted(values)
        assert len(set(values)) == len(values)


class TestLevelForXp:
    def test_exact_at_every_boundary(self):
        # An off-by-one here shows the student the wrong level right after a
        # level-up, which is the moment they are most likely to be looking.
        for level in range(1, 101):
            need = xp_required_for_level(level)
            assert level_for_xp(need) == level, f"at threshold for level {level}"
            if level > 1:
                assert level_for_xp(need - 1) == level - 1, f"just below level {level}"

    @pytest.mark.parametrize("xp", [0, -1, -10_000])
    def test_non_positive_xp_is_level_one(self, xp: int):
        assert level_for_xp(xp) == 1

    def test_capped_at_max_level(self):
        assert level_for_xp(10**9) == 100

    def test_custom_max_level_respected(self):
        assert level_for_xp(10**9, max_level=50) == 50


class TestLevelProgress:
    def test_mid_level_progress(self):
        # Level 9 spans 1,800 to 2,250.
        p = level_progress(2000)
        assert p.current_level == 9
        assert p.xp_into_level == 200
        assert p.xp_for_next_level == 450
        assert p.progress_percent == pytest.approx(44.44, abs=0.01)
        assert p.is_max_level is False

    def test_exactly_at_threshold_starts_new_level(self):
        p = level_progress(xp_required_for_level(10))
        assert p.current_level == 10
        assert p.xp_into_level == 0
        assert p.progress_percent == 0.0

    def test_max_level_reports_no_next(self):
        p = level_progress(10**6)
        assert p.current_level == 100
        assert p.is_max_level is True
        assert p.xp_for_next_level == 0
        assert p.progress_percent == 100.0

    def test_negative_xp_clamped(self):
        p = level_progress(-500)
        assert p.current_level == 1
        assert p.total_xp == 0

    def test_percent_always_in_range(self):
        for xp in (0, 1, 49, 50, 51, 2_249, 2_250, 100_000, 247_500, 999_999):
            assert 0.0 <= level_progress(xp).progress_percent <= 100.0


class TestTheCurveAgreesWithItself:
    def test_every_level_boundary_is_exact(self):
        """The level shown and the threshold published must be the same curve.

        `level_for_xp` inverts the threshold formula with a square root, and a
        float error of one part in a billion at a boundary would show a
        student level 6 while the progress bar said they needed one more point
        to reach it. The two corrective loops in `level_for_xp` exist for
        this; this is what proves they are doing their job.
        """
        for level in range(2, 101):
            threshold = xp_required_for_level(level)
            assert level_for_xp(threshold) == level, f"at exactly {threshold} XP"
            assert level_for_xp(threshold - 1) == level - 1, f"one XP short of level {level}"

    def test_it_never_reports_a_level_above_the_configured_maximum(self):
        assert level_for_xp(10_000_000, max_level=100) == 100
        assert level_for_xp(10_000_000, max_level=20) == 20
