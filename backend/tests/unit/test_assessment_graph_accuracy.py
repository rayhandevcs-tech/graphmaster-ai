"""The graph-accuracy analyzer.

The valuable finding is "you described a rise as a fall". The dangerous one is
the same sentence when the student was right — so most of these tests are about
the cases where the analyzer must reach no verdict at all.
"""

from __future__ import annotations

import pytest

from app.assessment.analyzers.graph_accuracy import GraphAccuracyAnalyzer
from app.assessment.protocol import AnalyzerOutput
from app.core.config import get_settings
from app.models.enums import ClaimType, ClaimVerdict, GraphType, IssueCategory, IssueSeverity

pytestmark = pytest.mark.usefixtures("spacy_model")

#: One rising series. Most beginner graphs look like this, and it is the case
#: where attribution is unambiguous.
SOLAR = {
    "labels": ["2019", "2020", "2021", "2022", "2023", "2024", "2025"],
    "datasets": [{"label": "Solar output (MWh)", "data": [120, 145, 190, 260, 255, 340, 410]}],
    "x_axis_label": "Year",
    "y_axis_label": "Energy generated",
    "unit": "MWh",
}

#: Three series: one steeply rising, one level, one gently rising. Solar
#: overtakes hydroelectric part-way through, which is what makes comparisons
#: interesting.
RENEWABLES = {
    "labels": ["2010", "2014", "2018", "2022"],
    "datasets": [
        {"label": "Solar", "data": [5, 40, 200, 410]},
        {"label": "Hydroelectric", "data": [230, 240, 235, 250]},
        {"label": "Wind", "data": [15, 30, 60, 90]},
    ],
    "x_axis_label": "Year",
    "y_axis_label": "Generation",
}


@pytest.fixture
def analyzer() -> GraphAccuracyAnalyzer:
    return GraphAccuracyAnalyzer(get_settings())


@pytest.fixture
def targets(term_factory):
    """The vocabulary a graph description is normally marked against."""
    return [
        term_factory("increase", category="increase"),
        term_factory("rise", category="increase"),
        term_factory("fall", category="decrease"),
        term_factory("decrease", category="decrease"),
        term_factory("fluctuate", category="fluctuation"),
        term_factory("stable", category="stability"),
        term_factory("peak", category="peak"),
        term_factory("lowest", category="lowest"),
        term_factory("higher than", category="comparison"),
        term_factory("lower than", category="comparison"),
    ]


def run(analyzer, assessment_context, text, targets, chart=SOLAR, graph_type=GraphType.LINE):
    return analyzer.run(
        assessment_context(text, targets=targets, chart_data=chart, graph_type=graph_type)
    )


def verdicts(output: AnalyzerOutput) -> list[ClaimVerdict]:
    return [c.verdict for c in output.claims]


# ── The finding that justifies the feature ───────────────────────────────────


