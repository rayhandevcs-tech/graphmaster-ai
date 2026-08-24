"""Class, platform and vocabulary analytics (FR-11.3, FR-11.4, FR-12.x).

Teacher-facing throughout. A teacher sees classes they own; an administrator
sees everything. A class a teacher does not teach is **refused**, not returned
empty — an empty report and a forbidden one look identical to the reader, and
the first one is a lie (FR-11.6).

The student's own equivalent lives on `/users/me/dashboard`.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, AnalyticsSvc, TeacherUser
from app.schemas.analytics import AnalyticsReport, TrendReport, VocabularyUsageReport

router = APIRouter(tags=["analytics"])

DateFrom = Query(default=None, description="First day of the period, inclusive")
DateTo = Query(default=None, description="Last day of the period, inclusive")


@router.get(
    "/class/{class_id}",
    response_model=AnalyticsReport,
    summary="Analytics for one class",
    description=(
        "Averages, the reward-tier spread, engagement and a per-student roster. The "
        "roster includes students with **no** marked work — their averages come back "
        "null rather than zero, because a student who has not started is not the same "
        "as one scoring nothing, and a teacher needs to be able to tell them apart.\n\n"
        "Returns 403 for a class the caller does not teach, and 404 for one that does "
        "not exist."
    ),
)
async def class_analytics(
    class_id: uuid.UUID,
    teacher: TeacherUser,
    analytics: AnalyticsSvc,
    date_from: date | None = DateFrom,
    date_to: date | None = DateTo,
) -> AnalyticsReport:
    return AnalyticsReport.model_validate(
        await analytics.class_report(class_id, viewer=teacher, date_from=date_from, date_to=date_to)
    )


@router.get(
    "/platform",
    response_model=AnalyticsReport,
    summary="Platform-wide analytics",
    description=(
        "The same shape as a class report, across every class. `students` is empty: "
        "the platform scope has no single roster, and listing every student on the "
        "installation would be a different — and much larger — response."
    ),
)
async def platform_analytics(
    _: AdminUser,
    analytics: AnalyticsSvc,
    date_from: date | None = DateFrom,
    date_to: date | None = DateTo,
) -> AnalyticsReport:
    return AnalyticsReport.model_validate(
        await analytics.platform_report(date_from=date_from, date_to=date_to)
    )


@router.get(
    "/vocabulary-usage",
    response_model=VocabularyUsageReport,
    summary="Most and least used target terms",
    description=(
        "Counted from what the analysis engine actually matched, so the figures agree "
        "with the scores students were given rather than coming from a second, subtly "
        "different detector.\n\n"
        "`least_used` includes terms with **zero** uses — usually the interesting "
        "answer, since a term nobody has reached for is invisible to any report built "
        "only from what students did write. Omit `class_id` for the whole platform."
    ),
)
async def vocabulary_usage(
    teacher: TeacherUser,
    analytics: AnalyticsSvc,
    class_id: uuid.UUID | None = None,
    date_from: date | None = DateFrom,
    date_to: date | None = DateTo,
    limit: int = Query(default=10, ge=1, le=200, description="Terms at each end"),
) -> VocabularyUsageReport:
    return VocabularyUsageReport.model_validate(
        await analytics.vocabulary_usage(
            viewer=teacher,
            class_id=class_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
    )


@router.get(
    "/trends",
    response_model=TrendReport,
    summary="Score and vocabulary movement over time",
    description=(
        "Bucketed by day, week or month in the platform timezone, so the points line "
        "up with the days a cohort actually practised rather than with UTC. Buckets "
        "with no marked work produce no point — a gap in the line is a week nobody "
        "practised, not a week everyone scored zero."
    ),
)
async def trends(
    teacher: TeacherUser,
    analytics: AnalyticsSvc,
    class_id: uuid.UUID | None = None,
    granularity: str = Query(default="day", pattern="^(day|week|month)$"),
    date_from: date | None = DateFrom,
    date_to: date | None = DateTo,
) -> TrendReport:
    return TrendReport.model_validate(
        await analytics.trends(
            viewer=teacher,
            class_id=class_id,
            date_from=date_from,
            date_to=date_to,
            granularity=granularity,
        )
    )
