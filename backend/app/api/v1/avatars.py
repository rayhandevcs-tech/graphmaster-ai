"""Avatar catalogue and selection."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AvatarRepo, CurrentUser, UserSvc
from app.schemas.avatar import AvatarOut, AvatarSelectRequest, AvatarWithLock
from app.schemas.user import UserProfile

router = APIRouter(tags=["avatars"])


@router.get(
    "",
    response_model=list[AvatarWithLock],
    summary="Avatars available to you, with unlock state",
)
async def list_avatars(user: CurrentUser, users: UserSvc) -> list[AvatarWithLock]:
    rows = await users.list_avatars_for(user)
    return [AvatarWithLock.model_validate(r) for r in rows]


@router.get("/all", response_model=list[AvatarOut], summary="The full avatar catalogue")
async def list_all_avatars(_: CurrentUser, avatars: AvatarRepo) -> list[AvatarOut]:
    return [AvatarOut.model_validate(a) for a in await avatars.list_all()]


@router.put("/select", response_model=UserProfile, summary="Choose your avatar")
async def select_avatar(
    payload: AvatarSelectRequest, user: CurrentUser, users: UserSvc
) -> UserProfile:
    return UserProfile.model_validate(await users.select_avatar(user, payload.avatar_id))
