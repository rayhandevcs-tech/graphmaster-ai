"""XP, streaks, badges and achievements (FR-7.x, FR-8.x).

One entry point — :meth:`GamificationService.on_submission_scored` — so the
award rules exist in exactly one place instead of being re-derived wherever a
score is written. It runs inside the caller's transaction, alongside the score
insert: a partial commit would show a student a score with no XP, which reads
as the system having lost their work.

Two invariants the rest of the module is built around:

* **The ledger is the truth and ``users.total_xp`` is a cache.** Every award
  inserts an ``xp_events`` row, and the cache is recomputed from the ledger
  rather than incremented, so it cannot drift.
* **Nothing here may cost a student their submission.** A refused bonus, a
  duplicate unlock or a malformed rule is absorbed; the score is already
  written by the time this runs, and losing it over a gamification detail
  would be a far worse failure than a missing badge.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import UserNotFoundError, ValidationError
from app.core.leveling import LevelProgress, level_for_xp, level_progress
from app.core.logging import get_logger
from app.gamification.periods import platform_today
from app.gamification.rules import (
    RuleOutcome,
    StudentStats,
    evaluate_rule,
    required_recent_window,
)
from app.gamification.streaks import advance_streak
from app.models.enums import XPReason
from app.models.gamification import Achievement, Badge, XPEvent
from app.models.identity import User
from app.models.submission import Score, Submission
from app.repositories.gamification import (
    AchievementRepository,
    BadgeRepository,
    XPRepository,
)
from app.repositories.submission import SubmissionRepository
from app.repositories.user import UserRepository

logger = get_logger(__name__)


@dataclass
class AwardResult:
    """What one scoring earned, for the result screen's animation sequence."""

    xp_awarded: int = 0
    xp_breakdown: list[dict[str, Any]] = field(default_factory=list)
    level_before: int = 1
    level_after: int = 1
    leveled_up: bool = False
    badge: dict[str, Any] | None = None
    new_achievements: list[dict[str, Any]] = field(default_factory=list)
    streak_days: int = 0