class TestTrendContradiction:
    def test_a_rise_described_as_a_fall_is_flagged(self, analyzer, assessment_context, targets):
        output = run(
            analyzer,
            assessment_context,
            "Overall, solar output fell steadily across the whole of the period shown.",
            targets,
        )

        assert verdicts(output) == [ClaimVerdict.INCORRECT]
        issue = output.issues[0]
        assert issue.category is IssueCategory.GRAPH_ACCURACY
        assert issue.subtype == "incorrect_trend"
        # The first finding in the platform that changes what the writing
        # *means*: a student reporting the opposite trend has described a
        # different chart.
        assert issue.severity is IssueSeverity.HIGH

    def test_the_correction_says_what_the_chart_does(self, analyzer, assessment_context, targets):
        output = run(
            analyzer,
            assessment_context,
            "Overall, solar output fell steadily across the whole of the period shown.",
            targets,
        )

        explanation = output.issues[0].explanation
        assert "rises" in explanation
        assert "Solar output" in explanation
        # Phrased as what the chart shows, never as an accusation.
        assert "wrong" not in explanation.lower()

    def test_the_highlight_lands_on_the_word_the_student_wrote(
        self, analyzer, assessment_context, targets
    ):
        text = "Overall, solar output fell steadily across the whole of the period shown."
        output = run(analyzer, assessment_context, text, targets)

        issue = output.issues[0]
        assert text[issue.start : issue.end] == "fell"

    def test_a_correctly_described_rise_is_recorded_as_correct(
        self, analyzer, assessment_context, targets
    ):
        output = run(
            analyzer,
            assessment_context,
            "Overall, solar output increased steadily across the whole of the period shown.",
            targets,
        )

        assert verdicts(output) == [ClaimVerdict.CORRECT]
        assert output.issues == ()
        assert output.score == 100.0

    def test_calling_a_rising_series_stable_is_flagged(self, analyzer, assessment_context, targets):
        output = run(
            analyzer,
            assessment_context,
            "Solar output remained stable across the whole of the period shown here.",
            targets,
        )

        assert verdicts(output) == [ClaimVerdict.INCORRECT]

    def test_calling_a_level_series_a_rise_is_a_milder_finding(
        self, analyzer, assessment_context, targets
    ):
        output = run(
            analyzer,
            assessment_context,
            "Hydroelectric output increased sharply throughout the whole of the period.",
            targets,
            chart=RENEWABLES,
        )

        # Wrong, but not an inversion: there is less to see on a level line.
        assert output.issues[0].severity is IssueSeverity.MEDIUM


class TestFluctuation:
    def test_a_series_that_reverses_repeatedly_supports_the_claim(
        self, analyzer, assessment_context, targets
    ):
        wobbly = {
            "labels": ["a", "b", "c", "d", "e", "f"],
            "datasets": [{"label": "Output", "data": [100, 180, 110, 190, 120, 200]}],
        }
        output = run(
            analyzer,
            assessment_context,
            "The figures fluctuated considerably over the whole of the period shown.",
            targets,
            chart=wobbly,
        )

        assert verdicts(output) == [ClaimVerdict.CORRECT]

    def test_a_straight_line_described_as_fluctuating_is_flagged(
        self, analyzer, assessment_context, targets
    ):
        straight = {
            "labels": ["a", "b", "c", "d"],
            "datasets": [{"label": "Output", "data": [10, 20, 30, 40]}],
        }
        output = run(
            analyzer,
            assessment_context,
            "The figures fluctuated considerably over the whole of the period shown.",
            targets,
            chart=straight,
        )

        assert verdicts(output) == [ClaimVerdict.INCORRECT]

    def test_a_single_turn_is_left_unjudged(self, analyzer, assessment_context, targets):
        # A rise then a fall is a shape with its own vocabulary, and calling
        # it fluctuation is neither clearly right nor clearly wrong.
        humped = {
            "labels": ["a", "b", "c", "d", "e"],
            "datasets": [{"label": "Output", "data": [100, 150, 200, 150, 100]}],
        }
        output = run(
            analyzer,
            assessment_context,
            "The figures fluctuated considerably over the whole of the period shown.",
            targets,
            chart=humped,
        )

        assert verdicts(output) == [ClaimVerdict.UNVERIFIED]
        assert output.issues == ()


# ── Peaks and troughs ────────────────────────────────────────────────────────


