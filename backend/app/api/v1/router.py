"""Aggregate router for API v1.

Feature routers are registered here as each sprint adds them.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    analysis,
    auth,
    avatars,
    classes,
    graphs,
    health,
    ocr,
    users,
    vocabulary,
)

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health")
api_router.include_router(auth.router, prefix="/auth")
api_router.include_router(users.router, prefix="/users")
api_router.include_router(avatars.router, prefix="/avatars")
api_router.include_router(classes.router, prefix="/classes")
api_router.include_router(graphs.router, prefix="/graphs")
api_router.include_router(ocr.router, prefix="/ocr")
api_router.include_router(vocabulary.router, prefix="/vocabulary")
api_router.include_router(analysis.router, prefix="/analysis")
