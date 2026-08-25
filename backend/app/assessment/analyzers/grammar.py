"""Grammar (Feature 1).

The only analyzer with an outbound dependency, and the only one that can be
switched off by a deployment decision rather than a missing model. Everything
about its shape follows from those two facts.

**It is diagnostic, like every analyzer here.** Nothing it produces reaches
``build_score``. A student with fifteen grammar errors and a student with none
receive the same ``final_score`` for the same vocabulary and the same writing
quality, earn the same XP, and sit in the same place on the leaderboard. That
is asserted in ``tests/unit/test_assessment_isolation.py`` rather than left to
intention, and the reason is in ``app/assessment/__init__.py``: folding
grammar into the score would re-rank every board and make the corpus scored
before it incomparable with everything after.

**It never names its provider to a student.** The endpoint, the engine and the
failure type are operator facts. They travel in ``detail`` and in the logs,
which the audience filter keeps away from students, and they are never written
into an issue's explanation.

**Its findings are narrower than LanguageTool's.** Misspellings and style
matches are dropped rather than reported, because two analyzers reporting the
same ground is how a result page starts contradicting itself — see
``app/assessment/grammar/rules.py``.
"""

from __future__ import annotations

from app.assessment.grammar.base import (
    GrammarCheckError,
    GrammarMatch,
    GrammarProvider,
    GrammarUnavailableError,
)
from app.assessment.grammar.factory import build_grammar_provider
from app.assessment.issues import AssessmentIssue
from app.assessment.protocol import AnalyzerOutput, AssessmentContext
from app.assessment.text import real_words, scale, span_in_original
from app.core.config import Settings
from app.core.logging import get_logger
from app.models.enums import AnalyzerStatus, IssueCategory

logger = get_logger(__name__)

#: Errors per word at or below which the answer earns full marks.
#:
#: Not zero. One agreement slip in a two-hundred-word description is not the
#: same failure as a page of them, and a scale that only rewards perfection
#: tells a student nothing about the distance between the two.
ACCURACY_CEILING = 99.0

#: Accuracy mapped to zero: one error in every ten words. Wide on purpose —
#: a narrow band turns two slips in a short answer into a failing grammar
#: figure, which says more about the answer's length than about its grammar.
ACCURACY_FLOOR = 90.0

#: Answers shorter than this are checked but not scored.
#:
#: A single error in a six-word sentence is 83% accuracy, which would be
#: reported beside a mark for work the student did well. The issues are still
#: shown; it is the *number* that is withheld, because it would not mean
#: anything.
MIN_WORDS_FOR_SCORE = 25


class GrammarAnalyzer:
    """Checks grammar through an injected provider, and survives its absence."""

    name = "grammar"

    def __init__(self, settings: Settings, *, provider: GrammarProvider | None = None) -> None:
        self.settings = settings
        # Injected, or built by the factory — never constructed here. The
        # analyzer names no engine, which is what lets every path through it be
        # exercised against a fake with no network, no JVM and no container.
        self.provider = provider if provider is not None else build_grammar_provider(settings)

    def warm_up(self) -> None:
        """Probe the engine during boot.

        The probe's answer is cached with a time to live, so this moves one
        round trip off whichever student submits first after a restart. A
        failure here is not fatal and is not even final: a negative probe
        expires, so a platform that started before its engine did will find it
        on the next submission rather than staying broken until a restart.
        """
        self.provider.is_available()

    def run(self, ctx: AssessmentContext) -> AnalyzerOutput:
        # Checked against the same normalised text every other analyzer reads,
        # so a grammar offset and a spelling offset mean the same thing before
        # either is mapped back. Checking the original instead would put this
        # analyzer on a different coordinate system from the rest.
        text = ctx.normalised.text

        try:
            report = self.provider.check(text, language=self.settings.GRAMMAR_LANGUAGE)
        except GrammarUnavailableError as exc:
            # A deployment fact, not a fault: the assessment stays *complete*.
            # Reporting this as a failure would leave every server without a
            # grammar engine permanently marked as producing partial results.
            return AnalyzerOutput(status=AnalyzerStatus.UNAVAILABLE, detail=str(exc))
        except GrammarCheckError as exc:
            # A configured engine that did not answer. This one *is* a fault,
            # and it is worth someone's attention — but not the student's
            # submission, which has already been scored by the time this runs.
            logger.warning("Grammar check failed: %s", exc)
            return AnalyzerOutput(status=AnalyzerStatus.FAILED, detail=str(exc))

        issues = tuple(_issue_from(ctx, match) for match in report.matches)
        word_count = len(real_words(ctx.doc))

        floor = self.settings.ASSESSMENT_ISSUE_CONFIDENCE_FLOOR
        # Counted the way the student sees it: only findings that assert a
        # mistake, and only ones confident enough to be shown. Marking someone
        # down for an issue captioned "we are not sure about this" — or for a
        # style note that is explicitly not a mistake — is the contradiction
        # the severity scale exists to prevent.
        counted = [i for i in issues if i.is_mistake and i.confidence >= floor]

        accuracy = _accuracy(len(counted), word_count)
        return AnalyzerOutput(
            issues=issues,
            score=(
                scale(accuracy, ACCURACY_FLOOR, ACCURACY_CEILING)
                if word_count >= MIN_WORDS_FOR_SCORE
                else None
            ),
            metrics={
                "grammar_issue_count": float(len(counted)),
                "grammar_accuracy_percentage": accuracy,
                "words_checked": float(word_count),
                "characters_checked": float(report.checked_chars),
                "suggestions_offered": float(sum(1 for i in issues if i.suggested_text)),
                "advisory_count": float(sum(1 for i in issues if not i.is_mistake)),
                # The provider's own cost, separate from the analyzer's. This
                # is the number that answers whether a remote engine is worth
                # its round trip.
                "provider_latency_ms": round(report.latency_ms, 3),
            },
        )


def _accuracy(errors: int, word_count: int) -> float:
    """Words free of a reported error, as a percentage.

    Per word rather than per sentence: sentence counts come from the parser's
    own segmentation, and a run-on sentence — which is itself a grammar
    finding — would shrink the denominator and flatter the answer that
    contained it.
    """
    if word_count <= 0:
        return 100.0
    return round(100.0 * max(0.0, 1.0 - errors / word_count), 2)


def _issue_from(ctx: AssessmentContext, match: GrammarMatch) -> AssessmentIssue:
    """One provider match, as an issue against the student's original text.

    The span is mapped back through the normalisation index. The provider saw
    normalised text — folded quotes, collapsed whitespace — so its offsets are
    indices into a string the student never wrote, and a highlight built from
    one lands on the wrong words.
    """
    start, end = span_in_original(ctx, match.start, match.end)
    return AssessmentIssue(
        category=IssueCategory.GRAMMAR,
        subtype=match.subtype,
        severity=match.severity,
        # From the student's own text rather than the provider's copy of it,
        # so the quoted words are the ones they will find in their answer.
        original_text=ctx.text[start:end],
        suggested_text=match.suggested_text,
        explanation=match.explanation,
        start=start,
        end=end,
        confidence=match.confidence,
        # The rule, not the endpoint. Enough to audit a false positive back to
        # its cause; nothing an operator would mind a teacher seeing.
        source=match.rule_id or "languagetool",
    )


__all__ = ["GrammarAnalyzer"]