class TestExtremes:
    def test_naming_the_wrong_year_for_the_peak_is_flagged(
        self, analyzer, assessment_context, targets
    ):
        output = run(
            analyzer,
            assessment_context,
            "Solar output reached its peak in 2020 before it levelled off again.",
            targets,
        )

        assert verdicts(output) == [ClaimVerdict.INCORRECT]
        assert output.issues[0].subtype == "incorrect_peak"
        assert "2025" in output.issues[0].explanation

    def test_naming_the_right_year_is_recorded_as_correct(
        self, analyzer, assessment_context, targets
    ):
        output = run(
            analyzer,
            assessment_context,
            "Solar output reached its peak in 2025 after climbing for several years.",
            targets,
        )

        assert verdicts(output) == [ClaimVerdict.CORRECT]

    def test_a_peak_with_no_year_named_is_left_unjudged(
        self, analyzer, assessment_context, targets
    ):
        # "Numbers peaked" is true of every series that has a maximum, which
        # is all of them.
        output = run(
            analyzer,
            assessment_context,
            "Solar output reached a peak before settling down again in the later years.",
            targets,
        )

        assert verdicts(output) == [ClaimVerdict.UNVERIFIED]

    def test_a_range_of_years_is_left_unjudged(self, analyzer, assessment_context, targets):
        # "Between 2019 and 2022 it peaked" describes a window, not a position.
        output = run(
            analyzer,
            assessment_context,
            "Between 2019 and 2022 solar output reached its peak and then held there.",
            targets,
        )

        assert verdicts(output) == [ClaimVerdict.UNVERIFIED]


# ── Comparisons ──────────────────────────────────────────────────────────────


class TestComparisons:
    def test_a_comparison_the_right_way_round_is_correct(
        self, analyzer, assessment_context, targets
    ):
        output = run(
            analyzer,
            assessment_context,
            "Hydroelectric was higher than wind throughout the whole of the period shown.",
            targets,
            chart=RENEWABLES,
        )

        assert verdicts(output) == [ClaimVerdict.CORRECT]

    def test_a_comparison_the_wrong_way_round_is_flagged(
        self, analyzer, assessment_context, targets
    ):
        output = run(
            analyzer,
            assessment_context,
            "Wind was higher than hydroelectric throughout the whole of the period shown.",
            targets,
            chart=RENEWABLES,
        )

        assert verdicts(output) == [ClaimVerdict.INCORRECT]
        assert output.issues[0].severity is IssueSeverity.HIGH
        assert "Hydroelectric is the higher" in output.issues[0].explanation

    def test_lower_than_is_judged_the_other_way(self, analyzer, assessment_context, targets):
        right = run(
            analyzer,
            assessment_context,
            "Wind was lower than hydroelectric throughout the whole of the period shown.",
            targets,
            chart=RENEWABLES,
        )
        wrong = run(
            analyzer,
            assessment_context,
            "Hydroelectric was lower than wind throughout the whole of the period shown.",
            targets,
            chart=RENEWABLES,
        )

        assert verdicts(right) == [ClaimVerdict.CORRECT]
        assert verdicts(wrong) == [ClaimVerdict.INCORRECT]

    def test_series_that_cross_are_left_unjudged(self, analyzer, assessment_context, targets):
        # Solar overtakes hydroelectric part-way through, so the claim depends
        # on a period the student may not have named.
        output = run(
            analyzer,
            assessment_context,
            "Solar was higher than hydroelectric throughout the whole of the period shown.",
            targets,
            chart=RENEWABLES,
        )

        assert verdicts(output) == [ClaimVerdict.UNVERIFIED]
        assert "cross" in output.claims[0].actual

    def test_a_comparison_naming_one_series_is_left_unjudged(
        self, analyzer, assessment_context, targets
    ):
        output = run(
            analyzer,
            assessment_context,
            "Solar was higher than it had been at the start of the period shown here.",
            targets,
            chart=RENEWABLES,
        )

        assert verdicts(output) == [ClaimVerdict.UNVERIFIED]


# ── The refusals ─────────────────────────────────────────────────────────────


