"""Aggregate router for API v1.

Feature routers are registered here as each sprint adds them.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health")
