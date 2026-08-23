"""Class (cohort) schemas.

Named ``class_`` because ``class`` is a Python keyword.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.avatar import AvatarOut
from app.schemas.common import ORMModel

# Join codes are read aloud in a classroom and typed from a slide, so the
# alphabet excludes characters that look alike in common fonts: O/0, I/1/L.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
CODE_PATTERN = r"^[A-Za-z0-9-]{4,32}$"

ClassCode = Annotated[str, Field(pattern=CODE_PATTERN)]


class ClassSummary(ORMModel):
    id: uuid.UUID
    name: str
    code: str
    description: str | None
    teacher_id: uuid.UUID
    is_active: bool
    student_count: int = 0
    created_at: datetime


class ClassDetail(ClassSummary):
    teacher_name: str
    updated_at: datetime


class ClassCreate(BaseModel):
    """A new class.

    ``code`` is optional. Teachers who already use a course code ("ENG201B")
    keep it; everyone else gets a generated one.
    """

    name: Annotated[str, Field(min_length=2, max_length=200)]
    description: str | None = Field(default=None, max_length=2000)
    code: ClassCode | None = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        cleaned = " ".join(v.strip().split())
        if not cleaned:
            raise ValueError("Class name cannot be blank.")
        return cleaned

    @field_validator("code")
    @classmethod
    def _upper_code(cls, v: str | None) -> str | None:
        # Stored and compared uppercase so a student typing "eng201b" joins.
        return v.strip().upper() if v is not None else None


class ClassUpdate(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=200)] | None = None
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = " ".join(v.strip().split())
        if not cleaned:
            raise ValueError("Class name cannot be blank.")
        return cleaned


class ClassStudent(ORMModel):
    """One roster row.

    Submission statistics (attempts, average score) join in at Sprint 6 when
    the submissions table has rows; the gamification figures below are already
    real.
    """

    id: uuid.UUID
    full_name: str
    email: EmailStr
    gender: str
    avatar: AvatarOut | None
    total_xp: int
    current_level: int
    current_streak_days: int
    last_activity_date: date | None
    is_active: bool


class ClassEnrolRequest(BaseModel):
    email: EmailStr


class ClassJoinRequest(BaseModel):
    code: ClassCode

    @field_validator("code")
    @classmethod
    def _upper_code(cls, v: str) -> str:
        return v.strip().upper()