class TestRefusals:
    def test_two_series_in_one_sentence_make_a_trend_claim_unattributable(
        self, analyzer, assessment_context, targets
    ):
        # Which one "increased" describes is a guess, and a guess is not worth
        # telling a student they misread their chart.
        output = run(
            analyzer,
            assessment_context,
            "Solar and wind both increased over the period that the chart shows.",
            targets,
            chart=RENEWABLES,
        )

        assert verdicts(output) == [ClaimVerdict.UNVERIFIED]
        assert output.claims[0].series_label is None

    def test_a_trend_claim_about_a_pie_chart_is_not_judged(
        self, analyzer, assessment_context, targets
    ):
        output = run(
            analyzer,
            assessment_context,
            "The figure increased sharply across the whole of the period shown here.",
            targets,
            chart=SOLAR,
            graph_type=GraphType.PIE,
        )

        assert verdicts(output) == [ClaimVerdict.UNVERIFIED]
        assert "ordered axis" in output.claims[0].actual

    def test_a_bar_chart_is_treated_the_same_way(self, analyzer, assessment_context, targets):
        # A bar chart's categories may be in any order.
        output = run(
            analyzer,
            assessment_context,
            "The figure increased sharply across the whole of the period shown here.",
            targets,
            chart=SOLAR,
            graph_type=GraphType.BAR,
        )

        assert verdicts(output) == [ClaimVerdict.UNVERIFIED]

    def test_no_chart_at_all_is_not_a_wrong_reading(self, analyzer, assessment_context, targets):
        output = run(
            analyzer,
            assessment_context,
            "Solar output fell steadily across the whole of the period shown here.",
            targets,
            chart=None,
        )

        assert output.claims == ()
        assert output.score is None
        assert output.issues == ()

    def test_vocabulary_that_makes_no_claim_produces_none(
        self, analyzer, assessment_context, term_factory
    ):
        # A term from a category with nothing to check against — the analyzer
        # should not invent a claim for every word the detector found.
        output = run(
            analyzer,
            assessment_context,
            "The graph illustrates the data clearly across the whole of the period.",
            [term_factory("illustrate", category="description")],
        )

        assert output.claims == ()


# ── Scoring ──────────────────────────────────────────────────────────────────


class TestScoring:
    def test_the_score_is_the_share_of_checkable_claims_that_were_right(
        self, analyzer, assessment_context, targets
    ):
        text = (
            "Overall, solar output increased steadily. It reached its peak in 2020. "
            "Output rose again towards the end of the period covered here."
        )
        output = run(analyzer, assessment_context, text, targets)

        assert output.metrics["claims_verified"] == 3.0
        assert output.metrics["claims_correct"] == 2.0
        assert output.score == pytest.approx(66.67, abs=0.01)

    def test_an_answer_with_nothing_checkable_is_not_scored_zero(
        self, analyzer, assessment_context, targets
    ):
        # A reading the engine could not resolve is not a wrong reading.
        output = run(
            analyzer,
            assessment_context,
            "Solar output reached a peak before settling down again in the later years.",
            targets,
        )

        assert output.score is None
        assert output.metrics["claims_unverified"] == 1.0

    def test_correct_claims_are_kept_as_well_as_incorrect_ones(
        self, analyzer, assessment_context, targets
    ):
        # "You read three trends and got two right" is the educational figure,
        # and it cannot be recovered from the errors alone.
        text = "Overall, solar output increased steadily. It reached its peak in 2020."
        output = run(analyzer, assessment_context, text, targets)

        assert len(output.claims) == 2
        assert {c.verdict for c in output.claims} == {
            ClaimVerdict.CORRECT,
            ClaimVerdict.INCORRECT,
        }

    def test_every_claim_records_where_it_was_made(self, analyzer, assessment_context, targets):
        text = "Overall, solar output increased steadily across the period shown here."
        output = run(analyzer, assessment_context, text, targets)

        claim = output.claims[0]
        assert text[claim.start : claim.end] == "increased"
        assert claim.claim_type is ClaimType.TREND

    def test_an_unverified_claim_never_names_a_series(self, analyzer, assessment_context, targets):
        # Recording it as unattributed *and* unverified would make the accuracy
        # figure unreadable.
        output = run(
            analyzer,
            assessment_context,
            "Solar and wind both increased over the period that the chart shows.",
            targets,
            chart=RENEWABLES,
        )

        assert all(c.series_label is None for c in output.claims if not c.is_verified)


