"""The spelling analyzer.

Most of these test what it does *not* flag. A spell checker that objects to a
student's own city, or to the vocabulary the exercise is marking them on,
teaches them to dismiss the whole panel — and a dismissed correction is worth
less than none at all.
"""

from __future__ import annotations

import pytest

from app.assessment.analyzers.spelling import SpellingAnalyzer, _edit_distance, _match_case
from app.assessment.protocol import AnalyzerOutput, AssessmentContext
from app.core.config import get_settings
from app.models.enums import AnalyzerStatus, IssueCategory, IssueSeverity

pytestmark = pytest.mark.usefixtures("spacy_model")

CHART = {
    "labels": ["2019", "2020", "2021", "2022"],
    "datasets": [{"label": "Chattogram", "data": [10.0, 20.0, 30.0, 40.0]}],
    "x_axis_label": "Year",
    "y_axis_label": "Visitors",
    "unit": "thousands",
}


@pytest.fixture
def analyzer() -> SpellingAnalyzer:
    return SpellingAnalyzer(get_settings())


def run(analyzer: SpellingAnalyzer, ctx: AssessmentContext) -> AnalyzerOutput:
    return analyzer.run(ctx)


def flagged(output: AnalyzerOutput) -> dict[str, str | None]:
    return {i.original_text: i.suggested_text for i in output.issues}


def shown(output: AnalyzerOutput) -> dict[str, str | None]:
    """Only what would survive the default confidence floor."""
    floor = get_settings().ASSESSMENT_ISSUE_CONFIDENCE_FLOOR
    return {i.original_text: i.suggested_text for i in output.issues if i.confidence >= floor}


# ── What it catches ──────────────────────────────────────────────────────────


class TestMisspellings:
    def test_it_finds_a_misspelling_and_offers_the_correction(self, analyzer, assessment_context):
        ctx = assessment_context("Visitor numbers rose gradualy across the whole period.")

        output = run(analyzer, ctx)

        assert flagged(output) == {"gradualy": "gradually"}
        issue = output.issues[0]
        assert issue.category is IssueCategory.SPELLING
        assert issue.subtype == "misspelling"
        assert issue.severity is IssueSeverity.MEDIUM

    def test_the_span_points_at_the_word_in_the_student_s_own_text(
        self, analyzer, assessment_context
    ):
        text = "Visitor numbers rose gradualy across the whole period."
        ctx = assessment_context(text)

        issue = run(analyzer, ctx).issues[0]

        # The parse runs over normalised text; an offset taken from it without
        # mapping back would land on the wrong word.
        assert text[issue.start : issue.end] == "gradualy"

    def test_offsets_survive_typographic_punctuation(self, analyzer, assessment_context):
        # Normalisation folds the curly apostrophe, which shifts every index
        # after it. This is the case that breaks a naive implementation.
        text = "The council’s report said numbers rose gradualy over the period."
        ctx = assessment_context(text)

        issue = run(analyzer, ctx).issues[0]

        assert text[issue.start : issue.end] == "gradualy"

    def test_it_finds_several_in_one_answer(self, analyzer, assessment_context):
        ctx = assessment_context(
            "The increase was very noticable and it was gradualy acheived over four years."
        )

        assert set(flagged(run(analyzer, ctx))) == {"noticable", "gradualy", "acheived"}

    def test_a_distant_correction_is_offered_less_confidently(self, analyzer, assessment_context):
        confident = run(analyzer, assessment_context("Numbers rose gradualy over time here."))
        distant = run(analyzer, assessment_context("Numbers rose acheived over time here."))

        assert confident.issues[0].severity is IssueSeverity.MEDIUM
        assert distant.issues[0].severity is IssueSeverity.LOW
        assert distant.issues[0].confidence < confident.issues[0].confidence

    def test_the_suggestion_keeps_the_student_s_capitalisation(self):
        # Replacing "Gradualy" with "gradually" at the start of a sentence is
        # a correction that introduces an error.
        assert _match_case("Gradualy", "gradually") == "Gradually"
        assert _match_case("GRADUALY", "gradually") == "GRADUALLY"
        assert _match_case("gradualy", "gradually") == "gradually"


# ── What it refuses to flag ──────────────────────────────────────────────────


