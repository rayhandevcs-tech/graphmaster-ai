"""What the assessment endpoints return.

Two audiences read these shapes and the difference between them is not a flag
in the payload — it is which analyzers are in it at all. The service builds a
student's copy *without* what they may not see, rather than serialising
everything and hiding fields, so nothing added to a schema later can leak what
an audience was never meant to receive.

Every aggregate carries the count it was taken over. No submission marked
before Sprint 16 has an assessment and there is no backfill, so every figure
here is over a subset — and an average printed without its `assessed_count`
reads as though it were over everything.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AssessmentIssueOut(BaseModel):
    """One finding, located in the student's own text."""

    model_config = ConfigDict(from_attributes=True)

    category: str
    subtype: str = Field(description="Stable slug, and the grouping key for class analytics.")
    severity: str = Field(description="`info` is a preference, not a mistake.")
    original_text: str
    suggested_text: str | None = Field(
        default=None,
        description="Null where there is no single right answer.",
    )
    explanation: str
    start_index: int = Field(
        description="Half-open, into the submitted answer: `answer_text[start:end]` is the span."
    )
    end_index: int
    confidence: float
    analyzer: str = Field(description="Which analyzer found it. Never names a provider.")


class AnalyzerStatusOut(BaseModel):
    """How one analyzer's run ended, and what it measured."""

    status: str = Field(
        description=(
            "`ok`, `unavailable` (not configured on this server), `skipped`, or `failed`. "
            "`unavailable` and `failed` are deliberately different: the first is a "
            "deployment fact and the second is a fault."
        )
    )
    score: float | None = Field(
        default=None,
        description="0-100 diagnostic figure. Null where the analyzer produces none.",
    )
    issue_count: int = 0
    duration_ms: float = 0.0
    metrics: dict[str, float] = Field(default_factory=dict)


class AssessmentResponse(BaseModel):
    """One submission's assessment, filtered to what the caller may see."""

    submission_id: uuid.UUID
    assessment_version: str
    status: str = Field(description="`complete`, `partial` (an analyzer failed), or `pending`.")
    issue_count: int = Field(description="Issues shown to this caller.")
    error_count: int = Field(description="Of those, the ones asserting a mistake.")
    suppressed_count: int = Field(
        description="Found but below this server's confidence floor. Counted, not shown."
    )
    truncated_categories: list[str] = Field(
        default_factory=list,
        description="Categories where the per-submission cap dropped issues.",
    )
    scores: dict[str, float | None] = Field(
        default_factory=dict,
        description=(
            "Per-analyzer diagnostic scores. Null means the analyzer did not run here, "
            "which is a different fact from a score of zero."
        ),
    )
    analyzers: dict[str, AnalyzerStatusOut] = Field(default_factory=dict)
    issues: list[AssessmentIssueOut] = Field(default_factory=list)
    assessed_at: dt.datetime


class IssueFrequencyEntry(BaseModel):
    subtype: str
    occurrences: int


class IssueFrequencyReport(BaseModel):
    """The commonest mistakes across a set of submissions."""

    scope: str
    class_id: uuid.UUID | None = None
    assessed_count: int = Field(
        description="Submissions in scope that actually carry an assessment."
    )
    submission_count: int = Field(description="Submissions in scope, assessed or not.")
    entries: list[IssueFrequencyEntry] = Field(default_factory=list)
    counts_by_category: dict[str, int] = Field(default_factory=dict)


class AnalyzerScoreSummary(BaseModel):
    """One analyzer's mean, with the count it was taken over."""

    analyzer: str
    assessed_count: int
    average: float | None = Field(
        default=None,
        description=(
            "Null — never zero — when nothing in scope was assessed for this analyzer. "
            "A class whose grammar was never checked is not one that scored nothing."
        ),
    )


class AnalyzerScoreReport(BaseModel):
    scope: str
    class_id: uuid.UUID | None = None
    submission_count: int
    summaries: list[AnalyzerScoreSummary] = Field(default_factory=list)


