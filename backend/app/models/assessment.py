"""Assessment models: the diagnostic record beside a score.

One row per submission in :class:`AssessmentDetail`, mirroring ``scores``, and
one row per finding in :class:`AssessmentIssue`. Nothing here is read by the
scoring engine or the gamification service — these tables record what the
student should do differently, and that is a different question from what
their work was worth.

Deliberately **not** four tables. Every analyzer produces the same eleven
columns, so a table per category would repeat the schema four times, turn "this
student's issues in reading order" into a four-way union, and make "the
mistakes this class makes most" four queries instead of one ``GROUP BY``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType
from app.models.enums import (
    AssessmentStatus,
    ClaimType,
    ClaimVerdict,
    IssueCategory,
    IssueSeverity,
    values,
)

if TYPE_CHECKING:
    from app.models.submission import Submission


def _in(column: str, enum: Any) -> str:
    """A ``CHECK … IN`` body generated from the enum itself.

    Written from the Python enum rather than typed out, so a value added to
    one and forgotten in the other is impossible — and so ``alembic check``
    notices when they diverge.
    """
    return f"{column} IN ({', '.join(repr(v) for v in values(enum))})"


class AssessmentDetail(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """The diagnostic header for one submission."""

    __tablename__ = "assessment_details"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("submissions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    assessment_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AssessmentStatus.COMPLETE.value
    )

    # Only the categories the assessment engine introduces. The vocabulary and
    # writing scores are already on `scores` and are deliberately not copied
    # here: a second copy is a second thing to keep in step, and two columns
    # that can disagree about one number are worse than one.
    #
    # NULL means "this analyzer did not run for this submission", which is a
    # different fact from 0.0 — "it ran, and the work was poor".
    grammar_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    spelling_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    sentence_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    word_usage_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    graph_accuracy_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    issue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Issues asserting a mistake — everything above ``INFO``. A style
    #: preference is not counted: telling a student they made nine mistakes
    #: when four were suggestions is exactly what the severity scale prevents.
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Found, but below the deployment's confidence floor. Counted rather than
    #: discarded, because a floor set too high is invisible otherwise.
    suppressed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    truncated_categories: Mapped[list[Any]] = mapped_column(JSONType, nullable=False, default=list)

    #: Per analyzer: status, duration, detail and metrics. This is what makes
    #: "no grammar issues" distinguishable from "grammar never ran here".
    analyzer_status: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    #: Who may see each analyzer's output, frozen at assessment time. Read at
    #: display time instead, a rollout stage that has since moved would
    #: retroactively reveal what was dark when the work was marked.
    analyzer_audiences: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, default=dict
    )

    submission: Mapped[Submission] = relationship(back_populates="assessment")
    issues: Mapped[list[AssessmentIssue]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="AssessmentIssue.start_index",
    )
    claims: Mapped[list[GraphAccuracyClaim]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(_in("status", AssessmentStatus), name="assessment_status_valid"),
        CheckConstraint(
            "grammar_score IS NULL OR (grammar_score >= 0 AND grammar_score <= 100)",
            name="grammar_score_range",
        ),
        CheckConstraint(
            "spelling_score IS NULL OR (spelling_score >= 0 AND spelling_score <= 100)",
            name="spelling_score_range",
        ),
        CheckConstraint(
            "sentence_score IS NULL OR (sentence_score >= 0 AND sentence_score <= 100)",
            name="sentence_score_range",
        ),
        CheckConstraint(
            "word_usage_score IS NULL OR (word_usage_score >= 0 AND word_usage_score <= 100)",
            name="word_usage_score_range",
        ),
        CheckConstraint(
            "graph_accuracy_score IS NULL OR "
            "(graph_accuracy_score >= 0 AND graph_accuracy_score <= 100)",
            name="graph_accuracy_score_range",
        ),
        CheckConstraint(
            "issue_count >= 0 AND error_count >= 0 AND suppressed_count >= 0",
            name="assessment_counts_non_negative",
        ),
        # A mistake is an issue, so there cannot be more of the first.
        CheckConstraint("error_count <= issue_count", name="errors_within_issues"),
        Index("ix_assessment_details_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<AssessmentDetail {self.submission_id} issues={self.issue_count}>"


class AssessmentIssue(Base, UUIDPrimaryKeyMixin):
    """One finding, whichever analyzer found it."""

    __tablename__ = "assessment_issues"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("assessment_details.id", ondelete="CASCADE"), nullable=False
    )

    category: Mapped[str] = mapped_column(String(24), nullable=False)
    #: Stable slug, and the grouping key for class analytics. The human wording
    #: lives in ``explanation`` so it can be rewritten without invalidating a
    #: year of "the mistakes this class makes most".
    subtype: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)

    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    #: NULL where there is no single right answer. "This sentence is hard to
    #: follow" has no replacement, and inventing one is worse than offering
    #: none.
    suggested_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str] = mapped_column(String(400), nullable=False)

    #: Half-open, into ``submissions.answer_text`` — so ``answer_text[start:end]``
    #: is exactly the span the student wrote.
    start_index: Mapped[int] = mapped_column(Integer, nullable=False)
    end_index: Mapped[int] = mapped_column(Integer, nullable=False)

    confidence: Mapped[float] = mapped_column(
        Numeric(4, 3), nullable=False, server_default=text("1.000")
    )
    #: ``analyzer`` or ``analyzer:provider`` — what an audit of a false
    #: positive starts from.
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    assessment: Mapped[AssessmentDetail] = relationship(back_populates="issues")

    __table_args__ = (
        CheckConstraint(_in("category", IssueCategory), name="issue_category_valid"),
        CheckConstraint(_in("severity", IssueSeverity), name="issue_severity_valid"),
        CheckConstraint("start_index >= 0 AND end_index >= start_index", name="issue_span_valid"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="issue_confidence_range"),
        # The result page: one submission's issues, in reading order.
        Index("ix_assessment_issues_reading_order", "assessment_id", "start_index"),
        # The teacher analytics: every issue of a kind, across a class.
        Index("ix_assessment_issues_kind", "category", "subtype"),
    )

    def __repr__(self) -> str:
        return f"<AssessmentIssue {self.category}/{self.subtype} @{self.start_index}>"


class GraphAccuracyClaim(Base, UUIDPrimaryKeyMixin):
    """One statement the student made about the chart, checked against it.

    Correct claims are stored as well as incorrect ones. "You read four trends
    and got three right" is the educational figure, and it cannot be recovered
    from the errors alone — a student with no issues might have made three
    correct claims or none.
    """

    __tablename__ = "graph_accuracy_claims"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("assessment_details.id", ondelete="CASCADE"), nullable=False
    )

    claim_type: Mapped[str] = mapped_column(String(24), nullable=False)
    #: The dataset the claim resolved to; NULL when it resolved to none, which
    #: is why the verdict is then ``unverified``.
    series_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    claimed: Mapped[str] = mapped_column(String(120), nullable=False)
    actual: Mapped[str] = mapped_column(String(120), nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(
        Numeric(4, 3), nullable=False, server_default=text("1.000")
    )

    start_index: Mapped[int] = mapped_column(Integer, nullable=False)
    end_index: Mapped[int] = mapped_column(Integer, nullable=False)

    #: The issue this claim produced, when it produced one. ``SET NULL`` rather
    #: than cascade: the claim is still a record of what the student said even
    #: if the issue built from it is gone.
    issue_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("assessment_issues.id", ondelete="SET NULL"), nullable=True
    )

    assessment: Mapped[AssessmentDetail] = relationship(back_populates="claims")

    __table_args__ = (
        CheckConstraint(_in("claim_type", ClaimType), name="claim_type_valid"),
        CheckConstraint(_in("verdict", ClaimVerdict), name="claim_verdict_valid"),
        CheckConstraint("start_index >= 0 AND end_index >= start_index", name="claim_span_valid"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="claim_confidence_range"),
        # A claim that resolved to nothing cannot have produced a correction.
        CheckConstraint(
            "issue_id IS NULL OR verdict = 'incorrect'",
            name="only_incorrect_claims_carry_an_issue",
        ),
        Index("ix_graph_accuracy_claims_assessment", "assessment_id"),
        Index("ix_graph_accuracy_claims_outcome", "verdict", "claim_type"),
    )

    def __repr__(self) -> str:
        return f"<GraphAccuracyClaim {self.claim_type} {self.verdict}>"