class TestFalsePositives:
    def test_it_leaves_the_target_vocabulary_alone(
        self, analyzer, assessment_context, term_factory
    ):
        # "plateaued" is in the dictionary, but the lemmatiser mangles it and
        # the vocabulary library carries terms a general dictionary will not.
        targets = [term_factory("plateau", category="stability")]
        ctx = assessment_context(
            "Numbers plateaued after 2020 and then plateaued again in the final year.",
            targets=targets,
        )

        assert flagged(run(analyzer, ctx)) == {}

    def test_it_leaves_the_words_written_on_the_chart_alone(self, analyzer, assessment_context):
        ctx = assessment_context(
            "Chattogram recorded the highest number of visitors across the whole period.",
            chart_data=CHART,
        )

        assert flagged(run(analyzer, ctx)) == {}

    def test_a_place_name_the_chart_does_not_list_is_not_shown_to_the_student(
        self, analyzer, assessment_context
    ):
        # The one the exemptions cannot know about. Reported for the record at
        # a confidence the floor suppresses, rather than telling a student
        # their own city is a misspelling of something else.
        ctx = assessment_context(
            "Chattogram increased steadily. Sylhet fluctuated and then settled again.",
            chart_data=CHART,
        )

        output = run(analyzer, ctx)

        assert shown(output) == {}
        assert output.metrics["uncertain_count"] == 1.0

    def test_a_word_the_student_was_credited_for_is_never_a_misspelling(
        self, analyzer, assessment_context, term_factory
    ):
        targets = [term_factory("fluctuate", category="fluctuation")]
        ctx = assessment_context(
            "The figures fluctuated wildly before they settled down again.", targets=targets
        )

        assert flagged(run(analyzer, ctx)) == {}

    @pytest.mark.parametrize("word", ["GDP", "km", "yr", "CO2"])
    def test_short_words_and_abbreviations_are_not_checked(
        self, analyzer, assessment_context, word: str
    ):
        ctx = assessment_context(f"The figure for {word} rose steadily across the period.")

        assert flagged(run(analyzer, ctx)) == {}

    def test_numbers_and_urls_are_not_checked(self, analyzer, assessment_context):
        ctx = assessment_context(
            "The source was https://example.edu/data and the figure reached 4500 units."
        )

        assert flagged(run(analyzer, ctx)) == {}

    def test_an_unknown_word_the_tagger_calls_a_proper_noun_is_still_checked(
        self, analyzer, assessment_context
    ):
        # The trap this analyzer exists to avoid. spaCy falls back to PROPN for
        # any word it does not know — which is exactly what a misspelling is —
        # so trusting that tag would exempt every typo in the answer.
        ctx = assessment_context("Numbers rose gradualy over the four years shown.")
        token = next(t for t in ctx.doc if t.text == "gradualy")

        assert token.pos_ == "PROPN"
        assert flagged(run(analyzer, ctx)) == {"gradualy": "gradually"}


# ── Score and metrics ────────────────────────────────────────────────────────


class TestScoring:
    def test_a_clean_answer_scores_full_marks(self, analyzer, assessment_context, strong_answer):
        output = run(analyzer, assessment_context(strong_answer))

        assert output.score == 100.0
        assert output.metrics["misspelling_count"] == 0.0

    def test_misspellings_lower_the_score(self, analyzer, assessment_context):
        clean = run(analyzer, assessment_context("Numbers rose steadily over the whole period."))
        typos = run(analyzer, assessment_context("Numbers rose gradualy over the whole periodd."))

        assert typos.score < clean.score

    def test_an_uncertain_finding_does_not_lower_the_score(self, analyzer, assessment_context):
        # Saying "we are not confident enough to show this" and then marking
        # the student down for it is a contradiction.
        ctx = assessment_context(
            "Chattogram increased steadily. Sylhet fluctuated and then settled again.",
            chart_data=CHART,
        )

        output = run(analyzer, ctx)

        assert output.metrics["uncertain_count"] == 1.0
        assert output.score == 100.0

    def test_an_answer_with_no_checkable_words_is_not_scored_zero(
        self, analyzer, assessment_context
    ):
        # Numbers and abbreviations only. Reporting 0% would be a judgement
        # about spelling that was never tested.
        output = run(analyzer, assessment_context("GDP 2019 2020 2021 CO2 km yr."))

        assert output.score is None
        assert output.metrics["words_checked"] == 0.0

    def test_it_reports_what_it_exempted(self, analyzer, assessment_context, term_factory):
        ctx = assessment_context(
            "Chattogram numbers increased.",
            targets=[term_factory("increase")],
            chart_data=CHART,
        )

        assert run(analyzer, ctx).metrics["exempted_terms"] > 0


# ── Failure and absence ──────────────────────────────────────────────────────


class TestUnavailable:
    def test_a_missing_dictionary_is_unavailable_rather_than_a_failure(
        self, analyzer, assessment_context, monkeypatch
    ):
        from app.assessment.analyzers import spelling

        monkeypatch.setattr(spelling, "_checker", lambda: None)
        output = run(analyzer, assessment_context("Numbers rose gradualy over the period."))

        # A library that is not installed is a deployment fact, not a fault —
        # the same rule the OCR chain and the export writers follow.
        assert output.status is AnalyzerStatus.UNAVAILABLE
        assert output.issues == ()
        assert output.score is None
        assert output.detail is not None

    def test_warming_up_without_a_dictionary_does_not_raise(self, analyzer, monkeypatch):
        from app.assessment.analyzers import spelling

        monkeypatch.setattr(spelling, "_checker", lambda: None)
        analyzer.warm_up()  # a warm-up must never stop the server booting


# ── The edit-distance helper ─────────────────────────────────────────────────


class TestEditDistance:
    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ("gradualy", "gradually", 1),
            ("teh", "the", 2),
            ("cat", "cat", 0),
            ("noticable", "noticeable", 1),
        ],
    )
    def test_it_measures_the_edits(self, a: str, b: str, expected: int):
        assert _edit_distance(a, b) == expected

    def test_it_gives_up_past_the_limit_rather_than_finishing_the_matrix(self):
        # Only "one keystroke out" versus "a different word" matters, and the
        # exact distance beyond that is never read.
        assert _edit_distance("increase", "photosynthesis", limit=2) == 3

    def test_a_large_length_difference_short_circuits(self):
        assert _edit_distance("a", "abcdefghij", limit=2) == 3
