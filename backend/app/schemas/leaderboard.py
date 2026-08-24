"""Leaderboard response shapes (FR-9.x)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import LeaderboardScope


class LeaderboardEntryOut(BaseModel):
    """One ranked student.

    Deliberately free of reward tiers. The board shows XP and level; a hammer
    count is a private detail of one student's own results screen and
    publishing it to their cohort is exactly the humiliation FR-7.6 rules out.
    """

    rank: int
    user_id: uuid.UUID
    full_name: str
    avatar_url: str | None = None
    level: int
    xp: int = Field(description="XP earned within this period, not lifetime")
    average_score: float
    submission_count: int
    achievement_count: int
    is_you: bool = False


class LeaderboardPeriod(BaseModel):
    scope: LeaderboardScope
    class_id: uuid.UUID | None = None
    period_start: date
    period_end: date
    generated_at: datetime | None = Field(
        default=None,
        description="When these rankings were materialised. Null before the first build.",
    )


class LeaderboardPage(BaseModel):
    period: LeaderboardPeriod
    entries: list[LeaderboardEntryOut]
    page: int
    page_size: int
    total: int
    total_pages: int


class LeaderboardPosition(BaseModel):
    """The caller's own standing, however far down the board (FR-9.5)."""

    period: LeaderboardPeriod
    entry: LeaderboardEntryOut | None = Field(
        default=None,
        description="Null when the caller has not practised in this period, so has no rank",
    )
    total_ranked: int


class LeaderboardRefreshOut(BaseModel):
    """How many rows each scope produced."""

    rebuilt: dict[str, int]
