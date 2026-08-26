"""The guarantee: nothing in the assessment engine can move a score.

This is the executable form of decision D1. The assessment pipeline exists to
explain a student's mistakes, and explaining is all it may do — the moment a
grammar error can nudge ``final_score``, every score already in the corpus
becomes incomparable with everything scored afterwards, every leaderboard
re-ranks, and reward tiers shift under students who have already been told
what they earned.

Two of these tests are written to fail loudly if a future sprint takes a
shortcut. They are the reason the framework was built before any analyzer that
actually finds something.
"""

from __future__ import annotations

import inspect

import pytest

from app.assessment.protocol import AnalyzerOutput, AssessmentContext
from app.assessment.registry import BUILDERS
from app.core.config import get_settings
from app.models.enums import AnalyzerStatus, IssueCategory, IssueSeverity
from app.nlp.analyzer import analyse
from app.nlp.scoring import build_score

pytestmark = pytest.mark.usefixtures("spacy_model")


@pytest.fixture
def targets(term_factory):
    return [
        term_factory("increase"),
        term_factory("fall", category="decrease"),
        term_factory("fluctuate", category="fluctuation"),
        term_factory("peak", category="peak"),
        term_factory("higher than", category="comparison"),
    ]


#: A spread of answers rather than one: a guarantee that holds only for the
#: happy path is not a guarantee. Two of these deliberately score badly.
CORPUS = [
    "Sales increased.",
    (
        "The graph shows the number of visitors to three attractions between 2019 "
        "and 2024. Overall, visitor numbers increased at the museum while the "
        "gallery fell steadily. Numbers at the castle fluctuated throughout the "
        "period, reaching a peak in 2022 before declining again. The museum was "
        "consistently higher than the other two attractions."
    ),
    "no vocabulary here at all just some plain words about nothing much",
    "increase increase increase increase increase increase increase increase",
    (
        "Overall the chart illustrates a clear upward trend. Sales increased "
        "sharply in the first quarter, then fell back before recovering. "
        "Revenue fluctuated more than costs did, and the peak came in June "
        "when the figure was considerably higher than at any earlier point."
    ),
]


# ── D1: the score is identical with and without assessment ───────────────────


@pytest.mark.parametrize("text", CORPUS)
def test_the_score_is_identical_whether_or_not_assessment_runs(text: str, targets):
    """Field by field, not just the final number.

    Comparing only ``final_score`` would miss a change to the detected terms,
    the category breakdown or the tier — each of which is stored, displayed
    and analysed independently.
    """
    settings = get_settings()
    off = settings.model_copy(update={"ASSESSMENT_ENABLED": False})

    without = analyse(text, targets, settings=off).to_score_fields()
    with_it = analyse(text, targets, settings=settings).to_score_fields()

    assert with_it == without


@pytest.mark.parametrize("text", CORPUS)
def test_the_assessment_is_absent_when_disabled_and_present_when_not(text: str, targets):
    settings = get_settings()
    off = settings.model_copy(update={"ASSESSMENT_ENABLED": False})

    assert analyse(text, targets, settings=off).assessment is None
    assert analyse(text, targets, settings=settings).assessment is not None


def test_to_score_fields_carries_no_assessment_key(targets):
    """The stored ``Score`` row must not gain a column by accident.

    A new key here would silently become a new column expectation in
    ``SubmissionService.analyse``, which passes this dictionary straight into
    the model constructor.
    """
    result = analyse("Sales increased and then fell.", targets)

    assert result.assessment is not None  # it ran
    fields = result.to_score_fields()
    assert not any("assessment" in key for key in fields)
    # The exact set the Score model expects, frozen.
    assert set(fields) == {
        "vocabulary_score",
        "writing_score",
        "final_score",
        "vocabulary_percentage",
        "detected_count",
        "unique_detected_count",
        "total_target_count",
        "detected_terms",
        "missing_terms",
        "category_breakdown",
        "writing_breakdown",
        "reward_tier",
        "feedback",
        "engine_version",
    }


def test_build_score_cannot_see_an_assessment():
    """Structural, not behavioural — and that is the point.

    A behavioural test can only prove that today's assessment does not change
    today's score. This proves the scoring function has no parameter through
    which one could be passed, so a future sprint cannot wire them together
    without deleting this test and explaining why.
    """
    parameters = set(inspect.signature(build_score).parameters)

    assert parameters == {"detection", "writing", "targets", "settings"}


