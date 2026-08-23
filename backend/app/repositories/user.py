"""User data access."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import selectinload

from app.models.enums import UserRole
from app.models.identity import User
from app.repositories.base import BaseRepository


def normalize_email(email: str) -> str:
    """Lowercase and trim.

    Pydantic's EmailStr normalises only the domain, so "N@Example.com" and
    "n@example.com" would otherwise be two distinct accounts.
    """
    return email.strip().lower()


class UserRepository(BaseRepository[User]):
    model = User

    async def get_with_avatar(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id).options(selectinload(User.avatar))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .where(User.email == normalize_email(email))
            .options(selectinload(User.avatar))
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        stmt = select(User.id).where(User.email == normalize_email(email))
        return (await self.db.execute(stmt)).first() is not None

    def build_list_query(
        self,
        *,
        role: UserRole | None = None,
        class_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> Select[Any]:
        stmt = select(User).options(selectinload(User.avatar))
        if role is not None:
            stmt = stmt.where(User.role == role.value)
        if class_id is not None:
            stmt = stmt.where(User.class_id == class_id)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        if search:
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(or_(User.email.ilike(pattern), User.full_name.ilike(pattern)))
        return stmt.order_by(User.created_at.desc())

    async def list_by_class(self, class_id: uuid.UUID) -> list[User]:
        stmt = (
            select(User)
            .where(User.class_id == class_id, User.role == UserRole.STUDENT.value)
            .options(selectinload(User.avatar))
            .order_by(User.full_name)
        )
        return list((await self.db.execute(stmt)).scalars().all())
