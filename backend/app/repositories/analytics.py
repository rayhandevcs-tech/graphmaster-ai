"""Aggregate queries behind the analytics endpoints and the report exports.

Everything here is computed from the live tables rather than read from
``analytics_snapshots``. At classroom scale these are small aggregates over an
indexed date range, and a cache would show a teacher stale numbers immediately
after a lesson — the moment they most want fresh ones. The snapshot table is
reserved for archiving a period permanently, which is a different job.

Vocabulary usage is counted out of ``scores.detected_terms``, which stores what
the engine actually matched. Recounting the answer text here would mean a
second, subtly different detector — and two detectors that disagree make the
analytics unusable as evidence.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Integer, Select, and_, cast, column, func, select, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Graph, VocabularyCategory, VocabularyItem
from app.models.enums import SubmissionStatus, UserRole
from app.models.gamification import UserAchievement
from app.models.identity import Class, User
from app.models.submission import Score, Submission


@dataclass(frozen=True)
class AnalyticsWindow:
    """What a set of metrics is being computed over.

    ``class_id`` and ``student_id`` narrow the population; the dates narrow the
    period. All four are optional, and the platform scope simply supplies none
    of them.
    """

    class_id: uuid.UUID | None = None
    student_id: uuid.UUID | None = None
    date_from: date | None = None
    date_to: date | None = None

    def instants(self, timezone: str) -> tuple[datetime | None, datetime | None]:
        """The date range as a half-open range of instants.

        Built in the platform timezone: a submission marked at 23:30 local
        belongs to that local day, and comparing it against UTC midnight would
        file it under the next one — which is how a "this week" report ends up
        missing the Sunday evening everyone worked.
        """
        tz = ZoneInfo(timezone)
        start = (
            datetime.combine(self.date_from, time.min, tzinfo=tz)
            if self.date_from is not None
            else None
        )
        end = (
            datetime.combine(self.date_to + timedelta(days=1), time.min, tzinfo=tz)
            if self.date_to is not None
            else None
        )
        return start, end


class AnalyticsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Building blocks ──────────────────────────────────────────────────────

    def _scored(self, window: AnalyticsWindow, timezone: str) -> Select[Any]:
        """Marked submissions joined to their scores, narrowed to the window."""
        start, end = window.instants(timezone)
        stmt = (
            select(Submission.id.label("submission_id"))
            .join(Score, Score.submission_id == Submission.id)
            .where(Submission.status == SubmissionStatus.SCORED.value)
        )
        if window.student_id is not None:
            stmt = stmt.where(Submission.user_id == window.student_id)
        if window.class_id is not None:
            stmt = stmt.join(User, User.id == Submission.user_id).where(
                User.class_id == window.class_id
            )
        if start is not None:
            stmt = stmt.where(Submission.scored_at >= start)
        if end is not None:
            stmt = stmt.where(Submission.scored_at < end)
        return stmt

    def _conditions(self, window: AnalyticsWindow, timezone: str) -> list[Any]:
        """The same narrowing as :meth:`_scored`, as a list of predicates.

        Used where the query already joins ``submissions`` for its own reasons
        and a subquery would force a second scan of the same rows.
        """
        start, end = window.instants(timezone)
        clauses: list[Any] = [Submission.status == SubmissionStatus.SCORED.value]
        if window.student_id is not None:
            clauses.append(Submission.user_id == window.student_id)
        if start is not None:
            clauses.append(Submission.scored_at >= start)
        if end is not None:
            clauses.append(Submission.scored_at < end)
        return clauses

    def _population(self, window: AnalyticsWindow) -> Select[Any]:
        """Active students in scope, whether or not they have submitted.

        Kept separate from the submission query because "how many students
        never started" is one of the more useful engagement numbers a teacher
        can be given, and it cannot be derived from rows that do not exist.
        """
        stmt = select(User.id).where(User.role == UserRole.STUDENT.value, User.is_active.is_(True))
        if window.class_id is not None:
            stmt = stmt.where(User.class_id == window.class_id)
        if window.student_id is not None:
            stmt = stmt.where(User.id == window.student_id)
        return stmt

    # ── Metrics ──────────────────────────────────────────────────────────────

    async def overview(self, window: AnalyticsWindow, *, timezone: str) -> dict[str, Any]:
        """Headline numbers: volume, averages and the tier spread."""
        scoped = self._scored(window, timezone).subquery("scoped")

        totals = select(
            func.count(Score.id),
            func.coalesce(func.avg(Score.final_score), 0),
            func.coalesce(func.avg(Score.vocabulary_percentage), 0),
            func.coalesce(func.max(Score.final_score), 0),
            func.coalesce(func.avg(Submission.word_count), 0),
            func.count(func.distinct(Submission.user_id)),
        ).select_from(
            scoped.join(Score, Score.submission_id == scoped.c.submission_id).join(
                Submission, Submission.id == scoped.c.submission_id
            )
        )
        count, avg_score, avg_vocab, best, avg_words, active = (await self.db.execute(totals)).one()

        tiers = (
            select(Score.reward_tier, func.count(Score.id))
            .select_from(scoped.join(Score, Score.submission_id == scoped.c.submission_id))
            .group_by(Score.reward_tier)
        )
        distribution = {tier: int(n) for tier, n in (await self.db.execute(tiers)).all()}

        enrolled = int(
            (
                await self.db.execute(
                    select(func.count()).select_from(self._population(window).subquery())
                )
            ).scalar_one()
        )

        return {
            "submission_count": int(count),
            "enrolled_student_count": enrolled,
            "active_student_count": int(active),
            "average_final_score": round(float(avg_score), 2),
            "average_vocabulary_percentage": round(float(avg_vocab), 2),
            "highest_final_score": round(float(best), 2),
            "average_word_count": round(float(avg_words), 1),
            "reward_tier_distribution": distribution,
        }

    async def vocabulary_usage(
        self, window: AnalyticsWindow, *, timezone: str
    ) -> list[dict[str, Any]]:
        """Every curated term with how often it was actually used.

        A ``LEFT JOIN`` from the library rather than a ``GROUP BY`` over what
        was detected, because the interesting answer to "least used" (FR-12.2)
        is the terms nobody used **at all** — and those produce no rows to
        group.
        """
        # `detected_terms` is JSONB on PostgreSQL, so the array is expanded in
        # the database. Pulling every score into Python to count them would
        # read the whole corpus into memory to build one histogram.
        element = (
            func.jsonb_array_elements(Score.detected_terms)
            .table_valued(column("value", JSONB))
            .lateral()
        )

        # Flattened first, aggregated second. Grouping directly by the JSON
        # extraction fails: its path is a bound parameter, so PostgreSQL cannot
        # see the GROUP BY expression and the SELECT expression as the same
        # thing and rejects the query.
        flattened = (
            select(
                element.c.value["lemma"].astext.label("lemma"),
                cast(element.c.value["count"].astext, Integer).label("uses"),
                Submission.id.label("submission_id"),
                Submission.user_id.label("user_id"),
            )
            .select_from(Submission)
            .join(Score, Score.submission_id == Submission.id)
            .join(element, true())
            .where(and_(*self._conditions(window, timezone)))
        )
        if window.class_id is not None:
            flattened = flattened.join(User, User.id == Submission.user_id).where(
                User.class_id == window.class_id
            )
        flat = flattened.subquery("flattened")

        usage = (
            select(
                flat.c.lemma.label("lemma"),
                func.sum(flat.c.uses).label("uses"),
                func.count(func.distinct(flat.c.submission_id)).label("submissions"),
                func.count(func.distinct(flat.c.user_id)).label("students"),
            )
            .group_by(flat.c.lemma)
            .subquery("usage")
        )

        stmt = (
            select(
                VocabularyItem.term,
                VocabularyItem.lemma,
                VocabularyCategory.code,
                VocabularyCategory.name,
                func.coalesce(usage.c.uses, 0),
                func.coalesce(usage.c.submissions, 0),
                func.coalesce(usage.c.students, 0),
            )
            .select_from(VocabularyItem)
            .join(VocabularyCategory, VocabularyCategory.id == VocabularyItem.category_id)
            .outerjoin(usage, usage.c.lemma == VocabularyItem.lemma)
            .where(VocabularyItem.is_active.is_(True))
            .order_by(func.coalesce(usage.c.uses, 0).desc(), VocabularyItem.term)
        )

        return [
            {
                "term": term,
                "lemma": lemma,
                "category": code,
                "category_name": name,
                "uses": int(uses),
                "submission_count": int(submissions),
                "student_count": int(students),
            }
            for term, lemma, code, name, uses, submissions, students in (
                await self.db.execute(stmt)
            ).all()
        ]

    async def trend(
        self, window: AnalyticsWindow, *, timezone: str, granularity: str = "day"
    ) -> list[dict[str, Any]]:
        """Average score and vocabulary use per day or week.

        Bucketed in the platform timezone, so the points line up with the days
        a cohort actually practised rather than with UTC.
        """
        bucket = func.date_trunc(granularity, func.timezone(timezone, Submission.scored_at)).label(
            "bucket"
        )

        stmt = (
            select(
                bucket,
                func.count(Score.id),
                func.avg(Score.final_score),
                func.avg(Score.vocabulary_percentage),
            )
            .select_from(Submission)
            .join(Score, Score.submission_id == Submission.id)
            .where(and_(*self._conditions(window, timezone)))
            .group_by(bucket)
            .order_by(bucket)
        )
        if window.class_id is not None:
            stmt = stmt.join(User, User.id == Submission.user_id).where(
                User.class_id == window.class_id
            )

        return [
            {
                "date": moment.date() if isinstance(moment, datetime) else moment,
                "submission_count": int(count),
                "average_final_score": round(float(avg_score), 2),
                "average_vocabulary_percentage": round(float(avg_vocab), 2),
            }
            for moment, count, avg_score, avg_vocab in (await self.db.execute(stmt)).all()
        ]

    async def engagement(self, window: AnalyticsWindow, *, timezone: str) -> dict[str, Any]:
        """Who is practising, and who has stopped."""
        population = self._population(window).subquery("population")

        enrolled = int(
            (await self.db.execute(select(func.count()).select_from(population))).scalar_one()
        )

        streaks = select(
            func.count(User.id).filter(User.current_streak_days >= 2),
            func.coalesce(func.avg(User.current_streak_days), 0),
            func.coalesce(func.max(User.longest_streak_days), 0),
        ).where(User.id.in_(select(population.c.id)))
        streak_holders, average_streak, longest_streak = (await self.db.execute(streaks)).one()

        scoped = self._scored(window, timezone).subquery("scoped_engagement")
        active = int(
            (
                await self.db.execute(
                    select(func.count(func.distinct(Submission.user_id)))
                    .select_from(scoped)
                    .join(Submission, Submission.id == scoped.c.submission_id)
                )
            ).scalar_one()
        )
        submissions = int(
            (await self.db.execute(select(func.count()).select_from(scoped))).scalar_one()
        )

        return {
            "enrolled_student_count": enrolled,
            "active_student_count": active,
            # Counted against enrolment, not against whoever happened to
            # submit: "everyone who practised, practised a lot" is a much
            # rosier number than "half the class never started", and a teacher
            # needs to be shown the second one.
            "inactive_student_count": max(0, enrolled - active),
            "submissions_per_active_student": round(submissions / active, 2) if active else 0.0,
            "participation_rate": round(active / enrolled * 100, 2) if enrolled else 0.0,
            "streak_holders": int(streak_holders),
            "average_streak_days": round(float(average_streak), 2),
            "longest_streak_days": int(longest_streak),
        }

    async def student_rows(self, window: AnalyticsWindow, *, timezone: str) -> list[dict[str, Any]]:
        """One rollup row per student in scope, including those with no work."""
        population = self._population(window).subquery("roster")
        conditions = self._conditions(window, timezone)

        marked = (
            select(
                Submission.user_id.label("user_id"),
                func.count(Score.id).label("submission_count"),
                func.avg(Score.final_score).label("average_final_score"),
                func.avg(Score.vocabulary_percentage).label("average_vocabulary_percentage"),
                func.max(Score.final_score).label("highest_final_score"),
                func.max(Submission.scored_at).label("last_submission_at"),
            )
            .select_from(Submission)
            .join(Score, Score.submission_id == Submission.id)
            .where(and_(*conditions))
            .group_by(Submission.user_id)
            .subquery("marked")
        )

        stmt = (
            select(
                User.id,
                User.full_name,
                User.email,
                Class.name,
                User.total_xp,
                User.current_level,
                User.current_streak_days,
                User.longest_streak_days,
                func.coalesce(marked.c.submission_count, 0),
                marked.c.average_final_score,
                marked.c.average_vocabulary_percentage,
                marked.c.highest_final_score,
                marked.c.last_submission_at,
            )
            .select_from(User)
            .join(population, population.c.id == User.id)
            .outerjoin(Class, Class.id == User.class_id)
            .outerjoin(marked, marked.c.user_id == User.id)
            .order_by(func.coalesce(marked.c.average_final_score, -1).desc(), User.full_name)
        )

        return [
            {
                "user_id": row[0],
                "full_name": row[1],
                "email": row[2],
                "class_name": row[3],
                "total_xp": int(row[4]),
                "current_level": int(row[5]),
                "current_streak_days": int(row[6]),
                "longest_streak_days": int(row[7]),
                "submission_count": int(row[8]),
                "average_final_score": _round(row[9]),
                "average_vocabulary_percentage": _round(row[10]),
                "highest_final_score": _round(row[11]),
                "last_submission_at": row[12],
            }
            for row in (await self.db.execute(stmt)).all()
        ]

    async def submission_rows(
        self, window: AnalyticsWindow, *, timezone: str, limit: int
    ) -> list[dict[str, Any]]:
        """Flat submission rows for the raw export."""
        stmt = (
            select(
                Submission.id,
                User.full_name,
                User.email,
                Class.name,
                Graph.title,
                Graph.graph_type,
                Submission.input_method,
                Submission.word_count,
                Submission.was_ocr_edited,
                Submission.ocr_provider,
                Score.final_score,
                Score.vocabulary_score,
                Score.writing_score,
                Score.vocabulary_percentage,
                Score.reward_tier,
                Score.unique_detected_count,
                Score.total_target_count,
                Submission.submitted_at,
                Submission.scored_at,
            )
            .select_from(Submission)
            .join(Score, Score.submission_id == Submission.id)
            .join(User, User.id == Submission.user_id)
            .join(Graph, Graph.id == Submission.graph_id)
            .outerjoin(Class, Class.id == User.class_id)
            .where(and_(*self._conditions(window, timezone)))
            .order_by(Submission.scored_at.desc())
            .limit(limit)
        )
        if window.class_id is not None:
            stmt = stmt.where(User.class_id == window.class_id)

        keys = (
            "submission_id",
            "student_name",
            "student_email",
            "class_name",
            "graph_title",
            "graph_type",
            "input_method",
            "word_count",
            "was_ocr_edited",
            "ocr_provider",
            "final_score",
            "vocabulary_score",
            "writing_score",
            "vocabulary_percentage",
            "reward_tier",
            "terms_used",
            "terms_targeted",
            "submitted_at",
            "scored_at",
        )
        return [dict(zip(keys, row, strict=True)) for row in (await self.db.execute(stmt)).all()]

    async def recent_activity(self, user_id: uuid.UUID, *, limit: int = 5) -> list[dict[str, Any]]:
        """The student's own last few marked attempts (FR-10.4)."""
        stmt = (
            select(
                Submission.id,
                Graph.title,
                Graph.graph_type,
                Score.final_score,
                Score.vocabulary_percentage,
                Score.reward_tier,
                Submission.scored_at,
            )
            .select_from(Submission)
            .join(Score, Score.submission_id == Submission.id)
            .join(Graph, Graph.id == Submission.graph_id)
            .where(
                Submission.user_id == user_id,
                Submission.status == SubmissionStatus.SCORED.value,
            )
            .order_by(Submission.scored_at.desc())
            .limit(limit)
        )
        keys = (
            "submission_id",
            "graph_title",
            "graph_type",
            "final_score",
            "vocabulary_percentage",
            "reward_tier",
            "scored_at",
        )
        return [dict(zip(keys, row, strict=True)) for row in (await self.db.execute(stmt)).all()]

    async def achievement_count(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count(UserAchievement.id)).where(UserAchievement.user_id == user_id)
        return int((await self.db.execute(stmt)).scalar_one())


def _round(value: Any) -> float | None:
    """Averages are ``None`` for a student with no marked work, not zero.

    Zero would place someone who has not started below someone scoring badly,
    which is a different — and unfair — statement about them.
    """
    return None if value is None else round(float(value), 2)
