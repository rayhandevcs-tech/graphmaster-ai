"""Fact derivation from `chart_data`.

Pure arithmetic over the stored chart — no language model, no student writing.
The thresholds here decide whether a student's reading is contradicted, so most
of these tests are about the boundary between "a trend" and "noise".
"""

from __future__ import annotations

import pytest

from app.assessment.chart import STABLE_BAND, derive
from app.models.enums import GraphType


def chart(*series: tuple[str, list[float | None]], labels: list[str] | None = None) -> dict:
    points = labels or [str(2000 + i) for i in range(len(series[0][1]))]
    return {
        "labels": points,
        "datasets": [{"label": name, "data": values} for name, values in series],
    }


def only(chart_data: dict, graph_type: GraphType = GraphType.LINE):
    facts = derive(chart_data, graph_type)
    assert facts is not None
    return facts.series[0]


# ── Direction ────────────────────────────────────────────────────────────────


class TestDirection:
    def test_a_climbing_series_rises(self):
        series = only(chart(("Solar", [120, 145, 190, 260, 340, 410])))

        assert series.rises and not series.falls and not series.is_stable
        assert series.direction == "increase"

    def test_a_descending_series_falls(self):
        series = only(chart(("Coal", [410, 340, 260, 190, 145, 120])))

        assert series.falls and not series.rises
        assert series.direction == "decrease"

    def test_a_nearly_level_series_is_stable(self):
        # The case that broke the first implementation. These readings span
        # only 20, so measuring net change against the *range* made a net rise
        # of 20 look like 100% movement — the flatter the line, the more
        # confidently it was called a trend.
        series = only(chart(("Hydroelectric", [230, 240, 235, 250])))

        assert series.is_stable
        assert not series.rises
        assert series.direction == "stability"

    def test_movement_is_measured_against_the_typical_level(self):
        flat = only(chart(("Flat", [230, 240, 235, 250])))
        steep = only(chart(("Steep", [5, 40, 200, 410])))

        assert flat.movement < STABLE_BAND
        assert steep.movement > 1.0

    def test_a_completely_flat_series_is_stable_rather_than_a_division_error(self):
        series = only(chart(("Flat", [100, 100, 100, 100])))

        assert series.movement == 0.0
        assert series.is_stable

    def test_a_series_at_zero_throughout_does_not_divide_by_zero(self):
        series = only(chart(("Nothing", [0, 0, 0, 0])))

        assert series.movement == 0.0
        assert series.is_stable


class TestFluctuation:
    def test_a_series_that_keeps_changing_its_mind_fluctuates(self):
        series = only(chart(("Wobbly", [100, 180, 110, 190, 120, 200])))

        assert series.fluctuates
        assert series.turning_points >= 2

    def test_a_single_peak_is_not_fluctuation(self):
        # A rise then a fall is a shape with its own vocabulary. Genuine
        # fluctuation is the pattern that keeps reversing.
        series = only(chart(("Humped", [100, 150, 200, 150, 100])))

        assert series.turning_points == 1
        assert not series.fluctuates

    def test_a_monotonic_series_has_no_turning_points(self):
        assert only(chart(("Up", [1, 2, 3, 4, 5]))).turning_points == 0

    def test_tiny_wobble_is_not_a_turning_point(self):
        # Without the noise threshold, rounding in the numbers a teacher typed
        # would read as fluctuation.
        series = only(chart(("Almost flat", [100, 100.4, 100.1, 100.5, 100.2, 200])))

        assert series.turning_points == 0


# ── Extremes ─────────────────────────────────────────────────────────────────


class TestExtremes:
    def test_it_finds_the_peak_and_the_trough_by_label(self):
        series = only(
            chart(("Solar", [120, 410, 190, 90]), labels=["2019", "2020", "2021", "2022"])
        )

        assert series.peak_label == "2020"
        assert series.trough_label == "2022"

    def test_the_first_of_two_equal_maxima_is_the_peak(self):
        # Arbitrary but deterministic: two identical high points make "when did
        # it peak" a question with two answers, and the claim checker treats
        # naming either as unverifiable rather than wrong.
        series = only(chart(("Twin", [10, 50, 20, 50]), labels=["a", "b", "c", "d"]))

        assert series.peak_label == "b"


# ── Missing and malformed data ───────────────────────────────────────────────


