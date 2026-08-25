"""The word-usage analyzer.

The property under test throughout is the one the specification names
directly: acceptable stylistic variation is never penalised. Everything this
analyzer produces is a suggestion, and the first test in the file is the one
that keeps it that way.
"""

from __future__ import annotations

import pytest

from app.assessment.analyzers.word_usage import WordUsageAnalyzer
from app.assessment.protocol import AnalyzerOutput
from app.core.config import get_settings
from app.models.enums import IssueCategory, IssueSeverity

pytestmark = pytest.mark.usefixtures("spacy_model")


@pytest.fixture
def analyzer() -> WordUsageAnalyzer:
    return WordUsageAnalyzer(get_settings())


def subtypes(output: AnalyzerOutput) -> set[str]:
    return {i.subtype for i in output.issues}


def issue_named(output: AnalyzerOutput, subtype: str):
    return next(i for i in output.issues if i.subtype == subtype)


#: The chart the strong answer describes. Passed wherever that answer is
#: analysed, as it is in production: its three series names are the subject,
#: and an analyzer that has not been told so would read naming them as
#: repetition.
RENEWABLES_CHART = {
    "labels": ["2010", "2014", "2018", "2022"],
    "datasets": [
        {"label": "Solar", "data": [5.0, 40.0, 200.0, 410.0]},
        {"label": "Hydroelectric", "data": [230.0, 240.0, 235.0, 250.0]},
        {"label": "Wind", "data": [15.0, 30.0, 60.0, 90.0]},
    ],
    "x_axis_label": "Year",
    "y_axis_label": "Generation",
    "unit": "gigawatt hours",
}

#: Long enough to clear the repetition threshold, and repetitive enough to
#: trip it. Both matter: the analyzer deliberately says nothing about a short
#: answer, so a short fixture would prove only that the guard works.
LONG_REPETITIVE = (
    "Overall the chart illustrates the pattern of sales across the period. "
    "Sales of the product rose in the first quarter of the year and the product "
    "then held steady. The product was the strongest performer and the product "
    "outsold every rival in the market. Later the product recovered again and "
    "the product finished the year in a stronger position than the product had "
    "started. The product remained ahead of every rival, and the product held "
    "that lead into the following year when the product was measured once more "
    "by the same team using the same method as before."
)


# ── The property that matters most ───────────────────────────────────────────


def test_nothing_this_analyzer_produces_is_ever_a_mistake(
    analyzer, assessment_context, weak_answer, strong_answer
):
    """Feature 5, asserted over everything it can find.

    Detecting genuinely *incorrect* word choice needs a model this platform
    does not have. Guessing at it would produce confident false positives, so
    this analyzer only ever offers preferences — and that has to be true of
    every issue it can emit, not just the ones a particular test happens to
    trigger.
    """
    texts = [weak_answer, strong_answer, LONG_REPETITIVE, "Sales went up a big amount, lots."]

    for text in texts:
        for issue in analyzer.run(assessment_context(text)).issues:
            assert issue.severity is IssueSeverity.INFO, issue.subtype
            assert issue.is_mistake is False
            assert issue.category is IssueCategory.WORD_USAGE


# ── Repetition ───────────────────────────────────────────────────────────────


class TestRepetition:
    def test_an_over_used_word_is_pointed_out(self, analyzer, assessment_context):
        output = analyzer.run(assessment_context(LONG_REPETITIVE))

        issue = issue_named(output, "repeated_word")
        assert "product" in issue.explanation

    def test_it_is_anchored_where_the_repetition_becomes_repetition(
        self, analyzer, assessment_context
    ):
        output = analyzer.run(assessment_context(LONG_REPETITIVE))
        issue = issue_named(output, "repeated_word")

        # The fourth use, not the first: the first three were fine, and
        # highlighting them tells the student the wrong thing about which word
        # to change.
        before = LONG_REPETITIVE[: issue.start].lower().count("product")
        assert before == 3
        assert LONG_REPETITIVE[issue.start : issue.end].lower() == "product"

    def test_the_target_vocabulary_is_never_called_repetitive(
        self, analyzer, assessment_context, term_factory
    ):
        # Using the vocabulary the exercise marks you on *is* the exercise.
        # Telling a student to vary it would undo the lesson.
        text = LONG_REPETITIVE.replace("product", "increase")
        targets = [term_factory("increase")]

        output = analyzer.run(assessment_context(text, targets=targets))

        assert "repeated_word" not in subtypes(output)

    def test_a_short_answer_is_not_judged_for_repetition(self, analyzer, assessment_context):
        # In sixty words, four uses of one word is the subject. In two hundred
        # it is a habit.
        text = "The product rose. The product fell. The product rose. The product held."

        assert "repeated_word" not in subtypes(analyzer.run(assessment_context(text)))


# ── Register ─────────────────────────────────────────────────────────────────


