"""Report request and response shapes."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ReportFormat, ReportStatus, ReportType


class ReportRequest(BaseModel):
    """Ask for one export (FR-11.5)."""

    report_type: ReportType
    format: ReportFormat = ReportFormat.CSV
    class_id: uuid.UUID | None = Field(
        default=None,
        description="Required for a class summary unless the caller is an administrator",
    )
    student_id: uuid.UUID | None = Field(default=None, description="Required for a student report")
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode="after")
    def _ordered_period(self) -> ReportRequest:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to.")
        return self


class ReportOut(BaseModel):
    """A generated export."""

    id: uuid.UUID
    report_type: ReportType
    format: ReportFormat
    status: ReportStatus
    class_id: uuid.UUID | None = None
    parameters: dict = Field(default_factory=dict)
    download_url: str | None = Field(
        default=None,
        description="Authenticated endpoint, not a static path — an export names "
        "students and their scores, so a guessable URL would be a disclosure",
    )
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ReportCapabilities(BaseModel):
    """What this deployment can produce.

    Published so a client can hide an Excel button that would only ever return
    503, rather than offering it and apologising afterwards.
    """

    formats: list[ReportFormat]
    types: list[ReportType]
    max_rows: int = Field(description="Ceiling on a raw submission export")
