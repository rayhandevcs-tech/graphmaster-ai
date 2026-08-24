"""Four leaderboard scopes, materialised rather than ranked per request (FR-9.x).

Ranking every student on every page view is a scan of the XP ledger, and a
live ranking also moves under a student mid-session in a way that reads as a
bug rather than as competition. So rankings are computed into
``leaderboard_entries`` and served from there.

Nothing schedules that computation in a single-container deployment, so a
stale period is rebuilt on the read that notices it. That keeps the board
correct without a cron daemon, at the cost of one slow request per period per
cache window — and the rebuild takes an advisory lock, so a burst of readers
produces one rebuild rather than a pile-up of colliding ones.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    ClassNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.gamification.periods import period_window, platform_today
from app.models.enums import LeaderboardScope
from app.models.gamification import LeaderboardEntry
from app.models.identity import User
from app.repositories.class_ import ClassRepository
from app.repositories.gamification import LeaderboardRepository

logger = get_logger(__name__)

# Scopes whose window is unbounded. Their period columns carry the sentinel
# dates from `app.gamification.periods`, and no time filter is applied at all —
# ALL_TIME_END is date.max, so computing "the day after" would overflow.
ALL_TIME_SCOPES = frozenset({LeaderboardScope.GLOBAL, LeaderboardScope.CLASS})


class LeaderboardService:
    def __init__(
        self,
        leaderboard: LeaderboardRepository,
        classes: ClassRepository,
        settings: Settings | None = None,
    ) -> None:
        self.leaderboard = leaderboard
        self.classes = classes
        self.settings = settings or get_settings()

    # ── Reads ────────────────────────────────────────────────────────────────

    async def page(
        self,
        *,
        scope: LeaderboardScope,
        class_id: uuid.UUID | None,
        viewer: User,
        page: int,
        page_size: int,
    ) -> tuple[list[LeaderboardEntry], int, dict[str, Any]]:
        resolved = await self._resolve_class(scope, class_id, viewer)
        period_start, period_end = self._window(scope)
        await self._ensure_fresh(scope=scope, class_id=resolved)

        stmt = self.leaderboard.build_page_query(
            scope=scope, period_start=period_start, class_id=resolved
        )
        rows, total = await self.leaderboard.paginate(stmt, page=page, page_size=page_size)
        meta = {
            "scope": scope.value,
            "class_id": resolved,
            "period_start": period_start,
            "period_end": period_end,
            "generated_at": await self.leaderboard.generated_at(
                scope=scope, period_start=period_start, class_id=resolved
            ),
        }
        return rows, total, meta

    async def own_entry(
        self, *, scope: LeaderboardScope, class_id: uuid.UUID | None, viewer: User
    ) -> tuple[LeaderboardEntry | None, dict[str, Any]]:
        """The caller's own row, however far down the board it is (FR-9.5).

        Read directly rather than by paging until it appears, so a student
        ranked 240th sees their position without the client fetching 12 pages.
        """
        resolved = await self._resolve_class(scope, class_id, viewer)
        period_start, period_end = self._window(scope)
        await self._ensure_fresh(scope=scope, class_id=resolved)

        entry = await self.leaderboard.entry_for(
            user_id=viewer.id, scope=scope, period_start=period_start, class_id=resolved
        )
        total = await self.leaderboard.count(
            self.leaderboard.build_page_query(
                scope=scope, period_start=period_start, class_id=resolved
            )
        )
        meta = {
            "scope": scope.value,
            "class_id": resolved,
            "period_start": period_start,
            "period_end": period_end,
            "total_ranked": total,
        }
        return entry, meta

    # ── Materialisation ──────────────────────────────────────────────────────

    async def refresh(self, *, scope: LeaderboardScope, class_id: uuid.UUID | None = None) -> int:
        """Recompute one period's rankings now."""
        period_start, period_end = self._window(scope)
        rows = await self.leaderboard.rank_students(
            class_id=class_id,
            event_dates=None if scope in ALL_TIME_SCOPES else (period_start, period_end),
            scored_between=self._instant_window(scope, period_start, period_end),
        )
        written = await self.leaderboard.replace_period(
            scope=scope,
            period_start=period_start,
            period_end=period_end,
            class_id=class_id,
            rows=rows,
        )
        logger.info("Rebuilt %s leaderboard for %s (%d ranked)", scope.value, period_start, written)
        return written

    async def refresh_all(self) -> dict[str, int]:
        """Rebuild every board, including one per active class."""
        counts = {
            scope.value: await self.refresh(scope=scope)
            for scope in (
                LeaderboardScope.GLOBAL,
                LeaderboardScope.WEEKLY,
                LeaderboardScope.MONTHLY,
            )
        }
        class_rows = 0
        for class_id in await self.classes.active_ids():
            class_rows += await self.refresh(scope=LeaderboardScope.CLASS, class_id=class_id)
        counts[LeaderboardScope.CLASS.value] = class_rows
        return counts

    async def _ensure_fresh(self, *, scope: LeaderboardScope, class_id: uuid.UUID | None) -> None:
        period_start, _ = self._window(scope)
        if not self._is_stale(
            await self.leaderboard.generated_at(
                scope=scope, period_start=period_start, class_id=class_id
            )
        ):
            return

        locked = await self.leaderboard.acquire_rebuild_lock(
            scope=scope, period_start=period_start, class_id=class_id
        )
        # Checked again now the lock is held. Several readers can find the
        # period stale at once; only the first through should pay for the
        # rebuild, and the rest should see the result of it.
        if not self._is_stale(
            await self.leaderboard.generated_at(
                scope=scope, period_start=period_start, class_id=class_id
            )
        ):
            return

        if locked:
            await self.refresh(scope=scope, class_id=class_id)
            return

        # No advisory lock available, so a concurrent rebuild is possible and
        # the uniqueness of a period's rows is left to the index. Losing that
        # race is not the reader's problem: the rebuild is abandoned inside a
        # savepoint — without one the failed insert would poison the request's
        # whole transaction — and they are served the rankings already on disk.
        # Slightly stale beats a 500 for having loaded a page at a busy moment.
        try:
            async with self.leaderboard.db.begin_nested():
                await self.refresh(scope=scope, class_id=class_id)
        except IntegrityError:
            logger.info(
                "Another rebuild of the %s leaderboard won; serving what is stored",
                scope.value,
            )

    def _is_stale(self, generated_at: datetime | None) -> bool:
        if generated_at is None:
            return True
        age = datetime.now(UTC) - generated_at
        return age > timedelta(minutes=self.settings.LEADERBOARD_CACHE_MINUTES)

    # ── Periods and scoping ──────────────────────────────────────────────────

    def _window(self, scope: LeaderboardScope) -> tuple[date, date]:
        return period_window(scope, today=platform_today(self.settings.PLATFORM_TIMEZONE))

    def _instant_window(
        self, scope: LeaderboardScope, period_start: date, period_end: date
    ) -> tuple[datetime, datetime] | None:
        """The period as a half-open range of instants, for timestamp columns.

        Built in the platform timezone rather than UTC: a submission scored at
        23:30 local belongs to that local day, and comparing against UTC
        midnight would file it under the next one.
        """
        if scope in ALL_TIME_SCOPES:
            return None
        tz = ZoneInfo(self.settings.PLATFORM_TIMEZONE)
        return (
            datetime.combine(period_start, time.min, tzinfo=tz),
            datetime.combine(period_end + timedelta(days=1), time.min, tzinfo=tz),
        )

    async def _resolve_class(
        self, scope: LeaderboardScope, class_id: uuid.UUID | None, viewer: User
    ) -> uuid.UUID | None:
        """Decide which class a request is really asking about, and may see.

        Students are pinned to their own class. A class board is a small,
        named group of identifiable people, so letting one student browse
        another cohort's ranking would publish their classmates' standing to
        someone with no relationship to them.
        """
        if scope is not LeaderboardScope.CLASS:
            return None

        if viewer.is_student:
            if viewer.class_id is None:
                raise ValidationError(
                    "You are not enrolled in a class yet, so there is no class "
                    "leaderboard to show. Ask your teacher for a class code."
                )
            return viewer.class_id

        if class_id is None:
            raise ValidationError("Specify which class to rank with `class_id`.")

        class_ = await self.classes.get(class_id)
        if class_ is None:
            raise ClassNotFoundError()
        if viewer.is_teacher and class_.teacher_id != viewer.id:
            raise PermissionDeniedError("You can only view leaderboards for your own classes.")
        return class_.id