class GamificationService:
    def __init__(
        self,
        xp: XPRepository,
        achievements: AchievementRepository,
        badges: BadgeRepository,
        submissions: SubmissionRepository,
        users: UserRepository,
        settings: Settings | None = None,
    ) -> None:
        self.xp = xp
        self.achievements = achievements
        self.badges = badges
        self.submissions = submissions
        self.users = users
        self.settings = settings or get_settings()

    # ── Awarding ─────────────────────────────────────────────────────────────

    async def on_submission_scored(
        self, submission: Submission, score: Score, *, student: User
    ) -> AwardResult:
        """Award everything one scored submission earns.

        Order matters. Base XP first, then the streak, then the badge, then
        achievements — because an achievement's own XP reward can push a
        student over a level boundary, so the level is recomputed once at the
        end rather than after each award. Evaluating achievements last is also
        what lets "First Steps" unlock on the submission that triggered it: the
        caller has already flushed the score, so the aggregates count it.
        """
        today = platform_today(self.settings.PLATFORM_TIMEZONE)
        result = AwardResult(level_before=student.current_level)

        await self._award_base_xp(submission, score, student=student, today=today, result=result)
        await self._apply_streak(submission, student=student, today=today, result=result)
        await self._award_badge(submission, score, student=student, result=result)
        await self._evaluate_achievements(submission, student=student, today=today, result=result)

        await self._refresh_totals(student, result=result)

        logger.info(
            "Submission %s awarded %d XP to %s (level %d -> %d, %d achievement(s))",
            submission.id,
            result.xp_awarded,
            student.id,
            result.level_before,
            result.level_after,
            len(result.new_achievements),
        )
        return result

    async def _award_base_xp(
        self,
        submission: Submission,
        score: Score,
        *,
        student: User,
        today: date,
        result: AwardResult,
    ) -> None:
        await self._record(
            result,
            user_id=student.id,
            amount=self.settings.XP_PER_SUBMISSION,
            reason=XPReason.SUBMISSION,
            event_date=today,
            submission_id=submission.id,
        )

        if float(score.final_score) >= self.settings.HIGH_SCORE_THRESHOLD:
            await self._record(
                result,
                user_id=student.id,
                amount=self.settings.XP_HIGH_SCORE_BONUS,
                reason=XPReason.HIGH_SCORE_BONUS,
                event_date=today,
                submission_id=submission.id,
            )

    async def _apply_streak(
        self, submission: Submission, *, student: User, today: date, result: AwardResult
    ) -> None:
        """Advance the practice streak and pay the daily bonus if it is due.

        The bonus needs a streak of at least two days, so it is paid for
        *continuing* rather than merely for turning up. Paying it on a reset day
        would reward breaking a streak exactly as much as keeping one, and would
        hand 50 XP to a student who practises once a week — which is the
        opposite of what a streak mechanic is for.
        """
        outcome = advance_streak(
            today=today,
            last_activity_date=student.last_activity_date,
            current_streak_days=student.current_streak_days,
            longest_streak_days=student.longest_streak_days,
        )

        student.current_streak_days = outcome.current_streak_days
        student.longest_streak_days = outcome.longest_streak_days
        student.last_activity_date = max(student.last_activity_date or today, today)
        result.streak_days = outcome.current_streak_days

        if not outcome.continued:
            return

        event = await self.xp.record_once_per_day(
            user_id=student.id,
            amount=self.settings.XP_STREAK_BONUS,
            reason=XPReason.STREAK_BONUS.value,
            event_date=today,
            submission_id=submission.id,
        )
        if event is None:
            # The daily index refused it, so a concurrent submission already
            # paid today's bonus. Nothing is wrong; this one simply does not
            # earn it twice.
            logger.debug("Streak bonus already awarded to %s on %s", student.id, today)
            return

        result.xp_breakdown.append({"reason": XPReason.STREAK_BONUS.value, "amount": event.amount})

    async def _award_badge(
        self, submission: Submission, score: Score, *, student: User, result: AwardResult
    ) -> None:
        badge = await self.badges.for_tier(score.reward_tier)
        if badge is None:
            # Reference data is missing — a database seeded before the badge
            # catalogue existed. Worth a loud log, but not worth failing a
            # submission that has already been marked.
            logger.error("No badge configured for reward tier %r", score.reward_tier)
            return

        awarded = await self.badges.award(
            user_id=student.id, badge_id=badge.id, submission_id=submission.id
        )
        if awarded is not None:
            result.badge = _badge_payload(badge)

    async def _evaluate_achievements(
        self, submission: Submission, *, student: User, today: date, result: AwardResult
    ) -> None:
        catalogue = await self.achievements.catalogue()
        if not catalogue:
            return

        stats = await self._stats_for(student, catalogue=catalogue)
        already_held = await self.achievements.unlocked_ids(student.id)

        for achievement in catalogue:
            if achievement.id in already_held:
                continue
            if not evaluate_rule(achievement.rule, stats).satisfied:
                continue

            unlocked = await self.achievements.unlock(
                user_id=student.id,
                achievement_id=achievement.id,
                submission_id=submission.id,
            )
            if unlocked is None:
                # A concurrent submission unlocked it first. The uniqueness
                # constraint is doing its job (FR-8.8); this call simply loses.
                continue

            result.new_achievements.append(_achievement_payload(achievement))

            if achievement.xp_reward > 0:
                await self._record(
                    result,
                    user_id=student.id,
                    amount=achievement.xp_reward,
                    reason=XPReason.ACHIEVEMENT,
                    event_date=today,
                    submission_id=submission.id,
                    achievement_id=achievement.id,
                )

    async def _refresh_totals(self, student: User, *, result: AwardResult) -> None:
        """Re-derive the cached total and level from the ledger.

        Recomputed rather than incremented. The two differ whenever an award
        was refused — the daily streak index, a lost race on an achievement —
        and a cache that adds up what it *tried* to award would drift a little
        further from the ledger on every such occasion, with nothing to correct
        it. One indexed sum per scoring buys a cache that is never wrong.
        """
        student.total_xp = await self.xp.total_for(student.id)
        student.current_level = level_for_xp(student.total_xp, max_level=self.settings.MAX_LEVEL)

        result.level_after = student.current_level
        result.leveled_up = result.level_after > result.level_before
        await self.users.db.flush()

    async def _record(
        self,
        result: AwardResult,
        *,
        user_id: uuid.UUID,
        amount: int,
        reason: XPReason,
        event_date: date,
        submission_id: uuid.UUID | None = None,
        achievement_id: uuid.UUID | None = None,
    ) -> None:
        await self.xp.record(
            user_id=user_id,
            amount=amount,
            reason=reason.value,
            event_date=event_date,
            submission_id=submission_id,
            achievement_id=achievement_id,
        )
        result.xp_breakdown.append({"reason": reason.value, "amount": amount})
        result.xp_awarded += amount

    async def _stats_for(self, student: User, *, catalogue: list[Achievement]) -> StudentStats:
        window = required_recent_window([a.rule for a in catalogue])
        stats = await self.submissions.scoring_stats(student.id, recent_window=window)
        return StudentStats(
            gender=student.gender,
            current_streak_days=student.current_streak_days,
            scored_submissions=stats.scored_submissions,
            tier_counts=stats.tier_counts,
            best_final_score=stats.best_final_score,
            distinct_graph_types=stats.distinct_graph_types,
            recent_vocabulary_percentages=stats.recent_vocabulary_percentages,
        )

    # ── Reads ────────────────────────────────────────────────────────────────

    async def level_state(self, user: User) -> LevelProgress:
        return level_progress(user.total_xp, max_level=self.settings.MAX_LEVEL)

    async def xp_history(
        self, user: User, *, page: int, page_size: int
    ) -> tuple[list[XPEvent], int]:
        stmt = self.xp.build_history_query(user.id)
        return await self.xp.paginate(stmt, page=page, page_size=page_size)

    async def achievement_progress(self, user: User) -> list[dict[str, Any]]:
        """The catalogue as this student sees it: unlocked, or how far off.

        Achievements whose rule can never apply to them — the gendered crown
        pair — are left out entirely rather than shown permanently locked.
        Displaying an unreachable goal alongside reachable ones misrepresents
        how much of the catalogue is actually open to them.
        """
        catalogue = await self.achievements.catalogue()
        stats = await self._stats_for(user, catalogue=catalogue)
        unlocked = {u.achievement_id: u for u in await self.achievements.unlocks_for(user.id)}

        rows: list[dict[str, Any]] = []
        for achievement in catalogue:
            outcome = evaluate_rule(achievement.rule, stats)
            if not outcome.applicable:
                continue
            unlock = unlocked.get(achievement.id)
            rows.append(
                {
                    **_achievement_payload(achievement),
                    "is_unlocked": unlock is not None,
                    "unlocked_at": unlock.unlocked_at if unlock else None,
                    **_progress_payload(outcome, unlocked=unlock is not None),
                }
            )
        return rows

    async def badge_progress(self, user: User) -> list[dict[str, Any]]:
        counts = await self.badges.counts_for(user.id)
        return [
            {**_badge_payload(badge), "earned_count": counts.get(badge.reward_tier, 0)}
            for badge in await self.badges.catalogue()
        ]

    # ── Administration ───────────────────────────────────────────────────────

    async def adjust_xp(
        self, *, user_id: uuid.UUID, amount: int, note: str, admin: User
    ) -> XPEvent:
        """Correct a student's XP with an offsetting ledger entry (§8).

        The ledger is append-only, so an over-award is corrected by adding a
        negative entry rather than by editing or deleting the original. The
        note is mandatory: an unexplained adjustment is indistinguishable from
        tampering when the data is later used as research evidence.
        """
        if amount == 0:
            raise ValidationError("An adjustment of zero XP has no effect.")
        if not note.strip():
            raise ValidationError("An XP adjustment must record why it was made.")

        target = await self.users.get(user_id)
        if target is None:
            raise UserNotFoundError()

        total = await self.xp.total_for(target.id)
        if total + amount < 0:
            # `users.total_xp` carries a non-negative CHECK, so an adjustment
            # past zero would be refused by the database as an opaque 500.
            raise ValidationError(
                f"That would take {target.full_name} below zero XP "
                f"(currently {total}). The largest reduction possible is {total}."
            )

        event = await self.xp.record(
            user_id=target.id,
            amount=amount,
            reason=XPReason.MANUAL_ADJUSTMENT.value,
            event_date=platform_today(self.settings.PLATFORM_TIMEZONE),
            note=note.strip(),
        )

        target.total_xp = await self.xp.total_for(target.id)
        target.current_level = level_for_xp(target.total_xp, max_level=self.settings.MAX_LEVEL)
        await self.users.db.flush()

        logger.info("Admin %s adjusted %s by %+d XP: %s", admin.id, target.id, amount, note.strip())
        return event


def _progress_payload(outcome: RuleOutcome, *, unlocked: bool) -> dict[str, Any]:
    target = max(outcome.target, 1)
    # An unlocked achievement reads as complete even if the statistic behind it
    # has since fallen — a broken streak does not un-earn Consistency Champion.
    progress = target if unlocked else min(outcome.progress, target)
    return {
        "progress": progress,
        "target": outcome.target,
        "progress_percent": round(progress / target * 100, 2),
    }


def _achievement_payload(achievement: Achievement) -> dict[str, Any]:
    return {
        "code": achievement.code,
        "title": achievement.title,
        "description": achievement.description,
        "icon": achievement.icon,
        "xp_reward": achievement.xp_reward,
    }


def _badge_payload(badge: Badge) -> dict[str, Any]:
    return {
        "code": badge.code,
        "name": badge.name,
        "description": badge.description,
        "icon": badge.icon,
        "reward_tier": badge.reward_tier,
    }
