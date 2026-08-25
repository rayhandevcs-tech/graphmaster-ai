"""The framework itself: the issue model, the supervisor and the registry.

None of this needs the language model. The analyzers under test here are
fakes, because what is being tested is the machinery around an analyzer — what
happens to its issues, its failures and its clock — rather than any judgement
about English.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from app.assessment import ASSESSMENT_VERSION, assessment_version
from app.assessment.issues import AssessmentIssue, deduplicate, order_for_display
from app.assessment.protocol import UNAVAILABLE, Analyzer, AnalyzerOutput, AssessmentContext
from app.assessment.registry import build_analyzers, known_analyzers
from app.assessment.result import AssessmentResult
from app.assessment.supervisor import run_analyzers
from app.core.config import get_settings
from app.models.enums import AnalyzerStatus, IssueCategory, IssueSeverity
from app.nlp.detector import DetectionResult
from app.nlp.normalise import normalise
from app.nlp.terms import compile_targets
from app.nlp.writing import WritingQuality

# ── Helpers ──────────────────────────────────────────────────────────────────


def issue(
    start: int = 0,
    end: int = 5,
    *,
    category: IssueCategory = IssueCategory.SPELLING,
    subtype: str = "misspelling",
    severity: IssueSeverity = IssueSeverity.MEDIUM,
    confidence: float = 1.0,
    text: str = "teh",
) -> AssessmentIssue:
    return AssessmentIssue(
        category=category,
        subtype=subtype,
        severity=severity,
        original_text=text,
        explanation="Explanation.",
        start=start,
        end=end,
        confidence=confidence,
        source="test",
    )


class Fake:
    """An analyzer that returns whatever it was constructed with."""

    def __init__(self, name: str, output: AnalyzerOutput) -> None:
        self.name = name
        self._output = output

    def run(self, ctx: AssessmentContext) -> AnalyzerOutput:
        return self._output


@pytest.fixture
def context() -> AssessmentContext:
    """A context the fake analyzers never read.

    ``doc`` is ``None`` on purpose: constructing a real one would pull in the
    language model for tests that are about plumbing, and no analyzer here
    touches it. A real analyzer that did would fail loudly, which is the
    correct outcome for a test that forgot to provide one.
    """
    return AssessmentContext(
        text="Sales rose.",
        doc=None,  # type: ignore[arg-type]
        normalised=normalise("Sales rose."),
        targets=compile_targets([]),
        detection=DetectionResult(detected=[], missing=[]),
        writing=WritingQuality(
            word_count=2,
            sentence_count=1,
            word_count_score=10.0,
            lexical_diversity_score=50.0,
            sentence_structure_score=40.0,
            overview_score=0.0,
            mattr=0.5,
            mean_sentence_length=2.0,
            subordination_ratio=0.0,
            has_overview=False,
            overview_sentence_index=None,
        ),
    )


# ── The issue model ──────────────────────────────────────────────────────────


class TestAssessmentIssue:
    def test_an_inverted_span_is_refused(self):
        # A highlight from 40 to 12 renders as nothing, or as the whole
        # answer, depending on the client. Refusing here means the analyzer
        # that produced it fails and is reported, rather than the student
        # seeing something inexplicable.
        with pytest.raises(ValueError, match="half-open"):
            issue(start=40, end=12)

    def test_a_negative_start_is_refused(self):
        with pytest.raises(ValueError, match="half-open"):
            issue(start=-1, end=4)

    def test_an_empty_span_is_allowed(self):
        # A missing word has a real position and no width: "insert 'the' here"
        # points between two characters.
        assert issue(start=7, end=7).start == 7

    @pytest.mark.parametrize("confidence", [-0.1, 1.1, 42.0])
    def test_confidence_outside_zero_to_one_is_refused(self, confidence: float):
        with pytest.raises(ValueError, match="confidence"):
            issue(confidence=confidence)

    def test_an_issue_must_carry_a_subtype(self):
        # The subtype is the grouping key for "the mistakes this class makes
        # most". An issue without one is invisible to the analytics it exists
        # to feed.
        with pytest.raises(ValueError, match="subtype"):
            issue(subtype="")

    def test_the_same_finding_twice_has_the_same_fingerprint(self):
        assert issue().fingerprint == issue().fingerprint

    def test_a_different_span_is_a_different_finding(self):
        assert issue(start=0, end=5).fingerprint != issue(start=6, end=11).fingerprint

    def test_a_different_subtype_at_the_same_span_is_a_different_finding(self):
        # A spell checker and a grammar checker can both object to one word
        # for different reasons, and both are worth saying.
        first = issue(subtype="misspelling")
        second = issue(subtype="wrong_word", category=IssueCategory.WORD_USAGE)
        assert first.fingerprint != second.fingerprint

    def test_a_long_explanation_is_cut_on_a_word_boundary(self):
        long_issue = AssessmentIssue(
            category=IssueCategory.GRAMMAR,
            subtype="tense",
            severity=IssueSeverity.HIGH,
            original_text="was",
            explanation="word " * 200,
            start=0,
            end=3,
        )
        truncated = long_issue.truncated()

        assert len(truncated.explanation) <= 400
        assert truncated.explanation.endswith("…")
        # Severed mid-word it would read as corruption rather than brevity.
        assert not truncated.explanation.rstrip("…").endswith("wor")

    def test_a_short_explanation_is_returned_unchanged(self):
        original = issue()
        assert original.truncated() is original

    def test_to_dict_names_the_fields_the_client_reads(self):
        assert set(issue().to_dict()) == {
            "category",
            "subtype",
            "severity",
            "original_text",
            "suggested_text",
            "explanation",
            "start",
            "end",
            "confidence",
            "source",
        }


class TestOrdering:
    def test_issues_are_ordered_by_position(self):
        # A student works through their answer from the top. A list grouped by
        # analyzer makes them jump around their own writing.
        ordered = order_for_display([issue(start=30, end=34), issue(start=2, end=6)])
        assert [i.start for i in ordered] == [2, 30]

    def test_the_more_serious_issue_is_read_first_at_the_same_span(self):
        ordered = order_for_display(
            [
                issue(severity=IssueSeverity.INFO, subtype="style"),
                issue(severity=IssueSeverity.HIGH, subtype="spelling"),
            ]
        )
        assert ordered[0].severity is IssueSeverity.HIGH

    def test_deduplication_keeps_the_more_confident_of_two_identical_findings(self):
        kept = deduplicate([issue(confidence=0.7), issue(confidence=0.95)])

        assert len(kept) == 1
        assert kept[0].confidence == 0.95

    def test_deduplication_leaves_genuinely_different_findings_alone(self):
        assert len(deduplicate([issue(start=0, end=3), issue(start=8, end=11)])) == 2


# ── The analyzer output ──────────────────────────────────────────────────────


class TestAnalyzerOutput:
    @pytest.mark.parametrize("score", [-1.0, 100.01, 250.0])
    def test_a_score_outside_zero_to_one_hundred_is_refused(self, score: float):
        with pytest.raises(ValueError, match="0"):
            AnalyzerOutput(score=score)

    def test_a_missing_score_is_allowed(self):
        # An analyzer that only finds issues has nothing to score.
        assert AnalyzerOutput().score is None

    def test_only_an_ok_status_counts_as_having_run(self):
        assert AnalyzerOutput(status=AnalyzerStatus.OK).ran
        assert not UNAVAILABLE.ran
        assert not AnalyzerOutput(status=AnalyzerStatus.FAILED).ran
        assert not AnalyzerOutput(status=AnalyzerStatus.SKIPPED).ran


# ── The supervisor ───────────────────────────────────────────────────────────


class TestSupervisor:
    def test_it_collects_issues_from_every_analyzer(self, context):
        analyzers: list[Analyzer] = [
            Fake("one", AnalyzerOutput(issues=(issue(start=0, end=3),))),
            Fake("two", AnalyzerOutput(issues=(issue(start=10, end=13),))),
        ]

        result = run_analyzers(analyzers, context)

        assert len(result.issues) == 2
        assert set(result.analyzers) == {"one", "two"}

    def test_it_records_how_long_each_analyzer_took(self, context):
        result = run_analyzers([Fake("one", AnalyzerOutput())], context)

        # Not an assertion about speed — an assertion that the measurement
        # exists, because the per-analyzer budget is enforced from it.
        assert result.analyzers["one"].duration_ms >= 0.0

    def test_an_issue_below_the_confidence_floor_is_suppressed_and_counted(self, context):
        settings = get_settings().model_copy(update={"ASSESSMENT_ISSUE_CONFIDENCE_FLOOR": 0.8})
        analyzers: list[Analyzer] = [
            Fake(
                "one",
                AnalyzerOutput(
                    issues=(
                        issue(start=0, end=3, confidence=0.9),
                        issue(start=10, end=13, confidence=0.5),
                    )
                ),
            )
        ]

        result = run_analyzers(analyzers, context, settings=settings)

        assert len(result.issues) == 1
        # Counted rather than dropped silently: a floor set too high is
        # otherwise invisible, and this is the number that says so.
        assert result.suppressed_count == 1

    def test_an_issue_exactly_on_the_floor_is_kept(self, context):
        settings = get_settings().model_copy(update={"ASSESSMENT_ISSUE_CONFIDENCE_FLOOR": 0.6})
        analyzers: list[Analyzer] = [Fake("one", AnalyzerOutput(issues=(issue(confidence=0.6),)))]

        assert len(run_analyzers(analyzers, context, settings=settings).issues) == 1

    def test_a_category_over_the_cap_is_trimmed_and_marked_as_trimmed(self, context):
        settings = get_settings().model_copy(update={"ASSESSMENT_MAX_ISSUES_PER_CATEGORY": 3})
        many = tuple(
            issue(start=i * 10, end=i * 10 + 4, confidence=0.6 + i / 100) for i in range(10)
        )

        result = run_analyzers(
            [Fake("one", AnalyzerOutput(issues=many))], context, settings=settings
        )

        assert len(result.issues) == 3
        # A truncated list shown as complete would tell the student they have
        # three mistakes when they have ten.
        assert result.truncated_categories == ("spelling",)

    def test_trimming_keeps_the_most_confident_rather_than_the_earliest(self, context):
        settings = get_settings().model_copy(update={"ASSESSMENT_MAX_ISSUES_PER_CATEGORY": 1})
        analyzers: list[Analyzer] = [
            Fake(
                "one",
                AnalyzerOutput(
                    issues=(
                        issue(start=0, end=4, confidence=0.61),
                        issue(start=50, end=54, confidence=0.99),
                    )
                ),
            )
        ]

        result = run_analyzers(analyzers, context, settings=settings)

        # A page of low-grade guesses at the top of the answer must not crowd
        # out a certain finding further down.
        assert result.issues[0].confidence == 0.99

    def test_a_cap_that_is_not_reached_marks_nothing_as_trimmed(self, context):
        result = run_analyzers([Fake("one", AnalyzerOutput(issues=(issue(),)))], context)
        assert result.truncated_categories == ()

    def test_an_unavailable_analyzer_is_not_a_failure(self, context):
        result = run_analyzers([Fake("grammar", UNAVAILABLE)], context)

        # "This server has no grammar checker" and "the grammar checker
        # crashed" are different facts, and only one is worth waking someone
        # for.
        assert result.analyzers["grammar"].status is AnalyzerStatus.UNAVAILABLE
        assert result.failed_analyzers == ()
        assert result.is_complete is True

    def test_a_failing_analyzer_does_not_stop_the_ones_after_it(self, context):
        class Boom:
            name = "boom"

            def run(self, ctx: AssessmentContext) -> AnalyzerOutput:
                raise RuntimeError("kaboom")

        analyzers: list[Analyzer] = [
            Boom(),
            Fake("after", AnalyzerOutput(issues=(issue(),))),
        ]

        result = run_analyzers(analyzers, context)

        assert result.analyzers["boom"].status is AnalyzerStatus.FAILED
        assert result.analyzers["after"].ran
        assert len(result.issues) == 1

    def test_a_failure_detail_does_not_quote_the_student(self, context):
        class Leaky:
            name = "leaky"

            def run(self, ctx: AssessmentContext) -> AnalyzerOutput:
                raise ValueError("could not handle 'Sales rose.' from this student")

        result = run_analyzers([Leaky()], context)
        detail = result.analyzers["leaky"].detail

        # The detail reaches operator logs and a teacher's screen. The
        # exception type says what broke; its message can carry the answer.
        assert detail == "ValueError while running leaky"
        assert "Sales rose" not in detail

    def test_a_slow_analyzer_is_warned_about_but_still_returns(self, context, caplog):
        import time

        class Slow:
            name = "slow"

            def run(self, ctx: AssessmentContext) -> AnalyzerOutput:
                time.sleep(0.02)
                return AnalyzerOutput(issues=(issue(),))

        settings = get_settings().model_copy(update={"ASSESSMENT_ANALYZER_BUDGET_MS": 1.0})

        with caplog.at_level(logging.WARNING):
            result = run_analyzers([Slow()], context, settings=settings)

        # Observed, not enforced: a CPU-bound analyzer cannot be preempted
        # safely, so the budget produces a warning and a recorded duration
        # rather than a cancellation.
        assert result.analyzers["slow"].ran
        assert len(result.issues) == 1
        assert any("over its" in record.message for record in caplog.records)

    def test_the_context_reports_the_word_count_the_writing_pass_measured(self, context):
        # One number, from the pass that counted it — an analyzer that counted
        # again could disagree with the score on the same page.
        assert context.word_count == context.writing.word_count == 2

    def test_no_analyzers_produces_an_empty_but_valid_result(self, context):
        result = run_analyzers([], context)

        assert result.issues == ()
        assert result.is_complete is True
        assert result.version.startswith(ASSESSMENT_VERSION)


# ── The result ───────────────────────────────────────────────────────────────


class TestAssessmentResult:
    def test_it_names_the_analyzers_that_actually_ran(self, context):
        analyzers: list[Analyzer] = [
            Fake("spelling", AnalyzerOutput()),
            Fake("grammar", UNAVAILABLE),
        ]

        result = run_analyzers(analyzers, context)

        # The distinction a teacher needs: grammar produced no issues because
        # it was never installed, not because the writing was clean.
        assert result.ran_analyzers == ("spelling",)

    def test_counts_include_the_categories_with_nothing_in_them(self, context):
        result = run_analyzers([Fake("one", AnalyzerOutput(issues=(issue(),)))], context)
        counts = result.counts_by_category()

        # A missing key reads as missing data; a zero reads as a finding.
        assert set(counts) == {c.value for c in IssueCategory}
        assert counts["spelling"] == 1
        assert counts["grammar"] == 0

    def test_only_mistakes_are_counted_as_errors(self, context):
        analyzers: list[Analyzer] = [
            Fake(
                "one",
                AnalyzerOutput(
                    issues=(
                        issue(start=0, end=3, severity=IssueSeverity.MEDIUM),
                        issue(
                            start=10,
                            end=13,
                            severity=IssueSeverity.INFO,
                            subtype="style",
                            category=IssueCategory.STYLE,
                        ),
                    )
                ),
            )
        ]

        result = run_analyzers(analyzers, context)

        assert len(result.issues) == 2
        assert result.error_count == 1

    def test_issues_can_be_read_back_by_category(self, context):
        analyzers: list[Analyzer] = [
            Fake(
                "one",
                AnalyzerOutput(
                    issues=(
                        issue(start=0, end=3),
                        issue(start=10, end=13, category=IssueCategory.GRAMMAR, subtype="tense"),
                    )
                ),
            )
        ]

        result = run_analyzers(analyzers, context)

        assert len(result.issues_for(IssueCategory.GRAMMAR)) == 1
        assert result.issues_for(IssueCategory.WORD_USAGE) == ()

    def test_to_dict_is_json_serialisable(self, context):
        import json

        analyzers: list[Analyzer] = [
            Fake("one", AnalyzerOutput(issues=(issue(),), score=72.5, metrics={"x": 1.0})),
            Fake("grammar", UNAVAILABLE),
        ]

        payload = run_analyzers(analyzers, context).to_dict()

        # It will be stored as JSONB and returned over the API; anything that
        # cannot round-trip through JSON fails at the worst possible moment.
        assert json.loads(json.dumps(payload))["scores"] == {"one": 72.5, "grammar": None}


# ── The registry ─────────────────────────────────────────────────────────────


class TestRegistry:
    def test_it_builds_the_configured_analyzers_in_order(self):
        settings = get_settings().model_copy(update={"ASSESSMENT_ANALYZERS": "writing,vocabulary"})

        assert [a.name for a in build_analyzers(settings)] == ["writing", "vocabulary"]

    def test_an_unknown_name_is_skipped_rather_than_fatal(self, caplog):
        settings = get_settings().model_copy(
            update={"ASSESSMENT_ANALYZERS": "vocabulary,speling,writing"}
        )

        with caplog.at_level(logging.WARNING):
            built = build_analyzers(settings)

        # A typo in a deployment's environment must not cost a student the
        # submission that happened to hit it — the same rule a malformed
        # achievement rule follows.
        assert [a.name for a in built] == ["vocabulary", "writing"]
        assert any("speling" in record.message for record in caplog.records)

    def test_disabling_assessment_builds_nothing(self):
        settings = get_settings().model_copy(update={"ASSESSMENT_ENABLED": False})
        assert build_analyzers(settings) == []

    def test_an_analyzer_named_twice_is_built_once(self):
        settings = get_settings().model_copy(
            update={"ASSESSMENT_ANALYZERS": "writing,writing,vocabulary"}
        )

        # Running it twice would double every issue it finds.
        assert [a.name for a in build_analyzers(settings)] == ["writing", "vocabulary"]

    def test_whitespace_and_empty_entries_are_tolerated(self):
        settings = get_settings().model_copy(
            update={"ASSESSMENT_ANALYZERS": " writing , , vocabulary "}
        )
        assert [a.name for a in build_analyzers(settings)] == ["writing", "vocabulary"]

    def test_an_empty_analyzer_list_disables_the_pass_entirely(self):
        from app.assessment.engine import run_assessment

        settings = get_settings().model_copy(update={"ASSESSMENT_ANALYZERS": ""})

        assert build_analyzers(settings) == []
        # And the engine returns None rather than an empty assessment: an
        # assessment that ran nothing and one that was switched off are the
        # same fact, and the client already handles the null.
        assert (
            run_assessment(
                text="Sales rose.",
                doc=None,  # type: ignore[arg-type]
                normalised=normalise("Sales rose."),
                targets=compile_targets([]),
                detection=DetectionResult(detected=[], missing=[]),
                writing=None,  # type: ignore[arg-type]
                settings=settings,
            )
            is None
        )

    def test_warming_up_builds_and_preloads_the_configured_analyzers(self, monkeypatch):
        from app.assessment import registry

        warmed: list[str] = []

        class Preloading:
            name = "preloading"

            def __init__(self, settings) -> None:
                pass

            def warm_up(self) -> None:
                warmed.append(self.name)

            def run(self, ctx):
                return AnalyzerOutput()

        monkeypatch.setitem(registry.BUILDERS, "preloading", Preloading)
        registry.warm_up(
            get_settings().model_copy(update={"ASSESSMENT_ANALYZERS": "preloading,writing"})
        )

        # `writing` has nothing to preload and must not be asked to.
        assert warmed == ["preloading"]

    def test_an_analyzer_that_cannot_warm_up_does_not_stop_the_server_booting(
        self, monkeypatch, caplog
    ):
        from app.assessment import registry

        class Broken:
            name = "broken"

            def __init__(self, settings) -> None:
                pass

            def warm_up(self) -> None:
                raise RuntimeError("dictionary file is truncated")

            def run(self, ctx):
                return AnalyzerOutput()

        monkeypatch.setitem(registry.BUILDERS, "broken", Broken)

        with caplog.at_level(logging.WARNING):
            # A warm-up is an optimisation. An analyzer that cannot preload can
            # still report itself unavailable on the first request.
            registry.warm_up(get_settings().model_copy(update={"ASSESSMENT_ANALYZERS": "broken"}))

        assert any("Could not warm up" in record.message for record in caplog.records)

    def test_every_known_analyzer_can_actually_be_built(self):
        # Guards against a registry entry whose constructor was renamed.
        for name in known_analyzers():
            settings = get_settings().model_copy(update={"ASSESSMENT_ANALYZERS": name})
            assert [a.name for a in build_analyzers(settings)] == [name]


# ── Versioning (D6) ──────────────────────────────────────────────────────────


class TestAssessmentVersion:
    def test_it_carries_the_code_version_and_a_fingerprint(self):
        version = assessment_version(get_settings())

        assert version.startswith(f"{ASSESSMENT_VERSION}+")
        assert len(version.split("+")[1]) == 8

    def test_the_same_configuration_produces_the_same_version(self):
        settings = get_settings()
        assert assessment_version(settings) == assessment_version(settings.model_copy())

    @pytest.mark.parametrize(
        "change",
        [
            {"ASSESSMENT_ANALYZERS": "writing"},
            {"GRAMMAR_PROVIDER": "local"},
            {"ASSESSMENT_ISSUE_CONFIDENCE_FLOOR": 0.75},
            {"ASSESSMENT_MAX_ISSUES_PER_CATEGORY": 5},
        ],
        ids=["analyzers", "grammar-provider", "confidence-floor", "issue-cap"],
    )
    def test_changing_the_rubric_changes_the_version(self, change: dict[str, Any]):
        # Two assessments produced under different analyzer sets are not
        # comparable. Without the fingerprint they would carry the same
        # version string and silently look as though they were.
        base = get_settings()
        assert assessment_version(base) != assessment_version(base.model_copy(update=change))

    def test_reordering_the_analyzers_does_not_change_the_version(self):
        # The set is what makes two results comparable; the order only decides
        # which analyzer may read another's output.
        base = get_settings().model_copy(update={"ASSESSMENT_ANALYZERS": "vocabulary,writing"})
        swapped = base.model_copy(update={"ASSESSMENT_ANALYZERS": "writing,vocabulary"})

        assert assessment_version(base) == assessment_version(swapped)


# ── The two adapters ─────────────────────────────────────────────────────────


class TestAdapters:
    def test_the_vocabulary_analyzer_reports_but_never_flags(self, context):
        from app.assessment.analyzers import VocabularyAnalyzer

        output = VocabularyAnalyzer(get_settings()).run(context)

        # Missing vocabulary is already carried by `scores.missing_terms` and
        # the feedback. Emitting it here too would double-count it in "the
        # mistakes this class makes most".
        assert output.issues == ()
        assert output.score == 0.0
        assert output.metrics["required_targets"] == 0.0

    def test_the_writing_analyzer_reports_the_score_the_rubric_uses(self, context):
        from app.assessment.analyzers import WritingAnalyzer

        output = WritingAnalyzer(get_settings()).run(context)

        assert output.issues == ()
        assert output.score == context.writing.score
        assert output.metrics["mattr"] == pytest.approx(0.5)

    def test_a_result_built_from_the_adapters_scores_both(self, context):
        from app.assessment.analyzers import VocabularyAnalyzer, WritingAnalyzer

        result: AssessmentResult = run_analyzers(
            [VocabularyAnalyzer(get_settings()), WritingAnalyzer(get_settings())], context
        )

        assert set(result.scores()) == {"vocabulary", "writing"}
        assert result.issues == ()
        assert result.is_complete
