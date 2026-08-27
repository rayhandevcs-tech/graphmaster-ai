"""Assignment data access."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, false, func, select
from sqlalchemy.orm import selectinload

from app.models.content import Assignment
from app.models.enums import SubmissionStatus, UserRole
from app.models.identity import Class, User
from app.models.submission import Score, Submission
from app.repositories.base import BaseRepository


@dataclass(frozen=True)
class SubmissionStanding:
    """One student's submission against one assignment, flattened for a report."""

    submission_id: uuid.UUID
    status: str
    submitted_at: datetime
    final_score: float | None


class AssignmentRepository(BaseRepository[Assignment]):
    model = Assignment

    async def get_full(self, assignment_id: uuid.UUID) -> Assignment | None:
        """One assignment with the graph and class a response names.

        Both are eager-loaded because every serialisation of an assignment
        shows the graph's title and the class's name; left lazy they raise
        ``MissingGreenlet`` the moment the async driver is asked for them.
        """
        stmt = (
            select(Assignment)
            .where(Assignment.id == assignment_id)
            .options(selectinload(Assignment.graph), selectinload(Assignment.class_))
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    def build_list_query(
        self,
        *,
        viewer: User,
        class_id: uuid.UUID | None = None,
        is_active: bool | None = None,
    ) -> Select[Any]:
        """A listing already narrowed to what ``viewer`` may see.

        Scoped here rather than in the router, the same way submissions are,
        so no endpoint can forget it and a caller-supplied ``class_id`` can
        only ever narrow a set that is already restricted.
        """
        stmt = select(Assignment).options(
            selectinload(Assignment.graph), selectinload(Assignment.class_)
        )
        stmt = self._apply_visibility(stmt, viewer)

        if class_id is not None:
            stmt = stmt.where(Assignment.class_id == class_id)
        if is_active is not None:
            stmt = stmt.where(Assignment.is_active.is_(is_active))

        # Soonest deadline first, and undated work after everything dated —
        # a task with no deadline is never the most urgent thing on the list.
        return stmt.order_by(
            Assignment.due_at.is_(None), Assignment.due_at, Assignment.created_at.desc()
        )

    def _apply_visibility(self, stmt: Select[Any], viewer: User) -> Select[Any]:
        if viewer.role == UserRole.ADMIN.value:
            return stmt
        if viewer.role == UserRole.TEACHER.value:
            taught = select(Class.id).where(Class.teacher_id == viewer.id)
            return stmt.where(Assignment.class_id.in_(taught))
        # A student sees the work set for their own class, and only while it
        # is open. An unenrolled student sees an empty list, which is correct:
        # nobody has set them anything.
        if viewer.class_id is None:
            return stmt.where(false())
        return stmt.where(
            Assignment.class_id == viewer.class_id, Assignment.is_active.is_(True)
        )

    async def standings(
        self, assignment_id: uuid.UUID, user_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, SubmissionStanding]:
        """Each student's latest submission for this assignment, in one query.

        Latest rather than best: the progress report answers "has this been
        done", and a student who re-attempted a graph filed a *new* submission
        (rule 19) rather than overwriting the first.
        """
        if not user_ids:
            return {}
        stmt = (
            select(
                Submission.user_id,
                Submission.id,
                Submission.status,
                Submission.submitted_at,
                Score.final_score,
            )
            .outerjoin(Score, Score.submission_id == Submission.id)
            .where(
                Submission.assignment_id == assignment_id,
                Submission.user_id.in_(list(user_ids)),
            )
            .order_by(Submission.user_id, Submission.submitted_at.desc())
        )
        standings: dict[uuid.UUID, SubmissionStanding] = {}
        for user_id, sub_id, status, submitted_at, final_score in (
            await self.db.execute(stmt)
        ).all():
            # Ordered newest-first per student, so the first row wins.
            standings.setdefault(
                user_id,
                SubmissionStanding(
                    submission_id=sub_id,
                    status=status,
                    submitted_at=submitted_at,
                    final_score=float(final_score) if final_score is not None else None,
                ),
            )
        return standings

    async def own_standing(
        self, assignment_id: uuid.UUID, user_id: uuid.UUID
    ) -> SubmissionStanding | None:
        return (await self.standings(assignment_id, [user_id])).get(user_id)

    async def submitted_counts(
        self, assignment_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, int]:
        """How many distinct students have filed against each assignment.

        Distinct students, not submissions: a student who attempted a graph
        three times has done the work once.
        """
        if not assignment_ids:
            return {}
        stmt = (
            select(Submission.assignment_id, func.count(func.distinct(Submission.user_id)))
            .where(Submission.assignment_id.in_(list(assignment_ids)))
            .group_by(Submission.assignment_id)
        )
        return {row[0]: int(row[1]) for row in (await self.db.execute(stmt)).all()}

    async def has_submissions(self, assignment_id: uuid.UUID) -> bool:
        stmt = select(Submission.id).where(Submission.assignment_id == assignment_id).limit(1)
        return (await self.db.execute(stmt)).first() is not None

    async def scored_average(self, assignment_id: uuid.UUID) -> float | None:
        """Mean final score across the scored submissions, or None for none.

        None rather than 0 (rule 32): a class that has not been marked yet is
        not a class that scored nothing.
        """
        stmt = (
            select(func.avg(Score.final_score))
            .select_from(Submission)
            .join(Score, Score.submission_id == Submission.id)
            .where(
                Submission.assignment_id == assignment_id,
                Submission.status == SubmissionStatus.SCORED.value,
            )
        )
        value = (await self.db.execute(stmt)).scalar_one_or_none()
        return round(float(value), 2) if value is not None else None
