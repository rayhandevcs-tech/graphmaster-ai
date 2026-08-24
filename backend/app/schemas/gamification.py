"""XP, achievement and badge response shapes."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import RewardTier, XPReason


class XPBreakdownItem(BaseModel):
    """One line of the XP a single submission earned."""

    reason: XPReason
    amount: int


class BadgeAwardOut(BaseModel):
    """The tier badge attached to one submission."""

    code: str
    name: str
    description: str
    icon: str
    reward_tier: RewardTier


class AchievementAwardOut(BaseModel):
    """An achievement unlocked by one submission."""

    code: str
    title: str
    description: str
    icon: str
    xp_reward: int


class GamificationOut(BaseModel):
    """XP, level, badge and achievements awarded for one submission.

    Delivered in the same payload as the score because the result screen
    sequences one animation from both: the reward tier decides which animation
    plays and the XP total decides what the bar counts up to, so splitting them
    across two calls would render the reward before the bar knew its target.
    """

    xp_awarded: int = 0
    xp_breakdown: list[XPBreakdownItem] = Field(default_factory=list)
    level_before: int = 1
    level_after: int = 1
    leveled_up: bool = False
    badge: BadgeAwardOut | None = Field(
        default=None,
        description="Null only if the badge catalogue is unseeded — the award itself "
        "is unconditional, since every score has a tier",
    )
    new_achievements: list[AchievementAwardOut] = Field(default_factory=list)
    streak_days: int = Field(
        default=0, description="The practice streak after this submission, in days"
    )


class XPEventOut(BaseModel):
    """One entry in the append-only ledger."""

    id: uuid.UUID
    amount: int = Field(
        description="Signed. A negative amount is an administrative correction — "
        "the ledger is never edited, so an over-award is offset rather than removed."
    )
    reason: XPReason
    event_date: date = Field(
        description="The calendar day in the platform timezone this event belongs to"
    )
    submission_id: uuid.UUID | None = None
    achievement_code: str | None = None
    note: str | None = None
    created_at: datetime


class LevelOut(BaseModel):
    """Where a student sits on the level curve (FR-8.5)."""

    current_level: int
    total_xp: int
    xp_into_level: int
    xp_for_next_level: int = Field(description="The span of the current level; 0 at the cap")
    progress_percent: float
    is_max_level: bool
    current_streak_days: int
    longest_streak_days: int


class AchievementOut(BaseModel):
    """A catalogue entry with this student's progress towards it.

    Progress is included for locked achievements because a visible distance —
    "7 / 10" — is what makes the catalogue motivating rather than decorative.
    Achievements that can never apply to the caller (the gendered crown pair)
    are absent from the listing entirely rather than shown permanently locked.
    """

    code: str
    title: str
    description: str
    icon: str
    xp_reward: int
    is_unlocked: bool
    unlocked_at: datetime | None = None
    progress: int
    target: int
    progress_percent: float


class BadgeOut(BaseModel):
    """A reward-tier badge and how many times this student has earned it."""

    code: str
    name: str
    description: str
    icon: str
    reward_tier: RewardTier
    earned_count: int


class XPAdjustment(BaseModel):
    """An administrative correction to a student's XP (§8 of the design)."""

    user_id: uuid.UUID
    amount: int = Field(
        description="Signed XP to add. Negative offsets an earlier over-award.",
        json_schema_extra={"example": -50},
    )
    note: str = Field(
        min_length=3,
        max_length=500,
        description="Why the adjustment was made. Mandatory: an unexplained change "
        "is indistinguishable from tampering once the data is used as evidence.",
    )

    @field_validator("note")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A reason is required.")
        return value
