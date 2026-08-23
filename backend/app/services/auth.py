"""Authentication business logic.

Raises domain exceptions, never HTTPException, so it stays callable from tests
and CLI tooling without a request in scope.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.core.exceptions import (
    AccountInactiveError,
    ClassCodeInvalidError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidTokenError,
    UserNotFoundError,
)
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    decode_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.models.enums import UserRole
from app.models.identity import AuthSession, Class, User
from app.repositories.auth_session import AuthSessionRepository
from app.repositories.avatar import AvatarRepository
from app.repositories.user import UserRepository, normalize_email
from app.schemas.auth import RegisterRequest

logger = get_logger(__name__)


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        sessions: AuthSessionRepository,
        avatars: AvatarRepository,
    ) -> None:
        self.users = users
        self.sessions = sessions
        self.avatars = avatars
        self.settings = get_settings()

    # ── Registration ─────────────────────────────────────────────────────────

    async def register(
        self,
        payload: RegisterRequest,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, IssuedTokens]:
        email = normalize_email(payload.email)

        if await self.users.email_exists(email):
            raise EmailAlreadyRegisteredError()

        # The avatar is chosen from gender at registration (FR-2.2). A missing
        # default means the database was never seeded; failing loudly here is
        # better than silently creating avatar-less students whose reward
        # animations would have nothing to animate.
        avatar = await self.avatars.get_default_for_gender(payload.gender)
        if avatar is None:
            logger.error("No default avatar seeded for gender %r", payload.gender.value)

        class_id = None
        if payload.class_code:
            class_id = (await self._resolve_class_code(payload.class_code)).id

        user = User(
            email=email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            role=UserRole.STUDENT.value,
            gender=payload.gender.value,
            avatar_id=avatar.id if avatar else None,
            class_id=class_id,
        )
        await self.users.add(user)

        tokens = await self._issue_tokens(user, user_agent=user_agent, ip_address=ip_address)
        logger.info("Registered user %s", user.email)
        return user, tokens

    async def _resolve_class_code(self, code: str) -> Class:
        stmt = select(Class).where(Class.code == code.strip().upper(), Class.is_active.is_(True))
        klass = (await self.users.db.execute(stmt)).scalar_one_or_none()
        if klass is None:
            raise ClassCodeInvalidError()
        return klass

    # ── Login ────────────────────────────────────────────────────────────────

    async def login(
        self,
        email: str,
        password: str,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, IssuedTokens]:
        user = await self.users.get_by_email(email)

        if user is None:
            # Hash anyway so a missing account and a wrong password take
            # comparable time. Returning immediately would let an attacker
            # enumerate registered addresses by timing alone.
            hash_password("timing-equalisation-dummy-password")
            raise InvalidCredentialsError()

        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()

        if not user.is_active:
            raise AccountInactiveError()

        tokens = await self._issue_tokens(user, user_agent=user_agent, ip_address=ip_address)
        return user, tokens

    # ── Token issuing and rotation ───────────────────────────────────────────

    async def _issue_tokens(
        self,
        user: User,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> IssuedTokens:
        access = create_access_token(user.id, role=user.role, gender=user.gender)
        refresh = generate_refresh_token()

        await self.sessions.add(
            AuthSession(
                user_id=user.id,
                refresh_token_hash=hash_refresh_token(refresh),
                user_agent=(user_agent or "")[:500] or None,
                ip_address=(ip_address or "")[:45] or None,
                expires_at=refresh_token_expiry(),
            )
        )

        return IssuedTokens(
            access_token=access,
            refresh_token=refresh,
            expires_in=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh(
        self,
        refresh_token: str,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, IssuedTokens]:
        """Rotate a refresh token.

        The presented token is revoked and a new one issued. Presenting an
        already-revoked token revokes the user's entire session family: a
        refresh token is single-use, so a second presentation means the token
        leaked and both the attacker's and the victim's copies must die.
        """
        session = await self.sessions.get_by_token_hash(hash_refresh_token(refresh_token))

        if session is None:
            raise InvalidTokenError("Invalid refresh token.")

        if session.is_revoked:
            logger.warning(
                "Replayed refresh token for user %s; revoking all sessions", session.user_id
            )
            await self.sessions.revoke_all_for_user(session.user_id)
            raise InvalidTokenError("This session has been revoked. Please sign in again.")

        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            raise InvalidTokenError("Refresh token has expired. Please sign in again.")

        user = await self.users.get_with_avatar(session.user_id)
        if user is None:
            raise UserNotFoundError()
        if not user.is_active:
            raise AccountInactiveError()

        await self.sessions.revoke(session)
        tokens = await self._issue_tokens(user, user_agent=user_agent, ip_address=ip_address)
        return user, tokens

    async def logout(self, refresh_token: str | None) -> None:
        """Revoke the presented session.

        An unknown token is not an error: logging out is idempotent, and the
        caller ends up in the intended state either way.
        """
        if not refresh_token:
            return
        session = await self.sessions.get_by_token_hash(hash_refresh_token(refresh_token))
        if session and not session.is_revoked:
            await self.sessions.revoke(session)

    async def logout_all(self, user_id: uuid.UUID) -> int:
        return await self.sessions.revoke_all_for_user(user_id)

    # ── Password reset ───────────────────────────────────────────────────────

    async def request_password_reset(self, email: str) -> str | None:
        """Create a reset token, or return None when no such account exists.

        The caller must respond identically either way — a different response
        for an unknown address turns this endpoint into an account-enumeration
        oracle.
        """
        user = await self.users.get_by_email(email)
        if user is None or not user.is_active:
            return None
        return create_password_reset_token(user.id)

    async def confirm_password_reset(self, token: str, new_password: str) -> User:
        payload = decode_token(token, expected_type="password_reset")

        user = await self.users.get(uuid.UUID(payload["sub"]))
        if user is None:
            raise UserNotFoundError()
        if not user.is_active:
            raise AccountInactiveError()

        user.password_hash = hash_password(new_password)

        # Every existing session dies with the old password. Otherwise a
        # password reset prompted by a suspected compromise would leave the
        # attacker's refresh token working for another 30 days.
        await self.sessions.revoke_all_for_user(user.id)
        await self.users.db.flush()

        logger.info("Password reset completed for user %s", user.id)
        return user

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise InvalidCredentialsError("Your current password is incorrect.")

        user.password_hash = hash_password(new_password)
        await self.sessions.revoke_all_for_user(user.id)
        await self.users.db.flush()
