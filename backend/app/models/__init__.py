"""SQLAlchemy models.

Imported eagerly here so that ``Base.metadata`` is fully populated before
Alembic autogenerate or ``create_all`` runs. A model that is never imported is
invisible to both.
"""

from app.models.content import (
    Graph,
    GraphTargetVocabulary,
    VocabularyCategory,
    VocabularyItem,
)
from app.models.gamification import (
    Achievement,
    Badge,
    LeaderboardEntry,
    UserAchievement,
    UserBadge,
    XPEvent,
)
from app.models.identity import AuthSession, Avatar, Class, User
from app.models.reporting import AnalyticsSnapshot, TeacherReport
from app.models.submission import Score, Submission

__all__ = [
    "Achievement",
    "AnalyticsSnapshot",
    "AuthSession",
    "Avatar",
    "Badge",
    "Class",
    "Graph",
    "GraphTargetVocabulary",
    "LeaderboardEntry",
    "Score",
    "Submission",
    "TeacherReport",
    "User",
    "UserAchievement",
    "UserBadge",
    "VocabularyCategory",
    "VocabularyItem",
    "XPEvent",
]
