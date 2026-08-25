"""Analyzer feature flags and staged rollout.

An analyzer moves ``dark`` → ``teacher`` → ``student`` as confidence in its
false-positive rate grows, and back the moment it does not — without a
redeploy. These tests cover the two halves of that: reading the configuration,
and the filter that decides what each audience is handed.
"""

from __future__ import annotations

import pytest

from app.assessment.issues import AssessmentIssue
from app.assessment.protocol import UNAVAILABLE, Analyzer, AnalyzerOutput, AssessmentContext
from app.assessment.supervisor import run_analyzers
from app.core.config import get_settings
from app.models.enums import AnalyzerAudience, IssueCategory, IssueSeverity


def issue(start: int, subtype: str, source: str = "unknown") -> AssessmentIssue:
    return AssessmentIssue(
        category=IssueCategory.SPELLING,
        subtype=subtype,
        severity=IssueSeverity.MEDIUM,
        original_text="teh",
        explanation="Explanation.",
        start=start,
        end=start + 3,
        source=source,
    )


class Fake:
    def __init__(self, name: str, output: AnalyzerOutput) -> None:
        self.name = name
        self._output = output

    def run(self, ctx: AssessmentContext) -> AnalyzerOutput:
        return self._output


@pytest.fixture
def context(assessment_context):
    pytest.importorskip("spacy")
    from app.nlp.pipeline import is_available

    if not is_available():
        pytest.skip("spaCy model not installed")
    return assessment_context("Sales rose steadily across the whole of the period.")


# ── Reading the configuration ────────────────────────────────────────────────


class TestConfiguration:
    def test_an_unlisted_analyzer_is_shown_to_students(self):
        # The default is the finished state. A rollout is a temporary
        # restriction, so it is the restriction that has to be spelled out.
        assert get_settings().analyzer_audience("spelling") is AnalyzerAudience.STUDENT

    def test_a_dark_analyzer_is_shown_to_nobody(self):
        settings = get_settings().model_copy(update={"ASSESSMENT_DARK_ANALYZERS": "spelling"})

        assert settings.analyzer_audience("spelling") is AnalyzerAudience.DARK

    def test_a_teacher_only_analyzer_is_withheld_from_students(self):
        settings = get_settings().model_copy(
            update={"ASSESSMENT_TEACHER_ONLY_ANALYZERS": "word_usage"}
        )

        assert settings.analyzer_audience("word_usage") is AnalyzerAudience.TEACHER

    def test_the_most_restrictive_listing_wins(self):
        # A deployment mid-way through a rollback. Answering "teacher" here
        # would show output someone has just decided to withdraw.
        settings = get_settings().model_copy(
            update={
                "ASSESSMENT_DARK_ANALYZERS": "spelling",
                "ASSESSMENT_TEACHER_ONLY_ANALYZERS": "spelling",
            }
        )

        assert settings.analyzer_audience("spelling") is AnalyzerAudience.DARK

    def test_whitespace_and_empty_entries_are_tolerated(self):
        settings = get_settings().model_copy(
            update={"ASSESSMENT_DARK_ANALYZERS": " spelling , , sentence "}
        )

        assert settings.analyzer_audience("spelling") is AnalyzerAudience.DARK
        assert settings.analyzer_audience("sentence") is AnalyzerAudience.DARK
        assert settings.analyzer_audience("word_usage") is AnalyzerAudience.STUDENT


# ── Attributing an issue to the analyzer that found it ───────────────────────


