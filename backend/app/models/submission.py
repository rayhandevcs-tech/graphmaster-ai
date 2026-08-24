"""Submission and score models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType
from app.models.enums import (
    InputMethod,
    OCRProviderName,
    RewardTier,
    SubmissionStatus,
    values,
)

if TYPE_CHECKING:
    from app.models.content import Graph
    from app.models.gamification import UserBadge, XPEvent
    from app.models.identity import User


class Submission(Base, UUIDPrimaryKeyMixin):
    """One student attempt at describing one graph."""

    __tablename__ = "submissions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    graph_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("graphs.id", ondelete="RESTRICT"), nullable=False
    )
    input_method: Mapped[str] = mapped_column(String(16), nullable=False)

    # The text actually scored. For handwriting this starts as `ocr_text` and
    # may then be corrected by the student.
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    original_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The unmodified machine output, kept alongside `answer_text` even after
    # the student edits it. The pair is what makes OCR accuracy measurable as
    # research data rather than merely observable as a low score.
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    ocr_blocks: Mapped[list[Any] | None] = mapped_column(JSONType, nullable=True)
    was_ocr_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SubmissionStatus.DRAFT.value
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="submissions")
    graph: Mapped[Graph] = relationship(back_populates="submissions")
    score: Mapped[Score | None] = relationship(
        back_populates="submission", cascade="all, delete-orphan", uselist=False
    )
    xp_events: Mapped[list[XPEvent]] = relationship(back_populates="submission")
    badge: Mapped[UserBadge | None] = relationship(
        back_populates="submission", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        CheckConstraint(
            f"input_method IN ({', '.join(repr(v) for v in values(InputMethod))})",
            name="input_method_valid",
        ),
        CheckConstraint(
            f"status IN ({', '.join(repr(v) for v in values(SubmissionStatus))})",
            name="status_valid",
        ),
        CheckConstraint(
            "ocr_provider IS NULL OR ocr_provider IN "
            f"({', '.join(repr(v) for v in values(OCRProviderName))})",
            name="ocr_provider_valid",
        ),
        CheckConstraint(
            "ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)",
            name="ocr_confidence_range",
        ),
        CheckConstraint("word_count >= 0", name="word_count_non_negative"),
        Index("ix_submissions_user_submitted", "user_id", "submitted_at"),
        Index("ix_submissions_graph_id", "graph_id"),
        Index("ix_submissions_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Submission {self.id} status={self.status}>"


class Score(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """The analysis result for one submission."""

    __tablename__ = "scores"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("submissions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    vocabulary_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    writing_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    final_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    vocabulary_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    detected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_detected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Stored rather than looked up at read time. A teacher may add a target
    # term next week; without this, every historical percentage for the graph
    # would silently change and the improvement trends would be corrupted.
    total_target_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    detected_terms: Mapped[list[Any]] = mapped_column(JSONType, nullable=False, default=list)
    missing_terms: Mapped[list[Any]] = mapped_column(JSONType, nullable=False, default=list)
    category_breakdown: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, default=dict
    )
    writing_breakdown: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, default=dict
    )

    reward_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    feedback: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)

    submission: Mapped[Submission] = relationship(back_populates="score")

    __table_args__ = (
        CheckConstraint(
            f"reward_tier IN ({', '.join(repr(v) for v in values(RewardTier))})",
            name="reward_tier_valid",
        ),
        CheckConstraint(
            "vocabulary_score >= 0 AND vocabulary_score <= 100", name="vocabulary_score_range"
        ),
        CheckConstraint("writing_score >= 0 AND writing_score <= 100", name="writing_score_range"),
        CheckConstraint("final_score >= 0 AND final_score <= 100", name="final_score_range"),
        CheckConstraint("total_target_count >= 0", name="total_target_non_negative"),
        Index("ix_scores_reward_tier", "reward_tier"),
        Index("ix_scores_final_score", "final_score"),
    )

    def __repr__(self) -> str:
        return f"<Score {self.final_score} tier={self.reward_tier}>"
