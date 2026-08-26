"""Assessment endpoints: what the student should do differently.

The scoring endpoints answer *what was this worth*. These answer *what went
wrong, where, and why* — and they are the first surface in the platform that
applies the analyzer audience filter, which is the reason every read here goes
through one service rather than being served alongside the submission it
belongs to.

**A student's copy is built without what they may not see.** Not serialised
with fields blanked, not filtered in the router: the payload is assembled from
the visible analyzers only, so a field added to a schema later cannot carry
through something withheld. The audiences come from the row the assessment was
written on, never from this server's current configuration — a rollout stage
that has moved since the work was marked must not retroactively reveal what was
dark when it was marked.

The class-level reads are teacher-facing and obey the two rules approved
before Sprint 17: every figure carries the count it was taken over, and a
trend line breaks where that count is zero rather than interpolating across
the gap.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Query

from app.api.deps import AssessmentSvc, CurrentUser, TeacherUser
from app.schemas.assessment import (
    AnalyzerScoreReport,
    AnalyzerTrendReport,
    AssessmentResponse,
    ConsistencyResponse,
    IssueFrequencyReport,
)

router = APIRouter(tags=["assessment"])

ClassId = Query(
    default=None,
    description="Narrow to one class. Required for a teacher; administrators may omit it.",
)
DateFrom = Query(default=None, description="First day of the period, inclusive")
DateTo = Query(default=None, description="Last day of the period, inclusive")


@router.get(
    "/submissions/{submission_id}",
    response_model=AssessmentResponse,
    summary="One submission's assessment",
    description=(
        "Issues located in the student's own text, per-analyzer status and the "
        "diagnostic category scores.\n\n"
        "**Filtered by audience.** A student receives only the analyzers promoted all "
        "the way to them; staff receive everything except what is still in a dark "
        "rollout. The withheld analyzers are absent from the payload rather than "
        "blanked, and the decision comes from the audiences recorded when the work was "
        "marked — not from the server's current rollout stage.\n\n"
        "Nothing here can move a score. `scores` are diagnostic figures reported "
        "beside `final_score`, never folded into it, and a null means the analyzer did "
        "not run for this submission — a different fact from a score of zero.\n\n"
        "Returns 404 for a submission the caller may not read, and for one with no "
        "assessment: an empty assessment would claim the work was checked and nothing "
        "was found."
    ),
)
async def submission_assessment(
    submission_id: uuid.UUID, user: CurrentUser, assessment: AssessmentSvc
) -> AssessmentResponse:
    return await assessment.for_submission(submission_id, viewer=user)


@router.get(
    "/issues",
    response_model=IssueFrequencyReport,
    summary="The commonest mistakes across a class",
    description=(
        "Grouped by `subtype`, which is a stable slug rather than display wording — the "
        "human phrasing can be rewritten between releases without invalidating a year "
        "of this report.\n\n"
        "`assessed_count` is reported beside `submission_count` and is not decoration: "
        "submissions marked before the assessment engine existed carry none, and there "
        "is no backfill, so this is always over a subset.\n\n"
        "Returns 403 for a class the caller does not teach — refused rather than "
        "returned empty, because an empty report and a forbidden one look identical "
        "and only one of them is true (FR-11.6)."
    ),
)
async def class_issues(
    user: TeacherUser,
    assessment: AssessmentSvc,
    class_id: uuid.UUID | None = ClassId,
    date_from: date | None = DateFrom,
    date_to: date | None = DateTo,
    limit: int = Query(default=10, ge=1, le=50),
) -> IssueFrequencyReport:
    return await assessment.issue_frequency(
        viewer=user, class_id=class_id, date_from=date_from, date_to=date_to, limit=limit
    )


@router.get(
    "/scores",
    response_model=AnalyzerScoreReport,
    summary="Every analyzer's mean, with the count behind each",
    description=(
        "The counts differ between analyzers and that is the finding, not noise: on a "
        "server with no grammar engine grammar's `assessed_count` is zero while "
        "spelling's is the whole cohort. An `average` is null — never zero — when "
        "nothing in scope was assessed for that analyzer, because a class whose grammar "
        "was never checked is not one that scored nothing."
    ),
)
async def class_scores(
    user: TeacherUser,
    assessment: AssessmentSvc,
    class_id: uuid.UUID | None = ClassId,
    date_from: date | None = DateFrom,
    date_to: date | None = DateTo,
) -> AnalyzerScoreReport:
    return await assessment.score_summary(
        viewer=user, class_id=class_id, date_from=date_from, date_to=date_to
    )


@router.get(
    "/trend/{analyzer}",
    response_model=AnalyzerTrendReport,
    summary="One analyzer's score over time",
    description=(
        "Periods roll over together in the platform timezone, so a cohort shares its "
        "boundaries.\n\n"
        "**A period with nothing assessed is absent from `points`, never present with a "
        "zero.** Consumers draw a gap. Interpolating across it would put a step change "
        "on the day the engine was switched on and render it as a sudden improvement in "
        "the class."
    ),
)
async def class_trend(
    analyzer: str,
    user: TeacherUser,
    assessment: AssessmentSvc,
    class_id: uuid.UUID | None = ClassId,
    interval: str = Query(default="week", pattern="^(day|week|month)$"),
    date_from: date | None = DateFrom,
    date_to: date | None = DateTo,
) -> AnalyzerTrendReport:
    return await assessment.score_trend(
        viewer=user,
        analyzer=analyzer,
        class_id=class_id,
        interval=interval,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/submissions/{submission_id}/consistency",
    response_model=ConsistencyResponse,
    summary="How this submission sits against the student's own earlier work",
    description=(
        "**Observations, not conclusions.** Nothing here is a probability that text was "
        "machine-generated, an authorship decision, or a risk value under any name. "
        "There is no composite across the measures, no threshold, and no ordering of "
        "students — a flag with no label is a verdict with the wording removed.\n\n"
        "Two limits travel in the payload rather than in a help page, because they "
        "change how every figure should be read: this platform's own feedback names the "
        "vocabulary a student then uses, so it is often the cause of what is measured "
        "here; and a settled profile is not evidence of anything, since these measures "
        "show change and a baseline can itself be assisted.\n\n"
        "A `baseline` is null — never zero, never 'consistent' — until the student has "
        "enough comparable prior submissions. That is the normal state for most of a "
        "term. `excluded` says how many were set aside and why: a comparison never "
        "crosses an engine-configuration change, an input-method change or a chart-type "
        "change.\n\n"
        "Teacher and administrator only, and 503 where the deployment has not enabled "
        "the comparison layer — an empty comparison and a switched-off one look "
        "identical, and only the first is a fact about the student."
    ),
)
async def submission_consistency(
    submission_id: uuid.UUID, user: TeacherUser, assessment: AssessmentSvc
) -> ConsistencyResponse:
    return await assessment.consistency(submission_id, viewer=user)
