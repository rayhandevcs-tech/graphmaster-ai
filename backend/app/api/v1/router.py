"""Aggregate router for API v1.

Feature routers are registered here as each sprint adds them.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, avatars, health, users

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health")
api_router.include_router(auth.router, prefix="/auth")
api_router.include_router(users.router, prefix="/users")
api_router.include_router(avatars.router, prefix="/avatars")
