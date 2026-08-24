"""Health endpoints and the global error envelope."""

from __future__ import annotations

from httpx import AsyncClient


class TestHealth:
    async def test_live(self, client: AsyncClient):
        r = await client.get("/api/v1/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "alive"

    async def test_ready_reports_database(self, client: AsyncClient):
        r = await client.get("/api/v1/health/ready")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ready"
        assert body["checks"]["database"]["status"] == "ok"

    async def test_root_metadata(self, client: AsyncClient):
        r = await client.get("/")
        assert r.status_code == 200
        assert r.json()["name"] == "GraphMaster"


class TestMiddleware:
    async def test_request_id_returned(self, client: AsyncClient):
        r = await client.get("/api/v1/health/live")
        assert r.headers.get("X-Request-ID")

    async def test_inbound_request_id_preserved(self, client: AsyncClient):
        # A proxy-supplied ID must flow through rather than being replaced,
        # or logs cannot be correlated across the two hops.
        r = await client.get("/api/v1/health/live", headers={"X-Request-ID": "abc-123"})
        assert r.headers["X-Request-ID"] == "abc-123"

    async def test_security_headers(self, client: AsyncClient):
        r = await client.get("/api/v1/health/live")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"


class TestErrorEnvelope:
    async def test_404_uses_envelope(self, client: AsyncClient):
        r = await client.get("/api/v1/does-not-exist")
        assert r.status_code == 404
        error = r.json()["error"]
        assert error["code"] == "NOT_FOUND"
        assert "message" in error and "details" in error

    async def test_405_uses_envelope(self, client: AsyncClient):
        r = await client.post("/api/v1/health/live")
        assert r.status_code == 405
        assert r.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


class TestReadinessTellsTheTruth:
    """A probe that lies keeps a broken instance in the load balancer."""

    async def test_an_unreachable_database_fails_readiness(self, client, monkeypatch):
        from sqlalchemy.ext.asyncio import AsyncSession

        async def unreachable(*args, **kwargs):
            raise OSError("connection refused")

        monkeypatch.setattr(AsyncSession, "execute", unreachable)

        response = await client.get("/api/v1/health/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["checks"]["database"]["status"] == "error"
        assert "connection refused" in body["checks"]["database"]["detail"]

    async def test_liveness_survives_an_unreachable_database(self, client, monkeypatch):
        """An orchestrator restarts what fails liveness.

        Restarting the API does not fix a database that is down; it only
        removes capacity while the database recovers.
        """
        from sqlalchemy.ext.asyncio import AsyncSession

        async def unreachable(*args, **kwargs):
            raise OSError("connection refused")

        monkeypatch.setattr(AsyncSession, "execute", unreachable)

        assert (await client.get("/api/v1/health/live")).status_code == 200

    async def test_a_missing_engine_is_reported_without_failing_readiness(self, client):
        """Neither OCR nor the language model is allowed to pull the instance out.

        With no OCR engine the platform still serves typed answers, and the
        spaCy probe is cached for the life of the process — flipping readiness
        on it would take the instance out permanently rather than for as long
        as the fault lasts.
        """
        response = await client.get("/api/v1/health/ready")

        assert response.status_code == 200
        checks = response.json()["checks"]
        assert checks["ocr"]["status"] in {"ok", "not_configured"}
        assert checks["nlp"]["status"] in {"ok", "not_configured"}
        assert response.json()["status"] == "ready"
