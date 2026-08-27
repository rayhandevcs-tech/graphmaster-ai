"""Assignment business logic.

Access follows the class rule from FR-11.6 exactly: a teacher may only act on
assignments belonging to classes they own, an administrator is unrestricted,
and a class the caller does not teach is **refused, not returned empty**
(rule 33) — an empty report and a forbidden one look identical, and the first
is a lie.

Nothing here touches scoring. An assignment is a label and a deadline; the
rubric, the tier, the XP award and the leaderboard behave the same whether a
submission belongs to one or not.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.core.exceptions import (
    AssignmentNotFoundError,
    ClassNotFoundError,
    GraphNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.models.content import Assignment
from app.models.identity import User
from app.repositories.assignment import AssignmentRepository, SubmissionStanding
from app.repositories.class_ import ClassRepository
from app.repositories.graph import GraphRepository
from app.repositories.user import UserRepository
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate

logger = get_logger(__name__)


class AssignmentService:
    def __init__(
        self,
        assignments: AssignmentRepository,
        classes: ClassRepository,
        graphs: GraphRepository,
        users: UserRepository,
    ) -> None:
        self.assignments = assignments
        self.classes = classes
        self.graphs = graphs
        self.users = users

    # ── Access control ───────────────────────────────────────────────────────

    def _require_teaches(self, assignment: Assignment, actor: User) -> None:
        if actor.is_admin:
            return
        if assignment.class_.teacher_id != actor.id:
            raise PermissionDeniedError("You can only manage work you set for your own classes.")

    async def _require_assignment(self, assignment_id: uuid.UUID) -> Assignment:
        assignment = await self.assignments.get_full(assignment_id)
        if assignment is None:
            raise AssignmentNotFoundError()
        return assignment

    async def _require_visible(self, assignment_id: uuid.UUID, viewer: User) -> Assignment:
        """The assignment, if this caller is allowed to see it at all.

        A student may read work set for their own class; anything else reads
        as absent rather than forbidden, because telling a student that an
        assignment exists in another section is itself a disclosure.
        """
        assignment = await self._require_assignment(assignment_id)
        if viewer.can_manage_content:
            self._require_teaches(assignment, viewer)
            return assignment
        if assignment.class_id != viewer.class_id or not assignment.is_active:
            raise AssignmentNotFoundError()
        return assignment

    async def require_open_for(self, assignment_id: uuid.UUID, *, student: User) -> Assignment:
        """The assignment a student is about to file work against.

        Deliberately the *visibility* rule and nothing more. A closed
        assignment reads as absent, but a **passed deadline does not**: the
        product refuses no work over a due date, it only records that the work
        arrived late. Refusing the answer a student finally sat down to write
        is the opposite of what the platform is for.
        """
        return await self._require_visible(assignment_id, student)

    # ── Serialisation ────────────────────────────────────────────────────────

    @staticmethod
    def _summary(assignment: Assignment) -> dict[str, Any]:
        return {
            "id": assignment.id,
            "class_id": assignment.class_id,
            "graph_id": assignment.graph_id,
            "title": assignment.title,
            "instructions": assignment.instructions,
            "due_at": assignment.due_at,
            "is_active": assignment.is_active,
            "created_at": assignment.created_at,
            "graph_title": assignment.graph.title,
            "graph_type": assignment.graph.graph_type,
            "class_name": assignment.class_.name,
        }

    def summaries(self, rows: list[Assignment]) -> list[dict[str, Any]]:
        return [self._summary(a) for a in rows]

    async def detail_payload(self, assignment: Assignment, *, viewer: User) -> dict[str, Any]:
        payload = self._summary(assignment) | {
            "assigned_by": assignment.assigned_by,
            "updated_at": assignment.updated_at,
        }
        if not viewer.can_manage_content:
            standing = await self.assignments.own_standing(assignment.id, viewer.id)
            if standing is not None:
                payload["submission_id"] = standing.submission_id
                payload["submission_status"] = standing.status
        return payload

    async def get(self, assignment_id: uuid.UUID, *, viewer: User) -> dict[str, Any]:
        assignment = await self._require_visible(assignment_id, viewer)
        return await self.detail_payload(assignment, viewer=viewer)

    # ── Writes ───────────────────────────────────────────────────────────────

    async def create(self, payload: AssignmentCreate, *, teacher: User) -> dict[str, Any]:
        class_ = await self.classes.get_with_teacher(payload.class_id)
        if class_ is None:
            raise ClassNotFoundError()
        if not teacher.is_admin and class_.teacher_id != teacher.id:
            raise PermissionDeniedError("You can only set work for classes you teach.")

        graph = await self.graphs.get_with_targets(payload.graph_id)
        if graph is None:
            raise GraphNotFoundError()
        if not graph.is_published:
            # A draft graph is invisible to students, so setting it would give
            # the class a task it cannot open.
            raise ValidationError("Publish the graph before setting it as work.")

        assignment = Assignment(
            class_id=class_.id,
            graph_id=graph.id,
            title=payload.title,
            instructions=payload.instructions,
            due_at=payload.due_at,
            assigned_by=teacher.id,
            is_active=True,
        )
        await self.assignments.add(assignment)
        logger.info(
            "Assignment %s (%r) set on class %s by %s",
            assignment.id,
            assignment.title,
            class_.id,
            teacher.id,
        )
        return await self.detail_payload(
            await self._require_assignment(assignment.id), viewer=teacher
        )

    async def update(
        self, assignment_id: uuid.UUID, payload: AssignmentUpdate, *, actor: User
    ) -> dict[str, Any]:
        assignment = await self._require_assignment(assignment_id)
        self._require_teaches(assignment, actor)

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(assignment, field, value)

        await self.assignments.db.flush()
        # Re-read rather than serialising the flushed instance: `updated_at`
        # has a server-side onupdate, so the flush expires it and reading it
        # back mid-response would need a lazy load the async driver cannot
        # service (rule 23).
        return await self.detail_payload(
            await self._require_assignment(assignment_id), viewer=actor
        )

    # ── Progress ─────────────────────────────────────────────────────────────

    async def progress(self, assignment_id: uuid.UUID, *, actor: User) -> dict[str, Any]:
        """Who has done the work and who has not.

        Counted against **enrolment** (rule 35). "Twelve of thirty" and the
        eighteen names that are missing is the figure a teacher acts on;
        "twelve submissions" lets half a class disappear behind the half that
        practised hard.
        """
        assignment = await self._require_assignment(assignment_id)
        self._require_teaches(assignment, actor)

        roster = await self.users.list_by_class(assignment.class_id)
        standings = await self.assignments.standings(assignment_id, [s.id for s in roster])

        students = [
            self._student_row(student, standings.get(student.id), assignment.due_at)
            for student in roster
        ]
        submitted = [row for row in students if row["submission_id"] is not None]

        return {
            "assignment": self._summary(assignment),
            "enrolled_count": len(roster),
            "submitted_count": len(submitted),
            "scored_count": sum(1 for row in submitted if row["final_score"] is not None),
            "late_count": sum(1 for row in submitted if row["is_late"]),
            "average_score": await self.assignments.scored_average(assignment_id),
            "students": students,
        }

    @staticmethod
    def _student_row(
        student: User, standing: SubmissionStanding | None, due_at: datetime | None
    ) -> dict[str, Any]:
        if standing is None:
            return {
                "user_id": student.id,
                "full_name": student.full_name,
                "submission_id": None,
                "status": None,
                # Null, never 0: a student who has not started is not one who
                # scored nothing (rule 32).
                "final_score": None,
                "submitted_at": None,
                "is_late": False,
            }
        return {
            "user_id": student.id,
            "full_name": student.full_name,
            "submission_id": standing.submission_id,
            "status": standing.status,
            "final_score": standing.final_score,
            "submitted_at": standing.submitted_at,
            # Recorded, never punished: a passed deadline never refuses work
            # and never changes a mark. The teacher can see it; the student's
            # score, tier and XP cannot feel it.
            "is_late": due_at is not None and standing.submitted_at > due_at,
        }
