"""Analysis and scoring schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import RewardTier
from app.nlp import MAX_ANALYSIS_CHARS


class AnalysisRequest(BaseModel):
    """Text to score against a graph's target vocabulary."""

    text: str = Field(
        min_length=1,
        max_length=MAX_ANALYSIS_CHARS,
        description="The student's description of the graph",
    )

    @field_validator("text")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        # `min_length` counts characters, so a field of spaces passes it. The
        # engine has nothing to analyse in that case, and a 422 naming the
        # problem beats a 500 from deep inside the pipeline.
        if not value.strip():
            raise ValueError("The answer is empty.")
        return value


class OccurrenceOut(BaseModel):
    """Where a term appeared, as offsets into the text that was submitted.

    Half-open, so ``text[start:end]`` is exactly the matched words — which is
    what lets the UI highlight them without re-running any matching of its own.
    """

    matched_form: str
    start: int
    end: int


class DetectedTermOut(BaseModel):
    term: str
    lemma: str
    category: str
    category_name: str
    is_required: bool
    count: int
    matched_forms: list[str]
    positions: list[list[int]]


class MissingTermOut(BaseModel):
    term: str
    lemma: str
    category: str
    category_name: str
    is_required: bool


class CategoryUsageOut(BaseModel):
    """Per-category vocabulary usage (FR-6.11)."""

    name: str
    detected: list[str]
    missing: list[str]
    detected_count: int
    target_count: int
    percentage: float


class WritingComponentsOut(BaseModel):
    word_count: float
    lexical_diversity: float
    sentence_structure: float
    overview: float


class WritingMeasuresOut(BaseModel):
    mattr: float
    mean_sentence_length: float
    subordination_ratio: float
    has_overview: bool
    overview_sentence_index: int | None = None


class WritingBreakdownOut(BaseModel):
    """The evidence behind the writing score.

    Exposed rather than hidden because the score is a heuristic and a teacher
    disputing it deserves to see what it measured.
    """

    word_count: int
    sentence_count: int
    components: WritingComponentsOut
    measures: WritingMeasuresOut


class FeedbackOut(BaseModel):
    headline: str
    message: str
    strengths: list[str]
    improvements: list[str]
    missing_by_category: dict[str, list[str]]
    next_step: str


class AnalysisResponse(BaseModel):
    """Everything the results screen needs."""

    graph_id: uuid.UUID
    vocabulary_score: float
    writing_score: float
    final_score: float
    vocabulary_percentage: float
    reward_tier: RewardTier = Field(
        description="Driven by the vocabulary percentage, not the final score (FR-7.1)"
    )
    detected_count: int = Field(description="Every occurrence, repeats included")
    unique_detected_count: int
    total_target_count: int = Field(
        description="Required targets only — the denominator of the percentage"
    )
    bonus_terms_used: int
    word_count: int
    detected_terms: list[DetectedTermOut]
    missing_terms: list[MissingTermOut]
    category_breakdown: dict[str, CategoryUsageOut]
    writing_breakdown: WritingBreakdownOut
    feedback: FeedbackOut
    engine_version: str


class TargetTermOut(BaseModel):
    term: str
    lemma: str
    category: str
    category_name: str
    is_required: bool
    is_phrase: bool
    weight: float


class TargetSummaryResponse(BaseModel):
    """The target set a submission would actually be scored against."""

    graph_id: uuid.UUID
    source: str = Field(
        description="'curated' when a teacher set the list, 'default' when derived from the "
        "chart type (FR-5.6)"
    )
    required_count: int
    optional_count: int
    terms: list[TargetTermOut]


class RubricOut(BaseModel):
    vocabulary_weight: float
    writing_weight: float
    tier_thresholds: dict[str, float]
    target_word_count: dict[str, int]


class PipelineOut(BaseModel):
    model: str
    available: bool
    version: str | None = None
    pipes: list[str] = Field(default_factory=list)


class EngineStatusResponse(BaseModel):
    """The deployed rubric and the state of the language model.

    Published so the client can render the marking criteria from the server's
    own configuration instead of hardcoding a copy that drifts out of step with
    a retuned rubric.
    """

    available: bool
    engine_version: str
    pipeline: PipelineOut
    rubric: RubricOut


def to_analysis_response(graph_id: uuid.UUID, result: Any) -> AnalysisResponse:
    """Build the response from an :class:`~app.nlp.analyzer.AnalysisResult`."""
    fields = result.to_score_fields()
    return AnalysisResponse(
        graph_id=graph_id,
        vocabulary_score=fields["vocabulary_score"],
        writing_score=fields["writing_score"],
        final_score=fields["final_score"],
        vocabulary_percentage=fields["vocabulary_percentage"],
        reward_tier=RewardTier(fields["reward_tier"]),
        detected_count=fields["detected_count"],
        unique_detected_count=fields["unique_detected_count"],
        total_target_count=fields["total_target_count"],
        bonus_terms_used=result.score.bonus_terms_used,
        word_count=result.word_count,
        detected_terms=[DetectedTermOut(**d) for d in fields["detected_terms"]],
        missing_terms=[MissingTermOut(**m) for m in fields["missing_terms"]],
        category_breakdown={
            code: CategoryUsageOut(**usage) for code, usage in fields["category_breakdown"].items()
        },
        writing_breakdown=WritingBreakdownOut(**fields["writing_breakdown"]),
        feedback=FeedbackOut(**fields["feedback"]),
        engine_version=fields["engine_version"],
    )
