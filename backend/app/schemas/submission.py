"""Submission and score response shapes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    GraphType,
    InputMethod,
    OCRProviderName,
    RewardTier,
    SubmissionStatus,
)
from app.nlp import MAX_ANALYSIS_CHARS
from app.schemas.analysis import (
    CategoryUsageOut,
    DetectedTermOut,
    FeedbackOut,
    MissingTermOut,
    WritingBreakdownOut,
)


class SubmissionCreate(BaseModel):
    """Open an attempt at a graph."""

    graph_id: uuid.UUID
    input_method: InputMethod = Field(
        default=InputMethod.TYPED,
        description="`typed` to write in the browser, `handwriting` to photograph a page",
    )


class SubmissionTextUpdate(BaseModel):
    """Set or correct the answer before analysis (FR-4.7)."""

    text: str = Field(
        min_length=1,
        max_length=MAX_ANALYSIS_CHARS,
        description="The student's description of the graph",
    )

    @field_validator("text")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        # `min_length` counts characters, so a field of spaces satisfies it
        # while leaving nothing to score.
        if not value.strip():
            raise ValueError("The answer is empty.")
        return value


class ScoreOut(BaseModel):
    """A persisted score, as stored on the submission."""

    vocabulary_score: float
    writing_score: float
    final_score: float
    vocabulary_percentage: float
    detected_count: int = Field(description="Every occurrence, repeats included")
    unique_detected_count: int
    total_target_count: int = Field(
        description="Required targets at the time of scoring — the denominator of the "
        "percentage, frozen so a later edit to the graph cannot move a historical score"
    )
    detected_terms: list[DetectedTermOut]
    missing_terms: list[MissingTermOut]
    category_breakdown: dict[str, CategoryUsageOut]
    writing_breakdown: WritingBreakdownOut
    reward_tier: RewardTier = Field(
        description="Driven by the vocabulary percentage, not the final score (FR-7.1)"
    )
    feedback: FeedbackOut
    engine_version: str = Field(
        description="Fingerprints the rubric as well as the code, so two scores sharing "
        "a version are genuinely comparable"
    )
    scored_at: datetime


class SubmissionSummary(BaseModel):
    """One row in a listing."""

    id: uuid.UUID
    graph_id: uuid.UUID
    graph_title: str | None = None
    graph_type: GraphType | None = None
    user_id: uuid.UUID
    student_name: str | None = None
    input_method: InputMethod
    status: SubmissionStatus
    word_count: int
    final_score: float | None = None
    vocabulary_percentage: float | None = None
    reward_tier: RewardTier | None = None
    submitted_at: datetime
    scored_at: datetime | None = None


class SubmissionDetail(BaseModel):
    """One submission with everything the client needs to render it."""

    id: uuid.UUID
    graph_id: uuid.UUID
    graph_title: str | None = None
    graph_type: GraphType | None = None
    user_id: uuid.UUID
    student_name: str | None = None
    input_method: InputMethod
    status: SubmissionStatus
    answer_text: str | None = None
    word_count: int

    ocr_text: str | None = Field(
        default=None,
        description="The unedited machine reading, kept alongside the corrected answer",
    )
    ocr_provider: OCRProviderName | None = None
    ocr_confidence: float | None = None
    was_ocr_edited: bool = False

    has_image: bool = False
    image_url: str | None = Field(
        default=None,
        description="Authenticated endpoint, not a static path — fetch it with the "
        "bearer token and render the blob",
    )

    error_message: str | None = None
    submitted_at: datetime
    scored_at: datetime | None = None
    score: ScoreOut | None = None
    reference_description: str | None = Field(
        default=None,
        description="The model answer. Released once the attempt is scored, and to "
        "teachers at any time.",
    )


class ExtractionResult(BaseModel):
    """What an upload produced, for the editable preview (FR-4.6, FR-4.7)."""

    submission_id: uuid.UUID
    status: SubmissionStatus
    ocr_text: str
    ocr_provider: OCRProviderName
    ocr_confidence: float | None = None
    word_count: int
    image_url: str | None = None
    warning: str | None = Field(
        default=None,
        description="Set for an empty or low-confidence read; never blocks the flow",
    )


class GamificationOut(BaseModel):
    """XP, level, badge and achievements awarded for one submission.

    Delivered in the same payload as the score because the result screen
    sequences one animation from both: the reward tier decides which animation
    plays and the XP total decides what the bar counts up to, so splitting them
    across two calls would render the reward before the bar knew its target.

    Populated by the gamification engine in Sprint 7; until then the fields
    carry their neutral values rather than being absent, so the client contract
    does not change when the engine lands.
    """

    xp_awarded: int = 0
    xp_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    level_before: int = 1
    level_after: int = 1
    leveled_up: bool = False
    badge: dict[str, Any] | None = None
    new_achievements: list[dict[str, Any]] = Field(default_factory=list)
    streak_days: int = 0


class SubmissionResult(BaseModel):
    """The response to scoring a submission."""

    submission: SubmissionDetail
    score: ScoreOut
    gamification: GamificationOut
    reference_description: str | None = Field(
        default=None, description="Released here because the attempt is now marked"
    )
