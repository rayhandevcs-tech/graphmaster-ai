"""Submission and score data access."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload

from app.models.content import Graph
from app.models.enums import InputMethod, RewardTier, SubmissionStatus, UserRole
from app.models.identity import Class, User
from app.models.submission import Score, Submission
from app.repositories.base import BaseRepository


@dataclass(frozen=True)
class ScoringStats:
    """A student's scoring history, aggregated for the achievement rules.

    Read as one batch per scoring rather than once per achievement: the
    catalogue is evaluated in full on every submission, and ten achievements
    each running their own count would make marking ten times as expensive for
    no additional information.
    """

    scored_submissions: int = 0
    tier_counts: dict[str, int] = field(default_factory=dict)
    best_final_score: float = 0.0
    distinct_graph_types: int = 0
    recent_vocabulary_percentages: tuple[float, ...] = ()


class SubmissionRepository(BaseRepository[Submission]):
    model = Submission

    # ── Reads ────────────────────────────────────────────────────────────────

    async def get_full(self, submission_id: uuid.UUID) -> Submission | None:
        """One submission with everything a detail response needs.

        The graph and score are eager-loaded because the response serialises
        both; left lazy they raise ``MissingGreenlet`` the moment the async
        driver is asked to service a synchronous attribute access.
        """
        stmt = (
            select(Submission)
            .where(Submission.id == submission_id)
            .options(
                selectinload(Submission.graph),
                selectinload(Submission.score),
                selectinload(Submission.user),
            )
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def lock(self, submission_id: uuid.UUID) -> Submission | None:
        """Read a submission and hold a row lock until the transaction ends.

        This is what makes scoring exactly-once. Without it, two ``analyze``
        calls racing on one submission both read a not-yet-scored row, both
        run the engine, and both try to insert a score — one dies on the
        unique constraint with a 500, and from Sprint 7 onwards both award XP
        for a single piece of work.

        No eager loads: ``FOR UPDATE`` may not be combined with the outer
        joins some loader strategies emit, and the caller re-reads through
        :meth:`get_full` once the write is done anyway.
        """
        stmt = select(Submission).where(Submission.id == submission_id).with_for_update()
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def reusable_draft(
        self, *, user_id: uuid.UUID, graph_id: uuid.UUID, input_method: InputMethod
    ) -> Submission | None:
        """An untouched draft this student already opened for this graph.

        Only a *pristine* draft qualifies — no text, no image. A student who
        double-taps "Start practice" gets the same row back instead of
        littering the table with abandoned attempts, but a draft they have
        actually put work into is never silently handed to a second attempt.
        """
        stmt = (
            select(Submission)
            .where(
                Submission.user_id == user_id,
                Submission.graph_id == graph_id,
                Submission.input_method == input_method.value,
                Submission.status == SubmissionStatus.DRAFT.value,
                Submission.answer_text.is_(None),
                Submission.original_image_path.is_(None),
            )
            .order_by(Submission.submitted_at.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    # ── Listing ──────────────────────────────────────────────────────────────

    def build_list_query(
        self,
        *,
        viewer: User,
        graph_id: uuid.UUID | None = None,
        student_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        status: SubmissionStatus | None = None,
        reward_tier: RewardTier | None = None,
        scored_only: bool = False,
    ) -> Select[Any]:
        """A listing query already narrowed to what ``viewer`` may see.

        The scoping is applied here rather than in the router so no caller can
        forget it: every listing path in the application goes through this one
        method, and a filter a student supplies can only ever narrow a set
        that is already restricted to their own rows.
        """
        stmt = select(Submission).options(
            selectinload(Submission.graph),
            selectinload(Submission.score),
            selectinload(Submission.user),
        )

        stmt = self._apply_visibility(stmt, viewer)

        if graph_id is not None:
            stmt = stmt.where(Submission.graph_id == graph_id)
        if status is not None:
            stmt = stmt.where(Submission.status == status.value)
        if scored_only:
            stmt = stmt.where(Submission.status == SubmissionStatus.SCORED.value)

        # Teacher-only narrowing. A student's own rows are already the whole
        # visible set, so these are ignored rather than rejected for them.
        if viewer.can_manage_content:
            if student_id is not None:
                stmt = stmt.where(Submission.user_id == student_id)
            if class_id is not None:
                stmt = stmt.join(User, User.id == Submission.user_id).where(
                    User.class_id == class_id
                )

        if reward_tier is not None:
            stmt = stmt.join(Score, Score.submission_id == Submission.id).where(
                Score.reward_tier == reward_tier.value
            )

        return stmt.order_by(Submission.submitted_at.desc())

    def _apply_visibility(self, stmt: Select[Any], viewer: User) -> Select[Any]:
        if viewer.role == UserRole.ADMIN.value:
            return stmt
        if viewer.role == UserRole.TEACHER.value:
            # A teacher sees the work of students enrolled in classes they own,
            # and nothing else. A teacher with no classes sees an empty list —
            # correct, not a bug: teaching nobody means having no student work
            # to read.
            taught = select(Class.id).where(Class.teacher_id == viewer.id)
            enrolled = select(User.id).where(User.class_id.in_(taught))
            return stmt.where(Submission.user_id.in_(enrolled))
        return stmt.where(Submission.user_id == viewer.id)

    # ── Aggregates ───────────────────────────────────────────────────────────

    async def scoring_stats(self, user_id: uuid.UUID, *, recent_window: int = 3) -> ScoringStats:
        """Everything the achievement catalogue asks about one student.

        ``recent_window`` is how far back the "N in a row" rules need to look;
        it comes from the catalogue rather than being fixed here, so adding a
        five-in-a-row achievement does not leave this reading three.
        """
        scored = Submission.status == SubmissionStatus.SCORED.value

        totals = (
            select(
                func.count(Score.id),
                func.coalesce(func.max(Score.final_score), 0),
                func.count(func.distinct(Graph.graph_type)),
            )
            .select_from(Submission)
            .join(Score, Score.submission_id == Submission.id)
            .join(Graph, Graph.id == Submission.graph_id)
            .where(Submission.user_id == user_id, scored)
        )
        count, best, graph_types = (await self.db.execute(totals)).one()

        tiers = (
            select(Score.reward_tier, func.count(Score.id))
            .select_from(Submission)
            .join(Score, Score.submission_id == Submission.id)
            .where(Submission.user_id == user_id, scored)
            .group_by(Score.reward_tier)
        )
        tier_counts = {tier: int(n) for tier, n in (await self.db.execute(tiers)).all()}

        recent = (
            select(Score.vocabulary_percentage)
            .select_from(Submission)
            .join(Score, Score.submission_id == Submission.id)
            .where(Submission.user_id == user_id, scored)
            .order_by(Submission.scored_at.desc(), Submission.id.desc())
            .limit(max(1, recent_window))
        )
        percentages = tuple(float(p) for p in (await self.db.execute(recent)).scalars().all())

        return ScoringStats(
            scored_submissions=int(count),
            tier_counts=tier_counts,
            best_final_score=float(best),
            distinct_graph_types=int(graph_types),
            recent_vocabulary_percentages=percentages,
        )

    async def visible_to(self, submission: Submission, viewer: User) -> bool:
        """Whether ``viewer`` may read one already-loaded submission."""
        if viewer.role == UserRole.ADMIN.value:
            return True
        if submission.user_id == viewer.id:
            return True
        if viewer.role != UserRole.TEACHER.value:
            return False
        stmt = (
            select(User.id)
            .join(Class, Class.id == User.class_id)
            .where(User.id == submission.user_id, Class.teacher_id == viewer.id)
        )
        return (await self.db.execute(stmt)).first() is not None
