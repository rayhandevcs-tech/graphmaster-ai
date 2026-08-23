"""Authentication request and response schemas."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import Gender
from app.schemas.user import UserProfile

# bcrypt ignores everything past 72 bytes, so a longer password would mean two
# different passwords unlock the same account. Capped here at the boundary.
PASSWORD_MIN = 8
PASSWORD_MAX = 72

Password = Annotated[str, Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)]


def _validate_password_strength(value: str) -> str:
    if len(value.encode("utf-8")) > PASSWORD_MAX:
        raise ValueError(
            f"Password must be at most {PASSWORD_MAX} bytes. "
            "Accented and non-Latin characters use more than one byte each."
        )
    if not re.search(r"[A-Za-z]", value):
        raise ValueError("Password must contain at least one letter.")
    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one digit.")
    return value


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: Password
    gender: Gender
    class_code: str | None = Field(
        default=None,
        max_length=32,
        description="Optional class join code; enrols the student immediately.",
    )

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _validate_password_strength(v)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        cleaned = " ".join(v.split())
        if not cleaned:
            raise ValueError("Full name cannot be blank.")
        return cleaned


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)


class RefreshRequest(BaseModel):
    """Only needed by clients that cannot use the refresh cookie."""

    refresh_token: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class AuthResponse(BaseModel):
    """Returned by register and login."""

    user: UserProfile
    tokens: TokenPair


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: Password

    @field_validator("new_password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX)
    new_password: Password

    @field_validator("new_password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _validate_password_strength(v)
