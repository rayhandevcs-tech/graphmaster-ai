"""The grammar analyzer: what it does with what a provider gives it.

The provider is faked throughout, which is the whole reason for the
abstraction. What is being tested here is not LanguageTool — it is the four
decisions the analyzer makes on top of any provider: where the issue lands in
the student's own text, what it is allowed to say, what counts against the
grammar figure, and what happens when the engine is missing or broken.
"""

from __future__ import annotations

import pytest

from app.assessment.analyzers.grammar import (
    ACCURACY_CEILING,
    ACCURACY_FLOOR,
    MIN_WORDS_FOR_SCORE,
    GrammarAnalyzer,
)
from app.assessment.grammar.base import (
    GrammarCheckError,
    GrammarMatch,
    GrammarReport,
    GrammarUnavailableError,
)
from app.core.config import get_settings
from app.models.enums import AnalyzerStatus, IssueCategory, IssueSeverity

pytestmark = pytest.mark.usefixtures("spacy_model")

#: Long enough to be scored, and wrong in one specific way.
ANSWER = (
    "The chart go up steadily between 2010 and 2024, and the figure for wind "
    "power rose in the same period while coal declined across every one of "
    "those years without exception at all."
)


class FakeProvider:
    """A provider that finds whatever the test tells it to find.

    Locates its needles in the text it is *given*, rather than being handed
    offsets — so it reports positions in the normalised string exactly as a
    real provider would, and the analyzer's mapping back to the student's own
    text is genuinely exercised.
    """

    name = "fake"

    def __init__(self, *finds, latency_ms: float = 12.5, available: bool = True) -> None:
        self.finds = finds
        self.latency_ms = latency_ms
        self.available = available
        self.checked: list[str] = []
        self.probes = 0

    def is_available(self) -> bool:
        self.probes += 1
        return self.available

    def check(self, text: str, *, language: str) -> GrammarReport:
        self.checked.append(text)
        matches = []
        for needle, spec in self.finds:
            index = text.find(needle)
            assert index >= 0, f"the fake provider was asked to find {needle!r}, which is not there"
            matches.append(
                GrammarMatch(
                    subtype=spec.get("subtype", "subject_verb_agreement"),
                    severity=spec.get("severity", IssueSeverity.MEDIUM),
                    original_text=needle,
                    explanation=spec.get("explanation", "That does not agree with its subject."),
                    start=index,
                    end=index + len(needle),
                    suggested_text=spec.get("suggested_text", "goes"),
                    confidence=spec.get("confidence", 0.85),
                    rule_id=spec.get("rule_id", "SUBJECT_VERB_AGREEMENT"),
                )
            )
        return GrammarReport(
            matches=tuple(matches),
            provider=self.name,
            latency_ms=self.latency_ms,
            checked_chars=len(text),
        )


class Raising:
    """A provider whose ``check`` fails the way a real one eventually will."""

    name = "raising"

    def __init__(self, exception: Exception) -> None:
        self.exception = exception

    def is_available(self) -> bool:
        return True

    def check(self, text: str, *, language: str) -> GrammarReport:
        raise self.exception


def analyzer(provider, **overrides) -> GrammarAnalyzer:
    return GrammarAnalyzer(get_settings().model_copy(update=overrides), provider=provider)


# ── Where the issue lands ────────────────────────────────────────────────────


class TestOffsets:
    def test_an_issue_indexes_the_students_own_text(self, assessment_context):
        ctx = assessment_context(ANSWER)
        out = analyzer(FakeProvider(("go", {}))).run(ctx)

        assert len(out.issues) == 1
        issue = out.issues[0]
        assert ctx.text[issue.start : issue.end] == "go"
        assert issue.original_text == "go"

    def test_the_span_survives_normalisation_moving_the_text(self, assessment_context):
        """The reason offsets are mapped rather than passed through.

        The provider is given normalised text — collapsed whitespace, folded
        quotes — so its offsets index a string the student never wrote. A
        highlight built from one lands on the wrong words.
        """
        original = "The chart   go up steadily and the figure  for wind power rose over time."
        ctx = assessment_context(original)

        out = analyzer(FakeProvider(("go", {}))).run(ctx)
        issue = out.issues[0]

        assert ctx.normalised.text != original, "this test needs normalisation to have moved things"
        assert original[issue.start : issue.end] == "go"

    def test_the_quoted_text_comes_from_the_original_not_the_providers_copy(
        self, assessment_context
    ):
        # A student reading "you wrote X" must be able to find X in their own
        # answer, spelled the way they spelled it.
        original = "The chart shows that sales “go” up over the whole period shown here."
        ctx = assessment_context(original)

        out = analyzer(FakeProvider(('"go"', {}))).run(ctx)

        assert out.issues[0].original_text == "“go”"


