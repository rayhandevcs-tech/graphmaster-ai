"""Assignment endpoints.

Work a teacher sets for one class. Authorisation is enforced in
``AssignmentService``, never here, so it cannot be skipped by adding an
endpoint — the same arrangement the class router uses.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import AssignmentRepo, AssignmentSvc, CurrentUser, TeacherUser
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentDetail,
    AssignmentProgress,
    AssignmentSummary,
    AssignmentUpdate,
)
from app.schemas.common import Page

router = APIRouter(tags=["assignments"])


@router.get(
    "",
    response_model=Page[AssignmentSummary],
    summary="Work set for you, or work you have set",
)
async def list_assignments(
    user: CurrentUser,
    repo: AssignmentRepo,
    assignments: AssignmentSvc,
    class_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[AssignmentSummary]:
    # One endpoint for both audiences: the repository narrows the set by role,
    # so a student sees their own class's open work and a teacher sees every
    # class they own.
    stmt = repo.build_list_query(viewer=user, class_id=class_id, is_active=is_active)
    rows, total = await repo.paginate(stmt, page=page, page_size=page_size)
    return Page[AssignmentSummary].build(
        [AssignmentSummary.model_validate(a) for a in assignments.summaries(list(rows))],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    response_model=AssignmentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Set a graph as work for a class",
)
async def create_assignment(
    payload: AssignmentCreate, teacher: TeacherUser, assignments: AssignmentSvc
) -> AssignmentDetail:
    return AssignmentDetail.model_validate(await assignments.create(payload, teacher=teacher))


@router.get("/{assignment_id}", response_model=AssignmentDetail, summary="Assignment detail")
async def get_assignment(
    assignment_id: uuid.UUID, user: CurrentUser, assignments: AssignmentSvc
) -> AssignmentDetail:
    return AssignmentDetail.model_validate(await assignments.get(assignment_id, viewer=user))


@router.patch("/{assignment_id}", response_model=AssignmentDetail, summary="Update an assignment")
async def update_assignment(
    assignment_id: uuid.UUID,
    payload: AssignmentUpdate,
    teacher: TeacherUser,
    assignments: AssignmentSvc,
) -> AssignmentDetail:
    return AssignmentDetail.model_validate(
        await assignments.update(assignment_id, payload, actor=teacher)
    )


@router.get(
    "/{assignment_id}/progress",
    response_model=AssignmentProgress,
    summary="Who has submitted, and who has not",
)
async def assignment_progress(
    assignment_id: uuid.UUID, teacher: TeacherUser, assignments: AssignmentSvc
) -> AssignmentProgress:
    return AssignmentProgress.model_validate(
        await assignments.progress(assignment_id, actor=teacher)
    )
