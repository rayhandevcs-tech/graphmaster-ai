"""Graph accuracy (Feature 6): did the student read the chart correctly?

This is the analyzer with the most educational value and the most dangerous
failure mode. Telling a student their reading of a trend is wrong, when it was
right, is worse than saying nothing at all — so almost every rule here is a
reason *not* to reach a verdict.

The shape of the work:

1. The chart is reduced to facts (:mod:`app.assessment.chart`).
2. The vocabulary detector has **already found and located** every direction,
   peak and comparison term the student used. Those occurrences are the claims;
   this analyzer does not go looking for direction words a second way, because
   two detectors that disagreed about the same sentence would make the result
   indefensible to the student (the same reasoning as rule 34).
3. Each claim is attributed to a series, or to none.
4. A verdict is reached only where both the attribution and the fact are
   unambiguous. Everything else is recorded as ``unverified`` and shown to
   nobody.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assessment import chart as chart_facts
from app.assessment.chart import ChartFacts, SeriesFact
from app.assessment.claims import GraphClaim
from app.assessment.issues import AssessmentIssue
from app.assessment.protocol import AnalyzerOutput, AssessmentContext
from app.assessment.text import real_sentences, sentence_span
from app.core.config import Settings
from app.models.enums import (
    ClaimType,
    ClaimVerdict,
    IssueCategory,
    IssueSeverity,
)

if TYPE_CHECKING:  # pragma: no cover
    from spacy.tokens import Span

#: Vocabulary categories that make a checkable claim, and what kind.
CLAIM_FOR_CATEGORY: dict[str, ClaimType] = {
    "increase": ClaimType.TREND,
    "decrease": ClaimType.TREND,
    "stability": ClaimType.TREND,
    "fluctuation": ClaimType.TREND,
    "peak": ClaimType.PEAK,
    "lowest": ClaimType.TROUGH,
    "comparison": ClaimType.COMPARISON,
}

#: Confidence in an attribution, by how it was made.
#:
#: A one-series chart leaves nothing else the claim could be about, so it is
#: the safest reading available. A distinctive word is nearly as good but can
#: still be defeated by a sentence that mentions one series while describing
#: another.
CONFIDENCE_SINGLE_SERIES = 0.9
CONFIDENCE_NAMED_SERIES = 0.8
CONFIDENCE_COMPARISON = 0.75

#: Words that make a comparison directional, and which way.
COMPARISON_UP = ("high", "great", "more", "larg", "exceed", "above", "outstrip", "overtook", "over")
COMPARISON_DOWN = ("low", "less", "small", "few", "below", "under", "behind")


class GraphAccuracyAnalyzer:
    """Checks what the student said about the chart against the chart."""

    name = "graph_accuracy"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, ctx: AssessmentContext) -> AnalyzerOutput:
        facts = chart_facts.derive(ctx.chart_data, ctx.graph_type)
        if facts is None:
            # A preview with no chart, or a chart too sparse to reduce. Scoring
            # that zero would be a judgement about a reading that was never
            # checkable.
            return AnalyzerOutput(metrics={"claims": 0.0})

        claims = _claims(ctx, facts)
        verified = [c for c in claims if c.is_verified]
        correct = [c for c in verified if c.is_correct]

        issues = tuple(
            issue
            for claim in claims
            if claim.verdict is ClaimVerdict.INCORRECT
            for issue in (_issue_for(claim),)
        )

        return AnalyzerOutput(
            issues=issues,
            claims=tuple(claims),
            # None when nothing could be checked: a chart the student described
            # in language this engine cannot resolve is not a wrong reading.
            score=round(100.0 * len(correct) / len(verified), 2) if verified else None,
            metrics={
                "claims": float(len(claims)),
                "claims_verified": float(len(verified)),
                "claims_correct": float(len(correct)),
                "claims_incorrect": float(len(verified) - len(correct)),
                "claims_unverified": float(len(claims) - len(verified)),
                "series_count": float(len(facts.series)),
            },
        )


# ── Building claims ──────────────────────────────────────────────────────────


def _claims(ctx: AssessmentContext, facts: ChartFacts) -> list[GraphClaim]:
    """One claim per located vocabulary term that makes a checkable statement."""
    sentences = [(s, *sentence_span(ctx, s)) for s in real_sentences(ctx.doc)]
    claims: list[GraphClaim] = []

    for detected in ctx.detection.detected:
        claim_type = CLAIM_FOR_CATEGORY.get(detected.term.category_code)
        if claim_type is None:
            continue

        for occurrence in detected.occurrences:
            sentence = _sentence_containing(sentences, occurrence.start)
            if sentence is None:  # pragma: no cover - every match sits in a sentence
                continue
            claims.append(
                _claim(
                    facts=facts,
                    sentence=sentence,
                    claim_type=claim_type,
                    category=detected.term.category_code,
                    matched=occurrence.matched_form,
                    start=occurrence.start,
                    end=occurrence.end,
                )
            )

    return claims


def _sentence_containing(sentences: list[tuple[Span, int, int]], position: int) -> Span | None:
    for sentence, start, end in sentences:
        if start <= position < end:
            return sentence
    return None


def _claim(
    *,
    facts: ChartFacts,
    sentence: Span,
    claim_type: ClaimType,
    category: str,
    matched: str,
    start: int,
    end: int,
) -> GraphClaim:
    lowered = sentence.text.lower()
    named = _series_named(facts, lowered)

    if claim_type is ClaimType.COMPARISON:
        return _comparison_claim(facts, named, matched, lowered, start, end)

    subject, confidence = _subject(facts, named)
    if subject is None:
        return _unverified(claim_type, matched, "the sentence names no single series", start, end)

    if claim_type is ClaimType.TREND:
        return _trend_claim(facts, subject, category, matched, confidence, start, end)
    return _extreme_claim(facts, subject, claim_type, matched, lowered, confidence, start, end)


def _subject(facts: ChartFacts, named: list[SeriesFact]) -> tuple[SeriesFact | None, float]:
    """Which series a claim is about, and how sure the attribution is."""
    if len(named) == 1:
        return named[0], CONFIDENCE_NAMED_SERIES
    if named:
        # Two series in one sentence, with a claim that is not a comparison.
        # Which one it describes is a guess, and a guess is not worth telling a
        # student they misread their chart.
        return None, 0.0
    single = facts.single_series
    return (single, CONFIDENCE_SINGLE_SERIES) if single else (None, 0.0)


def _series_named(facts: ChartFacts, lowered_sentence: str) -> list[SeriesFact]:
    """Series whose distinctive words appear in the sentence, in order of mention."""
    found: list[tuple[int, SeriesFact]] = []
    for series in facts.series:
        positions = [
            lowered_sentence.find(word)
            for word in series.distinctive_words
            if word in lowered_sentence
        ]
        if positions:
            found.append((min(positions), series))
    return [series for _, series in sorted(found, key=lambda pair: pair[0])]


# ── Verdicts ─────────────────────────────────────────────────────────────────


def _trend_claim(
    facts: ChartFacts,
    subject: SeriesFact,
    category: str,
    matched: str,
    confidence: float,
    start: int,
    end: int,
) -> GraphClaim:
    """Did the series move the way the student said it did?"""
    if not facts.is_sequential:
        # A pie chart is one snapshot, and a bar chart's categories may be in
        # any order — "sales rose" about either is not a claim about movement
        # this engine can judge.
        return _unverified(
            ClaimType.TREND, matched, "this chart type has no ordered axis", start, end
        )

    actual = subject.direction

    if category == "fluctuation":
        if subject.fluctuates:
            return _verdict(
                claim_type=ClaimType.TREND,
                verdict=ClaimVerdict.CORRECT,
                claimed=matched,
                actual="fluctuation",
                subject=subject,
                confidence=confidence,
                start=start,
                end=end,
            )
        if subject.turning_points == 0 and not subject.is_stable:
            return _verdict(
                claim_type=ClaimType.TREND,
                verdict=ClaimVerdict.INCORRECT,
                claimed=matched,
                actual=actual,
                subject=subject,
                confidence=confidence,
                start=start,
                end=end,
            )
        # One turning point is a rise and a fall — a shape with its own
        # vocabulary, and not clearly either.
        return _unverified(ClaimType.TREND, matched, "the series turns only once", start, end)

    if category == "stability":
        verdict = ClaimVerdict.CORRECT if subject.is_stable else ClaimVerdict.INCORRECT
        return _verdict(
            claim_type=ClaimType.TREND,
            verdict=verdict,
            claimed=matched,
            actual=actual,
            subject=subject,
            confidence=confidence,
            start=start,
            end=end,
        )

    # "increase" or "decrease".
    if (category == "increase" and subject.rises) or (category == "decrease" and subject.falls):
        return _verdict(
            claim_type=ClaimType.TREND,
            verdict=ClaimVerdict.CORRECT,
            claimed=matched,
            actual=actual,
            subject=subject,
            confidence=confidence,
            start=start,
            end=end,
        )
    return _verdict(
        claim_type=ClaimType.TREND,
        verdict=ClaimVerdict.INCORRECT,
        claimed=matched,
        actual=actual,
        subject=subject,
        confidence=confidence,
        start=start,
        end=end,
    )


def _extreme_claim(
    facts: ChartFacts,
    subject: SeriesFact,
    claim_type: ClaimType,
    matched: str,
    lowered_sentence: str,
    confidence: float,
    start: int,
    end: int,
) -> GraphClaim:
    """Did the student put the peak or the trough in the right place?

    Only checkable when they named a point on the axis. "Numbers peaked" is
    true of every series that has a maximum, which is all of them.
    """
    expected = subject.peak_label if claim_type is ClaimType.PEAK else subject.trough_label
    mentioned = [
        label for label in subject.point_labels if label and label.lower() in lowered_sentence
    ]

    if not mentioned:
        return _unverified(claim_type, matched, "no point on the axis was named", start, end)
    if expected in mentioned:
        return _verdict(
            claim_type=claim_type,
            verdict=ClaimVerdict.CORRECT,
            claimed=matched,
            actual=expected,
            subject=subject,
            confidence=confidence,
            start=start,
            end=end,
        )
    if len(mentioned) > 1:
        # Several points named in one sentence — "between 2019 and 2022 it
        # peaked" describes a window, not a position.
        return _unverified(claim_type, matched, "several points were named", start, end)
    return _verdict(
        claim_type=claim_type,
        verdict=ClaimVerdict.INCORRECT,
        claimed=matched,
        actual=expected,
        subject=subject,
        confidence=confidence,
        start=start,
        end=end,
    )


def _comparison_claim(
    facts: ChartFacts,
    named: list[SeriesFact],
    matched: str,
    lowered_sentence: str,
    start: int,
    end: int,
) -> GraphClaim:
    """Did the student get the relationship between two series the right way round?

    Judged only when one series sits above the other at *every* reading. Where
    the lines cross, the claim depends on a period the student may not have
    named, and this returns nothing rather than guessing.
    """
    if len(named) != 2:
        return _unverified(
            ClaimType.COMPARISON, matched, "the sentence does not name two series", start, end
        )

    upward = _comparison_direction(matched, lowered_sentence)
    if upward is None:
        return _unverified(
            ClaimType.COMPARISON, matched, "the comparison has no direction", start, end
        )

    subject, other = named
    # Pairwise. A student comparing hydroelectric with wind has said nothing
    # about solar, and asking "is either above everything else" would leave
    # every comparison on a three-series chart unchecked.
    dominant = facts.dominant(subject, other)
    if dominant is None:
        return _unverified(
            ClaimType.COMPARISON, matched, "the two series cross each other", start, end
        )

    subject_is_higher = dominant.label == subject.label
    verdict = ClaimVerdict.CORRECT if subject_is_higher == upward else ClaimVerdict.INCORRECT

    return _verdict(
        claim_type=ClaimType.COMPARISON,
        verdict=verdict,
        claimed=matched,
        actual=f"{dominant.label} is the higher",
        subject=subject,
        confidence=CONFIDENCE_COMPARISON,
        start=start,
        end=end,
    )


def _comparison_direction(matched: str, lowered_sentence: str) -> bool | None:
    """``True`` for "greater than", ``False`` for "less than", ``None`` if unclear."""
    for text in (matched.lower(), lowered_sentence):
        if any(cue in text for cue in COMPARISON_UP):
            return True
        if any(cue in text for cue in COMPARISON_DOWN):
            return False
    return None


def _verdict(
    *,
    claim_type: ClaimType,
    verdict: ClaimVerdict,
    claimed: str,
    actual: str,
    subject: SeriesFact,
    confidence: float,
    start: int,
    end: int,
) -> GraphClaim:
    return GraphClaim(
        claim_type=claim_type,
        verdict=verdict,
        claimed=claimed,
        actual=actual,
        series_label=subject.label,
        start=start,
        end=end,
        confidence=confidence,
    )


def _unverified(
    claim_type: ClaimType, claimed: str, reason: str, start: int, end: int
) -> GraphClaim:
    return GraphClaim(
        claim_type=claim_type,
        verdict=ClaimVerdict.UNVERIFIED,
        claimed=claimed,
        actual=reason,
        series_label=None,
        start=start,
        end=end,
        confidence=0.0,
    )


# ── Turning a contradiction into something the student can act on ────────────

#: Wording for each direction, in the student's own register.
DIRECTION_WORDS = {
    "increase": "rises",
    "decrease": "falls",
    "stability": "stays roughly level",
}


def _issue_for(claim: GraphClaim) -> AssessmentIssue:
    """The correction for a contradicted claim.

    Phrased as what the chart shows, never as an accusation about the student.
    A misread trend is the most useful thing this platform can tell somebody,
    and it is only useful if they read it.
    """
    series = claim.series_label or "this series"

    if claim.claim_type is ClaimType.TREND:
        actual = DIRECTION_WORDS.get(claim.actual, claim.actual)
        explanation = (
            f"You described {series} as “{claim.claimed}”, but the chart {actual} "
            f"across the period. Check the first and last values before describing "
            f"the trend."
        )
        # The one finding so far that changes what the writing *means*: a
        # student who reports the opposite trend has described a different
        # chart. A claim about a level series is wrong but not inverted.
        severity = IssueSeverity.HIGH if claim.actual != "stability" else IssueSeverity.MEDIUM
    elif claim.claim_type is ClaimType.COMPARISON:
        explanation = (
            f"You put {series} on the wrong side of this comparison: in the chart, "
            f"{claim.actual} throughout the period."
        )
        severity = IssueSeverity.HIGH
    else:
        where = "highest" if claim.claim_type is ClaimType.PEAK else "lowest"
        explanation = f"{series} is {where} at {claim.actual}, not where this sentence places it."
        severity = IssueSeverity.MEDIUM

    return AssessmentIssue(
        category=IssueCategory.GRAPH_ACCURACY,
        subtype=f"incorrect_{claim.claim_type.value}",
        severity=severity,
        original_text=claim.claimed,
        explanation=explanation,
        start=claim.start,
        end=claim.end,
        confidence=claim.confidence,
        source="chart",
    )


__all__ = ["GraphAccuracyAnalyzer"]