# ── What it is allowed to say ────────────────────────────────────────────────


class TestIssues:
    def test_every_issue_is_categorised_as_grammar(self, assessment_context):
        ctx = assessment_context(ANSWER)
        out = analyzer(FakeProvider(("go", {}), ("rose", {"subtype": "verb_tense"}))).run(ctx)

        assert {i.category for i in out.issues} == {IssueCategory.GRAMMAR}

    def test_the_subtype_and_severity_come_from_the_provider(self, assessment_context):
        ctx = assessment_context(ANSWER)
        out = analyzer(
            FakeProvider(("coal", {"subtype": "article_use", "severity": IssueSeverity.LOW}))
        ).run(ctx)

        assert out.issues[0].subtype == "article_use"
        assert out.issues[0].severity is IssueSeverity.LOW

    def test_the_source_records_the_rule_never_the_endpoint(self, assessment_context):
        """``source`` is what a false-positive audit starts from.

        It names the rule that fired, which is enough to find the cause — and
        it is a string a teacher may end up seeing, so an internal hostname
        does not belong in it.
        """
        ctx = assessment_context(ANSWER)
        out = analyzer(FakeProvider(("go", {"rule_id": "HE_VERB_AGR"}))).run(ctx)

        assert out.issues[0].source.endswith("HE_VERB_AGR")
        assert "http" not in out.issues[0].source

    def test_a_match_with_no_rule_identifier_still_names_its_engine(self, assessment_context):
        ctx = assessment_context(ANSWER)
        out = analyzer(FakeProvider(("go", {"rule_id": ""}))).run(ctx)

        assert "languagetool" in out.issues[0].source

    def test_an_explanation_is_never_empty(self, assessment_context):
        ctx = assessment_context(ANSWER)
        out = analyzer(FakeProvider(("go", {"explanation": "The verb does not agree."}))).run(ctx)

        assert out.issues[0].explanation


# ── What counts against the figure ───────────────────────────────────────────


class TestScore:
    def test_a_clean_answer_scores_full_marks(self, assessment_context):
        ctx = assessment_context(ANSWER)
        out = analyzer(FakeProvider()).run(ctx)

        assert out.status is AnalyzerStatus.OK
        assert out.score == 100.0
        assert out.metrics["grammar_accuracy_percentage"] == 100.0

    def test_errors_lower_the_figure(self, assessment_context):
        ctx = assessment_context(ANSWER)
        clean = analyzer(FakeProvider()).run(ctx)
        flawed = analyzer(
            FakeProvider(("go", {}), ("rose", {"subtype": "verb_tense"}), ("coal", {}))
        ).run(ctx)

        assert flawed.score < clean.score
        assert flawed.metrics["grammar_issue_count"] == 3.0

    def test_a_style_note_is_not_counted_as_a_mistake(self, assessment_context):
        """``INFO`` is the rung that means "this is not a mistake".

        Marking a student down for a note that explicitly asserts they did
        nothing wrong is the contradiction the severity scale exists to
        prevent.
        """
        ctx = assessment_context(ANSWER)
        out = analyzer(
            FakeProvider(("go", {"subtype": "inconsistency", "severity": IssueSeverity.INFO}))
        ).run(ctx)

        assert out.score == 100.0
        assert out.metrics["grammar_issue_count"] == 0.0
        assert out.metrics["advisory_count"] == 1.0
        assert len(out.issues) == 1  # still reported, just not counted

    def test_an_issue_too_uncertain_to_show_is_not_counted_either(self, assessment_context):
        """Saying "we are not sure about this" and then marking it is the same
        contradiction from the other direction."""
        ctx = assessment_context(ANSWER)
        out = analyzer(
            FakeProvider(("go", {"confidence": 0.2})),
            ASSESSMENT_ISSUE_CONFIDENCE_FLOOR=0.6,
        ).run(ctx)

        assert out.score == 100.0
        assert out.metrics["grammar_issue_count"] == 0.0

    def test_a_short_answer_is_checked_but_not_scored(self, assessment_context):
        """A single error in a six-word sentence is 83% accuracy.

        Reported beside work a student did well, that number says more about
        the answer's length than about its grammar — so the issues are shown
        and the figure is withheld.
        """
        ctx = assessment_context("The chart go up.")
        out = analyzer(FakeProvider(("go", {}))).run(ctx)

        assert out.score is None
        assert len(out.issues) == 1
        assert out.metrics["words_checked"] < MIN_WORDS_FOR_SCORE

    def test_the_accuracy_band_is_wide_enough_that_one_slip_is_not_a_failure(
        self, assessment_context
    ):
        ctx = assessment_context(ANSWER)
        out = analyzer(FakeProvider(("go", {}))).run(ctx)

        assert ACCURACY_FLOOR < out.metrics["grammar_accuracy_percentage"] <= 100.0
        assert out.score > 50.0
        assert ACCURACY_FLOOR < ACCURACY_CEILING < 100.0

    def test_the_metrics_report_what_the_figure_was_built_from(self, assessment_context):
        ctx = assessment_context(ANSWER)
        out = analyzer(FakeProvider(("go", {}), latency_ms=41.25)).run(ctx)

        assert set(out.metrics) == {
            "grammar_issue_count",
            "grammar_accuracy_percentage",
            "words_checked",
            "characters_checked",
            "suggestions_offered",
            "advisory_count",
            "provider_latency_ms",
        }
        # The provider's own cost, separate from the analyzer's: the number
        # that answers whether a remote engine is worth its round trip.
        assert out.metrics["provider_latency_ms"] == pytest.approx(41.25)


