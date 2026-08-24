"""Four leaderboard scopes (FR-9.x).

Rankings are materialised into a table and served from there, so a page view
does not rank the whole cohort. A period whose rankings have gone stale is
rebuilt by the read that notices — which is why a `GET` here can occasionally
write.

Only students are ranked. A teacher trying an exercise to check it should not
appear above the class they are marking.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, CurrentUser, LeaderboardSvc
from app.models.enums import LeaderboardScope
from app.models.gamification import LeaderboardEntry
from app.schemas.leaderboard import (
    LeaderboardEntryOut,
    LeaderboardPage,
    LeaderboardPeriod,
    LeaderboardPosition,
    LeaderboardRefreshOut,
)

router = APIRouter(tags=["leaderboard"])


@router.get(
    "",
    response_model=LeaderboardPage,
    summary="Ranked students for one scope",
    description=(
        "`global` and `class` rank all time; `weekly` covers the ISO week from Monday "
        "and `monthly` the calendar month, both measured in the platform timezone so "
        "a cohort rolls over together. Period XP comes from the ledger, which is why "
        "a weekly board is possible at all — it cannot be derived from a lifetime "
        "total.\n\n"
        "Ties break on average score, then achievement count: XP ties are common in a "
        "class of 40, and an arbitrary order makes the ranking look broken to the "
        "students it is meant to motivate.\n\n"
        "For `class`, students are pinned to their own class and `class_id` is "
        "ignored; teachers must name one they own."
    ),
)
async def get_leaderboard(
    user: CurrentUser,
    leaderboard: LeaderboardSvc,
    scope: LeaderboardScope = Query(default=LeaderboardScope.GLOBAL),
    class_id: uuid.UUID | None = Query(
        default=None, description="Required for `scope=class` unless the caller is a student"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> LeaderboardPage:
    rows, total, meta = await leaderboard.page(
        scope=scope, class_id=class_id, viewer=user, page=page, page_size=page_size
    )
    return LeaderboardPage(
        period=LeaderboardPeriod.model_validate(meta),
        entries=[_entry(row, viewer_id=user.id) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(1, -(-total // page_size)),
    )


@router.get(
    "/me",
    response_model=LeaderboardPosition,
    summary="The caller's own rank",
    description=(
        "Read straight from the caller's stored row, so a student ranked 240th sees "
        "their position without the client paging through the board to find it "
        "(FR-9.5). `entry` is null when they have not practised within the period and "
        "therefore hold no rank."
    ),
)
async def get_own_rank(
    user: CurrentUser,
    leaderboard: LeaderboardSvc,
    scope: LeaderboardScope = Query(default=LeaderboardScope.GLOBAL),
    class_id: uuid.UUID | None = Query(default=None),
) -> LeaderboardPosition:
    entry, meta = await leaderboard.own_entry(scope=scope, class_id=class_id, viewer=user)
    return LeaderboardPosition(
        period=LeaderboardPeriod.model_validate(meta),
        entry=_entry(entry, viewer_id=user.id) if entry else None,
        total_ranked=meta["total_ranked"],
    )


@router.post(
    "/refresh",
    response_model=LeaderboardRefreshOut,
    summary="Rebuild every leaderboard now",
    description=(
        "Rankings normally rebuild themselves when a read finds them stale. This "
        "forces it for all four scopes plus one board per active class — useful "
        "immediately before a lesson, or from a scheduled job in a deployment that "
        "has one."
    ),
)
async def refresh_leaderboards(
    admin: AdminUser, leaderboard: LeaderboardSvc
) -> LeaderboardRefreshOut:
    return LeaderboardRefreshOut(rebuilt=await leaderboard.refresh_all())


def _entry(row: LeaderboardEntry, *, viewer_id: uuid.UUID) -> LeaderboardEntryOut:
    return LeaderboardEntryOut(
        rank=row.rank,
        user_id=row.user_id,
        full_name=row.user.full_name,
        avatar_url=row.user.avatar.image_url if row.user.avatar else None,
        level=row.user.current_level,
        xp=row.xp,
        average_score=float(row.average_score),
        submission_count=row.submission_count,
        achievement_count=row.achievement_count,
        is_you=row.user_id == viewer_id,
    )
