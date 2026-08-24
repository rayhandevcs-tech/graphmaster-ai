"""Analytics and dashboard response shapes."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import AnalyticsScope, GraphType, RewardTier
from app.schemas.gamification import AchievementOut, BadgeOut


class TrendPoint(BaseModel):
    """One bucket of the score trend (FR-10.5, FR-12.4)."""

    date: date
    submission_count: int
    average_final_score: float
    average_vocabulary_percentage: float


class EngagementOut(BaseModel):
    """Who is practising, and who has stopped (FR-12.5)."""

    enrolled_student_count: int
    active_student_count: int
    inactive_student_count: int = Field(
        description="Enrolled students with no marked work in the period — counted "
        "against enrolment, not against whoever happened to submit"
    )
    submissions_per_active_student: float
    participation_rate: float
    streak_holders: int
    average_streak_days: float
    longest_streak_days: int


class StudentRow(BaseModel):
    """One student's rollup within a class report."""

    user_id: uuid.UUID
    full_name: str
    email: str
    class_name: str | None = None
    total_xp: int
    current_level: int
    current_streak_days: int
    longest_streak_days: int
    submission_count: int
    average_final_score: float | None = Field(
        default=None, description="Null — not zero — for a student with no marked work"
    )
    average_vocabulary_percentage: float | None = None
    highest_final_score: float | None = None
    last_submission_at: datetime | None = None


class AnalyticsReport(BaseModel):
    """Class or platform analytics (FR-11.3, FR-12.3, FR-12.5)."""

    scope: AnalyticsScope
    class_id: uuid.UUID | None = None
    class_name: str | None = None
    date_from: date | None = None
    date_to: date | None = None

    submission_count: int
    enrolled_student_count: int
    active_student_count: int
    average_final_score: float
    average_vocabulary_percentage: float
    highest_final_score: float
    average_word_count: float
    reward_tier_distribution: dict[str, int]

    engagement: EngagementOut
    trend: list[TrendPoint]
    students: list[StudentRow] = Field(
        default_factory=list, description="Empty for the platform scope, which has no roster"
    )


class VocabularyUsageRow(BaseModel):
    term: str
    lemma: str
    category: str
    category_name: str
    uses: int = Field(description="Total occurrences, repeats included")
    submission_count: int
    student_count: int


class VocabularyUsageReport(BaseModel):
    """Most and least used target terms (FR-12.1, FR-12.2)."""

    scope: AnalyticsScope
    class_id: uuid.UUID | None = None
    date_from: date | None = None
    date_to: date | None = None
    term_count: int
    used_term_count: int
    unused_term_count: int = Field(
        description="Curated terms nobody reached for at all — invisible to any "
        "report built only from what students did write"
    )
    most_used: list[VocabularyUsageRow]
    least_used: list[VocabularyUsageRow] = Field(description="Least used first")


class TrendReport(BaseModel):
    scope: AnalyticsScope
    class_id: uuid.UUID | None = None
    granularity: str
    date_from: date | None = None
    date_to: date | None = None
    points: list[TrendPoint]


class RecentActivity(BaseModel):
    submission_id: uuid.UUID
    graph_title: str
    graph_type: GraphType
    final_score: float
    vocabulary_percentage: float
    reward_tier: RewardTier
    scored_at: datetime


class StudentDashboard(BaseModel):
    """Everything the student's home screen renders (FR-10.1 to FR-10.5).

    One payload rather than five, because it paints as a single screen: five
    requests would show the XP bar, the streak and the chart arriving at
    different moments, which reads as the page being broken rather than
    loading.
    """

    total_attempts: int
    average_score: float
    highest_score: float
    average_vocabulary_percentage: float
    reward_tier_distribution: dict[str, int] = Field(
        description="The student's own tier counts. Private to this screen — a "
        "hammer count never appears on a leaderboard (FR-7.6)."
    )

    total_xp: int
    current_level: int
    xp_into_level: int
    xp_for_next_level: int
    level_progress_percent: float
    current_streak_days: int
    longest_streak_days: int

    achievements: list[AchievementOut] = Field(description="Unlocked only")
    badges: list[BadgeOut]
    recent_activity: list[RecentActivity]
    score_trend: list[TrendPoint]