def test_the_engine_version_does_not_move_when_assessment_configuration_does(targets):
    """D6: two versions, because they change for different reasons.

    Turning an analyzer on changes nothing about how a score was computed. If
    it moved ``engine_version``, a run of numerically identical scores would be
    marked as belonging to a different engine — breaking exactly the cohort
    comparison that field exists to protect.
    """
    settings = get_settings()
    changed = settings.model_copy(
        update={"ASSESSMENT_ANALYZERS": "writing", "ASSESSMENT_ISSUE_CONFIDENCE_FLOOR": 0.9}
    )

    before = analyse("Sales increased sharply.", targets, settings=settings)
    after = analyse("Sales increased sharply.", targets, settings=changed)

    assert before.engine_version == after.engine_version
    assert before.assessment is not None and after.assessment is not None
    assert before.assessment.version != after.assessment.version


# ── A broken analyzer must not cost the student their submission ─────────────


class Exploding:
    """An analyzer that fails the way a real one eventually will.

    Carries the name of whichever analyzer it stands in for, so the supervisor
    records the failure under the name the rest of the system knows.
    """

    def __init__(self, exception: Exception, name: str = "exploding") -> None:
        self._exception = exception
        self.name = name

    def run(self, ctx: AssessmentContext) -> AnalyzerOutput:
        raise self._exception


@pytest.mark.parametrize(
    "exception",
    [
        RuntimeError("provider connection reset"),
        ValueError("could not parse the span"),
        KeyError("series_label"),
        ZeroDivisionError("no sentences to average over"),
        AttributeError("'NoneType' object has no attribute 'text'"),
    ],
    ids=["runtime", "value", "key", "zero-division", "attribute"],
)
def test_an_analyzer_that_raises_does_not_break_the_analysis(exception: Exception, targets):
    from app.assessment import registry

    settings = get_settings().model_copy(
        update={"ASSESSMENT_ANALYZERS": "vocabulary,exploding,writing"}
    )
    text = "The graph shows sales increased before they fell back again."

    baseline = analyse(text, targets, settings=settings).to_score_fields()

    builders = dict(BUILDERS)
    builders["exploding"] = lambda _settings: Exploding(exception)
    registry.BUILDERS = builders
    try:
        result = analyse(text, targets, settings=settings)
    finally:
        registry.BUILDERS = BUILDERS

    # The score is untouched…
    assert result.to_score_fields() == baseline

    # …the failure is recorded rather than swallowed…
    assert result.assessment is not None
    assert result.assessment.analyzers["exploding"].status is AnalyzerStatus.FAILED
    assert result.assessment.failed_analyzers == ("exploding",)
    assert result.assessment.is_complete is False

    # …the detail names the fault without quoting the student's writing…
    detail = result.assessment.analyzers["exploding"].detail
    assert detail is not None
    assert type(exception).__name__ in detail

    # …and the analyzers either side of it still ran.
    assert result.assessment.analyzers["vocabulary"].ran
    assert result.assessment.analyzers["writing"].ran


def test_every_registered_analyzer_can_fail_alone(targets):
    """Each analyzer in turn, so no single one is load-bearing.

    Parametrised over the registry rather than a hardcoded list, so an
    analyzer added in a later sprint is covered the moment it is registered.
    """
    from app.assessment import registry

    text = "Sales increased steadily and then fell to a low point."
    baseline = analyse(text, targets).to_score_fields()

    for name in BUILDERS:
        builders = dict(BUILDERS)
        builders[name] = lambda _settings, broken=name: Exploding(
            RuntimeError(f"{broken} is broken"), name=broken
        )
        registry.BUILDERS = builders
        try:
            result = analyse(text, targets)
        finally:
            registry.BUILDERS = BUILDERS

        assert result.to_score_fields() == baseline, f"{name} moved the score when it failed"
        assert result.assessment is not None
        assert result.assessment.analyzers[name].status is AnalyzerStatus.FAILED


