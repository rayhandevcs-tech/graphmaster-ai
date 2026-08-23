"""User schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import Gender, UserRole
from app.schemas.avatar import AvatarOut
from app.schemas.common import ORMModel


class LevelProgress(BaseModel):
    """Where the user sits within their current level."""

    current_level: int
    total_xp: int
    xp_into_level: int = Field(description="XP earned since reaching the current level")
    xp_for_next_level: int = Field(description="XP span of the current level")
    progress_percent: float = Field(ge=0, le=100)
    is_max_level: bool


class UserProfile(ORMModel):
    """The caller's own profile."""

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    gender: Gender
    avatar: AvatarOut | None = None
    class_id: uuid.UUID | None = None
    total_xp: int
    current_level: int
    current_streak_days: int
    longest_streak_days: int
    last_activity_date: date | None = None
    is_active: bool
    created_at: datetime


class PublicUserProfile(ORMModel):
    """Another user's profile.

    Deliberately omits email, class membership and activity dates: one student
    browsing the leaderboard has no reason to learn another's contact details
    or attendance pattern.
    """

    id: uuid.UUID
    full_name: str
    gender: Gender
    avatar: AvatarOut | None = None
    current_level: int
    total_xp: int


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    avatar_id: uuid.UUID | None = None

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = " ".join(v.split())
        if not cleaned:
            raise ValueError("Full name cannot be blank.")
        return cleaned


class AdminUserUpdateRequest(BaseModel):
    """Fields only an administrator may change."""

    role: UserRole | None = None
    class_id: uuid.UUID | None = None
    is_active: bool | None = None


class UserListItem(ORMModel):
    """A row in the administrator's user list."""

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    gender: Gender
    class_id: uuid.UUID | None = None
    total_xp: int
    current_level: int
    is_active: bool
    created_at: datetime