class TestRegister:
    def test_a_conversational_word_is_offered_an_academic_alternative(
        self, analyzer, assessment_context
    ):
        text = "There was a big rise in sales across the whole of the period shown."
        output = analyzer.run(assessment_context(text))

        issue = issue_named(output, "informal_register")
        assert issue.suggested_text == "substantial"
        assert text[issue.start : issue.end] == "big"

    def test_the_explanation_says_it_is_a_preference(self, analyzer, assessment_context):
        output = analyzer.run(
            assessment_context("There was a big rise in sales across the period shown.")
        )

        # The wording matters as much as the severity: a student reading
        # "preference, not a mistake" understands what to do with it.
        assert "not a mistake" in issue_named(output, "informal_register").explanation

    def test_academic_writing_is_left_alone(self, analyzer, assessment_context, strong_answer):
        assert "informal_register" not in subtypes(analyzer.run(assessment_context(strong_answer)))

    def test_a_superlative_comparison_is_correct_academic_writing(
        self, analyzer, assessment_context, strong_answer
    ):
        # "the smallest contributor" is how a comparison between series is
        # *correctly* expressed. Flagging it would penalise the structure the
        # exercise teaches — and it must not quietly cost a mark either.
        output = analyzer.run(assessment_context(strong_answer))

        assert "smallest" in strong_answer
        assert "informal_register" not in subtypes(output)
        assert output.metrics["informal_usages"] == 0.0

    def test_hedges_are_counted_but_not_flagged_one_by_one(self, analyzer, assessment_context):
        # "very" is legitimate English. It costs a little on the score and
        # earns no correction of its own — a highlight on every intensifier
        # would bury the findings that matter.
        text = "Sales were very high and really quite strong across the whole period shown."
        output = analyzer.run(assessment_context(text))

        assert output.metrics["hedges"] >= 2
        assert "informal_register" not in subtypes(output)


# ── Richness ─────────────────────────────────────────────────────────────────


class TestRichness:
    def test_a_narrow_answer_is_noted(self, analyzer, assessment_context):
        text = (
            "Sales rose and sales rose again and then sales rose once more before sales "
            "rose further and sales rose still further and afterwards sales rose again "
            "and sales rose and sales rose and sales rose to finish. Sales rose and "
            "sales rose and sales rose and sales rose once more, and after that sales "
            "rose and sales rose and sales rose right to the very end of the period."
        )

        assert "narrow_vocabulary_range" in subtypes(analyzer.run(assessment_context(text)))

    def test_a_varied_answer_is_not(self, analyzer, assessment_context, strong_answer):
        assert "narrow_vocabulary_range" not in subtypes(
            analyzer.run(assessment_context(strong_answer, chart_data=RENEWABLES_CHART))
        )

    def test_a_short_answer_is_not_judged_for_range(self, analyzer, assessment_context):
        assert "narrow_vocabulary_range" not in subtypes(
            analyzer.run(assessment_context("Sales rose. Sales rose. Sales rose."))
        )


# ── Score and metrics ────────────────────────────────────────────────────────


class TestScoring:
    def test_a_varied_answer_scores_above_a_repetitive_one(
        self, analyzer, assessment_context, strong_answer
    ):
        varied = analyzer.run(assessment_context(strong_answer, chart_data=RENEWABLES_CHART))
        narrow = analyzer.run(assessment_context(LONG_REPETITIVE))

        assert varied.score > narrow.score

    def test_repetition_reaches_the_score_and_not_only_the_issues(
        self, analyzer, assessment_context
    ):
        # A long answer can repeat one word eight times and still look varied
        # by distinct-lemma ratio, so richness alone cannot separate "a
        # description of one thing" from "a description that keeps saying the
        # same thing".
        output = analyzer.run(assessment_context(LONG_REPETITIVE))

        assert output.metrics["repetition_load"] > 0.1
        assert output.score < 100.0

    def test_naming_the_chart_s_own_series_is_not_repetition(
        self, analyzer, assessment_context, strong_answer
    ):
        # A chart of three renewable sources cannot be described without
        # naming them repeatedly. Without the chart the analyzer has no way to
        # know that, which is exactly why it is passed one.
        with_chart = analyzer.run(assessment_context(strong_answer, chart_data=RENEWABLES_CHART))
        without = analyzer.run(assessment_context(strong_answer))

        assert with_chart.metrics["repeated_lemmas"] < without.metrics["repeated_lemmas"]
        assert with_chart.score > without.score

    def test_conversational_language_costs_something_but_not_everything(
        self, analyzer, assessment_context, strong_answer
    ):
        casual = strong_answer.replace("considerably higher", "a big lot higher")

        clean_score = analyzer.run(assessment_context(strong_answer)).score
        casual_score = analyzer.run(assessment_context(casual)).score

        # Capped, so a rich answer with three casual words is not marked down
        # to a poor one.
        assert casual_score < clean_score
        assert casual_score > clean_score - 30

    def test_an_answer_with_no_content_words_is_not_scored(self, analyzer, assessment_context):
        output = analyzer.run(assessment_context("The and of the and of."))

        assert output.score is None
        assert output.metrics["content_words"] == 0.0

    def test_it_reports_the_measures_behind_its_score(
        self, analyzer, assessment_context, strong_answer
    ):
        metrics = analyzer.run(assessment_context(strong_answer)).metrics

        for key in ("content_words", "distinct_content_lemmas", "lexical_richness"):
            assert key in metrics
        assert 0.0 <= metrics["lexical_richness"] <= 1.0
