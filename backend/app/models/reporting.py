"""Reporting models: analytics snapshots and teacher report exports."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType
from app.models.enums import (
    AnalyticsScope,
    ReportFormat,
    ReportStatus,
    ReportType,
    values,
)

if TYPE_CHECKING:
    from app.models.identity import User


class AnalyticsSnapshot(Base, UUIDPrimaryKeyMixin):
    """Precomputed metrics for a scope and period."""

    __tablename__ = "analytics_snapshots"

    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("classes.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # JSONB rather than wide columns: the metric set is expected to grow
    # throughout the research phase, and adding a metric should not require a
    # migration on a table already holding historical rows.
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            f"scope IN ({', '.join(repr(v) for v in values(AnalyticsScope))})",
            name="scope_valid",
        ),
        UniqueConstraint(
            "scope", "class_id", "user_id", "period_start", name="uq_analytics_snapshot"
        ),
        Index("ix_analytics_snapshots_scope_period", "scope", "period_start"),
    )


class TeacherReport(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """A generated CSV / Excel / PDF export."""

    __tablename__ = "teacher_reports"

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("classes.id", ondelete="CASCADE"), nullable=True
    )
    report_type: Mapped[str] = mapped_column(String(32), nullable=False)
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ReportStatus.PENDING.value
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    teacher: Mapped[User] = relationship(back_populates="reports")

    __table_args__ = (
        CheckConstraint(
            f"report_type IN ({', '.join(repr(v) for v in values(ReportType))})",
            name="report_type_valid",
        ),
        CheckConstraint(
            f"format IN ({', '.join(repr(v) for v in values(ReportFormat))})",
            name="format_valid",
        ),
        CheckConstraint(
            f"status IN ({', '.join(repr(v) for v in values(ReportStatus))})",
            name="status_valid",
        ),
        Index("ix_teacher_reports_teacher_created", "teacher_id", "created_at"),
    )
