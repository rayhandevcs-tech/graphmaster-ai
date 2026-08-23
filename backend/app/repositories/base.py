"""Repository base class.

Repositories own all SQL for one aggregate root. Services receive them by
injection, so a unit test can substitute a fake without a database.
"""

from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, entity_id: uuid.UUID) -> ModelT | None:
        return await self.db.get(self.model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        self.db.add(entity)
        # Flush rather than commit: the request-scoped session owns the
        # transaction boundary, so a repository committing here would break
        # the atomicity of any multi-step service operation.
        await self.db.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.db.delete(entity)
        await self.db.flush()

    async def count(self, stmt: Select[Any] | None = None) -> int:
        base = stmt if stmt is not None else select(self.model)
        # Wrap the caller's statement so its filters and joins are preserved;
        # order_by is stripped because it is meaningless in a COUNT and some
        # databases reject it alongside aggregation.
        counted = select(func.count()).select_from(base.order_by(None).subquery())
        return int((await self.db.execute(counted)).scalar_one())

    async def paginate(
        self, stmt: Select[Any], *, page: int, page_size: int
    ) -> tuple[list[ModelT], int]:
        total = await self.count(stmt)
        offset = (page - 1) * page_size
        rows = (await self.db.execute(stmt.offset(offset).limit(page_size))).scalars().all()
        return list(rows), total
