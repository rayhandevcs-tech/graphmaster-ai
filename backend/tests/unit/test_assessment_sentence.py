"""The sentence analyzer: length, variety, readability and shape."""

from __future__ import annotations

import pytest

from app.assessment.analyzers.sentence import SentenceAnalyzer
from app.assessment.protocol import AnalyzerOutput
from app.assessment.text import flesch_reading_ease, paragraph_count, syllables
from app.core.config import get_settings
from app.models.enums import IssueCategory, IssueSeverity

pytestmark = pytest.mark.usefixtures("spacy_model")


@pytest.fixture
def analyzer() -> SentenceAnalyzer:
    return SentenceAnalyzer(get_settings())


def subtypes(output: AnalyzerOutput) -> set[str]:
    return {i.subtype for i in output.issues}


def issue_named(output: AnalyzerOutput, subtype: str):
    return next(i for i in output.issues if i.subtype == subtype)


# ── Answer length (Feature 3) ────────────────────────────────────────────────


class TestAnswerLength:
    def test_a_short_answer_is_flagged_with_the_target_band(self, analyzer, assessment_context):
        output = analyzer.run(assessment_context("The graph goes up. Then it goes down."))

        issue = issue_named(output, "answer_too_short")
        assert issue.severity is IssueSeverity.MEDIUM
        # The band comes from configuration, so the advice and the mark agree.
        settings = get_settings()
        assert str(settings.TARGET_WORD_COUNT_MIN) in issue.explanation
        assert str(settings.TARGET_WORD_COUNT_MAX) in issue.explanation

    def test_an_answer_in_the_band_is_not_flagged_for_length(
        self, analyzer, assessment_context, strong_answer
    ):
        output = analyzer.run(assessment_context(strong_answer))

        assert "answer_too_short" not in subtypes(output)
        assert "answer_too_long" not in subtypes(output)

    def test_a_very_long_answer_is_flagged_gently(self, analyzer, assessment_context):
        text = "Sales rose steadily in this particular quarter of the year. " * 40
        output = analyzer.run(assessment_context(text))

        issue = issue_named(output, "answer_too_long")
        # Writing too much is a lesser failure than writing two lines: the
        # student engaged with the task.
        assert issue.severity is IssueSeverity.LOW

    def test_a_length_issue_covers_the_whole_answer(self, analyzer, assessment_context):
        text = "The graph goes up. Then it goes down."
        output = analyzer.run(assessment_context(text))

        issue = issue_named(output, "answer_too_short")
        assert (issue.start, issue.end) == (0, len(text))


# ── Sentence-level findings (Feature 4) ──────────────────────────────────────


class TestSentences:
    def test_an_overlong_sentence_is_flagged_where_it_sits(self, analyzer, assessment_context):
        long_sentence = (
            "Overall the chart shows that sales of the three products rose steadily across "
            "the whole period although the rate of growth varied considerably between them "
            "and the gap between the strongest and the weakest widened noticeably towards "
            "the end of the period shown in the figure."
        )
        text = f"Overall, sales rose. {long_sentence}"
        output = analyzer.run(assessment_context(text))

        issue = issue_named(output, "overlong_sentence")
        assert issue.severity is IssueSeverity.LOW
        assert text[issue.start : issue.end].startswith("Overall the chart shows")

    def test_three_sentences_opening_the_same_way_are_flagged(self, analyzer, assessment_context):
        text = (
            "The graph shows visitor numbers. The graph shows a rise in 2020. "
            "The graph shows a fall afterwards. Numbers settled in the final year."
        )
        output = analyzer.run(assessment_context(text))

        issue = issue_named(output, "repeated_sentence_opening")
        # A preference about rhythm, not a mistake.
        assert issue.severity is IssueSeverity.INFO
        assert issue.is_mistake is False

    def test_two_sentences_opening_the_same_way_are_left_alone(self, analyzer, assessment_context):
        # "The graph shows… The figure for…" is ordinary writing. A third in a
        # row is the pattern a marker would circle.
        text = (
            "The graph shows visitor numbers. The graph shows a rise in 2020. "
            "Numbers then fell away sharply before settling in the final year."
        )

        assert "repeated_sentence_opening" not in subtypes(analyzer.run(assessment_context(text)))

    def test_uniform_sentence_lengths_are_reported_as_a_preference(
        self, analyzer, assessment_context
    ):
        text = (
            "Sales rose in March. Costs fell in April. Profit grew in May. "
            "Output held in June. Demand eased in July."
        )
        output = analyzer.run(assessment_context(text))

        assert "low_sentence_variety" in subtypes(output)
        assert issue_named(output, "low_sentence_variety").severity is IssueSeverity.INFO

    def test_a_missing_overview_is_a_real_finding(self, analyzer, assessment_context):
        text = (
            "Sales of the first product rose from 20 to 45 units between 2019 and 2022. "
            "The second product fell from 60 to 30 across the same four years."
        )
        output = analyzer.run(assessment_context(text))

        issue = issue_named(output, "missing_overview")
        # The single most-taught convention of graph description.
        assert issue.severity is IssueSeverity.MEDIUM
        assert text[issue.start : issue.end].startswith("Sales of the first product")

    def test_an_answer_with_an_overview_is_not_flagged(
        self, analyzer, assessment_context, strong_answer
    ):
        assert "missing_overview" not in subtypes(analyzer.run(assessment_context(strong_answer)))

    def test_a_long_single_paragraph_is_reported_as_a_preference(
        self, analyzer, assessment_context, strong_answer
    ):
        output = analyzer.run(assessment_context(strong_answer))

        assert "single_paragraph" in subtypes(output)
        assert issue_named(output, "single_paragraph").severity is IssueSeverity.INFO

    def test_a_broken_up_answer_is_not_flagged_for_paragraphs(
        self, analyzer, assessment_context, strong_answer
    ):
        halves = strong_answer.split(". ")
        split = ". ".join(halves[:4]) + ".\n\n" + ". ".join(halves[4:])

        assert "single_paragraph" not in subtypes(analyzer.run(assessment_context(split)))


