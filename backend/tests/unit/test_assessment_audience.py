"""Who may see which analyzer, and the parsing that decides it.

The predicate has two callers — the live result a scoring request builds and
the stored row a teacher opens weeks later — and the whole reason it lives in
one module is that those two must not answer differently. Half of this file
tests the parsing of a stored audience map, which is the half that meets data
written by releases that no longer exist.
"""

from __future__ import annotations

import pytest

from app.assessment.audience import analyzer_of, stored_audiences, visible_analyzers
from app.models.enums import AnalyzerAudience

STAGES = {
    "spelling": AnalyzerAudience.STUDENT,
    "sentence": AnalyzerAudience.STUDENT,
    "grammar": AnalyzerAudience.TEACHER,
    "writing_profile": AnalyzerAudience.TEACHER,
    "experimental": AnalyzerAudience.DARK,
}


class TestVisibility:
    def test_a_student_sees_only_what_was_promoted_all_the_way(self):
        assert visible_analyzers(STAGES, AnalyzerAudience.STUDENT) == {"spelling", "sentence"}

    def test_a_teacher_sees_everything_except_the_dark_stage(self):
        visible = visible_analyzers(STAGES, AnalyzerAudience.TEACHER)

        assert visible == {"spelling", "sentence", "grammar", "writing_profile"}
        assert "experimental" not in visible

    def test_the_dark_viewer_is_the_unfiltered_internal_view(self):
        assert visible_analyzers(STAGES, AnalyzerAudience.DARK) == set(STAGES)

    def test_an_analyzer_with_no_recorded_audience_is_visible_to_nobody(self):
        """What an assessment written before the audience map looks like.

        Withholding is the safe reading: the row cannot say who was meant to
        see it, and the honest answer to "who may see this" when the record
        does not say is nobody.
        """
        for viewer in (AnalyzerAudience.STUDENT, AnalyzerAudience.TEACHER):
            assert "spelling" not in visible_analyzers({}, viewer)

    def test_the_live_and_stored_paths_agree(self):
        """The property the module exists for.

        ``AssessmentResult.for_audience`` filters an in-memory result; the
        service filters a stored row. If these two ever disagree, the leak is
        in the stored path — the one a person actually reads from, and the one
        the engine tests do not touch.
        """
        from app.assessment.result import AssessmentResult

        result = AssessmentResult(version="1.0.0", analyzers={}, issues=(), audiences=dict(STAGES))

        for viewer in AnalyzerAudience:
            through_result = set(result.for_audience(viewer).audiences)
            through_predicate = visible_analyzers(STAGES, viewer)
            assert through_result == through_predicate, viewer


class TestParsingAStoredMap:
    def test_a_well_formed_map_parses(self):
        parsed = stored_audiences({"spelling": "student", "grammar": "teacher"})

        assert parsed == {
            "spelling": AnalyzerAudience.STUDENT,
            "grammar": AnalyzerAudience.TEACHER,
        }

    @pytest.mark.parametrize("raw", [None, "not a mapping", ["spelling"], 42])
    def test_anything_that_is_not_a_map_yields_nothing(self, raw):
        assert stored_audiences(raw) == {}

    def test_an_unrecognised_stage_resolves_to_dark(self):
        """The most restrictive reading, not the most convenient one.

        A stage this build cannot parse means the row does not say who was
        meant to see that analyzer. Defaulting to `student` there would
        publish, on a guess, exactly what the rollout ladder exists to hold
        back.
        """
        parsed = stored_audiences({"spelling": "everyone", "grammar": None, "sentence": 7})

        assert parsed == {
            "spelling": AnalyzerAudience.DARK,
            "grammar": AnalyzerAudience.DARK,
            "sentence": AnalyzerAudience.DARK,
        }

    def test_an_unrecognised_stage_is_then_hidden_from_both_audiences(self):
        parsed = stored_audiences({"mystery": "everyone"})

        assert visible_analyzers(parsed, AnalyzerAudience.STUDENT) == set()
        assert visible_analyzers(parsed, AnalyzerAudience.TEACHER) == set()

    def test_a_non_string_key_is_dropped(self):
        assert stored_audiences({7: "student", "spelling": "student"}) == {
            "spelling": AnalyzerAudience.STUDENT
        }

    def test_it_never_raises(self):
        """It runs while a teacher is opening a page."""
        assert stored_audiences({"a": object()}) == {"a": AnalyzerAudience.DARK}


class TestAnalyzerOf:
    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("spelling", "spelling"),
            ("grammar:languagetool", "grammar"),
            ("grammar:MORFOLOGIK_RULE_EN_GB", "grammar"),
            ("", ""),
        ],
    )
    def test_only_the_analyzer_half_is_published(self, source, expected):
        """A provider name on a screen is what the grammar rules forbid."""
        assert analyzer_of(source) == expected


class TestReadingAStoredSeverity:
    """`_is_mistake` over a row, including one the database would refuse.

    A `CHECK` constraint keeps an unrecognised severity out of
    `assessment_issues`, so this branch is unreachable through the API today.
    It is still the right behaviour to pin: the constraint is the guard, and
    the reader should not depend on the guard being there — a future migration
    that widens the scale would otherwise turn an unknown grade into a mistake
    the student is told they made.
    """

    @staticmethod
    def row(severity: str):
        from types import SimpleNamespace

        return SimpleNamespace(severity=severity)

    @pytest.mark.parametrize(
        ("severity", "expected"),
        [("high", True), ("medium", True), ("low", True), ("info", False)],
    )
    def test_the_scale_reads_as_it_should(self, severity, expected):
        from app.services.assessment import _is_mistake

        assert _is_mistake(self.row(severity)) is expected

    @pytest.mark.parametrize("severity", ["catastrophic", "", "HIGH", None])
    def test_an_unreadable_grade_is_not_counted_as_a_mistake(self, severity):
        """The safe direction: never inflate what a student is told they got wrong."""
        from app.services.assessment import _is_mistake

        assert _is_mistake(self.row(severity)) is False


class TestTheServiceGuardsItsOwnArguments:
    """Defence in depth behind the router's own validation.

    The route constrains `interval` with a pattern and rejects a bad one with
    422 before the service is reached, so these raise only for a caller that
    is not HTTP — a script, a future report job. Answering "no data" for a
    misspelled analyzer would report a working class as one with nothing to
    show, which is the same lie an empty forbidden report tells.
    """

    @staticmethod
    def service():
        from app.core.config import Settings
        from app.services.assessment import AssessmentService

        settings = Settings(
            SECRET_KEY="a-perfectly-fine-secret-key-over-32-chars",
            DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
        )
        # The guards run before anything is read, so the collaborators are
        # never touched and need not exist.
        return AssessmentService(None, None, None, None, settings)  # type: ignore[arg-type]

    async def test_an_unknown_analyzer_is_refused(self):
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Unknown analyzer"):
            await self.service().score_trend(viewer=None, analyzer="nonsense", class_id=None)

    async def test_an_unknown_interval_is_refused(self):
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Unknown interval"):
            await self.service().score_trend(
                viewer=None, analyzer="spelling", class_id=None, interval="fortnight"
            )
