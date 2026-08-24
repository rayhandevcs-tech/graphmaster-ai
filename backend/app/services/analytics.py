"""Class, platform and student analytics (FR-10.x, FR-12.x).

Two audiences with different rules. A **student** gets their own dashboard and
nothing else. A **teacher** gets aggregates for classes they own; a class they
do not teach is refused, not quietly emptied, because an empty class report and
a forbidden one look identical and the first is a lie.

Everything is computed live. At classroom scale these are small aggregates over
an indexed date range, and a cached figure would be stale exactly when a
teacher most wants it — in the minutes after a lesson.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import ClassNotFoundError, PermissionDeniedError, ValidationError
from app.core.leveling import level_progress
from app.models.enums import AnalyticsScope
from app.models.identity import Class, User
from app.repositories.analytics import AnalyticsRepository, AnalyticsWindow
from app.repositories.class_ import ClassRepository
from app.services.gamification import GamificationService

# How many terms each end of the vocabulary report returns by default. Enough
# to see a pattern, few enough to read on one screen.
VOCABULARY_LIMIT = 10


class AnalyticsService:
    def __init__(
        self,
        analytics: AnalyticsRepository,
        classes: ClassRepository,
        gamification: GamificationService,
        settings: Settings | None = None,
    ) -> None:
        self.analytics = analytics
        self.classes = classes
        self.gamification = gamification
        self.settings = settings or get_settings()

    @property
    def timezone(self) -> str:
        return self.settings.PLATFORM_TIMEZONE

    # ── Teacher and administrator views ──────────────────────────────────────

    async def class_report(
        self,
        class_id: uuid.UUID,
        *,
        viewer: User,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        """Everything a teacher needs about one cohort (FR-11.3, FR-12.3)."""
        class_ = await self.require_class(class_id, viewer)
        window = self._window(class_id=class_.id, date_from=date_from, date_to=date_to)

        return {
            "scope": AnalyticsScope.CLASS.value,
            "class_id": class_.id,
            "class_name": class_.name,
            "date_from": date_from,
            "date_to": date_to,
            **await self.analytics.overview(window, timezone=self.timezone),
            "engagement": await self.analytics.engagement(window, timezone=self.timezone),
            "trend": await self.analytics.trend(window, timezone=self.timezone),
            "students": await self.analytics.student_rows(window, timezone=self.timezone),
        }

    async def platform_report(
        self, *, date_from: date | None = None, date_to: date | None = None
    ) -> dict[str, Any]:
        """The same picture across every class, for an administrator."""
        window = self._window(date_from=date_from, date_to=date_to)
        return {
            "scope": AnalyticsScope.PLATFORM.value,
            "class_id": None,
            "class_name": None,
            "date_from": date_from,
            "date_to": date_to,
            **await self.analytics.overview(window, timezone=self.timezone),
            "engagement": await self.analytics.engagement(window, timezone=self.timezone),
            "trend": await self.analytics.trend(window, timezone=self.timezone),
            "students": [],
        }

    async def vocabulary_usage(
        self,
        *,
        viewer: User,
        class_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = VOCABULARY_LIMIT,
    ) -> dict[str, Any]:
        """Most and least used target terms (FR-12.1, FR-12.2).

        "Least used" counts terms with **zero** uses, which is the answer a
        teacher actually needs: a term nobody has ever reached for is the one
        to teach next, and it is invisible to any report built only from what
        students did write.
        """
        if class_id is not None:
            await self.require_class(class_id, viewer)
        window = self._window(class_id=class_id, date_from=date_from, date_to=date_to)

        rows = await self.analytics.vocabulary_usage(window, timezone=self.timezone)
        used = [row for row in rows if row["uses"] > 0]

        return {
            "scope": (AnalyticsScope.CLASS if class_id else AnalyticsScope.PLATFORM).value,
            "class_id": class_id,
            "date_from": date_from,
            "date_to": date_to,
            "term_count": len(rows),
            "used_term_count": len(used),
            "unused_term_count": len(rows) - len(used),
            "most_used": used[:limit],
            # Taken from the tail of the same ordering, then reversed, so the
            # least used term is first rather than last.
            "least_used": list(reversed(rows[-limit:])),
        }

    async def trends(
        self,
        *,
        viewer: User,
        class_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        granularity: str = "day",
    ) -> dict[str, Any]:
        """Score and vocabulary movement over time (FR-12.4)."""
        if granularity not in {"day", "week", "month"}:
            raise ValidationError("Granularity must be day, week or month.")
        if class_id is not None:
            await self.require_class(class_id, viewer)

        window = self._window(class_id=class_id, date_from=date_from, date_to=date_to)
        points = await self.analytics.trend(window, timezone=self.timezone, granularity=granularity)
        return {
            "scope": (AnalyticsScope.CLASS if class_id else AnalyticsScope.PLATFORM).value,
            "class_id": class_id,
            "granularity": granularity,
            "date_from": date_from,
            "date_to": date_to,
            "points": points,
        }

    # ── The student's own dashboard ──────────────────────────────────────────

    async def student_dashboard(self, student: User) -> dict[str, Any]:
        """The student's own summary (FR-10.1 to FR-10.5).

        Assembled in one call because the dashboard renders as a single screen:
        five requests to paint it would show the XP bar, the streak and the
        chart arriving at different moments, which reads as the page being
        broken rather than as it loading.
        """
        window = AnalyticsWindow(student_id=student.id)
        overview = await self.analytics.overview(window, timezone=self.timezone)
        progress = level_progress(student.total_xp, max_level=self.settings.MAX_LEVEL)

        return {
            "total_attempts": overview["submission_count"],
            "average_score": overview["average_final_score"],
            "highest_score": overview["highest_final_score"],
            "average_vocabulary_percentage": overview["average_vocabulary_percentage"],
            "reward_tier_distribution": overview["reward_tier_distribution"],
            "total_xp": progress.total_xp,
            "current_level": progress.current_level,
            "xp_into_level": progress.xp_into_level,
            "xp_for_next_level": progress.xp_for_next_level,
            "level_progress_percent": progress.progress_percent,
            "current_streak_days": student.current_streak_days,
            "longest_streak_days": student.longest_streak_days,
            "achievements": [
                row
                for row in await self.gamification.achievement_progress(student)
                if row["is_unlocked"]
            ],
            "badges": await self.gamification.badge_progress(student),
            "recent_activity": await self.analytics.recent_activity(student.id),
            "score_trend": await self.analytics.trend(window, timezone=self.timezone),
        }

    # ── Internals ────────────────────────────────────────────────────────────

    def _window(
        self,
        *,
        class_id: uuid.UUID | None = None,
        student_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> AnalyticsWindow:
        if date_from and date_to and date_from > date_to:
            raise ValidationError("The start of the period must not be after its end.")
        return AnalyticsWindow(
            class_id=class_id, student_id=student_id, date_from=date_from, date_to=date_to
        )

    async def require_class(self, class_id: uuid.UUID, viewer: User) -> Class:
        """Resolve a class the viewer is entitled to read.

        A teacher is refused another teacher's class rather than shown an empty
        one: FR-11.6 is about what they may *see*, and an empty report would
        still tell them the class exists and has no work in it.
        """
        class_ = await self.classes.get(class_id)
        if class_ is None:
            raise ClassNotFoundError()
        if viewer.is_teacher and class_.teacher_id != viewer.id:
            raise PermissionDeniedError("You can only view analytics for your own classes.")
        return class_
