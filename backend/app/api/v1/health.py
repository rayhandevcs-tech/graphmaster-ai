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
from app.nlp.pipeline import pipeline_info
from app.ocr.factory import get_ocr_chain

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

    # Reported but never allowed to fail readiness: with no OCR engine the
    # platform still serves typed answers, which is most of it. Failing
    # readiness here would pull a working instance out of the load balancer.
    chain = get_ocr_chain()
    checks["ocr"] = {
        "status": "ok" if chain.is_operational else "not_configured",
        "providers": {s.name: s.available for s in chain.statuses()},
    }
    # Also reported without failing readiness, for the same reason and one
    # more: the model load is cached, so a probe that failed at boot stays
    # failed for the life of the process. Flipping readiness on it would take
    # the instance out permanently rather than for as long as the fault lasts,
    # and everything that is not scoring still works.
    nlp = pipeline_info()
    checks["nlp"] = {
        "status": "ok" if nlp["available"] else "not_configured",
        "model": nlp["model"],
        "model_version": nlp["version"],
    }

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if healthy else "not_ready",
        "version": __version__,
        "environment": settings.ENVIRONMENT,
        "checks": checks,
    }
