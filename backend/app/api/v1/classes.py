"""Class (cohort) endpoints.

A teacher may only act on classes they own; an administrator is unrestricted
(FR-11.6). The rule is enforced in ``ClassService``, not here, so it cannot be
skipped by adding an endpoint.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response, status

from app.api.deps import ClassRepo, ClassSvc, StudentUser, TeacherUser
from app.schemas.class_ import (
    ClassCreate,
    ClassDetail,
    ClassEnrolRequest,
    ClassJoinRequest,
    ClassStudent,
    ClassSummary,
    ClassUpdate,
)
from app.schemas.common import Page

router = APIRouter(tags=["classes"])


@router.post(
    "/join",
    response_model=ClassDetail,
    summary="Join a class with its code (students)",
)
async def join_class(
    payload: ClassJoinRequest, student: StudentUser, classes: ClassSvc
) -> ClassDetail:
    return ClassDetail.model_validate(await classes.join_by_code(payload.code, student=student))


@router.get("", response_model=Page[ClassSummary], summary="Your classes")
async def list_classes(
    teacher: TeacherUser,
    repo: ClassRepo,
    classes: ClassSvc,
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[ClassSummary]:
    # Administrators see every class; a teacher sees only their own.
    teacher_filter = None if teacher.is_admin else teacher.id
    stmt = repo.build_list_query(teacher_id=teacher_filter, is_active=is_active)
    rows, total = await repo.paginate(stmt, page=page, page_size=page_size)
    return Page[ClassSummary].build(
        [ClassSummary.model_validate(c) for c in await classes.summaries(list(rows))],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    response_model=ClassDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a class",
)
async def create_class(
    payload: ClassCreate, teacher: TeacherUser, classes: ClassSvc
) -> ClassDetail:
    return ClassDetail.model_validate(await classes.create(payload, teacher=teacher))


@router.get("/{class_id}", response_model=ClassDetail, summary="Class detail")
async def get_class(class_id: uuid.UUID, teacher: TeacherUser, classes: ClassSvc) -> ClassDetail:
    return ClassDetail.model_validate(await classes.get(class_id, actor=teacher))


@router.patch("/{class_id}", response_model=ClassDetail, summary="Update a class")
async def update_class(
    class_id: uuid.UUID, payload: ClassUpdate, teacher: TeacherUser, classes: ClassSvc
) -> ClassDetail:
    return ClassDetail.model_validate(await classes.update(class_id, payload, actor=teacher))


@router.get(
    "/{class_id}/students",
    response_model=list[ClassStudent],
    summary="Class roster",
)
async def list_class_students(
    class_id: uuid.UUID, teacher: TeacherUser, classes: ClassSvc
) -> list[ClassStudent]:
    return [ClassStudent.model_validate(s) for s in await classes.roster(class_id, actor=teacher)]


@router.post(
    "/{class_id}/students",
    response_model=ClassStudent,
    status_code=status.HTTP_201_CREATED,
    summary="Enrol a student by email",
)
async def enrol_student(
    class_id: uuid.UUID,
    payload: ClassEnrolRequest,
    teacher: TeacherUser,
    classes: ClassSvc,
) -> ClassStudent:
    student = await classes.enrol_by_email(class_id, payload.email, actor=teacher)
    return ClassStudent.model_validate(student)


@router.delete(
    "/{class_id}/students/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a student from a class",
)
async def unenrol_student(
    class_id: uuid.UUID, user_id: uuid.UUID, teacher: TeacherUser, classes: ClassSvc
) -> Response:
    await classes.unenrol(class_id, user_id, actor=teacher)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
