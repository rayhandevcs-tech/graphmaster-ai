"""Aggregate router for API v1.

Feature routers are registered here as each sprint adds them.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    analysis,
    analytics,
    assessment,
    assignments,
    auth,
    avatars,
    classes,
    gamification,
    graphs,
    health,
    leaderboard,
    ocr,
    reports,
    submissions,
    users,
    vocabulary,
)

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health")
api_router.include_router(auth.router, prefix="/auth")
api_router.include_router(users.router, prefix="/users")
api_router.include_router(avatars.router, prefix="/avatars")
api_router.include_router(classes.router, prefix="/classes")
api_router.include_router(assignments.router, prefix="/assignments")
api_router.include_router(graphs.router, prefix="/graphs")
api_router.include_router(ocr.router, prefix="/ocr")
api_router.include_router(vocabulary.router, prefix="/vocabulary")
api_router.include_router(analysis.router, prefix="/analysis")
api_router.include_router(submissions.router, prefix="/submissions")
api_router.include_router(gamification.router, prefix="/gamification")
api_router.include_router(leaderboard.router, prefix="/leaderboard")
api_router.include_router(analytics.router, prefix="/analytics")
api_router.include_router(assessment.router, prefix="/assessment")
api_router.include_router(reports.router, prefix="/reports")
