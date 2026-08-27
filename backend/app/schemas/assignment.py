"""Assignment schemas.

An assignment is a class, a graph and an expectation. Everything else about
how the work is marked is unchanged, so these schemas carry no scoring fields
at all — the score lives on the submission, exactly where it did before.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.models.enums import GraphType
from app.schemas.common import ORMModel


class AssignmentSummary(ORMModel):
    """One row in a task list, for a teacher or a student."""

    id: uuid.UUID
    class_id: uuid.UUID
    graph_id: uuid.UUID
    title: str
    instructions: str | None
    due_at: datetime | None = Field(
        default=None,
        description="Null means no deadline, which is not the same as overdue",
    )
    is_active: bool
    created_at: datetime

    # Denormalised for the listing, so a task list does not need one request
    # per row to show what it is actually asking the student to describe.
    graph_title: str
    graph_type: GraphType
    class_name: str

    # ── Two audiences, and never both at once ────────────────────────────────
    #
    # A teacher's card answers "how much of the class has done this"; a
    # student's answers "have I done this". The fields the other audience does
    # not get are null rather than absent, so one response model serves both
    # without a client having to guess which shape arrived.

    #: How many enrolled students have filed against this. **Teacher only.**
    #:
    #: Null for a student, deliberately: telling them how many classmates have
    #: finished is the comparison FR-7.6 keeps off the leaderboard, arriving by
    #: another door. Their own card says whether *they* have started.
    submitted_count: int | None = None
    #: The denominator, which is enrolment and never "whoever submitted"
    #: (rule 35). **Teacher only.**
    enrolled_count: int | None = None

    #: The reader's own attempt, when they have one. **Student only.**
    #:
    #: A teacher reading an assignment sees the whole class through
    #: ``/progress``; this answers the one question a student has on opening
    #: it — "have I done this yet?"
    submission_id: uuid.UUID | None = None
    submission_status: str | None = None


class AssignmentDetail(AssignmentSummary):
    assigned_by: uuid.UUID | None
    updated_at: datetime


class AssignmentCreate(BaseModel):
    class_id: uuid.UUID
    graph_id: uuid.UUID
    title: Annotated[str, Field(min_length=2, max_length=200)]
    instructions: str | None = Field(default=None, max_length=4000)
    due_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v: str) -> str:
        cleaned = " ".join(v.strip().split())
        if not cleaned:
            raise ValueError("Assignment title cannot be blank.")
        return cleaned


class AssignmentUpdate(BaseModel):
    """Everything an assignment may become after it is set.

    ``class_id`` and ``graph_id`` are absent on purpose: moving an assignment
    to another graph would silently change what the submissions already filed
    against it were answering.
    """

    title: Annotated[str, Field(min_length=2, max_length=200)] | None = None
    instructions: str | None = Field(default=None, max_length=4000)
    due_at: datetime | None = None
    is_active: bool | None = None

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = " ".join(v.strip().split())
        if not cleaned:
            raise ValueError("Assignment title cannot be blank.")
        return cleaned


class AssignmentStudentProgress(BaseModel):
    """One enrolled student's standing against one assignment."""

    user_id: uuid.UUID
    full_name: str
    submission_id: uuid.UUID | None = None
    status: str | None = Field(
        default=None,
        description="The submission's status, or null for a student who has not started",
    )
    final_score: float | None = Field(
        default=None, description="Null until the submission is scored — never 0 (rule 32)"
    )
    submitted_at: datetime | None = None
    is_late: bool = Field(
        default=False,
        description="Submitted after the deadline. Recorded, never punished.",
    )


class AssignmentProgress(BaseModel):
    """Who has done the work and who has not.

    Counted against **enrolment**, not against whoever happened to submit
    (rule 35): a class where half the students never started must not read as
    full marks. ``average_score`` is null rather than 0 when nothing has been
    scored yet (rule 32).
    """

    assignment: AssignmentSummary
    enrolled_count: int
    submitted_count: int
    scored_count: int
    late_count: int
    average_score: float | None = None
    students: list[AssignmentStudentProgress]