# ── When the engine is missing or broken ─────────────────────────────────────


class TestFailureContainment:
    def test_no_provider_is_unavailable_not_failed(self, assessment_context):
        """The distinction that decides whether every submission on a server
        with no grammar engine is marked partial."""
        ctx = assessment_context(ANSWER)
        out = analyzer(Raising(GrammarUnavailableError("nothing configured here"))).run(ctx)

        assert out.status is AnalyzerStatus.UNAVAILABLE
        assert out.issues == ()
        assert out.score is None
        assert out.detail

    def test_a_configured_engine_that_fails_is_a_fault(self, assessment_context):
        ctx = assessment_context(ANSWER)
        out = analyzer(Raising(GrammarCheckError("the service could not be reached"))).run(ctx)

        assert out.status is AnalyzerStatus.FAILED
        assert out.issues == ()
        assert out.detail

    def test_the_default_configuration_reports_unavailable_rather_than_crashing(
        self, assessment_context
    ):
        # No provider injected: the analyzer builds one through the factory,
        # which on a default deployment is the disabled provider.
        ctx = assessment_context(ANSWER)
        out = GrammarAnalyzer(get_settings()).run(ctx)

        assert out.status is AnalyzerStatus.UNAVAILABLE

    @pytest.mark.parametrize(
        "exception",
        [
            RuntimeError("connection reset"),
            ValueError("bad offset"),
            KeyError("matches"),
            TimeoutError("timed out"),
        ],
        ids=["runtime", "value", "key", "timeout"],
    )
    def test_an_unexpected_provider_exception_is_contained_by_the_supervisor(
        self, exception: Exception, assessment_context
    ):
        """The analyzer catches what it knows about; the supervisor catches the rest.

        Nothing a provider can raise may reach the caller — the student's score
        has already been computed by the time this runs.
        """
        from app.assessment.supervisor import run_analyzers

        result = run_analyzers([analyzer(Raising(exception))], assessment_context(ANSWER))

        assert result.analyzers["grammar"].status is AnalyzerStatus.FAILED
        assert result.issues == ()

    def test_warm_up_probes_the_engine_and_survives_its_absence(self, assessment_context):
        provider = FakeProvider(available=False)
        analyzer(provider).warm_up()

        assert provider.probes == 1

    def test_the_provider_sees_normalised_text_not_the_raw_answer(self, assessment_context):
        # One coordinate system for every analyzer: a grammar offset and a
        # spelling offset mean the same thing before either is mapped back.
        ctx = assessment_context("The chart   go up over the whole of the period shown here.")
        provider = FakeProvider(("go", {}))
        analyzer(provider).run(ctx)

        assert provider.checked == [ctx.normalised.text]

    def test_an_answer_with_no_words_is_not_reported_as_failing(self):
        """Accuracy over nothing is 100%, not zero.

        Zero would be a judgement about grammar that was never tested — the
        same reason a missing class average is ``None`` rather than a nought.
        """
        from app.assessment.analyzers.grammar import _accuracy

        assert _accuracy(errors=0, word_count=0) == 100.0
        assert _accuracy(errors=3, word_count=0) == 100.0
