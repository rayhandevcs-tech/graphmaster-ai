"""Avatar data access."""

from __future__ import annotations

from sqlalchemy import select

from app.models.enums import Gender
from app.models.identity import Avatar
from app.repositories.base import BaseRepository


class AvatarRepository(BaseRepository[Avatar]):
    model = Avatar

    async def get_by_code(self, code: str) -> Avatar | None:
        stmt = select(Avatar).where(Avatar.code == code)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_default_for_gender(self, gender: Gender | str) -> Avatar | None:
        value = gender.value if isinstance(gender, Gender) else gender
        stmt = select(Avatar).where(Avatar.gender == value, Avatar.is_default.is_(True))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_gender(self, gender: Gender | str) -> list[Avatar]:
        value = gender.value if isinstance(gender, Gender) else gender
        stmt = (
            select(Avatar).where(Avatar.gender == value).order_by(Avatar.unlock_level, Avatar.name)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_all(self) -> list[Avatar]:
        stmt = select(Avatar).order_by(Avatar.gender, Avatar.unlock_level, Avatar.name)
        return list((await self.db.execute(stmt)).scalars().all())
