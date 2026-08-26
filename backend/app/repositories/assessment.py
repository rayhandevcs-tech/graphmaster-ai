"""Assessment persistence.

The engine produces a frozen :class:`~app.assessment.result.AssessmentResult`
that knows nothing about the database; this is the one place that turns one
into rows. Writes join whatever transaction the caller is already in — the
assessment and the score it accompanies land together or not at all.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import desc, func, select
from sqlalchemy.orm import selectinload

from app.assessment.result import AssessmentResult
from app.models.assessment import AssessmentDetail, AssessmentIssue, GraphAccuracyClaim
from app.models.enums import AssessmentStatus, ClaimVerdict, IssueCategory
from app.repositories.base import BaseRepository

if TYPE_CHECKING:  # pragma: no cover
    import datetime

#: Which analyzer's score goes in which column.
#:
#: Vocabulary and writing are absent on purpose: those two live on ``scores``,
#: and a second copy here would be a second thing to keep in step and two
#: columns that could disagree about one number.
SCORE_COLUMNS = {
    "grammar": "grammar_score",
    "spelling": "spelling_score",
    "sentence": "sentence_score",
    "word_usage": "word_usage_score",
    "graph_accuracy": "graph_accuracy_score",
}


@dataclass(frozen=True, slots=True)
class ScoreSummary:
    """One analyzer's score across a set of submissions.

    ``assessed_count`` is reported beside every figure and is not decoration.
    A cohort where four submissions of thirty were checked for grammar and a
    cohort where all thirty were are not the same evidence, and an average
    printed without the count reads as though they were.

    ``average`` is ``None`` — never ``0.0`` — when nothing was assessed. A
    class whose grammar was never checked is not a class that scored nothing,
    and a zero would sort them below a class that genuinely struggled. It is
    also the signal a trend line must break on rather than interpolate across:
    missing assessment data is *unavailable*, not a value.
    """

    assessed_count: int
    average: float | None


class AssessmentRepository(BaseRepository[AssessmentDetail]):
    model = AssessmentDetail

    async def create_for(
        self, submission_id: uuid.UUID, result: AssessmentResult
    ) -> AssessmentDetail:
        """Persist one assessment and its issues.

        Flushed, never committed: the request-scoped session owns the
        transaction, and the submission service is mid-way through writing a
        score and an XP award when this is called.
        """
        detail = AssessmentDetail(
            submission_id=submission_id,
            assessment_version=result.version,
            status=(
                AssessmentStatus.COMPLETE.value
                if result.is_complete
                else AssessmentStatus.PARTIAL.value
            ),
            issue_count=len(result.issues),
            error_count=result.error_count,
            suppressed_count=result.suppressed_count,
            truncated_categories=list(result.truncated_categories),
            analyzer_status={name: out.to_dict() for name, out in result.analyzers.items()},
            analyzer_audiences={
                name: audience.value for name, audience in result.audiences.items()
            },
        )

        for analyzer, column in SCORE_COLUMNS.items():
            output = result.analyzers.get(analyzer)
            # None when the analyzer did not run here, which is a different
            # fact from a score of zero and is stored as a different value.
            setattr(detail, column, output.score if output is not None else None)

        issues = [
            AssessmentIssue(
                category=issue.category.value,
                subtype=issue.subtype,
                severity=issue.severity.value,
                original_text=issue.original_text,
                suggested_text=issue.suggested_text,
                # Truncated here rather than trusted: the column is 400
                # characters and an analyzer that writes an essay would
                # otherwise fail the whole scoring transaction.
                explanation=issue.truncated().explanation,
                start_index=issue.start,
                end_index=issue.end,
                confidence=issue.confidence,
                source=issue.source,
            )
            for issue in result.issues
        ]
        detail.issues = issues

        # Claims are linked to the issue they produced, where they produced
        # one. Matched on the span and the claim type rather than carried
        # through the engine as an object reference: the engine's issue and its
        # claim are separate frozen values, and threading an identity between
        # them would only exist to survive this one write.
        by_span = {
            (i.start_index, i.end_index, i.subtype): i
            for i in issues
            if i.category == IssueCategory.GRAPH_ACCURACY.value
        }
        detail.claims = [
            GraphAccuracyClaim(
                claim_type=claim.claim_type.value,
                series_label=claim.series_label,
                claimed=claim.claimed[:120],
                actual=claim.actual[:120],
                verdict=claim.verdict.value,
                confidence=claim.confidence,
                start_index=claim.start,
                end_index=claim.end,
                issue_id=None,
                issue=(
                    by_span.get((claim.start, claim.end, f"incorrect_{claim.claim_type.value}"))
                    if claim.verdict is ClaimVerdict.INCORRECT
                    else None
                ),
            )
            for claim in result.claims
        ]

        return await self.add(detail)

    async def for_submission(self, submission_id: uuid.UUID) -> AssessmentDetail | None:
        """One submission's assessment with its issues, in reading order."""
        stmt = (
            select(AssessmentDetail)
            .where(AssessmentDetail.submission_id == submission_id)
            .options(selectinload(AssessmentDetail.issues))
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def issue_counts(self, submission_ids: list[uuid.UUID]) -> dict[str, int]:
        """Issue counts by category across a set of submissions.

        Grouped in the database rather than in Python: the teacher analytics
        this feeds runs over a whole class, and pulling every issue back to
        count them would read the cohort's corrections into memory to build one
        histogram.
        """
        if not submission_ids:
            return {category.value: 0 for category in IssueCategory}

        stmt = (
            select(AssessmentIssue.category, func.count())
            .join(AssessmentDetail, AssessmentDetail.id == AssessmentIssue.assessment_id)
            .where(AssessmentDetail.submission_id.in_(submission_ids))
            .group_by(AssessmentIssue.category)
        )
        found = dict((await self.db.execute(stmt)).all())

        # Zeros included: a missing key reads as missing data, a zero reads as
        # a finding.
        return {category.value: int(found.get(category.value, 0)) for category in IssueCategory}

    # ── Teacher analytics ────────────────────────────────────────────────────
    #
    # Foundation, not presentation: these answer the questions a class report
    # asks, and the report itself composes them. They are teacher-facing by
    # construction — every one of them takes a set of submission ids that the
    # caller has already established the teacher may see, and none of them can
    # be reached with a student's own submission alone.

    async def issue_frequency(
        self,
        submission_ids: list[uuid.UUID],
        *,
        category: IssueCategory | None = None,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        """The commonest mistakes across a set of submissions, most frequent first.

        Grouped by ``subtype``, which is why that column is a stable slug
        rather than display wording: the human phrasing in ``explanation`` can
        be rewritten between releases without invalidating a year of "the
        mistakes this class makes most".

        Counted in the database. A class report over a term would otherwise
        read every correction the cohort has ever received into memory to
        build one histogram.
        """
        if not submission_ids:
            return []

        counter = func.count().label("occurrences")
        stmt = (
            select(AssessmentIssue.subtype, counter)
            .join(AssessmentDetail, AssessmentDetail.id == AssessmentIssue.assessment_id)
            .where(AssessmentDetail.submission_id.in_(submission_ids))
            .group_by(AssessmentIssue.subtype)
            # Subtype breaks the tie so a report run twice on unchanged data
            # does not reorder equally common mistakes between runs.
            .order_by(desc(counter), AssessmentIssue.subtype)
            .limit(limit)
        )
        if category is not None:
            stmt = stmt.where(AssessmentIssue.category == category.value)

        return [
            (str(subtype), int(count)) for subtype, count in (await self.db.execute(stmt)).all()
        ]

    async def score_summary(self, submission_ids: list[uuid.UUID], analyzer: str) -> ScoreSummary:
        """One analyzer's mean score, and how many submissions it actually ran on.

        Rows where the score is NULL are excluded from both figures rather
        than counted as zero. NULL means the analyzer did not run for that
        submission — no engine configured, or it failed — and averaging it in
        as a nought would report a class as failing at grammar because their
        server has no grammar checker.
        """
        column = _score_column(analyzer)
        if not submission_ids:
            return ScoreSummary(assessed_count=0, average=None)

        stmt = (
            select(func.count(column), func.avg(column))
            .where(AssessmentDetail.submission_id.in_(submission_ids))
            .where(column.is_not(None))
        )
        assessed, average = (await self.db.execute(stmt)).one()

        assessed = int(assessed or 0)
        return ScoreSummary(
            assessed_count=assessed,
            average=round(float(average), 2) if assessed and average is not None else None,
        )

    async def score_series(
        self, submission_ids: list[uuid.UUID], analyzer: str
    ) -> list[tuple[datetime.datetime, float]]:
        """Every assessed score with the moment it was produced, oldest first.

        Returned unbucketed on purpose. A trend line's periods are boundaries
        in ``PLATFORM_TIMEZONE`` — a cohort must roll over together — and
        expressing that in SQL would push a timezone conversion into the
        database, where SQLite and PostgreSQL disagree about how to do it. The
        service layer buckets these in the platform's zone, the way every
        other date in the platform is already handled.

        Submissions with no score for this analyzer are absent rather than
        present with a zero, so a period with nothing in it comes out empty —
        which is what a broken line is drawn from.
        """
        column = _score_column(analyzer)
        if not submission_ids:
            return []

        stmt = (
            select(AssessmentDetail.created_at, column)
            .where(AssessmentDetail.submission_id.in_(submission_ids))
            .where(column.is_not(None))
            .order_by(AssessmentDetail.created_at)
        )
        return [
            (created_at, float(score)) for created_at, score in (await self.db.execute(stmt)).all()
        ]


def _score_column(analyzer: str):
    """The column holding ``analyzer``'s score, or a clear failure.

    Raises rather than returning None: an analyzer name that has no column is
    a programming error in the caller, and answering "no data" for it would
    report an empty class report as a real finding — the same lie an empty
    forbidden report tells.
    """
    name = SCORE_COLUMNS.get(analyzer)
    if name is None:
        raise ValueError(
            f"No assessment score column for analyzer {analyzer!r}. "
            f"Known: {', '.join(sorted(SCORE_COLUMNS))}."
        )
    return getattr(AssessmentDetail, name)


__all__ = ["SCORE_COLUMNS", "AssessmentRepository", "ScoreSummary"]
