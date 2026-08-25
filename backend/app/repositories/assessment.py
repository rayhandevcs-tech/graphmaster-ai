"""Assessment persistence.

The engine produces a frozen :class:`~app.assessment.result.AssessmentResult`
that knows nothing about the database; this is the one place that turns one
into rows. Writes join whatever transaction the caller is already in — the
assessment and the score it accompanies land together or not at all.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.assessment.result import AssessmentResult
from app.models.assessment import AssessmentDetail, AssessmentIssue
from app.models.enums import AssessmentStatus, IssueCategory
from app.repositories.base import BaseRepository

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

        detail.issues = [
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


__all__ = ["SCORE_COLUMNS", "AssessmentRepository"]
