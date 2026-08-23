"""Avatar schemas."""

from __future__ import annotations

import uuid

from pydantic import Field

from app.models.enums import Gender
from app.schemas.common import ORMModel


class AvatarOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    gender: Gender
    image_url: str
    is_default: bool
    unlock_level: int


class AvatarWithLock(AvatarOut):
    """An avatar annotated for the requesting user.

    `is_unlocked` is computed per request rather than stored: it depends on the
    caller's level, so it is not a property of the avatar itself.
    """

    is_unlocked: bool = Field(description="Whether the requesting user may select this avatar")
    is_selected: bool = Field(description="Whether this is the user's current avatar")


class AvatarSelectRequest(ORMModel):
    avatar_id: uuid.UUID
