"""Refresh-token session data access."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.models.identity import AuthSession
from app.repositories.base import BaseRepository


class AuthSessionRepository(BaseRepository[AuthSession]):
    model = AuthSession

    async def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        stmt = select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def revoke(self, session: AuthSession) -> None:
        session.revoked_at = datetime.now(UTC)
        await self.db.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        """Revoke every live session for a user.

        Used on refresh-token replay (the presented token was already revoked,
        so it was probably stolen) and on a role change, so an elevated or
        downgraded role cannot persist in a still-valid access token.
        """
        stmt = (
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        return int((await self.db.execute(stmt)).rowcount or 0)

    async def delete_expired(self) -> int:
        """Housekeeping: drop sessions that can no longer be used."""
        from sqlalchemy import delete

        stmt = delete(AuthSession).where(AuthSession.expires_at < datetime.now(UTC))
        return int((await self.db.execute(stmt)).rowcount or 0)
