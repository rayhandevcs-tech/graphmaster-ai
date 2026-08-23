"""Liveness and readiness endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db

logger = get_logger(__name__)
router = APIRouter(tags=["health"])


@router.get("/live", summary="Liveness probe")
async def live() -> dict[str, str]:
    """The process is running. Deliberately checks nothing else.

    An orchestrator restarts a container that fails liveness, so a dependency
    outage must not fail this: restarting the API does not fix a database that
    is down, it only removes capacity while the database recovers.
    """
    return {"status": "alive", "version": __version__}


@router.get("/ready", summary="Readiness probe")
async def ready(response: Response, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Dependencies are reachable, so this instance can serve traffic."""
    settings = get_settings()
    checks: dict[str, Any] = {}
    healthy = True

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as exc:
        logger.error("Readiness database check failed: %s", exc)
        checks["database"] = {"status": "error", "detail": str(exc)}
        healthy = False

    checks["ocr"] = {"status": "not_configured", "providers": settings.ocr_provider_order}
    checks["nlp"] = {"status": "not_configured", "model": settings.SPACY_MODEL}

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if healthy else "not_ready",
        "version": __version__,
        "environment": settings.ENVIRONMENT,
        "checks": checks,
    }
