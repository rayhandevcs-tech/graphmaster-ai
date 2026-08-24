"""CSV, Excel and PDF exports (FR-11.5).

Generation is synchronous, so a `POST` returns a finished report. The record
still moves through `pending` on its way there, and a failure is stored as
`failed` with a reason rather than vanishing into a 500 — which is both what a
teacher needs to see and what an asynchronous runner would leave behind if one
were ever attached at the `JobRunner` seam.

Files stream through an authenticated endpoint. An export names students, their
scores and their email addresses; serving that from a guessable path would be a
disclosure with extra steps.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import StreamingResponse

from app.api.deps import ReportSvc, TeacherUser
from app.core.config import get_settings
from app.models.enums import ReportType
from app.reports import available_formats
from app.schemas.common import Page
from app.schemas.report import ReportCapabilities, ReportOut, ReportRequest
from app.services.report import MAX_EXPORT_ROWS

router = APIRouter(tags=["reports"])


def _payload(report, prefix: str) -> dict:
    return {
        "id": report.id,
        "report_type": report.report_type,
        "format": report.format,
        "status": report.status,
        "class_id": report.class_id,
        "parameters": report.parameters,
        "download_url": (f"{prefix}/reports/{report.id}/download" if report.file_path else None),
        "error_message": report.error_message,
        "created_at": report.created_at,
        "completed_at": report.completed_at,
    }


@router.get(
    "/capabilities",
    response_model=ReportCapabilities,
    summary="What this server can export",
    description=(
        "CSV is always available. Excel and PDF depend on optional libraries being "
        "installed, so a client should read this rather than offering a button that "
        "would only ever return 503."
    ),
)
async def capabilities(_: TeacherUser) -> ReportCapabilities:
    return ReportCapabilities(
        formats=available_formats(), types=list(ReportType), max_rows=MAX_EXPORT_ROWS
    )


@router.post(
    "",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a report",
    description=(
        "Four types. `class_summary` needs a `class_id` unless the caller is an "
        "administrator; `student_detail` needs a `student_id` in one of the caller's "
        "own classes; `vocabulary_usage` and `submission_export` take either.\n\n"
        "The access rules are the ones the equivalent screens use, so an export can "
        "never reach data a teacher could not read on the page — a report is the "
        "easiest place to leak another teacher's class, precisely because nobody "
        "reads a CSV the way they read a page.\n\n"
        "Returns 503 when the requested format's library is not installed on this "
        "server; the record is stored as `failed` with the reason either way."
    ),
)
async def create_report(
    payload: ReportRequest, teacher: TeacherUser, reports: ReportSvc
) -> ReportOut:
    report = await reports.create(
        teacher=teacher,
        report_type=payload.report_type,
        fmt=payload.format,
        class_id=payload.class_id,
        student_id=payload.student_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
    )
    return ReportOut.model_validate(_payload(report, get_settings().API_V1_PREFIX))


@router.get(
    "",
    response_model=Page[ReportOut],
    summary="Reports you have generated",
    description="Teachers see their own; administrators see everyone's.",
)
async def list_reports(
    teacher: TeacherUser,
    reports: ReportSvc,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[ReportOut]:
    stmt = reports.build_list_query(teacher)
    rows, total = await reports.page(stmt, page=page, page_size=page_size)
    prefix = get_settings().API_V1_PREFIX
    return Page[ReportOut].build(
        [ReportOut.model_validate(_payload(row, prefix)) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/{report_id}",
    response_model=ReportOut,
    summary="One report's status",
    description=(
        "Someone else's report reads as missing rather than forbidden, so the "
        "endpoint cannot be used to confirm that a guessed id exists."
    ),
)
async def get_report(report_id: uuid.UUID, teacher: TeacherUser, reports: ReportSvc) -> ReportOut:
    report = await reports.get_for(report_id, viewer=teacher)
    return ReportOut.model_validate(_payload(report, get_settings().API_V1_PREFIX))


@router.get(
    "/{report_id}/download",
    summary="Download the generated file",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/octet-stream": {}}, "description": "The file"}},
    description=(
        "Authenticated, so a browser will not fetch it from an `<a href>` without a "
        "token — clients download it as a blob. Responses carry "
        "`Cache-Control: private, no-store`, because a shared cache holding a class's "
        "scores would defeat the access check above."
    ),
)
async def download_report(
    report_id: uuid.UUID, teacher: TeacherUser, reports: ReportSvc
) -> StreamingResponse:
    stream, content_type, filename = await reports.download(report_id, viewer=teacher)
    return StreamingResponse(
        stream,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a report",
    description="Removes the record and the stored file.",
)
async def delete_report(report_id: uuid.UUID, teacher: TeacherUser, reports: ReportSvc) -> Response:
    await reports.delete(report_id, viewer=teacher)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
