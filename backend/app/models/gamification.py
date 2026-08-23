"""Gamification models: XP ledger, achievements, badges, leaderboard."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType
from app.models.enums import LeaderboardScope, RewardTier, XPReason, values

if TYPE_CHECKING:
    from app.models.identity import Class, User
    from app.models.submission import Submission


class XPEvent(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Append-only XP ledger.

    Never updated, never deleted; corrections are offsetting entries. The
    ledger is what makes weekly and monthly leaderboards possible at all — XP
    within a period cannot be derived from a lifetime total.
    """

    __tablename__ = "xp_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True
    )
    achievement_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("achievements.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The calendar day this event belongs to, in the configured platform
    # timezone. Stored explicitly rather than derived from `created_at` in the
    # index: casting a timestamptz to date depends on the session TimeZone, so
    # PostgreSQL rejects it as non-IMMUTABLE in an index expression, and
    # hardcoding `AT TIME ZONE 'UTC'` would quietly ignore PLATFORM_TIMEZONE.
    event_date: Mapped[date] = mapped_column(Date, nullable=False)

    user: Mapped[User] = relationship(back_populates="xp_events")
    submission: Mapped[Submission | None] = relationship(back_populates="xp_events")
    achievement: Mapped[Achievement | None] = relationship(back_populates="xp_events")

    __table_args__ = (
        CheckConstraint(
            f"reason IN ({', '.join(repr(v) for v in values(XPReason))})",
            name="reason_valid",
        ),
        Index("ix_xp_events_user_created", "user_id", "created_at"),
        Index("ix_xp_events_reason", "reason"),
        # One streak bonus per user per calendar day, enforced by the database.
        # An application-level "already awarded today?" check is a
        # read-then-write race: two submissions arriving together both read
        # "no" and both insert.
        Index(
            "uq_xp_events_streak_daily",
            "user_id",
            "event_date",
            unique=True,
            postgresql_where=text("reason = 'streak_bonus'"),
            sqlite_where=text("reason = 'streak_bonus'"),
        ),
    )

    def __repr__(self) -> str:
        return f"<XPEvent {self.amount:+d} {self.reason}>"


class Achievement(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """A permanent, one-time milestone.

    Distinct from a badge, which reflects performance on a single attempt and
    is re-awardable.
    """

    __tablename__ = "achievements"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String(32), nullable=False, default="🏅")
    xp_reward: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Declarative unlock condition, evaluated by GamificationService, so adding
    # an achievement is a data change rather than a code change.
    rule: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    unlocks: Mapped[list[UserAchievement]] = relationship(back_populates="achievement")
    xp_events: Mapped[list[XPEvent]] = relationship(back_populates="achievement")

    __table_args__ = (CheckConstraint("xp_reward >= 0", name="xp_reward_non_negative"),)

    def __repr__(self) -> str:
        return f"<Achievement {self.code}>"


class UserAchievement(Base, UUIDPrimaryKeyMixin):
    """A student's unlock of one achievement."""

    __tablename__ = "user_achievements"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    achievement_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False
    )
    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True
    )
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="achievements")
    achievement: Mapped[Achievement] = relationship(back_populates="unlocks")

    __table_args__ = (
        # Single award per user, enforced by the database so that concurrent
        # submissions cannot double-unlock.
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
        Index("ix_user_achievements_user_id", "user_id"),
    )


class Badge(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """A reward-tier badge, re-awardable on every submission."""

    __tablename__ = "badges"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String(32), nullable=False, default="🏆")
    reward_tier: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)

    awards: Mapped[list[UserBadge]] = relationship(back_populates="badge")

    __table_args__ = (
        CheckConstraint(
            f"reward_tier IN ({', '.join(repr(v) for v in values(RewardTier))})",
            name="reward_tier_valid",
        ),
    )

    def __repr__(self) -> str:
        return f"<Badge {self.code}>"


class UserBadge(Base, UUIDPrimaryKeyMixin):
    """A badge awarded for one specific submission."""

    __tablename__ = "user_badges"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    badge_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("badges.id", ondelete="RESTRICT"), nullable=False
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("submissions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="badges")
    badge: Mapped[Badge] = relationship(back_populates="awards")
    submission: Mapped[Submission] = relationship(back_populates="badge")

    __table_args__ = (Index("ix_user_badges_user_awarded", "user_id", "awarded_at"),)


class LeaderboardEntry(Base, UUIDPrimaryKeyMixin):
    """A materialised ranking row.

    Rankings are precomputed rather than ranked per request: ranking the full
    user set on every page view is a scan of the XP ledger, and a live ranking
    also shifts under a student mid-session in a way that reads as a bug.
    """

    __tablename__ = "leaderboard_entries"

    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("classes.id", ondelete="CASCADE"), nullable=True
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    xp: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    average_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    submission_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    achievement_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="leaderboard_entries")
    class_: Mapped[Class | None] = relationship(back_populates="leaderboard_entries")

    __table_args__ = (
        CheckConstraint(
            f"scope IN ({', '.join(repr(v) for v in values(LeaderboardScope))})",
            name="scope_valid",
        ),
        # A class-scoped row must name a class; every other scope must not.
        CheckConstraint(
            "(scope = 'class' AND class_id IS NOT NULL) "
            "OR (scope <> 'class' AND class_id IS NULL)",
            name="class_scope_consistent",
        ),
        CheckConstraint("rank >= 1", name="rank_positive"),
        UniqueConstraint(
            "scope", "class_id", "period_start", "user_id", name="uq_leaderboard_entry"
        ),
        Index("ix_leaderboard_lookup", "scope", "class_id", "period_start", "rank"),
    )

    def __repr__(self) -> str:
        return f"<LeaderboardEntry #{self.rank} {self.scope} xp={self.xp}>"