def test_an_assessment_that_cannot_be_assembled_leaves_the_score_intact(targets, monkeypatch):
    """The outer belt, above the supervisor.

    The supervisor contains an analyzer's failure; this contains a failure
    *building* the pipeline — a malformed configuration, a builder that raises
    at construction — which happens before any analyzer is called.
    """
    from app.assessment import engine

    def refuse(_settings):
        raise RuntimeError("registry is corrupt")

    text = "Sales increased and then fell."
    baseline = analyse(text, targets).to_score_fields()

    monkeypatch.setattr(engine, "build_analyzers", refuse)
    result = analyse(text, targets)

    assert result.to_score_fields() == baseline
    assert result.assessment is None


# ── Grammar is diagnostic, and only diagnostic ───────────────────────────────


class LoudGrammarProvider:
    """A grammar engine that objects to almost every word.

    Deliberately extreme. A guarantee that holds when the checker finds two
    problems is not the guarantee being made here: the claim is that grammar
    cannot move a score *at all*, so the test drives it with a provider that
    would sink the answer if it could.
    """

    name = "loud"

    def is_available(self) -> bool:
        return True

    def check(self, text: str, *, language: str):
        from app.assessment.grammar.base import GrammarMatch, GrammarReport
        from app.models.enums import IssueSeverity

        matches = []
        offset = 0
        for word in text.split(" "):
            if len(word) > 3:
                matches.append(
                    GrammarMatch(
                        subtype="subject_verb_agreement",
                        severity=IssueSeverity.HIGH,
                        original_text=word,
                        explanation="That does not agree with its subject.",
                        start=offset,
                        end=offset + len(word),
                        suggested_text=word + "s",
                        confidence=1.0,
                        rule_id="TEST_EVERYTHING_IS_WRONG",
                    )
                )
            offset += len(word) + 1
        return GrammarReport(matches=tuple(matches), provider=self.name, checked_chars=len(text))


def with_loud_grammar():
    """A registry whose grammar analyzer is backed by the noisy provider."""
    from app.assessment.analyzers.grammar import GrammarAnalyzer

    builders = dict(BUILDERS)
    builders["grammar"] = lambda settings: GrammarAnalyzer(settings, provider=LoudGrammarProvider())
    return builders


@pytest.mark.parametrize("text", CORPUS)
def test_grammar_findings_cannot_move_the_score(text: str, targets):
    """The Sprint 18 form of D1, field by field.

    ``final_score``, ``vocabulary_score``, ``writing_score``,
    ``vocabulary_percentage`` and ``reward_tier`` are all in
    ``to_score_fields``, and every one of them is compared — a grammar result
    that moved the tier without moving the number would be just as fatal to
    the corpus's comparability.
    """
    from app.assessment import registry

    baseline = analyse(text, targets).to_score_fields()

    registry.BUILDERS = with_loud_grammar()
    try:
        result = analyse(text, targets)
    finally:
        registry.BUILDERS = BUILDERS

    assert result.to_score_fields() == baseline

    # The grammar analyzer really did run and really did find a great deal.
    grammar = result.assessment.analyzers["grammar"]
    assert grammar.status is AnalyzerStatus.OK
    assert grammar.metrics["grammar_issue_count"] > 0 or len(text.split()) < 4


def test_the_grammar_score_is_reported_beside_the_final_score_never_inside_it(targets):
    """A low grammar figure alongside an untouched final score.

    This is the shape the whole design exists to produce: the student is told
    their grammar needs work *and* marked on the vocabulary and writing they
    were assessed on, with no arithmetic between the two.
    """
    from app.assessment import registry

    text = CORPUS[1]
    baseline = analyse(text, targets)

    registry.BUILDERS = with_loud_grammar()
    try:
        result = analyse(text, targets)
    finally:
        registry.BUILDERS = BUILDERS

    grammar = result.assessment.analyzers["grammar"]
    assert grammar.score == 0.0, "the noisy provider should have sunk the grammar figure"
    assert result.score.final_score == baseline.score.final_score
    assert result.score.reward_tier is baseline.score.reward_tier


def test_the_xp_and_tier_inputs_are_untouched_by_grammar(targets):
    """XP, achievements and the leaderboard all read the score, and nothing else.

    They are not tested here by re-running the gamification engine — they are
    tested by proving the *only* values it reads are identical. A field the
    awarding code cannot see cannot change what it awards.
    """
    from app.assessment import registry

    text = CORPUS[4]
    baseline = analyse(text, targets)

    registry.BUILDERS = with_loud_grammar()
    try:
        result = analyse(text, targets)
    finally:
        registry.BUILDERS = BUILDERS

    assert result.score.final_score == baseline.score.final_score
    assert result.score.vocabulary_percentage == baseline.score.vocabulary_percentage
    assert result.score.reward_tier is baseline.score.reward_tier
    assert result.engine_version == baseline.engine_version


