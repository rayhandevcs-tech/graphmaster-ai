"""The analysis entry point.

One call takes a student's text plus the graph's target vocabulary and returns
everything a ``Score`` row needs. Everything below it is pure: no database, no
request, no clock — so the engine can be run over a corpus offline to produce
the reliability figures the project's evaluation chapter needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import AnalysisError
from app.models.enums import Gender, GraphType
from app.nlp import MAX_ANALYSIS_CHARS
from app.nlp.detector import DetectionResult, detect
from app.nlp.feedback import generate as generate_feedback
from app.nlp.normalise import NormalisedText, normalise
from app.nlp.pipeline import get_nlp
from app.nlp.scoring import (
    ScoreBreakdown,
    build_score,
    category_breakdown,
    engine_version,
)
from app.nlp.terms import CompiledTargets, TargetTerm, compile_targets, dedupe
from app.nlp.writing import WritingQuality, assess


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """The complete outcome of analysing one answer."""

    score: ScoreBreakdown
    detection: DetectionResult
    writing: WritingQuality
    feedback: dict[str, Any]
    categories: dict[str, dict[str, Any]]
    engine_version: str
    normalised: NormalisedText

    @property
    def word_count(self) -> int:
        return self.writing.word_count

    def to_score_fields(self) -> dict[str, Any]:
        """Column values for a ``Score`` row.

        Assembled here rather than in the service so the mapping from analysis
        output to stored columns lives next to the analysis that produced it.
        """
        return {
            "vocabulary_score": self.score.vocabulary_score,
            "writing_score": self.score.writing_score,
            "final_score": self.score.final_score,
            "vocabulary_percentage": self.score.vocabulary_percentage,
            "detected_count": self.score.detected_count,
            "unique_detected_count": self.score.unique_detected_count,
            "total_target_count": self.score.total_target_count,
            "detected_terms": [d.to_dict() for d in self.detection.detected],
            "missing_terms": [
                {
                    "term": t.term,
                    "lemma": t.lemma,
                    "category": t.category_code,
                    "category_name": t.category_name,
                    "is_required": t.is_required,
                }
                for t in self.detection.missing
            ],
            "category_breakdown": self.categories,
            "writing_breakdown": self.writing.to_dict(),
            "reward_tier": self.score.reward_tier.value,
            "feedback": self.feedback,
            "engine_version": self.engine_version,
        }


def analyse(
    text: str,
    targets: list[TargetTerm],
    *,
    settings: Settings | None = None,
    graph_type: GraphType | None = None,
    gender: Gender | None = None,
) -> AnalysisResult:
    """Analyse one answer against one graph's target vocabulary.

    Raises :class:`AnalysisError` for text that cannot be analysed at all, and
    :class:`AnalysisEngineUnavailableError` when the language model is missing
    from the server.
    """
    settings = settings or get_settings()

    if not text or not text.strip():
        raise AnalysisError("There is no text to analyse.")
    if len(text) > MAX_ANALYSIS_CHARS:
        raise AnalysisError(
            f"The answer is {len(text):,} characters. "
            f"The limit for analysis is {MAX_ANALYSIS_CHARS:,}."
        )

    compiled = compile_targets(dedupe(targets))
    normalised = normalise(text)
    if not normalised.text:
        # Everything in the answer was whitespace or invisible control
        # characters. Reported as unanalysable rather than scored zero: a zero
        # is a judgement about writing, and there is no writing here.
        raise AnalysisError("There is no text to analyse.")

    doc = get_nlp()(normalised.text)

    detection = detect(doc, normalised, compiled)
    writing = assess(
        doc,
        target_min=settings.TARGET_WORD_COUNT_MIN,
        target_max=settings.TARGET_WORD_COUNT_MAX,
    )
    score = build_score(detection, writing, compiled, settings)

    return AnalysisResult(
        score=score,
        detection=detection,
        writing=writing,
        feedback=generate_feedback(
            detection=detection,
            writing=writing,
            score=score,
            targets=compiled,
            graph_type=graph_type,
            gender=gender,
            target_min=settings.TARGET_WORD_COUNT_MIN,
            target_max=settings.TARGET_WORD_COUNT_MAX,
        ),
        categories=category_breakdown(detection, compiled),
        engine_version=engine_version(settings),
        normalised=normalised,
    )


def compiled_targets(targets: list[TargetTerm]) -> CompiledTargets:
    """Expose compilation for callers that want to inspect a target set."""
    return compile_targets(dedupe(targets))


__all__ = ["AnalysisResult", "WritingQuality", "analyse", "compiled_targets"]
