"""XP ledger, achievement, badge and leaderboard data access."""

from __future__ import annotations

import uuid
import zlib
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Select, and_, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models.enums import LeaderboardScope, UserRole
from app.models.gamification import (
    Achievement,
    Badge,
    LeaderboardEntry,
    UserAchievement,
    UserBadge,
    XPEvent,
)
from app.models.identity import User
from app.models.submission import Score, Submission
from app.repositories.base import BaseRepository


class XPRepository(BaseRepository[XPEvent]):
    model = XPEvent

    async def record(
        self,
        *,
        user_id: uuid.UUID,
        amount: int,
        reason: str,
        event_date: date,
        submission_id: uuid.UUID | None = None,
        achievement_id: uuid.UUID | None = None,
        note: str | None = None,
    ) -> XPEvent:
        event = XPEvent(
            user_id=user_id,
            amount=amount,
            reason=reason,
            event_date=event_date,
            submission_id=submission_id,
            achievement_id=achievement_id,
            note=note,
        )
        return await self.add(event)

    async def record_once_per_day(
        self,
        *,
        user_id: uuid.UUID,
        amount: int,
        reason: str,
        event_date: date,
        submission_id: uuid.UUID | None = None,
    ) -> XPEvent | None:
        """Insert an event the daily partial unique index may refuse.

        Returns ``None`` when the database rejected it because one already
        exists for this student and day. The check is the index rather than a
        preceding ``SELECT``: two submissions arriving together would both read
        "not awarded yet" and both insert, which is exactly the farming route
        the once-per-day rule exists to close.

        The insert runs inside a savepoint. Without one, the failed statement
        would poison the whole transaction and take the score down with it —
        losing the student's work over a bonus they simply did not qualify for.
        """
        try:
            async with self.db.begin_nested():
                return await self.record(
                    user_id=user_id,
                    amount=amount,
                    reason=reason,
                    event_date=event_date,
                    submission_id=submission_id,
                )
        except IntegrityError:
            return None

    async def total_for(self, user_id: uuid.UUID) -> int:
        """Sum the ledger. The authoritative figure ``users.total_xp`` caches."""
        stmt = select(func.coalesce(func.sum(XPEvent.amount), 0)).where(XPEvent.user_id == user_id)
        return int((await self.db.execute(stmt)).scalar_one())

    def build_history_query(self, user_id: uuid.UUID) -> Select[Any]:
        return (
            select(XPEvent)
            .where(XPEvent.user_id == user_id)
            .options(selectinload(XPEvent.achievement))
            .order_by(XPEvent.created_at.desc(), XPEvent.id.desc())
        )


