"""Sentence quality and answer length (Features 3 and 4).

Two of the specification's features live here because they measure the same
object. Word count, sentence count, paragraph count and mean sentence length
are all readings off one parse, and splitting them across two analyzers would
mean two passes and two chances for the numbers to disagree.

Everything this produces is *about the shape of the writing*, never about the
words chosen — that is the word-usage analyzer next door.
"""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

from app.assessment.issues import AssessmentIssue
from app.assessment.protocol import AnalyzerOutput, AssessmentContext
from app.assessment.text import (
    flesch_reading_ease,
    paragraph_count,
    real_sentences,
    real_words,
    scale,
    sentence_span,
    syllables,
)
from app.core.config import Settings
from app.models.enums import IssueCategory, IssueSeverity

if TYPE_CHECKING:  # pragma: no cover
    from spacy.tokens import Span

#: A sentence longer than this has usually lost its reader.
#:
#: Well above the 25-word top of the rubric's *mean* band: a single long
#: sentence among short ones is good writing, and flagging at the mean would
#: punish variety — the thing this analyzer is trying to encourage.
OVERLONG_SENTENCE = 40

#: Consecutive sentences opening on the same word before it reads as a tic.
#:
#: Three, not two. "The graph shows… The figure for…" is ordinary; a third in
#: a row is the pattern a marker would circle.
REPEATED_OPENINGS = 3

#: Coefficient of variation of sentence length. Below the floor every sentence
#: is the same length, which reads as a list; the ceiling is where variety
#: stops adding anything.
VARIETY_FLOOR = 0.15
VARIETY_TARGET = 0.45

#: Flesch reading ease. Academic description sits in this band: below it the
#: prose is impenetrable, above it the register has slipped towards speech.
READABILITY_MIN = 30.0
READABILITY_MAX = 65.0
READABILITY_ZERO_LOW = 5.0
READABILITY_ZERO_HIGH = 95.0

#: Long enough that a single block of text is genuinely hard to read.
PARAGRAPH_EXPECTED_ABOVE = 120

#: Multiple of the target maximum past which an answer is flagged as over-long.
OVERLONG_ANSWER_FACTOR = 1.5


class SentenceAnalyzer:
    """Length, variety, readability and the shape of the answer."""

    name = "sentence"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, ctx: AssessmentContext) -> AnalyzerOutput:
        words = real_words(ctx.doc)
        sentences = real_sentences(ctx.doc)

        if not sentences:
            # Nothing was segmented as a sentence. Scoring that zero would be
            # a judgement about sentence quality where there are no sentences.
            return AnalyzerOutput(metrics={"sentence_count": 0.0})

        lengths = [len([t for t in s if not t.is_punct and not t.is_space]) for s in sentences]
        syllable_count = sum(syllables(t.text) for t in words)
        paragraphs = paragraph_count(ctx.text)

        mean_length = statistics.fmean(lengths)
        stdev = statistics.pstdev(lengths) if len(lengths) > 1 else 0.0
        variation = stdev / mean_length if mean_length else 0.0
        readability = flesch_reading_ease(len(words), len(sentences), syllable_count)

        issues: list[AssessmentIssue] = []
        issues.extend(self._length_issues(ctx, len(words)))
        issues.extend(_overlong_sentences(ctx, sentences, lengths))
        issues.extend(_repeated_openings(ctx, sentences))
        issues.extend(_variety_issue(ctx, sentences, variation))
        issues.extend(_paragraph_issue(ctx, len(words), paragraphs))
        issues.extend(_overview_issue(ctx, sentences))

        variety_score = scale(variation, VARIETY_FLOOR, VARIETY_TARGET)
        readability_score = _readability_score(readability)
        flow_score = round(
            100.0 * sum(1 for length in lengths if length <= OVERLONG_SENTENCE) / len(lengths), 2
        )

        return AnalyzerOutput(
            issues=tuple(issues),
            score=round((variety_score + readability_score + flow_score) / 3, 2),
            metrics={
                "word_count": float(len(words)),
                "sentence_count": float(len(sentences)),
                "paragraph_count": float(paragraphs),
                "mean_sentence_length": round(mean_length, 2),
                "sentence_length_stdev": round(stdev, 2),
                "length_variation": round(variation, 4),
                "longest_sentence": float(max(lengths)),
                "shortest_sentence": float(min(lengths)),
                "readability": readability,
                "variety_score": variety_score,
                "readability_score": readability_score,
                "flow_score": flow_score,
            },
        )

    def _length_issues(self, ctx: AssessmentContext, word_count: int) -> list[AssessmentIssue]:
        """Feature 3: is the answer the length the task asks for?

        The band comes from configuration, never a literal — the same values
        the rubric scores against, so the advice and the mark agree.
        """
        minimum = self.settings.TARGET_WORD_COUNT_MIN
        maximum = self.settings.TARGET_WORD_COUNT_MAX
        whole = (0, len(ctx.text))

        if word_count < minimum:
            return [
                AssessmentIssue(
                    category=IssueCategory.SENTENCE,
                    subtype="answer_too_short",
                    severity=IssueSeverity.MEDIUM,
                    original_text="",
                    explanation=(
                        f"Your answer is {word_count} words. Aim for {minimum}–{maximum}: a "
                        f"shorter description cannot cover the overview, the main trends and a "
                        f"comparison."
                    ),
                    start=whole[0],
                    end=whole[1],
                    confidence=1.0,
                    source="length",
                )
            ]

        if word_count > maximum * OVERLONG_ANSWER_FACTOR:
            return [
                AssessmentIssue(
                    category=IssueCategory.SENTENCE,
                    subtype="answer_too_long",
                    severity=IssueSeverity.LOW,
                    original_text="",
                    explanation=(
                        f"Your answer is {word_count} words against a target of "
                        f"{minimum}–{maximum}. Describing every data point is not the task; "
                        f"selecting the important ones is."
                    ),
                    start=whole[0],
                    end=whole[1],
                    confidence=1.0,
                    source="length",
                )
            ]

        return []