class TrendPoint(BaseModel):
    """One period of a trend line."""

    period: dt.date
    assessed_count: int
    average: float | None = Field(
        default=None,
        description=(
            "Null where nothing in the period was assessed. The line **breaks** here; "
            "it is never interpolated, because bridging the gap would draw a step "
            "change on the day the engine was switched on and read as a real one."
        ),
    )


class AnalyzerTrendReport(BaseModel):
    scope: str
    class_id: uuid.UUID | None = None
    analyzer: str
    interval: str
    timezone: str = Field(description="Periods roll over together in this zone.")
    points: list[TrendPoint] = Field(default_factory=list)


# ── Writing consistency ──────────────────────────────────────────────────────
#
# Teacher-facing only, and measurement only. Nothing below carries a verdict, a
# composite, a threshold or an ordering of students — see
# docs/architecture/10-assessment-architecture.md §15.


class BaselineOut(BaseModel):
    """What one measure has looked like for this student until now."""

    mean: float
    spread: float = Field(description="Population standard deviation. Never divided into anything.")
    n: int = Field(description="Comparable prior submissions this was built from.")
    lowest: float
    highest: float


class MeasureChangeOut(BaseModel):
    measure: str
    current: float | None = Field(
        default=None, description="Null where this submission has no figure for the measure."
    )
    baseline: BaselineOut | None = Field(
        default=None,
        description=(
            "Null when there are too few comparable prior submissions — the normal "
            "state for most of a term. Renders as 'no baseline yet', never as zero "
            "and never as 'consistent'."
        ),
    )
    difference: float | None = Field(
        default=None,
        description="Current minus the baseline mean, in the measure's own units. Not a z-score.",
    )


class ConsistencyResponse(BaseModel):
    """How one submission's measurements sit against the student's own history.

    Observations for a teacher to read. The system draws no conclusion from
    them, and two limits belong beside them wherever they are shown: the
    platform's own feedback is the largest cause of the changes it measures,
    and a settled profile is not evidence of anything, because a baseline can
    itself be assisted.
    """

    submission_id: uuid.UUID
    student_id: uuid.UUID
    model_version: str = Field(description="The comparison's version. Nothing is stored.")
    compared_count: int = Field(description="Prior submissions that passed every gate.")
    considered_count: int = Field(description="Prior submissions looked at, gates included.")
    excluded: dict[str, int] = Field(
        default_factory=dict,
        description="How many prior submissions each gate excluded, and why.",
    )
    changes: list[MeasureChangeOut] = Field(default_factory=list)
    limitations: list[str] = Field(
        default_factory=list,
        description="Shown with the figures, not in a help page.",
    )


def issue_out(row: Any) -> AssessmentIssueOut:
    """Build the issue payload, resolving the analyzer out of the stored source.

    ``source`` is ``analyzer`` or ``analyzer:provider``. Only the first half
    is published: which grammar engine produced a correction is an operator
    fact, and a hostname or an engine name on a student's screen is exactly
    what the provider rules forbid.
    """
    from app.assessment.audience import analyzer_of

    return AssessmentIssueOut(
        category=row.category,
        subtype=row.subtype,
        severity=row.severity,
        original_text=row.original_text,
        suggested_text=row.suggested_text,
        explanation=row.explanation,
        start_index=row.start_index,
        end_index=row.end_index,
        confidence=float(row.confidence),
        analyzer=analyzer_of(row.source),
    )


__all__ = [
    "AnalyzerScoreReport",
    "AnalyzerScoreSummary",
    "AnalyzerStatusOut",
    "AnalyzerTrendReport",
    "AssessmentIssueOut",
    "AssessmentResponse",
    "BaselineOut",
    "ConsistencyResponse",
    "IssueFrequencyEntry",
    "IssueFrequencyReport",
    "MeasureChangeOut",
    "TrendPoint",
    "issue_out",
]
