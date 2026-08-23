"""Class (cohort) data access."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload

from app.models.enums import UserRole
from app.models.identity import Class, User
from app.repositories.base import BaseRepository


class ClassRepository(BaseRepository[Class]):
    model = Class

    async def get_with_teacher(self, class_id: uuid.UUID) -> Class | None:
        stmt = select(Class).where(Class.id == class_id).options(selectinload(Class.teacher))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, code: str) -> Class | None:
        stmt = (
            select(Class)
            .where(Class.code == code.strip().upper())
            .options(selectinload(Class.teacher))
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def code_exists(self, code: str) -> bool:
        stmt = select(Class.id).where(Class.code == code.strip().upper())
        return (await self.db.execute(stmt)).first() is not None

    def build_list_query(
        self,
        *,
        teacher_id: uuid.UUID | None = None,
        is_active: bool | None = None,
    ) -> Select[Any]:
        stmt = select(Class).options(selectinload(Class.teacher))
        if teacher_id is not None:
            stmt = stmt.where(Class.teacher_id == teacher_id)
        if is_active is not None:
            stmt = stmt.where(Class.is_active == is_active)
        return stmt.order_by(Class.created_at.desc())

    async def student_counts(self, class_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Enrolment counts keyed by class, in one query rather than per row."""
        if not class_ids:
            return {}
        stmt = (
            select(User.class_id, func.count())
            .where(
                User.class_id.in_(list(class_ids)),
                User.role == UserRole.STUDENT.value,
                User.is_active.is_(True),
            )
            .group_by(User.class_id)
        )
        return {row[0]: int(row[1]) for row in (await self.db.execute(stmt)).all()}

    async def student_count(self, class_id: uuid.UUID) -> int:
        return (await self.student_counts([class_id])).get(class_id, 0)
