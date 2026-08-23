"""User and avatar business logic."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import (
    AvatarNotFoundError,
    PermissionDeniedError,
    UserNotFoundError,
)
from app.core.leveling import level_progress
from app.core.logging import get_logger
from app.models.enums import UserRole
from app.models.identity import Avatar, User
from app.repositories.auth_session import AuthSessionRepository
from app.repositories.avatar import AvatarRepository
from app.repositories.user import UserRepository
from app.schemas.user import AdminUserUpdateRequest, UserUpdateRequest

logger = get_logger(__name__)


class UserService:
    def __init__(
        self,
        users: UserRepository,
        avatars: AvatarRepository,
        sessions: AuthSessionRepository | None = None,
    ) -> None:
        self.users = users
        self.avatars = avatars
        self.sessions = sessions
        self.settings = get_settings()

    async def get_profile(self, user_id: uuid.UUID) -> User:
        user = await self.users.get_with_avatar(user_id)
        if user is None:
            raise UserNotFoundError()
        return user

    async def get_public_profile(self, user_id: uuid.UUID) -> User:
        user = await self.users.get_with_avatar(user_id)
        if user is None or not user.is_active:
            # Deactivated accounts read as absent rather than as forbidden, so
            # the endpoint cannot be used to discover which accounts exist.
            raise UserNotFoundError()
        return user

    async def update_profile(self, user: User, payload: UserUpdateRequest) -> User:
        if payload.full_name is not None:
            user.full_name = payload.full_name

        if payload.avatar_id is not None:
            avatar = await self._require_selectable_avatar(user, payload.avatar_id)
            await self._assign_avatar(user, avatar)

        await self.users.db.flush()
        return await self.get_profile(user.id)

    async def select_avatar(self, user: User, avatar_id: uuid.UUID) -> User:
        avatar = await self._require_selectable_avatar(user, avatar_id)
        await self._assign_avatar(user, avatar)
        await self.users.db.flush()
        return await self.get_profile(user.id)

    async def _assign_avatar(self, user: User, avatar: Avatar) -> None:
        """Point the user at ``avatar``, keeping the loaded relationship in step.

        Setting only ``avatar_id`` leaves the already-loaded ``avatar``
        relationship stale: a later read returns the same instance from the
        session's identity map rather than re-querying, so the response would
        carry the previous avatar (or none at all). Assigning the relationship
        itself keeps both in agreement.
        """
        user.avatar = avatar
        user.avatar_id = avatar.id

    async def _require_selectable_avatar(self, user: User, avatar_id: uuid.UUID) -> Avatar:
        avatar = await self.avatars.get(avatar_id)
        if avatar is None:
            raise AvatarNotFoundError()

        if avatar.gender != user.gender:
            # Enforced server-side because the client's avatar list is only a
            # convenience; the rule cannot live in the UI alone.
            raise PermissionDeniedError("That avatar is not available for your profile.")

        if avatar.unlock_level > user.current_level:
            raise PermissionDeniedError(
                f"That avatar unlocks at level {avatar.unlock_level}. "
                f"You are level {user.current_level}."
            )

        return avatar

    async def list_avatars_for(self, user: User) -> list[dict[str, Any]]:
        """The avatar catalogue annotated for one user.

        Only the user's own gender is listed: an avatar of the other gender can
        never be selected, so showing it would only advertise a locked door.
        """
        avatars = await self.avatars.list_for_gender(user.gender)
        return [
            {
                "id": a.id,
                "code": a.code,
                "name": a.name,
                "gender": a.gender,
                "image_url": a.image_url,
                "is_default": a.is_default,
                "unlock_level": a.unlock_level,
                "is_unlocked": a.unlock_level <= user.current_level,
                "is_selected": a.id == user.avatar_id,
            }
            for a in avatars
        ]

    def level_progress(self, user: User) -> dict[str, Any]:
        progress = level_progress(user.total_xp, max_level=self.settings.MAX_LEVEL)
        return {
            "current_level": progress.current_level,
            "total_xp": progress.total_xp,
            "xp_into_level": progress.xp_into_level,
            "xp_for_next_level": progress.xp_for_next_level,
            "progress_percent": progress.progress_percent,
            "is_max_level": progress.is_max_level,
        }

    # ── Administrative ───────────────────────────────────────────────────────

    async def admin_update(
        self, target_id: uuid.UUID, payload: AdminUserUpdateRequest, *, actor: User
    ) -> User:
        target = await self.users.get_with_avatar(target_id)
        if target is None:
            raise UserNotFoundError()

        if target.id == actor.id and payload.role is not None and payload.role != UserRole.ADMIN:
            # An administrator demoting themselves could leave the platform
            # with no administrator at all and no way back in.
            raise PermissionDeniedError("You cannot change your own role.")

        if target.id == actor.id and payload.is_active is False:
            raise PermissionDeniedError("You cannot deactivate your own account.")

        role_changed = payload.role is not None and payload.role.value != target.role

        if payload.role is not None:
            target.role = payload.role.value
        if payload.class_id is not None:
            target.class_id = payload.class_id
        if payload.is_active is not None:
            target.is_active = payload.is_active

        # The role is a claim inside issued access tokens, so a change must
        # invalidate them. Otherwise a demoted user keeps their old privileges
        # until the token expires.
        if (role_changed or payload.is_active is False) and self.sessions is not None:
            await self.sessions.revoke_all_for_user(target.id)

        await self.users.db.flush()
        logger.info("Admin %s updated user %s", actor.id, target.id)
        return await self.get_profile(target.id)