class AchievementRepository(BaseRepository[Achievement]):
    model = Achievement

    async def catalogue(self) -> list[Achievement]:
        stmt = (
            select(Achievement)
            .where(Achievement.is_active.is_(True))
            .order_by(Achievement.display_order, Achievement.code)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def unlocks_for(self, user_id: uuid.UUID) -> list[UserAchievement]:
        stmt = (
            select(UserAchievement)
            .where(UserAchievement.user_id == user_id)
            .options(selectinload(UserAchievement.achievement))
            .order_by(UserAchievement.unlocked_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def unlocked_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        stmt = select(UserAchievement.achievement_id).where(UserAchievement.user_id == user_id)
        return set((await self.db.execute(stmt)).scalars().all())

    async def unlock(
        self,
        *,
        user_id: uuid.UUID,
        achievement_id: uuid.UUID,
        submission_id: uuid.UUID | None = None,
    ) -> UserAchievement | None:
        """Award an achievement, or return ``None`` if it was already held.

        ``UNIQUE (user_id, achievement_id)`` is what guarantees the single
        award (FR-8.8); the savepoint is what stops a concurrent double-unlock
        from failing the submission that triggered it.
        """
        try:
            async with self.db.begin_nested():
                return await self.add(
                    UserAchievement(
                        user_id=user_id,
                        achievement_id=achievement_id,
                        submission_id=submission_id,
                    )
                )
        except IntegrityError:
            return None


class BadgeRepository(BaseRepository[Badge]):
    model = Badge

    async def catalogue(self) -> list[Badge]:
        return list((await self.db.execute(select(Badge).order_by(Badge.code))).scalars().all())

    async def for_tier(self, tier: str) -> Badge | None:
        stmt = select(Badge).where(Badge.reward_tier == tier)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def award(
        self, *, user_id: uuid.UUID, badge_id: uuid.UUID, submission_id: uuid.UUID
    ) -> UserBadge | None:
        """Attach a tier badge to one submission.

        ``submission_id`` is unique on ``user_badges``, so a re-award is
        refused by the database rather than by a check here.
        """
        try:
            async with self.db.begin_nested():
                return await self.add(
                    UserBadge(user_id=user_id, badge_id=badge_id, submission_id=submission_id)
                )
        except IntegrityError:
            return None

    async def counts_for(self, user_id: uuid.UUID) -> dict[str, int]:
        """How many badges of each tier this student has earned."""
        stmt = (
            select(Badge.reward_tier, func.count(UserBadge.id))
            .join(UserBadge, UserBadge.badge_id == Badge.id)
            .where(UserBadge.user_id == user_id)
            .group_by(Badge.reward_tier)
        )
        return {tier: int(count) for tier, count in (await self.db.execute(stmt)).all()}


class LeaderboardRepository(BaseRepository[LeaderboardEntry]):
    model = LeaderboardEntry

    # ── Reads ────────────────────────────────────────────────────────────────

    def build_page_query(
        self,
        *,
        scope: LeaderboardScope,
        period_start: date,
        class_id: uuid.UUID | None,
    ) -> Select[Any]:
        return (
            select(LeaderboardEntry)
            .where(
                LeaderboardEntry.scope == scope.value,
                LeaderboardEntry.period_start == period_start,
                (
                    LeaderboardEntry.class_id == class_id
                    if class_id is not None
                    else LeaderboardEntry.class_id.is_(None)
                ),
            )
            .options(selectinload(LeaderboardEntry.user).selectinload(User.avatar))
            .order_by(LeaderboardEntry.rank)
        )

    async def entry_for(
        self,
        *,
        user_id: uuid.UUID,
        scope: LeaderboardScope,
        period_start: date,
        class_id: uuid.UUID | None,
    ) -> LeaderboardEntry | None:
        stmt = self.build_page_query(
            scope=scope, period_start=period_start, class_id=class_id
        ).where(LeaderboardEntry.user_id == user_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def generated_at(
        self,
        *,
        scope: LeaderboardScope,
        period_start: date,
        class_id: uuid.UUID | None,
    ) -> datetime | None:
        """When this period was last materialised, or ``None`` if never."""
        stmt = select(func.max(LeaderboardEntry.generated_at)).where(
            LeaderboardEntry.scope == scope.value,
            LeaderboardEntry.period_start == period_start,
            (
                LeaderboardEntry.class_id == class_id
                if class_id is not None
                else LeaderboardEntry.class_id.is_(None)
            ),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    # ── Materialisation ──────────────────────────────────────────────────────

    async def acquire_rebuild_lock(
        self, *, scope: LeaderboardScope, period_start: date, class_id: uuid.UUID | None
    ) -> bool:
        """Serialise rebuilds of one period across connections.

        A rebuild is delete-then-insert, so two running together would both
        clear the period and then collide on ``uq_leaderboard_entry``. The lock
        is held for the rest of the transaction and released with it, so a
        request that dies mid-rebuild cannot leave it stuck.

        Returns False where the backend has no advisory locks, leaving the
        caller to fall back on serialising by conflict.
        """
        if self._dialect() != "postgresql":
            return False

        # crc32 is unsigned 32-bit and the advisory-lock key is a bigint, so
        # the hash always fits without any range juggling.
        key = zlib.crc32(f"{scope.value}:{class_id}:{period_start.isoformat()}".encode())
        await self.db.execute(select(func.pg_advisory_xact_lock(key)))
        return True

    def _dialect(self) -> str:
        try:
            return str(self.db.get_bind().dialect.name)
        except Exception:  # pragma: no cover - an unbound session in a fake
            return ""

    async def replace_period(
        self,
        *,
        scope: LeaderboardScope,
        period_start: date,
        period_end: date,
        class_id: uuid.UUID | None,
        rows: list[dict[str, Any]],
    ) -> int:
        """Swap one period's rankings for a freshly computed set."""
        await self.db.execute(
            delete(LeaderboardEntry).where(
                LeaderboardEntry.scope == scope.value,
                LeaderboardEntry.period_start == period_start,
                (
                    LeaderboardEntry.class_id == class_id
                    if class_id is not None
                    else LeaderboardEntry.class_id.is_(None)
                ),
            )
        )
        # Flush the delete before the inserts. Left pending, SQLAlchemy is free
        # to order the INSERTs first and the unique constraint rejects them.
        await self.db.flush()

        generated = datetime.now(UTC)
        for row in rows:
            self.db.add(
                LeaderboardEntry(
                    scope=scope.value,
                    class_id=class_id,
                    period_start=period_start,
                    period_end=period_end,
                    generated_at=generated,
                    **row,
                )
            )
        await self.db.flush()
        return len(rows)

    async def rank_students(
        self,
        *,
        class_id: uuid.UUID | None,
        event_dates: tuple[date, date] | None,
        scored_between: tuple[datetime, datetime] | None,
    ) -> list[dict[str, Any]]:
        """Rank participating students for one period.

        Three aggregates over three tables, each computed in its own grouped
        subquery and joined in. Joining the tables directly instead would
        multiply the rows — a student with 5 XP events and 3 submissions would
        have their average taken over 15 — and produce silently wrong numbers
        rather than an error.
        """
        xp = self._xp_subquery(event_dates)
        scores = self._score_subquery(scored_between)
        achievements = self._achievement_subquery(scored_between)

        participants = (
            select(
                User.id.label("user_id"),
                func.coalesce(xp.c.xp, 0).label("xp"),
                func.coalesce(scores.c.average_score, 0).label("average_score"),
                func.coalesce(scores.c.submission_count, 0).label("submission_count"),
                func.coalesce(achievements.c.achievement_count, 0).label("achievement_count"),
            )
            .select_from(User)
            .outerjoin(xp, xp.c.user_id == User.id)
            .outerjoin(scores, scores.c.user_id == User.id)
            .outerjoin(achievements, achievements.c.user_id == User.id)
            .where(
                # Students only. A teacher who tries an exercise to check it
                # should not appear above the class they are marking.
                User.role == UserRole.STUDENT.value,
                User.is_active.is_(True),
                # Someone who has not practised in the period has no rank at
                # all, rather than sharing last place with everyone else who
                # did not: a weekly board listing every enrolled student on
                # zero buries the handful who actually worked.
                and_(
                    func.coalesce(xp.c.xp, 0) > 0,
                    func.coalesce(scores.c.submission_count, 0) > 0,
                ),
            )
        )
        if class_id is not None:
            participants = participants.where(User.class_id == class_id)

        ranked_from = participants.subquery("participants")
        stmt = select(
            ranked_from.c.user_id,
            ranked_from.c.xp,
            ranked_from.c.average_score,
            ranked_from.c.submission_count,
            ranked_from.c.achievement_count,
            func.rank()
            .over(
                order_by=[
                    ranked_from.c.xp.desc(),
                    ranked_from.c.average_score.desc(),
                    ranked_from.c.achievement_count.desc(),
                ]
            )
            .label("rank"),
        ).select_from(ranked_from)

        return [
            {
                "user_id": row.user_id,
                "xp": int(row.xp),
                "average_score": round(float(row.average_score), 2),
                "submission_count": int(row.submission_count),
                "achievement_count": int(row.achievement_count),
                "rank": int(row.rank),
            }
            for row in (await self.db.execute(stmt)).all()
        ]

    def _xp_subquery(self, event_dates: tuple[date, date] | None) -> Any:
        stmt = select(
            XPEvent.user_id.label("user_id"), func.sum(XPEvent.amount).label("xp")
        ).group_by(XPEvent.user_id)
        if event_dates is not None:
            stmt = stmt.where(XPEvent.event_date.between(*event_dates))
        return stmt.subquery("period_xp")

    def _score_subquery(self, window: tuple[datetime, datetime] | None) -> Any:
        stmt = (
            select(
                Submission.user_id.label("user_id"),
                func.avg(Score.final_score).label("average_score"),
                func.count(Score.id).label("submission_count"),
            )
            .select_from(Submission)
            .join(Score, Score.submission_id == Submission.id)
            .group_by(Submission.user_id)
        )
        if window is not None:
            stmt = stmt.where(Submission.scored_at >= window[0], Submission.scored_at < window[1])
        return stmt.subquery("period_scores")

    def _achievement_subquery(self, window: tuple[datetime, datetime] | None) -> Any:
        stmt = select(
            UserAchievement.user_id.label("user_id"),
            func.count(UserAchievement.id).label("achievement_count"),
        ).group_by(UserAchievement.user_id)
        if window is not None:
            stmt = stmt.where(
                UserAchievement.unlocked_at >= window[0],
                UserAchievement.unlocked_at < window[1],
            )
        return stmt.subquery("period_achievements")
