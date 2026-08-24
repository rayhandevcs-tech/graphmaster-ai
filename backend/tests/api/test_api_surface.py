"""Invariants that must hold across the whole API surface.

Every other test module asserts what one endpoint does. These assert what
*all* of them do — which is the only way a rule survives the next sprint. A
route added without an authentication dependency is not a failing test
anywhere else; it is simply a hole nobody notices until someone finds it.

The surface is read from the OpenAPI document rather than from FastAPI's
route objects: it is the contract the frontend and the marking scheme are
written against, and reading it here means the test cannot drift from what is
published.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app as fastapi_app

# The exact wording `get_current_user` refuses with when the Authorization
# header is missing. Asserting on it is what separates "this route is
# guarded" from "this route happened to answer 401".
MISSING_TOKEN = "Authentication required."

HTTP_METHODS = {"get", "post", "patch", "put", "delete"}

# Endpoints that must answer without a token, each for a stated reason. This
# list is deliberately hand-written: making a route public should require
# adding a line here, in a diff a reviewer reads.
PUBLIC: dict[tuple[str, str], str] = {
    ("GET", "/api/v1/health/live"): "an orchestrator probes it before any user exists",
    ("GET", "/api/v1/health/ready"): "a load balancer probes it without credentials",
    ("POST", "/api/v1/auth/register"): "creating the account is what produces the token",
    ("POST", "/api/v1/auth/login"): "exchanging credentials for a token",
    ("POST", "/api/v1/auth/refresh"): "the refresh token is the credential",
    ("POST", "/api/v1/auth/logout"): "logging out must work with an access token already expired",
    ("POST", "/api/v1/auth/password-reset/request"): "a locked-out user has no token by definition",
    ("POST", "/api/v1/auth/password-reset/confirm"): "the reset token is the credential",
}


def operations() -> list[tuple[str, str, dict[str, Any]]]:
    """Every (method, path, operation) published in the OpenAPI document."""
    spec = fastapi_app.openapi()
    return [
        (method.upper(), path, operation)
        for path, item in spec["paths"].items()
        for method, operation in item.items()
        if method in HTTP_METHODS
    ]


def concrete(path: str) -> str:
    """Fill path parameters with syntactically valid values.

    The values never matter: authentication is resolved before the handler
    runs, so a request that is refused for want of a token is refused whatever
    the identifier says.
    """
    filled = path
    while "{" in filled:
        start = filled.index("{")
        end = filled.index("}")
        name = filled[start + 1 : end]
        value = "weekly" if name == "scope" else str(uuid.uuid4())
        filled = filled[:start] + value + filled[end + 1 :]
    return filled


class TestAuthenticationIsUniversal:
    async def test_every_endpoint_outside_the_allowlist_demands_a_token(self, client: AsyncClient):
        """No route reaches its handler without authentication.

        A missing dependency is invisible from a route's own tests, which all
        pass a token. This is the test that fails.
        """
        unguarded: list[str] = []

        for method, path, _operation in operations():
            if (method, path) in PUBLIC:
                continue
            response = await client.request(method, concrete(path))
            # The message is checked, not only the status: a route that
            # happens to answer 401 for its own reasons is not the same as
            # one that refused for want of a token, and only the second is
            # evidence the dependency is wired up.
            refused_for_want_of_a_token = (
                response.status_code == 401 and response.json()["error"]["message"] == MISSING_TOKEN
            )
            if not refused_for_want_of_a_token:
                unguarded.append(f"{method} {path} -> {response.status_code}")

        assert not unguarded, "Endpoints reachable without a token: " + "; ".join(unguarded)

    async def test_the_refusal_is_always_the_documented_envelope(self, client: AsyncClient):
        """A client parses one error shape, not one per router."""
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 401
        body = response.json()
        assert set(body) == {"error"}
        assert set(body["error"]) == {"code", "message", "details"}
        assert body["error"]["code"] in {"UNAUTHORIZED", "INVALID_TOKEN"}

    async def test_a_garbled_token_is_refused_rather_than_crashing(self, client: AsyncClient):
        refused = []
        for value in ("Bearer", "Bearer ", "Bearer not.a.jwt", "Basic abc123", "Bearer ...."):
            response = await client.get("/api/v1/users/me", headers={"Authorization": value})
            refused.append((value, response.status_code))
        assert all(status == 401 for _, status in refused), refused

    async def test_a_signed_token_with_a_nonsense_subject_is_refused(self, client: AsyncClient):
        """The signature verifying does not make the claims usable.

        Anything that reaches the database as an identifier has to be parsed
        first — a `sub` that is not a UUID must be refused, not passed through
        to a query that raises a 500 and confirms the token was otherwise
        good.
        """
        from app.core.security import create_access_token

        token = create_access_token("not-a-uuid", role="student", gender="female")
        response = await client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_TOKEN"

    async def test_a_token_for_a_deleted_account_is_refused(self, client: AsyncClient):
        """The signature outlives the account; the session must not.

        Reported as an invalid token rather than 404: from the caller's side
        the session is simply no longer usable, and "no such user" would
        confirm which identifiers exist.
        """
        from app.core.security import create_access_token

        token = create_access_token(uuid.uuid4(), role="student", gender="female")
        response = await client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_TOKEN"

    async def test_every_public_endpoint_is_genuinely_reachable(self, client: AsyncClient):
        """The allowlist is not a list of things that happen to 401 anyway.

        Without this, deleting a route and leaving its allowlist entry behind
        would look exactly like a working public endpoint.
        """
        published = {(method, path) for method, path, _ in operations()}
        assert set(PUBLIC) <= published, "The allowlist names routes that no longer exist"

        for method, path in PUBLIC:
            response = await client.request(method, path)
            if response.status_code != 401:
                continue
            # `/auth/refresh` is public and still answers 401 without a body:
            # the refresh token *is* its credential. What must not happen is a
            # refusal for a missing bearer header, which would mean the route
            # is not public at all.
            message = response.json()["error"]["message"]
            assert message != MISSING_TOKEN, f"{method} {path} is allowlisted but demands a token"


class TestPublishedContract:
    async def test_every_endpoint_is_versioned(self):
        """NFR-5.5. An unversioned path cannot be deprecated without breaking clients."""
        prefix = get_settings().API_V1_PREFIX
        unversioned = [f"{m} {p}" for m, p, _ in operations() if not p.startswith(prefix)]
        assert not unversioned, unversioned

    async def test_operation_ids_are_unique(self):
        """Duplicates silently overwrite each other in a generated client."""
        seen: dict[str, str] = {}
        clashes: list[str] = []
        for method, path, operation in operations():
            identifier = operation.get("operationId")
            if identifier is None:
                continue
            if identifier in seen:
                clashes.append(f"{identifier}: {seen[identifier]} and {method} {path}")
            seen[identifier] = f"{method} {path}"
        assert not clashes, clashes

    async def test_every_endpoint_is_documented(self):
        """A summary and a tag are what turn /docs into something usable."""
        undocumented = [
            f"{m} {p}"
            for m, p, operation in operations()
            if not operation.get("summary") or not operation.get("tags")
        ]
        assert not undocumented, undocumented

    async def test_every_paginated_endpoint_bounds_its_page_size(self):
        """An unbounded page size is a database read anyone can make arbitrarily large.

        `page_size=100000` on a list endpoint with no ceiling is one request
        that loads a table into memory and serialises it — no authentication
        problem, no clever payload, just a number nobody bounded.
        """
        unbounded: list[str] = []

        for method, path, operation in operations():
            for parameter in operation.get("parameters", []):
                if parameter.get("name") not in {"page_size", "limit"}:
                    continue
                schema = parameter.get("schema", {})
                ceiling = schema.get("maximum")
                floor = schema.get("minimum")
                if ceiling is None or ceiling > 500 or floor is None or floor < 1:
                    unbounded.append(
                        f"{method} {path} {parameter['name']} "
                        f"(minimum={floor}, maximum={ceiling})"
                    )

        assert not unbounded, unbounded

    async def test_the_document_itself_is_served(self, client: AsyncClient):
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        assert response.json()["info"]["title"]


class TestErrorEnvelope:
    async def test_an_unknown_path_uses_the_envelope(self, client: AsyncClient):
        response = await client.get("/api/v1/no-such-thing")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    async def test_a_wrong_method_uses_the_envelope(self, client: AsyncClient):
        response = await client.delete("/api/v1/health/live")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"

    async def test_malformed_json_is_a_validation_error_not_a_crash(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            content=b"{not json at all",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_a_validation_error_names_the_field(self, client: AsyncClient):
        """NFR-4.7: the message must say what to fix."""
        response = await client.post("/api/v1/auth/login", json={"email": "not-an-email"})
        assert response.status_code == 422
        fields = response.json()["error"]["details"]["fields"]
        assert "email" in fields and "password" in fields

    async def test_an_unexpected_error_returns_no_stack_trace(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        user_factory,
        auth_headers,
    ):
        """A traceback in a response body maps the application for an attacker.

        The fault is planted in a repository method rather than in a route
        function: FastAPI binds the route's callable when the router is
        included, so replacing the module attribute afterwards changes
        nothing. A method is looked up on the class at call time, which makes
        this a real request failing inside real request handling.
        """
        from app.repositories.user import UserRepository

        async def explode(self, user_id):
            raise RuntimeError("secret internal detail: /srv/app/app/services/auth.py")

        monkeypatch.setattr(UserRepository, "get_with_avatar", explode)

        user = await user_factory()

        # Starlette's server-error handler builds the response and then
        # re-raises, so the process running the app still logs the fault. The
        # default test transport re-raises it at the client too, which would
        # mean asserting on an exception instead of on what a browser
        # receives — so this one client is told to hand the response back.
        transport = ASGITransport(app=fastapi_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as forgiving:
            response = await forgiving.get(
                "/api/v1/users/me",
                headers={**auth_headers(user), "X-Request-ID": "trace-me"},
            )

        assert response.status_code == 500
        body = response.json()
        assert body["error"]["code"] == "INTERNAL_ERROR"
        assert "secret internal detail" not in response.text
        assert "Traceback" not in response.text
        # The request ID is the only thing returned, so a user can quote it
        # and an operator can find the trace in the log.
        assert body["error"]["details"]["request_id"] == "trace-me"


class TestSecurityHeaders:
    async def test_every_response_carries_the_hardening_headers(self, client: AsyncClient):
        expected = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        }
        for method, path in [("GET", "/api/v1/health/live"), ("GET", "/api/v1/users/me")]:
            response = await client.request(method, path)
            for header, value in expected.items():
                assert response.headers.get(header) == value, f"{method} {path} missing {header}"

    async def test_hsts_is_sent_only_in_production(self, client: AsyncClient, monkeypatch):
        """A development server sending HSTS pins localhost to HTTPS.

        The browser remembers it for a year, and every other project the
        developer runs on localhost breaks — so the header is correct in
        production and actively harmful anywhere else.
        """
        from app.core.config import get_settings

        settings = get_settings()

        assert "Strict-Transport-Security" not in (await client.get("/api/v1/health/live")).headers

        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        response = await client.get("/api/v1/health/live")
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]

    async def test_a_request_id_is_returned_even_on_an_error(self, client: AsyncClient):
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 401
        assert response.headers.get("X-Request-ID")