# ── Metrics and score ────────────────────────────────────────────────────────


class TestMetrics:
    def test_it_reports_the_counts_the_specification_asks_for(
        self, analyzer, assessment_context, strong_answer
    ):
        metrics = analyzer.run(assessment_context(strong_answer)).metrics

        for key in ("word_count", "sentence_count", "paragraph_count", "mean_sentence_length"):
            assert key in metrics
        assert metrics["word_count"] > 100
        assert metrics["sentence_count"] > 5

    def test_every_issue_it_raises_is_a_sentence_issue(
        self, analyzer, assessment_context, weak_answer
    ):
        output = analyzer.run(assessment_context(weak_answer))

        assert {i.category for i in output.issues} == {IssueCategory.SENTENCE}

    def test_a_varied_answer_scores_better_than_a_monotonous_one(
        self, analyzer, assessment_context, strong_answer
    ):
        monotonous = "Sales rose in March. Costs fell in April. Profit grew in May. " * 6

        varied = analyzer.run(assessment_context(strong_answer))
        flat = analyzer.run(assessment_context(monotonous))

        assert varied.score > flat.score

    def test_text_with_no_sentences_is_not_scored(self, analyzer, assessment_context):
        output = analyzer.run(assessment_context("..."))

        # Scoring that zero would be a judgement about sentence quality where
        # there are no sentences.
        assert output.score is None
        assert output.metrics["sentence_count"] == 0.0


# ── The shared text measures ─────────────────────────────────────────────────


class TestTextMeasures:
    @pytest.mark.parametrize(
        ("word", "expected"),
        [
            ("the", 1),
            ("be", 1),
            ("make", 1),
            ("large", 1),
            ("gradually", 4),
            ("fluctuation", 4),
            ("a", 1),
        ],
    )
    def test_syllable_counts_are_about_right(self, word: str, expected: int):
        assert syllables(word) == expected

    @pytest.mark.parametrize(
        ("word", "expected"),
        [("increase", 2), ("period", 3), ("steadily", 3), ("considerably", 5), ("queue", 1)],
    )
    def test_it_handles_the_words_this_domain_actually_uses(self, word: str, expected: int):
        assert syllables(word) == expected

    @pytest.mark.parametrize(("word", "counted"), [("hydroelectric", 4), ("approximately", 6)])
    def test_its_known_limits_are_recorded_rather_than_hidden(self, word: str, counted: int):
        # Both are one out: "hydroelectric" splits across a morpheme boundary
        # the rules cannot see, and "approximately" keeps a silent "e" that the
        # trailing-"ly" hides. One syllable moves the reading-ease index by
        # about a point, which is inside the tolerance of a figure reported as
        # an indication rather than a grade. Pinned so a future change to the
        # heuristic is a visible decision.
        assert syllables(word) == counted

    def test_an_empty_word_has_no_syllables(self):
        assert syllables("") == 0
        assert syllables("'-") == 0

    def test_readability_is_higher_for_simpler_prose(self):
        simple = flesch_reading_ease(word_count=100, sentence_count=10, syllable_count=120)
        dense = flesch_reading_ease(word_count=100, sentence_count=3, syllable_count=250)

        assert simple > dense

    def test_readability_is_clamped_rather_than_negative(self):
        # The raw formula runs past both ends on unusual text, and a negative
        # "readability" reads as a bug rather than as very dense writing.
        assert flesch_reading_ease(100, 1, 400) == 0.0
        assert flesch_reading_ease(100, 100, 100) <= 100.0

    def test_readability_of_nothing_is_zero_rather_than_a_division_error(self):
        assert flesch_reading_ease(0, 0, 0) == 0.0

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("One block only.", 1),
            ("First block.\n\nSecond block.", 2),
            ("First.\r\n\r\nSecond.\r\n\r\nThird.", 3),
            ("Trailing whitespace.\n\n\n\n", 1),
        ],
    )
    def test_paragraphs_are_counted_from_the_student_s_own_text(self, text: str, expected: int):
        # Normalisation collapses whitespace runs, which erases the blank lines
        # that make a paragraph — so this measure must read the original.
        assert paragraph_count(text) == expected