# ── The claim value itself ───────────────────────────────────────────────────


class TestClaimModel:
    def test_an_inverted_span_is_refused(self):
        from app.assessment.claims import GraphClaim

        with pytest.raises(ValueError, match="half-open"):
            GraphClaim(
                claim_type=ClaimType.TREND,
                verdict=ClaimVerdict.CORRECT,
                claimed="rose",
                actual="increase",
                series_label="Solar",
                start=40,
                end=12,
            )

    def test_confidence_outside_the_scale_is_refused(self):
        from app.assessment.claims import GraphClaim

        with pytest.raises(ValueError, match="confidence"):
            GraphClaim(
                claim_type=ClaimType.TREND,
                verdict=ClaimVerdict.CORRECT,
                claimed="rose",
                actual="increase",
                series_label="Solar",
                start=0,
                end=4,
                confidence=1.5,
            )

    def test_an_unverified_claim_cannot_name_a_series(self):
        from app.assessment.claims import GraphClaim

        # A claim that resolved to a series is one the engine could judge.
        # Recording it as unverified *and* attributed would make the accuracy
        # figure unreadable.
        with pytest.raises(ValueError, match="unverified"):
            GraphClaim(
                claim_type=ClaimType.TREND,
                verdict=ClaimVerdict.UNVERIFIED,
                claimed="rose",
                actual="could not resolve",
                series_label="Solar",
                start=0,
                end=4,
            )

    def test_a_correct_claim_reports_itself_as_verified_and_correct(self):
        from app.assessment.claims import GraphClaim

        claim = GraphClaim(
            claim_type=ClaimType.TREND,
            verdict=ClaimVerdict.CORRECT,
            claimed="rose",
            actual="increase",
            series_label="Solar",
            start=0,
            end=4,
        )

        assert claim.is_verified and claim.is_correct

    def test_an_incorrect_claim_is_verified_but_not_correct(self):
        from app.assessment.claims import GraphClaim

        claim = GraphClaim(
            claim_type=ClaimType.TREND,
            verdict=ClaimVerdict.INCORRECT,
            claimed="fell",
            actual="increase",
            series_label="Solar",
            start=0,
            end=4,
        )

        assert claim.is_verified and not claim.is_correct

    def test_it_serialises_to_the_fields_the_row_stores(self):
        from app.assessment.claims import GraphClaim

        payload = GraphClaim(
            claim_type=ClaimType.PEAK,
            verdict=ClaimVerdict.CORRECT,
            claimed="peak",
            actual="2025",
            series_label="Solar",
            start=10,
            end=14,
            confidence=0.9,
        ).to_dict()

        assert set(payload) == {
            "claim_type",
            "verdict",
            "claimed",
            "actual",
            "series_label",
            "start",
            "end",
            "confidence",
        }


class TestDirectionlessComparison:
    def test_a_comparison_with_no_direction_is_left_unjudged(
        self, analyzer, assessment_context, term_factory
    ):
        # "Compared to" says two things are being compared, not which is
        # greater. Guessing a direction here would invent the claim.
        output = run(
            analyzer,
            assessment_context,
            "Solar can be compared to wind across the whole of the period shown here.",
            [term_factory("compared to", category="comparison")],
            chart=RENEWABLES,
        )

        assert verdicts(output) == [ClaimVerdict.UNVERIFIED]
        assert "direction" in output.claims[0].actual

    def test_a_position_outside_every_sentence_resolves_to_none(self):
        from app.assessment.analyzers.graph_accuracy import _sentence_containing

        # Defensive: every match the detector reports sits inside a sentence.
        # If the sentence map and the offset map ever disagree, the claim is
        # dropped rather than attributed to the wrong sentence.
        assert _sentence_containing([], 12) is None
