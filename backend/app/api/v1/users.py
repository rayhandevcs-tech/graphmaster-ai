"""User profile and administration endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, AnalyticsSvc, CurrentUser, StudentUser, UserRepo, UserSvc
from app.models.enums import UserRole
from app.schemas.analytics import StudentDashboard
from app.schemas.common import Page
from app.schemas.user import (
    AdminUserUpdateRequest,
    LevelProgress,
    PublicUserProfile,
    UserListItem,
    UserProfile,
    UserUpdateRequest,
)

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserProfile, summary="Your own profile")
async def get_me(user: CurrentUser, users: UserSvc) -> UserProfile:
    return UserProfile.model_validate(await users.get_profile(user.id))


@router.patch("/me", response_model=UserProfile, summary="Update your profile")
async def update_me(payload: UserUpdateRequest, user: CurrentUser, users: UserSvc) -> UserProfile:
    return UserProfile.model_validate(await users.update_profile(user, payload))


@router.get("/me/level", response_model=LevelProgress, summary="Your level progress")
async def get_my_level(user: CurrentUser, users: UserSvc) -> LevelProgress:
    return LevelProgress.model_validate(users.level_progress(user))


@router.get(
    "/me/dashboard",
    response_model=StudentDashboard,
    summary="Your dashboard",
    description=(
        "Everything the student's home screen renders (FR-10.1 to FR-10.5): attempt "
        "totals and averages, XP and level progress, the practice streak, unlocked "
        "achievements, badge counts, recent attempts and a score trend.\n\n"
        "Delivered as one payload rather than six, because it paints as a single "
        "screen — six requests would show the XP bar, the streak and the chart "
        "arriving at different moments, which reads as the page being broken rather "
        "than loading.\n\n"
        "Students only. Teachers and administrators have `/analytics/*`, which answers "
        "a different question about other people."
    ),
)
async def get_my_dashboard(student: StudentUser, analytics: AnalyticsSvc) -> StudentDashboard:
    return StudentDashboard.model_validate(await analytics.student_dashboard(student))


@router.get(
    "/{user_id}",
    response_model=PublicUserProfile,
    summary="Another user's public profile",
)
async def get_public_profile(
    user_id: uuid.UUID, _: CurrentUser, users: UserSvc
) -> PublicUserProfile:
    return PublicUserProfile.model_validate(await users.get_public_profile(user_id))


# ── Administration ───────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=Page[UserListItem],
    summary="List users (administrators only)",
)
async def list_users(
    _: AdminUser,
    repo: UserRepo,
    role: UserRole | None = None,
    class_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[UserListItem]:
    stmt = repo.build_list_query(role=role, class_id=class_id, is_active=is_active, search=search)
    rows, total = await repo.paginate(stmt, page=page, page_size=page_size)
    return Page[UserListItem].build(
        [UserListItem.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.patch(
    "/{user_id}",
    response_model=UserProfile,
    summary="Update a user's role, class or status (administrators only)",
)
async def admin_update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdateRequest,
    actor: AdminUser,
    users: UserSvc,
) -> UserProfile:
    return UserProfile.model_validate(await users.admin_update(user_id, payload, actor=actor))