class TestAttribution:
    def test_the_supervisor_stamps_the_analyzer_onto_every_issue(self, context):
        analyzers: list[Analyzer] = [Fake("spelling", AnalyzerOutput(issues=(issue(0, "a"),)))]

        result = run_analyzers(analyzers, context)

        # `source` is what the audience filter and a false-positive audit both
        # key on, so an issue that forgot to set it would be unattributable.
        assert result.issues[0].source == "spelling"
        assert result.issues[0].analyzer == "spelling"

    def test_an_analyzer_s_own_provider_detail_is_kept(self, context):
        analyzers: list[Analyzer] = [
            Fake("spelling", AnalyzerOutput(issues=(issue(0, "a", source="dictionary"),)))
        ]

        result = run_analyzers(analyzers, context)

        assert result.issues[0].source == "spelling:dictionary"
        assert result.issues[0].analyzer == "spelling"

    def test_a_source_already_naming_the_analyzer_is_left_alone(self, context):
        analyzers: list[Analyzer] = [
            Fake("spelling", AnalyzerOutput(issues=(issue(0, "a", source="spelling:hunspell"),)))
        ]

        assert run_analyzers(analyzers, context).issues[0].source == "spelling:hunspell"


# ── The audience filter ──────────────────────────────────────────────────────


@pytest.fixture
def three_stage_result(context):
    """One assessment with an analyzer at each rollout stage."""
    settings = get_settings().model_copy(
        update={
            "ASSESSMENT_DARK_ANALYZERS": "sentence",
            "ASSESSMENT_TEACHER_ONLY_ANALYZERS": "word_usage",
        }
    )
    analyzers: list[Analyzer] = [
        Fake("spelling", AnalyzerOutput(issues=(issue(0, "shipped"),), score=90.0)),
        Fake("word_usage", AnalyzerOutput(issues=(issue(10, "teacher_only"),), score=80.0)),
        Fake("sentence", AnalyzerOutput(issues=(issue(20, "dark"),), score=70.0)),
    ]
    return run_analyzers(analyzers, context, settings=settings)


class TestAudienceFilter:
    def test_the_unfiltered_result_carries_everything(self, three_stage_result):
        assert {i.subtype for i in three_stage_result.issues} == {
            "shipped",
            "teacher_only",
            "dark",
        }

    def test_a_teacher_sees_everything_except_what_is_still_dark(self, three_stage_result):
        for_teacher = three_stage_result.for_audience(AnalyzerAudience.TEACHER)

        assert {i.subtype for i in for_teacher.issues} == {"shipped", "teacher_only"}
        assert set(for_teacher.analyzers) == {"spelling", "word_usage"}
        assert for_teacher.scores() == {"spelling": 90.0, "word_usage": 80.0}

    def test_a_student_sees_only_what_has_been_promoted_all_the_way(self, three_stage_result):
        for_student = three_stage_result.for_audience(AnalyzerAudience.STUDENT)

        assert {i.subtype for i in for_student.issues} == {"shipped"}
        assert set(for_student.analyzers) == {"spelling"}

    def test_the_filtered_result_is_built_rather_than_serialised_with_omissions(
        self, three_stage_result
    ):
        # A filtered *object* cannot leak through a field someone adds to a
        # schema later; an omission at serialisation time can.
        payload = three_stage_result.for_audience(AnalyzerAudience.STUDENT).to_dict()

        assert "dark" not in str(payload)
        assert "teacher_only" not in str(payload)

    def test_the_counts_still_describe_the_assessment_that_ran(self, three_stage_result):
        for_student = three_stage_result.for_audience(AnalyzerAudience.STUDENT)

        # Deliberate: the suppressed count describes the whole assessment, not
        # the slice being shown. A student's copy saying "0 suppressed" when
        # three findings were withheld would be a different lie.
        assert for_student.suppressed_count == three_stage_result.suppressed_count

    def test_filtering_for_the_internal_view_changes_nothing(self, three_stage_result):
        assert three_stage_result.for_audience(AnalyzerAudience.DARK) is three_stage_result

    def test_an_unavailable_analyzer_still_carries_its_audience(self, context):
        analyzers: list[Analyzer] = [Fake("grammar", UNAVAILABLE)]

        result = run_analyzers(analyzers, context)

        # So a client can say "this server cannot check grammar" rather than
        # "your grammar is perfect".
        assert result.audiences["grammar"] is AnalyzerAudience.STUDENT
        assert "grammar" in result.for_audience(AnalyzerAudience.STUDENT).analyzers
