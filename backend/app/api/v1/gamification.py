"""XP, achievements and badges (FR-8.x).

Everything here reads the caller's own record. Awarding happens in one place —
``GamificationService.on_submission_scored``, called while a submission is
being marked — so there is no endpoint that grants XP, and no way for a client
to ask for any.

The one exception is the administrative adjustment, which appends an offsetting
entry rather than editing the ledger.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, CurrentUser, GamificationSvc
from app.schemas.common import Page
from app.schemas.gamification import (
    AchievementOut,
    BadgeOut,
    LevelOut,
    XPAdjustment,
    XPEventOut,
)

router = APIRouter(tags=["gamification"])


@router.get(
    "/level",
    response_model=LevelOut,
    summary="Level, XP and streak",
    description=(
        "Levels are derived from total XP by a fixed quadratic curve, so this is "
        "computed rather than stored: `25 x (n-1) x n` XP reaches level n. "
        "`xp_for_next_level` is the span of the current level, which is what an XP "
        "bar needs as its maximum; it is 0 at the level cap."
    ),
)
async def get_level(user: CurrentUser, gamification: GamificationSvc) -> LevelOut:
    progress = await gamification.level_state(user)
    return LevelOut(
        current_level=progress.current_level,
        total_xp=progress.total_xp,
        xp_into_level=progress.xp_into_level,
        xp_for_next_level=progress.xp_for_next_level,
        progress_percent=progress.progress_percent,
        is_max_level=progress.is_max_level,
        current_streak_days=user.current_streak_days,
        longest_streak_days=user.longest_streak_days,
    )


@router.get(
    "/xp-history",
    response_model=Page[XPEventOut],
    summary="The caller's XP ledger",
    description=(
        "Append-only and newest first. Nothing in the ledger is ever edited or "
        "deleted, so a correction appears as a second, negative entry beside the "
        "award it offsets rather than replacing it."
    ),
)
async def get_xp_history(
    user: CurrentUser,
    gamification: GamificationSvc,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[XPEventOut]:
    events, total = await gamification.xp_history(user, page=page, page_size=page_size)
    return Page[XPEventOut].build(
        [
            XPEventOut(
                id=event.id,
                amount=event.amount,
                reason=event.reason,
                event_date=event.event_date,
                submission_id=event.submission_id,
                achievement_code=event.achievement.code if event.achievement else None,
                note=event.note,
                created_at=event.created_at,
            )
            for event in events
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/achievements",
    response_model=list[AchievementOut],
    summary="The achievement catalogue with the caller's progress",
    description=(
        "Locked entries carry progress towards their threshold, so the client can "
        "show how far away each one is. Achievements that can never apply to the "
        "caller — Graph King for a female student, Graph Queen for a male one — are "
        "omitted rather than shown permanently locked, so each student has exactly "
        "one reachable crown achievement (FR-7.2)."
    ),
)
async def list_achievements(
    user: CurrentUser, gamification: GamificationSvc
) -> list[AchievementOut]:
    rows = await gamification.achievement_progress(user)
    return [AchievementOut.model_validate(row) for row in rows]


@router.get(
    "/badges",
    response_model=list[BadgeOut],
    summary="Tier badges and how many the caller has earned",
    description=(
        "Badges are re-awardable: one is attached to every scored submission "
        "according to its reward tier, so `earned_count` is a tally rather than a "
        "flag. Achievements, by contrast, unlock once and stay unlocked."
    ),
)
async def list_badges(user: CurrentUser, gamification: GamificationSvc) -> list[BadgeOut]:
    rows = await gamification.badge_progress(user)
    return [BadgeOut.model_validate(row) for row in rows]


@router.post(
    "/adjustments",
    response_model=XPEventOut,
    status_code=status.HTTP_201_CREATED,
    summary="Correct a student's XP",
    description=(
        "Appends a signed entry to the ledger; nothing is edited or removed. A "
        "mandatory note records why, because an unexplained change is "
        "indistinguishable from tampering once the data is used as research "
        "evidence. Returns 422 for an adjustment that would take the student below "
        "zero XP."
    ),
)
async def adjust_xp(
    payload: XPAdjustment, admin: AdminUser, gamification: GamificationSvc
) -> XPEventOut:
    event = await gamification.adjust_xp(
        user_id=payload.user_id, amount=payload.amount, note=payload.note, admin=admin
    )
    return XPEventOut(
        id=event.id,
        amount=event.amount,
        reason=event.reason,
        event_date=event.event_date,
        submission_id=event.submission_id,
        achievement_code=None,
        note=event.note,
        created_at=event.created_at,
    )
