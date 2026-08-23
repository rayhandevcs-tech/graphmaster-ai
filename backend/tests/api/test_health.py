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
