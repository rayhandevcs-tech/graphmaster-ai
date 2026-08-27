"""The practice flow (FR-4.x, FR-6.x).

A student opens a submission, gets text into it — by typing, or by
photographing handwriting and correcting what was read — and then asks for it
to be marked. Scoring is the point of no return: once a submission is scored
its text is frozen, because the score carries XP that has already been awarded
and counts towards achievements and the leaderboard.

Re-attempting a graph means opening a *new* submission. Nothing is overwritten,
so a student's improvement across attempts stays visible — which is the
longitudinal data the project's evaluation depends on.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, StudentUser, SubmissionSvc
from app.core.exceptions import FileTooLargeError
from app.core.rate_limit import ANALYZE_LIMIT, UPLOAD_LIMIT, enforce
from app.models.enums import RewardTier, SubmissionStatus
from app.schemas.common import Page
from app.schemas.gamification import GamificationOut
from app.schemas.submission import (
    ExtractionResult,
    ScoreOut,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionResult,
    SubmissionSummary,
    SubmissionTextUpdate,
)

router = APIRouter(tags=["submissions"])


@router.post(
    "",
    response_model=SubmissionDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Open a submission for a graph",
    description=(
        "Choose `typed` or `handwriting` up front — it decides which route the client "
        "shows next, and it is recorded as research data about how students actually "
        "answer. Opening the same graph twice without having written anything returns "
        "the draft already open rather than creating a second one. Returns 404 for an "
        "unknown or unpublished graph."
    ),
)
async def create_submission(
    payload: SubmissionCreate, student: StudentUser, submissions: SubmissionSvc
) -> SubmissionDetail:
    submission = await submissions.start(
        graph_id=payload.graph_id,
        input_method=payload.input_method,
        student=student,
        assignment_id=payload.assignment_id,
    )
    return SubmissionDetail.model_validate(submissions.detail_payload(submission, viewer=student))


@router.post(
    "/{submission_id}/upload",
    response_model=ExtractionResult,
    summary="Upload handwriting and read it",
    description=(
        "Stores the photograph, runs the recognition chain, and returns the text as an "
        "**editable preview** — nothing is scored yet. The reading is also kept "
        "unmodified as `ocr_text`, so a later correction stays measurable.\n\n"
        "Returns 413 for an oversized file, 415 for anything that is not a JPG, PNG or "
        "WEBP image, and 422 with `OCR_FAILED` when every engine fails — in which case "
        "the submission is left in `failed` **with the image still retained**, so the "
        "student can try another photograph or type the answer into the same attempt."
    ),
)
async def upload_handwriting(
    submission_id: uuid.UUID,
    request: Request,
    student: StudentUser,
    submissions: SubmissionSvc,
    file: UploadFile = File(description="JPG, PNG or WEBP photograph of handwriting"),
) -> ExtractionResult:
    enforce(request, UPLOAD_LIMIT)

    data = await _read_within_limit(file, submissions.settings.max_upload_bytes)
    submission, warning = await submissions.upload(
        submission_id, data, filename=file.filename, student=student
    )
    payload = submissions.detail_payload(submission, viewer=student)

    return ExtractionResult(
        submission_id=submission.id,
        status=SubmissionStatus(submission.status),
        ocr_text=submission.ocr_text or "",
        ocr_provider=submission.ocr_provider,
        ocr_confidence=payload["ocr_confidence"],
        word_count=submission.word_count,
        image_url=payload["image_url"],
        warning=warning,
    )


@router.patch(
    "/{submission_id}/text",
    response_model=SubmissionDetail,
    summary="Set or correct the answer text",
    description=(
        "The editable step FR-4.7 requires: a student may fix whatever the recogniser "
        "misread before anything is marked. Correcting an extracted answer sets "
        "`was_ocr_edited`. Also the way to recover a submission whose recognition "
        "failed — type the answer and the attempt continues. Returns 409 once the "
        "submission has been scored."
    ),
)
async def set_answer_text(
    submission_id: uuid.UUID,
    payload: SubmissionTextUpdate,
    student: StudentUser,
    submissions: SubmissionSvc,
) -> SubmissionDetail:
    submission = await submissions.set_text(submission_id, payload.text, student=student)
    return SubmissionDetail.model_validate(submissions.detail_payload(submission, viewer=student))


@router.post(
    "/{submission_id}/analyze",
    response_model=SubmissionResult,
    summary="Submit for marking",
    description=(
        "Runs detection, writing assessment, scoring, tier and feedback, and stores the "
        "result. This is final: the submission is frozen afterwards and re-analysis is "
        "refused with 409, because the score carries XP that has already been awarded.\n\n"
        "Returns 409 when there is no answer text yet or the submission is already "
        "scored, and 503 when the language model is not installed on this server — in "
        "which case nothing is consumed and the same request will succeed once the "
        "server is provisioned.\n\n"
        "The response carries the score **and** what it earned — XP, level, tier badge, "
        "any achievements unlocked and the practice streak — in one payload, because "
        "the result screen sequences a single animation from both: the tier decides "
        "which one plays and the XP total decides what the bar counts up to."
    ),
)
async def analyze_submission(
    submission_id: uuid.UUID,
    request: Request,
    student: StudentUser,
    submissions: SubmissionSvc,
) -> SubmissionResult:
    enforce(request, ANALYZE_LIMIT)

    submission, _, awards = await submissions.analyse(submission_id, student=student)
    payload = submissions.detail_payload(submission, viewer=student)

    return SubmissionResult(
        submission=SubmissionDetail.model_validate(payload),
        score=ScoreOut.model_validate(payload["score"]),
        gamification=GamificationOut.model_validate(awards, from_attributes=True),
        reference_description=payload.get("reference_description"),
    )


@router.get(
    "",
    response_model=Page[SubmissionSummary],
    summary="List submissions",
    description=(
        "Students see their own attempts. Teachers see the attempts of students "
        "enrolled in classes they own, and administrators see everything. The scoping "
        "is applied before any filter, so the query parameters can only narrow what the "
        "caller may already read."
    ),
)
async def list_submissions(
    user: CurrentUser,
    submissions: SubmissionSvc,
    graph_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = Query(
        default=None, description="Teachers and administrators only; ignored for students."
    ),
    class_id: uuid.UUID | None = Query(
        default=None, description="Teachers and administrators only; ignored for students."
    ),
    submission_status: SubmissionStatus | None = Query(default=None, alias="status"),
    reward_tier: RewardTier | None = None,
    scored_only: bool = Query(default=False, description="Only attempts that were marked"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[SubmissionSummary]:
    stmt = submissions.submissions.build_list_query(
        viewer=user,
        graph_id=graph_id,
        student_id=student_id,
        class_id=class_id,
        status=submission_status,
        reward_tier=reward_tier,
        scored_only=scored_only,
    )
    rows, total = await submissions.submissions.paginate(stmt, page=page, page_size=page_size)
    return Page[SubmissionSummary].build(
        [SubmissionSummary.model_validate(submissions.summary_payload(r)) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/{submission_id}",
    response_model=SubmissionDetail,
    summary="One submission with its score",
    description=(
        "A student requesting someone else's submission receives 404 rather than 403, "
        "so the endpoint cannot be used to confirm that a guessed id exists."
    ),
)
async def get_submission(
    submission_id: uuid.UUID, user: CurrentUser, submissions: SubmissionSvc
) -> SubmissionDetail:
    submission = await submissions.get_for(submission_id, viewer=user)
    return SubmissionDetail.model_validate(submissions.detail_payload(submission, viewer=user))


@router.get(
    "/{submission_id}/image",
    summary="The uploaded handwriting image",
    response_class=StreamingResponse,
    responses={200: {"content": {"image/*": {}}, "description": "The stored original"}},
    description=(
        "Streamed through an authenticated endpoint rather than served from a static "
        "path, so one student's handwriting cannot be read by guessing another's URL. "
        "A browser will not attach a bearer token to an `<img src>`, so clients fetch "
        "this as a blob and render the object URL — that inconvenience is the point."
    ),
)
async def get_submission_image(
    submission_id: uuid.UUID, user: CurrentUser, submissions: SubmissionSvc
) -> StreamingResponse:
    stream, content_type = await submissions.image(submission_id, viewer=user)
    return StreamingResponse(
        stream,
        media_type=content_type,
        headers={
            "Content-Disposition": "inline",
            # Private and revalidated: the image is one student's work, and a
            # shared cache holding it would defeat the access check above.
            "Cache-Control": "private, no-store",
        },
    )


@router.delete(
    "/{submission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Discard an unscored attempt",
    description=(
        "Only an attempt that was never marked can be discarded. A scored submission "
        "is part of the student's history and carries awarded XP, so deleting it would "
        "leave the ledger describing work that no longer exists — that returns 409."
    ),
)
async def delete_submission(
    submission_id: uuid.UUID, student: StudentUser, submissions: SubmissionSvc
) -> Response:
    await submissions.discard(submission_id, student=student)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _read_within_limit(file: UploadFile, limit: int) -> bytes:
    """Read the upload, refusing to buffer more than the limit.

    Read in chunks and stop at the first byte past the maximum. Calling
    `await file.read()` outright would pull an arbitrarily large body into
    memory before any size check could reject it, which turns the size limit
    into exactly the resource-exhaustion vector it exists to prevent.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(64 * 1024):
        total += len(chunk)
        if total > limit:
            raise FileTooLargeError(f"The image exceeds the {limit // 1_048_576} MB limit.")
        chunks.append(chunk)
    return b"".join(chunks)
