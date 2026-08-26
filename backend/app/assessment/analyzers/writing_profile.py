"""The writing profile: one submission's measurements, and nothing else.

This is the measurement half of the writing-consistency feature. It records
*what this answer is like*; it says nothing about what the student's earlier
answers were like, and it draws no conclusion of any kind. The comparison
lives in :mod:`app.assessment.consistency`, runs at read time, and stores
nothing.

**Why the split.** ``assessment_version`` exists so that a stored result is
reproducible: the row's version plus the same input determines the same
output. An analyzer that read the student's history would break that — re-run
the same submission a month later and it would answer differently under an
unchanged version string, so the fingerprint would still *look* like a
guarantee while guaranteeing nothing. Three smaller reasons run the same way:
the Protocol requires purity, a history-reading analyzer would make submission
*n* depend on submissions 1…*n*−1 (so deleting an old one silently corrupts
every later result), and the analyzer suite would stop running without a
database.

**It emits no issues and no score, and both are deliberate.** There is nothing
here to tell a student — by C2 there must not be — so there is no issue to
raise. And a 0–100 "consistency score" is a risk score inverted: one number,
monotone, orderable, whose low end means *this one*. Returning ``None`` closes
that door structurally, because ``SCORE_COLUMNS`` has no entry for this
analyzer and a scalar would have nowhere to go even if a later change tried to
return one.

**It is never visible to a student.** Not by configuration —
``NEVER_STUDENT_ANALYZERS`` in :mod:`app.core.config` makes it a property of
the build, so a deployment that forgets an environment variable cannot publish
a student's own profile to them.

**The overlap with ``writing`` is intentional.** Three of these measures are
already reported by the writing analyzer. They are restated here because this
map is a *versioned measurement contract* that a year of baselines will be
compared against, and it must not shift when the writing analyzer changes what
it chooses to report. One is free to move; the other is not.
"""

from __future__ import annotations

import statistics

from app.assessment.protocol import AnalyzerOutput, AssessmentContext
from app.assessment.text import real_sentences
from app.core.config import Settings
from app.models.enums import AnalyzerStatus

#: The measures that make up a profile, in the order a teacher reads them.
#:
#: A stable contract, not a convenience. These strings are the keys under
#: ``assessment_details.analyzer_status['writing_profile']['metrics']`` and
#: they are what every baseline in the corpus is keyed on, so renaming one
#: invalidates the history rather than relabelling it. The human wording
#: belongs to the presentation layer, exactly as it does for issue subtypes.
MEASURES: tuple[str, ...] = (
    "lexical_diversity",
    "mean_sentence_length",
    "sentence_length_variation",
    "subordination_ratio",
    "vocabulary_coverage",
)

#: Reported alongside the measures, and not themselves compared. They are the
#: context a teacher needs to read the measures — and ``word_count`` is what
#: the comparability gate for length is applied to.
CONTEXT_METRICS: tuple[str, ...] = ("word_count", "sentence_count")


class WritingProfileAnalyzer:
    """Measures one answer. Compares nothing."""

    name = "writing_profile"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.min_words = settings.CONSISTENCY_MIN_WORDS

    def run(self, ctx: AssessmentContext) -> AnalyzerOutput:
        word_count = ctx.writing.word_count

        if word_count < self.min_words:
            # `SKIPPED`, not `FAILED`: a short answer is a fact about the
            # answer, not a fault in the analyzer. It is also not `OK` with
            # zeroed measures — lexical diversity over forty words is noise,
            # and a noisy point in a baseline is worse than a missing one,
            # because a missing point is visible as missing.
            return AnalyzerOutput(
                status=AnalyzerStatus.SKIPPED,
                detail=(
                    f"{word_count} words is below the {self.min_words}-word floor "
                    f"for a stable profile."
                ),
            )

        metrics = {
            # Already computed, on the parse that has already happened.
            "lexical_diversity": float(ctx.writing.mattr),
            "mean_sentence_length": float(ctx.writing.mean_sentence_length),
            "sentence_length_variation": _sentence_length_variation(ctx),
            "subordination_ratio": float(ctx.writing.subordination_ratio),
            "vocabulary_coverage": _vocabulary_coverage(ctx),
            "word_count": float(word_count),
            "sentence_count": float(ctx.writing.sentence_count),
        }

        return AnalyzerOutput(
            status=AnalyzerStatus.OK,
            # No issues: there is nothing here to correct, and by C2 nothing
            # here may reach the student who wrote it.
            issues=(),
            # No score: see the module docstring. This is not an omission.
            score=None,
            metrics=metrics,
        )


def _sentence_length_variation(ctx: AssessmentContext) -> float:
    """How much the answer's sentence lengths differ from each other, in words.

    Reported beside the mean rather than folded into it, because two answers
    with the same average sentence length can read completely differently: one
    with every sentence at nineteen words, one alternating eight and thirty.
    A mean alone cannot tell a teacher which they are looking at, and this is
    the measure that can be demonstrated by quoting two sentences.

    Population standard deviation, not sample: these are all the sentences in
    the answer, not a sample drawn from a larger set of them.
    """
    lengths = [
        len([t for t in sentence if not t.is_punct and not t.is_space])
        for sentence in real_sentences(ctx.doc)
    ]
    # `pstdev` needs at least one value, and a single sentence has no spread
    # to measure rather than an undefined one.
    if len(lengths) < 2:
        return 0.0
    return float(statistics.pstdev(lengths))


def _vocabulary_coverage(ctx: AssessmentContext) -> float:
    """The share of required target terms this answer used, 0–100.

    The same arithmetic as ``scoring.vocabulary_percentage`` and the
    vocabulary analyzer, read from the detection that has already run. It is
    *reported* here and never recomputed for scoring — this value cannot reach
    ``build_score``, which continues to call the scoring module.

    A percentage rather than a count, because graphs carry different numbers
    of required terms and a raw count would make two answers to two graphs
    look incomparable when they are not.
    """
    required = len(ctx.targets.required)
    if not required:
        # No required targets means the exercise is unscoreable for vocabulary
        # anyway — publishing forbids it. Zero, rather than a division.
        return 0.0
    detected_unique = len(ctx.detection.detected)
    return round(min(detected_unique / required * 100.0, 100.0), 2)


__all__ = ["CONTEXT_METRICS", "MEASURES", "WritingProfileAnalyzer"]
