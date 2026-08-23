"""Identity and access models: avatars, classes, users, auth sessions."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID
from app.models.enums import Gender, UserRole, values

if TYPE_CHECKING:
    from app.models.content import Graph, VocabularyItem
    from app.models.gamification import (
        LeaderboardEntry,
        UserAchievement,
        UserBadge,
        XPEvent,
    )
    from app.models.reporting import TeacherReport
    from app.models.submission import Submission


class Avatar(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Cartoon avatar art. Reference data shared by many users."""

    __tablename__ = "avatars"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    gender: Mapped[str] = mapped_column(String(16), nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unlock_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    users: Mapped[list[User]] = relationship(back_populates="avatar")

    __table_args__ = (
        CheckConstraint(
            f"gender IN ({', '.join(repr(v) for v in values(Gender))})",
            name="gender_valid",
        ),
        CheckConstraint("unlock_level >= 1", name="unlock_level_positive"),
        Index("ix_avatars_gender", "gender"),
        # Exactly one default per gender, enforced by the database rather than
        # by convention — two defaults would make registration non-deterministic.
        Index(
            "uq_avatars_default_per_gender",
            "gender",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default"),
        ),
    )


class Class(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A teacher-owned cohort.

    Required by the class leaderboard and by teacher access scoping: a teacher
    may only see submissions from classes they own.
    """

    __tablename__ = "classes"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    teacher: Mapped[User] = relationship(back_populates="taught_classes", foreign_keys=[teacher_id])
    students: Mapped[list[User]] = relationship(
        back_populates="student_class",
        foreign_keys="User.class_id",
    )
    leaderboard_entries: Mapped[list[LeaderboardEntry]] = relationship(
        back_populates="class_", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_classes_teacher_id", "teacher_id"),)


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A student, teacher or administrator."""

    __tablename__ = "users"

    # Stored lowercase and compared as such. PostgreSQL CITEXT would give
    # case-insensitivity natively, but it is an extension the test suite's
    # SQLite backend has no equivalent for; normalising on write is portable
    # and has the same effect.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=UserRole.STUDENT.value)
    gender: Mapped[str] = mapped_column(String(16), nullable=False)

    avatar_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("avatars.id", ondelete="SET NULL"), nullable=True
    )
    # users.class_id and classes.teacher_id reference each other, so the two
    # tables cannot be created in any single order. use_alter defers this
    # constraint to an ALTER TABLE after both tables exist, breaking the cycle
    # for both create_all and Alembic.
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey(
            "classes.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_users_class_id_classes",
        ),
        nullable=True,
    )

    # Denormalised caches of the XP ledger, written in the same transaction as
    # the ledger insert. The ledger stays authoritative; these exist so a
    # profile or leaderboard read is not a SUM() over every event.
    total_xp: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    current_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    current_streak_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_activity_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    avatar: Mapped[Avatar | None] = relationship(back_populates="users")
    student_class: Mapped[Class | None] = relationship(
        back_populates="students", foreign_keys=[class_id]
    )
    taught_classes: Mapped[list[Class]] = relationship(
        back_populates="teacher", foreign_keys="Class.teacher_id"
    )
    auth_sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    submissions: Mapped[list[Submission]] = relationship(back_populates="user")
    xp_events: Mapped[list[XPEvent]] = relationship(back_populates="user")
    achievements: Mapped[list[UserAchievement]] = relationship(back_populates="user")
    badges: Mapped[list[UserBadge]] = relationship(back_populates="user")
    leaderboard_entries: Mapped[list[LeaderboardEntry]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    authored_graphs: Mapped[list[Graph]] = relationship(back_populates="creator")
    authored_vocabulary: Mapped[list[VocabularyItem]] = relationship(back_populates="creator")
    reports: Mapped[list[TeacherReport]] = relationship(back_populates="teacher")

    __table_args__ = (
        CheckConstraint(
            f"role IN ({', '.join(repr(v) for v in values(UserRole))})",
            name="role_valid",
        ),
        CheckConstraint(
            f"gender IN ({', '.join(repr(v) for v in values(Gender))})",
            name="gender_valid",
        ),
        CheckConstraint("current_level >= 1 AND current_level <= 100", name="level_range"),
        CheckConstraint("total_xp >= 0", name="total_xp_non_negative"),
        CheckConstraint("current_streak_days >= 0", name="current_streak_non_negative"),
        CheckConstraint("longest_streak_days >= 0", name="longest_streak_non_negative"),
        Index("ix_users_role", "role"),
        Index("ix_users_class_id", "class_id"),
        Index("ix_users_total_xp", "total_xp"),
    )

    @property
    def is_student(self) -> bool:
        return self.role == UserRole.STUDENT.value

    @property
    def is_teacher(self) -> bool:
        return self.role == UserRole.TEACHER.value

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN.value

    @property
    def can_manage_content(self) -> bool:
        return self.role in (UserRole.TEACHER.value, UserRole.ADMIN.value)

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"


class AuthSession(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """A refresh-token record.

    Access tokens stay stateless; this table is what makes a refresh token
    revocable, which is what allows logout and stolen-token response to work.
    """

    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # SHA-256 of the token; the raw value is never stored, so a database leak
    # does not hand over usable sessions.
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="auth_sessions")

    __table_args__ = (
        Index("ix_auth_sessions_user_id", "user_id"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
    )

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None