def _overlong_sentences(
    ctx: AssessmentContext, sentences: list[Span], lengths: list[int]
) -> list[AssessmentIssue]:
    issues: list[AssessmentIssue] = []
    for sentence, length in zip(sentences, lengths, strict=True):
        if length <= OVERLONG_SENTENCE:
            continue
        start, end = sentence_span(ctx, sentence)
        issues.append(
            AssessmentIssue(
                category=IssueCategory.SENTENCE,
                subtype="overlong_sentence",
                severity=IssueSeverity.LOW,
                original_text=ctx.text[start:end],
                explanation=(
                    f"This sentence runs to {length} words. Splitting it in two would make the "
                    f"trend it describes easier to follow."
                ),
                start=start,
                end=end,
                confidence=0.85,
                source="structure",
            )
        )
    return issues


def _repeated_openings(ctx: AssessmentContext, sentences: list[Span]) -> list[AssessmentIssue]:
    """Consecutive sentences that begin the same way.

    Compared on the lemma, so "The graph shows" and "The graphs showed" count
    as the same opening — which is how a reader hears them.
    """
    issues: list[AssessmentIssue] = []
    run_start = 0
    openings = [_opening_lemma(s) for s in sentences]

    for index in range(1, len(openings) + 1):
        same = index < len(openings) and openings[index] and openings[index] == openings[run_start]
        if same:
            continue

        run_length = index - run_start
        if run_length >= REPEATED_OPENINGS and openings[run_start]:
            start, _ = sentence_span(ctx, sentences[run_start])
            _, end = sentence_span(ctx, sentences[index - 1])
            issues.append(
                AssessmentIssue(
                    category=IssueCategory.SENTENCE,
                    subtype="repeated_sentence_opening",
                    severity=IssueSeverity.INFO,
                    original_text=ctx.text[start:end],
                    explanation=(
                        f"{run_length} sentences in a row begin with “{openings[run_start]}”. "
                        f"Varying the opening makes the description read less like a list."
                    ),
                    start=start,
                    end=end,
                    confidence=0.8,
                    source="structure",
                )
            )
        run_start = index

    return issues


def _opening_lemma(sentence: Span) -> str:
    for token in sentence:
        if not token.is_punct and not token.is_space:
            return token.lemma_.lower()
    return ""


def _variety_issue(
    ctx: AssessmentContext, sentences: list[Span], variation: float
) -> list[AssessmentIssue]:
    if len(sentences) < 4 or variation >= VARIETY_FLOOR:
        return []
    return [
        AssessmentIssue(
            category=IssueCategory.SENTENCE,
            subtype="low_sentence_variety",
            severity=IssueSeverity.INFO,
            original_text="",
            explanation=(
                "Your sentences are all about the same length. Mixing a short sentence in "
                "after two longer ones is what makes a description feel deliberate rather "
                "than mechanical."
            ),
            start=0,
            end=len(ctx.text),
            confidence=0.75,
            source="structure",
        )
    ]


def _paragraph_issue(
    ctx: AssessmentContext, word_count: int, paragraphs: int
) -> list[AssessmentIssue]:
    if word_count < PARAGRAPH_EXPECTED_ABOVE or paragraphs > 1:
        return []
    return [
        AssessmentIssue(
            category=IssueCategory.SENTENCE,
            subtype="single_paragraph",
            severity=IssueSeverity.INFO,
            original_text="",
            explanation=(
                f"All {word_count} words are in one paragraph. Graph descriptions usually "
                f"break after the overview, then again between the trends being compared."
            ),
            start=0,
            end=len(ctx.text),
            confidence=0.7,
            source="structure",
        )
    ]


def _overview_issue(ctx: AssessmentContext, sentences: list[Span]) -> list[AssessmentIssue]:
    """The single most-taught convention of graph description.

    Read from the writing pass rather than detected again here: the rubric
    already decided whether there is an overview, and a second opinion on the
    same page would be indefensible.
    """
    if ctx.writing.has_overview:
        return []

    start, end = sentence_span(ctx, sentences[0])
    return [
        AssessmentIssue(
            category=IssueCategory.SENTENCE,
            subtype="missing_overview",
            severity=IssueSeverity.MEDIUM,
            original_text=ctx.text[start:end],
            explanation=(
                "There is no overview statement. Open with what the chart shows overall — "
                "“Overall, sales rose steadily across the period” — before describing the "
                "detail."
            ),
            start=start,
            end=end,
            confidence=0.85,
            source="structure",
        )
    ]


def _readability_score(readability: float) -> float:
    """Full marks inside the academic band, tapering on both sides."""
    if READABILITY_MIN <= readability <= READABILITY_MAX:
        return 100.0
    if readability < READABILITY_MIN:
        return scale(readability, READABILITY_ZERO_LOW, READABILITY_MIN)
    return round(100.0 - scale(readability, READABILITY_MAX, READABILITY_ZERO_HIGH), 2)


__all__ = ["SentenceAnalyzer"]
