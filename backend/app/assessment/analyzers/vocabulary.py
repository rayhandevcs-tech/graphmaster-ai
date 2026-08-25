"""Vocabulary, as an analyzer.

An adapter, not a second implementation. The detection has already run by the
time the context is built; this reports it in the assessment's shape so that a
consumer reading ``AssessmentResult`` sees the whole picture rather than
vocabulary in one place and everything else in another.

**It emits no issues, deliberately.** A missing target term is already carried
by ``scores.missing_terms`` and ``feedback.missing_by_category``. Re-emitting
it here would put the same fact in the API twice and, worse, double-count it
in the "most common mistakes in this class" analytics — the figures a teacher
would act on. Rule 34 of the project conventions makes the same point about
re-scanning: one fact, one source.
"""

from __future__ import annotations

from app.assessment.protocol import AnalyzerOutput, AssessmentContext


class VocabularyAnalyzer:
    """Reports the existing detection as metrics and a diagnostic score."""

    name = "vocabulary"

    def run(self, ctx: AssessmentContext) -> AnalyzerOutput:
        required = len(ctx.targets.required)
        detected_unique = len(ctx.detection.detected)
        bonus = sum(1 for d in ctx.detection.detected if not d.term.is_required)

        # The same arithmetic as `scoring.vocabulary_percentage`, and it must
        # stay that way. It is *reported* here, never recomputed for scoring:
        # `build_score` continues to call the scoring module, and this value
        # never reaches it.
        percentage = round(min(detected_unique / required * 100.0, 100.0), 2) if required else 0.0

        return AnalyzerOutput(
            score=percentage,
            metrics={
                "required_targets": float(required),
                "unique_detected": float(detected_unique),
                "total_occurrences": float(ctx.detection.total_occurrences),
                "bonus_terms_used": float(bonus),
                "missing_required": float(sum(1 for t in ctx.detection.missing if t.is_required)),
            },
        )


__all__ = ["VocabularyAnalyzer"]
