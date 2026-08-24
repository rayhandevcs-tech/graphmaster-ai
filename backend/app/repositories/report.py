"""Teacher report data access."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, select

from app.models.identity import Class, User
from app.models.reporting import TeacherReport
from app.repositories.base import BaseRepository


class ReportRepository(BaseRepository[TeacherReport]):
    model = TeacherReport

    def build_list_query(self, viewer: User) -> Select[Any]:
        """The caller's own reports, or everyone's for an administrator.

        An export carries students' names, scores and email addresses, so the
        listing is scoped here rather than in the router: every path to a
        report goes through this method, and a filter cannot widen what it
        already narrowed.
        """
        stmt = select(TeacherReport).order_by(TeacherReport.created_at.desc())
        if not viewer.is_admin:
            stmt = stmt.where(TeacherReport.teacher_id == viewer.id)
        return stmt

    async def teaches(self, *, teacher_id: uuid.UUID, student_id: uuid.UUID) -> bool:
        """Whether this student is enrolled in a class the teacher owns."""
        stmt = (
            select(User.id)
            .join(Class, Class.id == User.class_id)
            .where(User.id == student_id, Class.teacher_id == teacher_id)
        )
        return (await self.db.execute(stmt)).first() is not None
