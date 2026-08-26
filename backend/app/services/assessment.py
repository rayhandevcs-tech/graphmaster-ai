"""Reading assessments back.

The engine writes; this reads. Three responsibilities, and the first is the
one everything else rests on:

1. **Audience.** A student sees only what has been promoted all the way to
   them, and the decision is made from the audiences *frozen on the row* — not
   from this server's current configuration. A rollout stage that has moved
   since the work was marked must not retroactively reveal what was dark when
   it was marked.
2. **Access.** Whose assessment a caller may read is exactly whose submission
   they may read; the rule is not restated here. A class a teacher does not
   teach is refused rather than returned empty (FR-11.6).
3. **Aggregation.** The class-level figures obey the two rules approved before
   Sprint 17: every metric reports the count it was taken over, and a trend
   line breaks where that count is zero rather than interpolating across it.

Everything is computed live. ``analytics_snapshots`` stays unwritten — a
cached figure is stale exactly when a teacher wants it, in the minutes after a
lesson.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections import defaultdict
from typing import Any
from zoneinfo import ZoneInfo

from app.assessment.audience import analyzer_of, stored_audiences, visible_analyzers
from app.assessment.consistency import (
    ConsistencyDisabledError,
    compare_student,
    require_enabled,
)
from app.core.config import Settings
from app.core.exceptions import (
    ConsistencyUnavailableError,
    SubmissionNotFoundError,
    ValidationError,
)
from app.models.assessment import AssessmentDetail
from app.models.enums import AnalyzerAudience, IssueSeverity
from app.models.identity import User
from app.repositories.analytics import AnalyticsRepository, AnalyticsWindow
from app.repositories.assessment import SCORE_COLUMNS, AssessmentRepository
from app.schemas.assessment import (
    AnalyzerScoreReport,
    AnalyzerScoreSummary,
    AnalyzerStatusOut,
    AnalyzerTrendReport,
    AssessmentResponse,
    BaselineOut,
    ConsistencyResponse,
    IssueFrequencyEntry,
    IssueFrequencyReport,
    MeasureChangeOut,
    TrendPoint,
    issue_out,
)
from app.services.analytics import AnalyticsService
from app.services.submission import SubmissionService

#: Shown beside every consistency reading, in the payload rather than in a help
#: page a reader has to go and find.
#:
#: Both of these are properties of the method and no engineering removes them.
#: The second matters more than it looks: without it, a settled profile gets
#: read as "cleared", which is a harm in the opposite direction from the one
#: everybody worries about.
CONSISTENCY_LIMITATIONS = (
    "These are measurements, not conclusions. A change usually means the student "
    "is learning — and this platform's own feedback names the vocabulary they then "
    "use, so it is often the cause of what is measured here.",
    "A settled profile is not evidence that anything is or is not the case. These "
    "measures show change, so they cannot show anything about work that has been "
    "consistent from the start.",
    "Interpretation belongs to you. Nothing here is a judgement about the student "
    "or their work.",
)

INTERVALS = {"day": 1, "week": 7, "month": 30}


class AssessmentService:
    def __init__(
        self,
        assessments: AssessmentRepository,
        analytics_repo: AnalyticsRepository,
        submissions: SubmissionService,
        analytics: AnalyticsService,
        settings: Settings,
    ) -> None:
        self.assessments = assessments
        self.analytics_repo = analytics_repo
        self.submissions = submissions
        self.analytics = analytics
        self.settings = settings

    # ── One submission ───────────────────────────────────────────────────────

    async def for_submission(self, submission_id: uuid.UUID, *, viewer: User) -> AssessmentResponse:
        """One submission's assessment, filtered to what ``viewer`` may see.

        Access is delegated: ``SubmissionService.get_for`` already decides who
        may read a submission, and answers 404 rather than 403 for one that is
        not theirs — so the existence of another student's work is not
        confirmed by the error code. An assessment is a facet of a submission
        and inherits that rule rather than restating it.
        """
        await self.submissions.get_for(submission_id, viewer=viewer)

        detail = await self.assessments.for_submission(submission_id)
        if detail is None:
            # A submission scored before the engine existed, or on a server
            # with assessment switched off. Not an error in the request — but
            # not an empty assessment either, because an empty one would say
            # the work was checked and nothing was found.
            raise SubmissionNotFoundError("This submission has no assessment.")

        return self._filtered(detail, audience=self.audience_for(viewer))

    @staticmethod
    def audience_for(viewer: User) -> AnalyzerAudience:
        """Which rung of the rollout ladder this caller reads at.

        Staff read at ``TEACHER``; everyone else reads at ``STUDENT``. There is
        no administrator rung: an administrator's extra power is over accounts
        and content, not over another student's writing.
        """
        return AnalyzerAudience.TEACHER if viewer.can_manage_content else AnalyzerAudience.STUDENT

    def _filtered(
        self, detail: AssessmentDetail, *, audience: AnalyzerAudience
    ) -> AssessmentResponse:
        """Build the payload with the withheld analyzers absent, not blanked.

        The filtering happens here, on the way into the schema, so a field
        added to :class:`AssessmentResponse` later cannot carry through
        something the audience was never meant to receive.
        """
        audiences = stored_audiences(detail.analyzer_audiences)
        visible = visible_analyzers(audiences, audience)

        shown = [row for row in detail.issues if analyzer_of(row.source) in visible]
        issues = [issue_out(row) for row in shown]

        analyzers = {
            name: AnalyzerStatusOut(
                status=str(entry.get("status", "ok")),
                score=_number(entry.get("score")),
                issue_count=int(entry.get("issue_count") or 0),
                duration_ms=float(entry.get("duration_ms") or 0.0),
                metrics={
                    key: float(value)
                    for key, value in (entry.get("metrics") or {}).items()
                    if isinstance(value, (int, float)) and not isinstance(value, bool)
                },
            )
            for name, entry in (detail.analyzer_status or {}).items()
            if name in visible and isinstance(entry, dict)
        }

        # The per-analyzer score columns are filtered too. They are a second
        # copy of what `analyzer_status` already holds, and a dark analyzer
        # whose column came through would publish exactly the figure the stage
        # exists to withhold.
        scores = {
            name: _number(getattr(detail, column))
            for name, column in SCORE_COLUMNS.items()
            if name in visible
        }

        return AssessmentResponse(
            submission_id=detail.submission_id,
            assessment_version=detail.assessment_version,
            status=detail.status,
            issue_count=len(issues),
            error_count=sum(1 for row in shown if _is_mistake(row)),
            # Counted over the whole assessment, not the visible slice: these
            # describe the run that happened, not what is being shown.
            suppressed_count=detail.suppressed_count,
            truncated_categories=list(detail.truncated_categories or []),
            scores=scores,
            analyzers=analyzers,
            issues=issues,
            assessed_at=detail.created_at,
        )

    # ── Class aggregates ─────────────────────────────────────────────────────

    async def issue_frequency(
        self,
        *,
        viewer: User,
        class_id: uuid.UUID | None,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
        limit: int = 10,
    ) -> IssueFrequencyReport:
        """The commonest mistakes in scope, most frequent first."""
        ids = await self._scope(viewer, class_id, date_from, date_to)

        entries = await self.assessments.issue_frequency(ids, limit=limit)
        counts = await self.assessments.issue_counts(ids)

        return IssueFrequencyReport(
            scope="class" if class_id else "platform",
            class_id=class_id,
            assessed_count=await self.assessments.assessed_count(ids),
            submission_count=len(ids),
            entries=[IssueFrequencyEntry(subtype=s, occurrences=n) for s, n in entries],
            counts_by_category=counts,
        )

    async def score_summary(
        self,
        *,
        viewer: User,
        class_id: uuid.UUID | None,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
    ) -> AnalyzerScoreReport:
        """Every analyzer's mean in scope, each with its own assessed count.

        The counts differ between analyzers and that is the point: on a server
        with no grammar engine, grammar's count is zero while spelling's is the
        whole cohort, and one figure without the other would read as a class
        that is bad at grammar rather than one nobody checked.
        """
        ids = await self._scope(viewer, class_id, date_from, date_to)

        summaries = []
        for analyzer in sorted(SCORE_COLUMNS):
            summary = await self.assessments.score_summary(ids, analyzer)
            summaries.append(
                AnalyzerScoreSummary(
                    analyzer=analyzer,
                    assessed_count=summary.assessed_count,
                    average=summary.average,
                )
            )

        return AnalyzerScoreReport(
            scope="class" if class_id else "platform",
            class_id=class_id,
            submission_count=len(ids),
            summaries=summaries,
        )

    async def score_trend(
        self,
        *,
        viewer: User,
        analyzer: str,
        class_id: uuid.UUID | None,
        interval: str = "week",
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
    ) -> AnalyzerTrendReport:
        """One analyzer's score over time, with the line broken where it must be.

        Buckets are computed here rather than in SQL: a period boundary is a
        date in ``PLATFORM_TIMEZONE`` — a cohort must roll over together — and
        expressing that in the query would push a timezone conversion into the
        database, where SQLite and PostgreSQL disagree about how to do it.
        """
        if analyzer not in SCORE_COLUMNS:
            raise ValidationError(
                f"Unknown analyzer {analyzer!r}. Known: {', '.join(sorted(SCORE_COLUMNS))}."
            )
        if interval not in INTERVALS:
            raise ValidationError(
                f"Unknown interval {interval!r}. Known: {', '.join(sorted(INTERVALS))}."
            )

        ids = await self._scope(viewer, class_id, date_from, date_to)
        series = await self.assessments.score_series(ids, analyzer)

        zone = ZoneInfo(self.settings.PLATFORM_TIMEZONE)
        buckets: dict[dt.date, list[float]] = defaultdict(list)
        for moment, score in series:
            buckets[_bucket(moment.astimezone(zone).date(), interval)].append(score)

        return AnalyzerTrendReport(
            scope="class" if class_id else "platform",
            class_id=class_id,
            analyzer=analyzer,
            interval=interval,
            timezone=self.settings.PLATFORM_TIMEZONE,
            points=[
                TrendPoint(
                    period=period,
                    assessed_count=len(values),
                    # Periods with nothing assessed are simply absent, so a
                    # consumer draws a gap. A zero here would be read as a
                    # cohort that suddenly scored nothing.
                    average=round(sum(values) / len(values), 2) if values else None,
                )
                for period, values in sorted(buckets.items())
            ],
        )

    # ── Writing consistency ──────────────────────────────────────────────────

    async def consistency(self, submission_id: uuid.UUID, *, viewer: User) -> ConsistencyResponse:
        """How one submission sits against the same student's earlier work.

        Teacher-facing, and gated twice over: the router demands staff, and
        this refuses outright on a deployment where the comparison layer is
        switched off. A silent empty result would be indistinguishable from a
        student with no history, and only one of those is a fact about them.
        """
        try:
            require_enabled(self.settings)
        except ConsistencyDisabledError as exc:
            # Translated at the boundary: the comparison package knows nothing
            # about HTTP, and a service raises the platform's own exceptions.
            raise ConsistencyUnavailableError() from exc

        submission = await self.submissions.get_for(submission_id, viewer=viewer)

        history = await self.analytics_repo.scored_submission_ids(
            AnalyticsWindow(student_id=submission.user_id),
            timezone=self.settings.PLATFORM_TIMEZONE,
        )
        rows = await self.assessments.profile_series(history)

        current = next((row for row in rows if row.submission_id == submission_id), None)
        if current is None or not current.has_profile:
            # A row comes back for every assessed submission, carrying
            # `profile=None` where nothing was measured — the pre-Sprint-19
            # corpus, an answer below the word floor, or a deployment that has
            # not switched measurement on. Comparing from there would answer
            # 200 with every baseline null, which reads as "we looked and this
            # student has no history" rather than "nothing was measured here".
            raise SubmissionNotFoundError("This submission has no writing profile.")

        comparison = compare_student(
            current,
            [row for row in rows if row.submission_id != submission_id],
            min_words=self.settings.CONSISTENCY_MIN_WORDS,
            min_baseline=self.settings.CONSISTENCY_MIN_BASELINE,
        )

        return ConsistencyResponse(
            submission_id=submission_id,
            student_id=submission.user_id,
            model_version=comparison.model_version,
            compared_count=comparison.compared_count,
            considered_count=comparison.considered_count,
            excluded=dict(comparison.excluded),
            changes=[
                MeasureChangeOut(
                    measure=change.measure,
                    current=change.current,
                    baseline=(
                        None
                        if change.baseline is None
                        else BaselineOut(
                            mean=change.baseline.mean,
                            spread=change.baseline.spread,
                            n=change.baseline.n,
                            lowest=change.baseline.lowest,
                            highest=change.baseline.highest,
                        )
                    ),
                    difference=change.difference,
                )
                for change in comparison.changes
            ],
            limitations=list(CONSISTENCY_LIMITATIONS),
        )

    # ── Internals ────────────────────────────────────────────────────────────

    async def _scope(
        self,
        viewer: User,
        class_id: uuid.UUID | None,
        date_from: dt.date | None,
        date_to: dt.date | None,
    ) -> list[uuid.UUID]:
        """The submissions in scope, once the viewer is known to be entitled.

        ``require_class`` is reused rather than reimplemented: it refuses a
        class the caller does not teach instead of returning an empty one, and
        that rule needs exactly one home.
        """
        if class_id is not None:
            await self.analytics.require_class(class_id, viewer)
        elif viewer.is_teacher:
            # A teacher asking for the unscoped view would otherwise read the
            # whole installation. The platform scope is an administrator's.
            raise ValidationError("Name a class. Only administrators may read platform-wide.")

        if date_from and date_to and date_from > date_to:
            raise ValidationError("The start of the period must not be after its end.")

        return await self.analytics_repo.scored_submission_ids(
            AnalyticsWindow(class_id=class_id, date_from=date_from, date_to=date_to),
            timezone=self.settings.PLATFORM_TIMEZONE,
        )


def _bucket(day: dt.date, interval: str) -> dt.date:
    """The first day of the period ``day`` falls in."""
    if interval == "day":
        return day
    if interval == "week":
        return day - dt.timedelta(days=day.weekday())
    return day.replace(day=1)


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_mistake(row: Any) -> bool:
    """Whether a stored issue asserts a mistake.

    An unrecognised severity counts as a preference rather than an error: an
    unreadable row must not inflate the number a student is told they got
    wrong.
    """
    try:
        return IssueSeverity(row.severity).is_mistake
    except ValueError:
        return False


__all__ = ["CONSISTENCY_LIMITATIONS", "AssessmentService", "ConsistencyDisabledError"]