class TestMissingData:
    def test_a_gap_is_dropped_rather_than_read_as_zero(self):
        # Chart.js renders null as a gap. Reading it as zero would invent a
        # catastrophic fall the student is then contradicted for not describing.
        series = only(chart(("Patchy", [100, None, 120, 140])))

        assert series.values == (100.0, 120.0, 140.0)
        assert series.minimum == 100.0

    def test_a_series_of_one_reading_carries_no_trend(self):
        assert derive(chart(("Single", [42])), GraphType.LINE) is None

    def test_a_chart_with_no_labels_yields_nothing(self):
        assert derive({"labels": [], "datasets": [{"label": "x", "data": [1, 2]}]}, None) is None

    def test_a_chart_with_no_datasets_yields_nothing(self):
        assert derive({"labels": ["a", "b"], "datasets": []}, None) is None

    def test_no_chart_at_all_yields_nothing(self):
        assert derive(None, GraphType.LINE) is None

    def test_a_dataset_whose_data_is_not_a_list_is_skipped(self):
        assert (
            derive({"labels": ["a", "b"], "datasets": [{"label": "x", "data": "12"}]}, None) is None
        )

    def test_booleans_are_not_readings(self):
        # `isinstance(True, int)` is true in Python, and a chart carrying
        # booleans is malformed rather than a series of ones and zeros.
        assert derive(chart(("Odd", [True, False, True])), GraphType.LINE) is None


# ── Series identity ──────────────────────────────────────────────────────────


class TestDistinctiveWords:
    def test_a_series_is_identified_by_the_words_only_it_uses(self):
        facts = derive(chart(("Solar output", [1, 2]), ("Wind output", [3, 4])), GraphType.LINE)
        assert facts is not None

        solar, wind = facts.series
        # "output" is shared, so it identifies neither.
        assert solar.distinctive_words == {"solar"}
        assert wind.distinctive_words == {"wind"}

    def test_generic_words_never_identify_a_series(self):
        facts = derive(chart(("Total number", [1, 2]), ("Solar", [3, 4])), GraphType.LINE)
        assert facts is not None

        assert facts.series[0].distinctive_words == frozenset()

    def test_two_series_with_the_same_label_identify_nothing(self):
        facts = derive(chart(("Sales", [1, 2]), ("Sales", [3, 4])), GraphType.LINE)
        assert facts is not None

        assert all(s.distinctive_words == frozenset() for s in facts.series)

    def test_a_lone_series_needs_no_distinguishing(self):
        facts = derive(chart(("Solar output", [1, 2])), GraphType.LINE)
        assert facts is not None

        assert facts.single_series is facts.series[0]

    def test_a_chart_with_several_series_has_no_single_series(self):
        facts = derive(chart(("A", [1, 2]), ("B", [3, 4])), GraphType.LINE)
        assert facts is not None

        assert facts.single_series is None


# ── Comparing two series ─────────────────────────────────────────────────────


class TestDominance:
    def test_one_series_above_the_other_throughout_is_dominant(self):
        facts = derive(chart(("High", [230, 240, 250]), ("Low", [15, 30, 60])), GraphType.LINE)
        assert facts is not None
        high, low = facts.series

        assert facts.dominant(high, low) is high
        assert facts.dominant(low, high) is high

    def test_crossing_series_have_no_dominant_one(self):
        # The claim then depends on a period the student may not have named.
        facts = derive(chart(("Solar", [5, 400]), ("Hydro", [230, 250])), GraphType.LINE)
        assert facts is not None

        assert facts.dominant(*facts.series) is None

    def test_touching_series_have_no_dominant_one(self):
        # Equal at one reading is not "above throughout".
        facts = derive(chart(("A", [10, 20, 30]), ("B", [5, 20, 25])), GraphType.LINE)
        assert facts is not None

        assert facts.dominant(*facts.series) is None

    def test_series_of_different_lengths_are_not_compared(self):
        facts = derive(
            {
                "labels": ["a", "b", "c"],
                "datasets": [
                    {"label": "Long", "data": [1, 2, 3]},
                    {"label": "Short", "data": [9, 9]},
                ],
            },
            GraphType.LINE,
        )
        assert facts is not None

        # Comparing their means would answer a different question.
        assert facts.dominant(*facts.series) is None


# ── Chart types ──────────────────────────────────────────────────────────────


class TestChartTypes:
    @pytest.mark.parametrize("graph_type", [GraphType.LINE, GraphType.AREA])
    def test_an_ordered_axis_supports_trend_claims(self, graph_type: GraphType):
        facts = derive(chart(("A", [1, 2, 3])), graph_type)
        assert facts is not None
        assert facts.is_sequential

    @pytest.mark.parametrize("graph_type", [GraphType.PIE, GraphType.BAR])
    def test_an_unordered_axis_does_not(self, graph_type: GraphType):
        # A pie chart is one snapshot; a bar chart's categories may be in any
        # order. "Sales rose" about either is not a claim about movement.
        facts = derive(chart(("A", [1, 2, 3])), graph_type)
        assert facts is not None
        assert not facts.is_sequential

    def test_an_unknown_type_is_treated_as_unordered(self):
        facts = derive(chart(("A", [1, 2, 3])), None)
        assert facts is not None
        assert not facts.is_sequential