def test_changing_the_grammar_provider_moves_the_assessment_version_alone(targets):
    """Feature 8. The provider is part of the diagnostic configuration.

    Two answers checked by different engines are not comparable as
    assessments, so the fingerprint has to say so — and neither of them was
    scored differently, so ``engine_version`` must not move.
    """
    settings = get_settings()
    local = settings.model_copy(
        update={"GRAMMAR_PROVIDER": "local", "GRAMMAR_HOST": "lt", "GRAMMAR_PORT": 8081}
    )

    before = analyse("Sales increased sharply.", targets, settings=settings)
    after = analyse("Sales increased sharply.", targets, settings=local)

    assert before.engine_version == after.engine_version
    assert before.assessment.version != after.assessment.version


def test_changing_the_grammar_language_moves_the_assessment_version(targets):
    """en-GB and en-US disagree about enough that two answers checked under
    them are not comparable as assessments."""
    settings = get_settings()
    american = settings.model_copy(update={"GRAMMAR_LANGUAGE": "en-US"})

    before = analyse("Sales increased sharply.", targets, settings=settings)
    after = analyse("Sales increased sharply.", targets, settings=american)

    assert before.engine_version == after.engine_version
    assert before.assessment.version != after.assessment.version


def test_a_grammar_provider_that_is_absent_leaves_the_assessment_complete(targets):
    """A deployment fact is not a fault.

    Every server running the default configuration has no grammar engine. If
    that marked their assessments partial, the status would mean nothing.
    """
    result = analyse(CORPUS[1], targets)

    assert result.assessment.analyzers["grammar"].status is AnalyzerStatus.UNAVAILABLE
    assert result.assessment.is_complete is True


# ── D4: the integrity result is not reachable from here ──────────────────────


def test_the_assessment_result_carries_no_integrity_surface():
    """D4, held in place before the integrity engine exists.

    Integrity is teacher-facing: a student must never see a risk score, a
    probability, a percentage or an AI-related label. The cheapest way to keep
    that true is for the object the student's result page is built from to have
    no such field at all, so the leak cannot be made by a careless serialiser.
    """
    from app.assessment.result import AssessmentResult

    forbidden = {"risk", "integrity", "ai_", "probability", "suspicion", "plagiar"}
    exposed = {name for name in dir(AssessmentResult) if not name.startswith("_")}

    for name in exposed:
        assert not any(word in name.lower() for word in forbidden), (
            f"AssessmentResult.{name} looks like an integrity field. Integrity is "
            f"teacher-only (D4) and belongs on its own model, not on the one the "
            f"student's result page is built from."
        )


def test_issue_categories_contain_nothing_a_student_should_not_see():
    """No category may name cheating, AI, or risk.

    An issue is shown to the student with its category. A category called
    ``ai_generated`` would put an accusation on their screen no matter how the
    surrounding copy was worded.
    """
    forbidden = {"ai", "risk", "integrity", "cheat", "plagiarism", "suspicious"}

    for category in IssueCategory:
        assert category.value.lower() not in forbidden
        assert "ai_" not in category.value.lower()


def test_severity_can_express_a_preference_without_calling_it_a_mistake():
    """Feature 5: acceptable stylistic variation is never penalised.

    ``INFO`` is not the bottom of a ladder of badness — it is the rung that
    means "this is not a mistake". The distinction has to live in the type, or
    a suggestion is only a convention the next contributor can forget.
    """
    assert {s.value for s in IssueSeverity} == {"info", "low", "medium", "high"}
    assert IssueSeverity.INFO.is_mistake is False
    assert all(s.is_mistake for s in IssueSeverity if s is not IssueSeverity.INFO)


def test_the_severity_scale_is_ordered():
    # StrEnum sorts alphabetically, which would put "high" below "info".
    ordered = sorted(IssueSeverity, key=lambda s: s.rank)
    assert ordered == [
        IssueSeverity.INFO,
        IssueSeverity.LOW,
        IssueSeverity.MEDIUM,
        IssueSeverity.HIGH,
    ]
