"""Writing quality, as an analyzer.

The same adapter role as :mod:`~app.assessment.analyzers.vocabulary`: the four
heuristics have already run, and this reports them in the assessment's shape.
No issues, because the components are already exposed as
``writing_breakdown`` and duplicating them would put one finding in the API
twice.

Sprint 16's sentence and word-usage analyzers are where writing gains
*locatable* findings. The distinction is worth keeping: these four are
whole-answer measures with no span to point at, and an issue that cannot say
where it is cannot be highlighted or corrected.
"""

from __future__ import annotations

from app.assessment.protocol import AnalyzerOutput, AssessmentContext


class WritingAnalyzer:
    """Reports the existing writing-quality heuristics."""

    name = "writing"

    def run(self, ctx: AssessmentContext) -> AnalyzerOutput:
        writing = ctx.writing

        return AnalyzerOutput(
            # `writing.score` is the same property `build_score` reads. Read
            # here, never written: this analyzer cannot change it.
            score=writing.score,
            metrics={
                "word_count": float(writing.word_count),
                "sentence_count": float(writing.sentence_count),
                "word_count_score": writing.word_count_score,
                "lexical_diversity_score": writing.lexical_diversity_score,
                "sentence_structure_score": writing.sentence_structure_score,
                "overview_score": writing.overview_score,
                "mattr": writing.mattr,
                "mean_sentence_length": writing.mean_sentence_length,
                "subordination_ratio": writing.subordination_ratio,
                # Carried as a number so the whole metrics map is one type.
                # The integrity baseline in sprint 19 consumes these, and a
                # mixed-type map would need a special case for one field.
                "has_overview": float(writing.has_overview),
            },
        )


__all__ = ["WritingAnalyzer"]
