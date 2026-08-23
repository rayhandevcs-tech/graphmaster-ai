"""Password hashing and JWT handling."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError

# bcrypt truncates silently at 72 bytes, so passwords are length-capped before
# hashing rather than being quietly accepted with their tails ignored.
BCRYPT_MAX_BYTES = 72

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh", "password_reset"]


# ── Passwords ────────────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    _reject_overlong(password)
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    if len(plain.encode("utf-8")) > BCRYPT_MAX_BYTES:
        return False
    try:
        return _pwd_context.verify(plain, hashed)
    except ValueError:
        # Raised for a malformed or truncated stored hash. A corrupt hash must
        # read as "wrong password", never as a server error that would tell an
        # attacker they had found an interesting account.
        return False


def _reject_overlong(password: str) -> None:
    if len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must be at most {BCRYPT_MAX_BYTES} bytes long.")


# ── Access tokens ────────────────────────────────────────────────────────────


def create_access_token(
    subject: str | uuid.UUID,
    *,
    role: str,
    gender: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "gender": gender,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, *, expected_type: TokenType = "access") -> dict[str, Any]:
    """Decode and validate a JWT.

    Raises ``TokenExpiredError`` or ``InvalidTokenError``; never returns an
    unvalidated payload.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        # python-jose reports expiry as a plain JWTError subclass, so the
        # message is the only signal available to distinguish the two.
        if "expired" in str(exc).lower():
            raise TokenExpiredError() from exc
        raise InvalidTokenError() from exc

    if payload.get("type") != expected_type:
        # Without this check an access token would be accepted wherever a
        # password-reset token is expected, and vice versa.
        raise InvalidTokenError(f"Expected a {expected_type} token.")

    if not payload.get("sub"):
        raise InvalidTokenError("Token is missing its subject claim.")

    return payload


# ── Refresh tokens ───────────────────────────────────────────────────────────


def generate_refresh_token() -> str:
    """A 256-bit opaque token. Not a JWT: it must be revocable server-side."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """SHA-256, not bcrypt.

    The token is already 256 bits of entropy, so it is not brute-forceable and
    needs no key stretching. It is also verified on every refresh, where a
    deliberately slow hash would be a pointless cost.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=get_settings().REFRESH_TOKEN_EXPIRE_DAYS)


# ── Password reset ───────────────────────────────────────────────────────────


def create_password_reset_token(user_id: str | uuid.UUID, *, ttl_minutes: int = 30) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "password_reset",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
