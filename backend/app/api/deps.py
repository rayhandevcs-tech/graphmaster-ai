"""Shared FastAPI dependencies."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccountInactiveError,
    InsufficientRoleError,
    InvalidTokenError,
)
from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.identity import User
from app.ocr.factory import get_ocr_chain
from app.repositories.auth_session import AuthSessionRepository
from app.repositories.avatar import AvatarRepository
from app.repositories.class_ import ClassRepository
from app.repositories.gamification import (
    AchievementRepository,
    BadgeRepository,
    LeaderboardRepository,
    XPRepository,
)
from app.repositories.graph import GraphRepository
from app.repositories.submission import SubmissionRepository
from app.repositories.user import UserRepository
from app.repositories.vocabulary import (
    VocabularyCategoryRepository,
    VocabularyItemRepository,
)
from app.services.analysis import AnalysisService
from app.services.auth import AuthService
from app.services.class_ import ClassService
from app.services.gamification import GamificationService
from app.services.graph import GraphService
from app.services.leaderboard import LeaderboardService
from app.services.ocr import OCRService
from app.services.submission import SubmissionService
from app.services.user import UserService
from app.services.vocabulary import VocabularyService
from app.storage.factory import get_storage

# auto_error=False so a missing header raises our own InvalidTokenError in the
# shared envelope, rather than Starlette's bare 403 with a different shape.
bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")

DbSession = Annotated[AsyncSession, Depends(get_db)]


# ── Repositories ─────────────────────────────────────────────────────────────


def get_user_repository(db: DbSession) -> UserRepository:
    return UserRepository(db)


def get_avatar_repository(db: DbSession) -> AvatarRepository:
    return AvatarRepository(db)


def get_auth_session_repository(db: DbSession) -> AuthSessionRepository:
    return AuthSessionRepository(db)


def get_vocabulary_category_repository(db: DbSession) -> VocabularyCategoryRepository:
    return VocabularyCategoryRepository(db)


def get_vocabulary_item_repository(db: DbSession) -> VocabularyItemRepository:
    return VocabularyItemRepository(db)


def get_graph_repository(db: DbSession) -> GraphRepository:
    return GraphRepository(db)


def get_class_repository(db: DbSession) -> ClassRepository:
    return ClassRepository(db)


def get_submission_repository(db: DbSession) -> SubmissionRepository:
    return SubmissionRepository(db)


def get_xp_repository(db: DbSession) -> XPRepository:
    return XPRepository(db)


def get_achievement_repository(db: DbSession) -> AchievementRepository:
    return AchievementRepository(db)


def get_badge_repository(db: DbSession) -> BadgeRepository:
    return BadgeRepository(db)


def get_leaderboard_repository(db: DbSession) -> LeaderboardRepository:
    return LeaderboardRepository(db)


UserRepo = Annotated[UserRepository, Depends(get_user_repository)]
AvatarRepo = Annotated[AvatarRepository, Depends(get_avatar_repository)]
SessionRepo = Annotated[AuthSessionRepository, Depends(get_auth_session_repository)]
VocabCategoryRepo = Annotated[
    VocabularyCategoryRepository, Depends(get_vocabulary_category_repository)
]
VocabItemRepo = Annotated[VocabularyItemRepository, Depends(get_vocabulary_item_repository)]
GraphRepo = Annotated[GraphRepository, Depends(get_graph_repository)]
ClassRepo = Annotated[ClassRepository, Depends(get_class_repository)]
SubmissionRepo = Annotated[SubmissionRepository, Depends(get_submission_repository)]
XPRepo = Annotated[XPRepository, Depends(get_xp_repository)]
AchievementRepo = Annotated[AchievementRepository, Depends(get_achievement_repository)]
BadgeRepo = Annotated[BadgeRepository, Depends(get_badge_repository)]
LeaderboardRepo = Annotated[LeaderboardRepository, Depends(get_leaderboard_repository)]


# ── Services ─────────────────────────────────────────────────────────────────


def get_auth_service(users: UserRepo, sessions: SessionRepo, avatars: AvatarRepo) -> AuthService:
    return AuthService(users, sessions, avatars)


def get_user_service(users: UserRepo, avatars: AvatarRepo, sessions: SessionRepo) -> UserService:
    return UserService(users, avatars, sessions)


def get_vocabulary_service(
    categories: VocabCategoryRepo, items: VocabItemRepo
) -> VocabularyService:
    return VocabularyService(categories, items)


def get_graph_service(graphs: GraphRepo, items: VocabItemRepo) -> GraphService:
    return GraphService(graphs, items)


def get_class_service(classes: ClassRepo, users: UserRepo) -> ClassService:
    return ClassService(classes, users)


def get_analysis_service(
    graphs: GraphRepo, items: VocabItemRepo, graph_service: GraphSvc
) -> AnalysisService:
    return AnalysisService(graphs, items, graph_service)


def get_gamification_service(
    xp: XPRepo,
    achievements: AchievementRepo,
    badges: BadgeRepo,
    submissions: SubmissionRepo,
    users: UserRepo,
) -> GamificationService:
    return GamificationService(xp, achievements, badges, submissions, users)


def get_leaderboard_service(leaderboard: LeaderboardRepo, classes: ClassRepo) -> LeaderboardService:
    return LeaderboardService(leaderboard, classes)


def get_submission_service(
    submissions: SubmissionRepo,
    graph_service: GraphSvc,
    analysis: AnalysisSvc,
    ocr: OCRSvc,
    gamification: GamificationSvc,
) -> SubmissionService:
    return SubmissionService(submissions, graph_service, analysis, ocr, gamification)


def get_ocr_service() -> OCRService:
    # Both dependencies are process-wide singletons: the chain holds the
    # loaded recognition models, and rebuilding either per request would add
    # seconds of model loading to every upload.
    return OCRService(get_ocr_chain(), get_storage())


AuthSvc = Annotated[AuthService, Depends(get_auth_service)]
UserSvc = Annotated[UserService, Depends(get_user_service)]
VocabularySvc = Annotated[VocabularyService, Depends(get_vocabulary_service)]
GraphSvc = Annotated[GraphService, Depends(get_graph_service)]
ClassSvc = Annotated[ClassService, Depends(get_class_service)]
OCRSvc = Annotated[OCRService, Depends(get_ocr_service)]
AnalysisSvc = Annotated[AnalysisService, Depends(get_analysis_service)]
GamificationSvc = Annotated[GamificationService, Depends(get_gamification_service)]
LeaderboardSvc = Annotated[LeaderboardService, Depends(get_leaderboard_service)]
SubmissionSvc = Annotated[SubmissionService, Depends(get_submission_service)]


# ── Authentication ───────────────────────────────────────────────────────────


async def get_current_user(
    request: Request,
    users: UserRepo,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User:
    """Resolve the caller from the bearer token."""
    if credentials is None or not credentials.credentials:
        raise InvalidTokenError("Authentication required.")

    payload = decode_token(credentials.credentials, expected_type="access")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, TypeError) as exc:
        raise InvalidTokenError("Malformed token subject.") from exc

    user = await users.get_with_avatar(user_id)
    if user is None:
        # The token verified, but the account is gone. Reported as an invalid
        # token rather than 404 — from the caller's side the session is simply
        # no longer usable.
        raise InvalidTokenError("This account no longer exists.")

    if not user.is_active:
        raise AccountInactiveError()

    # Published for the rate limiter so authenticated callers are metered per
    # user rather than sharing one bucket per campus NAT address.
    request.state.user_id = str(user.id)

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(
    request: Request,
    users: UserRepo,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User | None:
    """The caller if a valid token was supplied, otherwise None."""
    if credentials is None or not credentials.credentials:
        return None
    try:
        return await get_current_user(request, users, credentials)
    except (InvalidTokenError, AccountInactiveError):
        return None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


# ── Authorisation ────────────────────────────────────────────────────────────


def require_role(
    *roles: UserRole,
) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Gate an endpoint to the given roles.

    Declared at the router so the requirement is visible in the route
    definition and in the generated OpenAPI, rather than buried in a handler.
    """
    allowed = {r.value for r in roles}

    async def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise InsufficientRoleError(
                f"This action requires one of: {', '.join(sorted(allowed))}."
            )
        return user

    return dependency


require_student = require_role(UserRole.STUDENT)
require_teacher = require_role(UserRole.TEACHER, UserRole.ADMIN)
require_admin = require_role(UserRole.ADMIN)

StudentUser = Annotated[User, Depends(require_student)]
TeacherUser = Annotated[User, Depends(require_teacher)]
AdminUser = Annotated[User, Depends(require_admin)]
