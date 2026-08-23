"""User profile, RBAC and administration endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.models.enums import UserRole


class TestCurrentUser:
    async def test_returns_own_profile(self, client: AsyncClient, user_factory, auth_headers):
        user = await user_factory(email="me@test.edu", full_name="Nadia Rahman")
        r = await client.get("/api/v1/users/me", headers=auth_headers(user))
        assert r.status_code == 200
        assert r.json()["email"] == "me@test.edu"
        assert r.json()["full_name"] == "Nadia Rahman"

    async def test_requires_authentication(self, client: AsyncClient):
        r = await client.get("/api/v1/users/me")
        assert r.status_code == 401

    async def test_rejects_garbage_token(self, client: AsyncClient):
        r = await client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert r.status_code == 401

    async def test_rejects_token_for_deleted_user(self, client: AsyncClient, auth_headers):
        from types import SimpleNamespace

        ghost = SimpleNamespace(id=uuid.uuid4(), role="student", gender="female")
        r = await client.get("/api/v1/users/me", headers=auth_headers(ghost))
        assert r.status_code == 401

    async def test_rejects_deactivated_user(self, client: AsyncClient, user_factory, auth_headers):
        user = await user_factory(is_active=False)
        r = await client.get("/api/v1/users/me", headers=auth_headers(user))
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "ACCOUNT_INACTIVE"

    async def test_update_name(self, client: AsyncClient, user_factory, auth_headers):
        user = await user_factory()
        r = await client.patch(
            "/api/v1/users/me",
            headers=auth_headers(user),
            json={"full_name": "  Updated   Name  "},
        )
        assert r.status_code == 200
        assert r.json()["full_name"] == "Updated Name"


class TestLevelProgress:
    async def test_reports_progress_within_level(
        self, client: AsyncClient, user_factory, auth_headers
    ):
        # Level 9 spans 1,800 to 2,250 XP.
        user = await user_factory(total_xp=2000)
        r = await client.get("/api/v1/users/me/level", headers=auth_headers(user))
        body = r.json()
        assert body["current_level"] == 9
        assert body["xp_into_level"] == 200
        assert body["xp_for_next_level"] == 450
        assert body["is_max_level"] is False

    async def test_max_level_reports_no_next(self, client: AsyncClient, user_factory, auth_headers):
        user = await user_factory(total_xp=999_999)
        body = (await client.get("/api/v1/users/me/level", headers=auth_headers(user))).json()
        assert body["current_level"] == 100
        assert body["is_max_level"] is True
        assert body["xp_for_next_level"] == 0


class TestPublicProfile:
    async def test_hides_email_and_class(self, client: AsyncClient, user_factory, auth_headers):
        viewer = await user_factory(email="viewer@test.edu")
        other = await user_factory(email="other@test.edu", total_xp=500)

        r = await client.get(f"/api/v1/users/{other.id}", headers=auth_headers(viewer))
        assert r.status_code == 200

        body = r.json()
        assert "email" not in body, "public profile must not expose contact details"
        assert "class_id" not in body
        assert "last_activity_date" not in body
        assert body["full_name"] == "Test User"

    async def test_deactivated_user_reads_as_absent(
        self, client: AsyncClient, user_factory, auth_headers
    ):
        viewer = await user_factory()
        hidden = await user_factory(is_active=False)
        r = await client.get(f"/api/v1/users/{hidden.id}", headers=auth_headers(viewer))
        assert r.status_code == 404

    async def test_unknown_user_is_404(self, client: AsyncClient, user_factory, auth_headers):
        viewer = await user_factory()
        r = await client.get(f"/api/v1/users/{uuid.uuid4()}", headers=auth_headers(viewer))
        assert r.status_code == 404


class TestRoleBasedAccess:
    @pytest.mark.parametrize(
        "role,expected",
        [(UserRole.STUDENT, 403), (UserRole.TEACHER, 403), (UserRole.ADMIN, 200)],
    )
    async def test_user_list_is_admin_only(
        self, client: AsyncClient, user_factory, auth_headers, role, expected
    ):
        user = await user_factory(role=role)
        r = await client.get("/api/v1/users", headers=auth_headers(user))
        assert r.status_code == expected

    async def test_forbidden_uses_role_error_code(
        self, client: AsyncClient, user_factory, auth_headers
    ):
        student = await user_factory(role=UserRole.STUDENT)
        r = await client.get("/api/v1/users", headers=auth_headers(student))
        assert r.json()["error"]["code"] == "INSUFFICIENT_ROLE"


class TestAdministration:
    async def test_list_is_paginated(self, client: AsyncClient, user_factory, auth_headers):
        admin = await user_factory(role=UserRole.ADMIN)
        for i in range(5):
            await user_factory(email=f"s{i}@test.edu")

        r = await client.get("/api/v1/users?page=1&page_size=3", headers=auth_headers(admin))
        body = r.json()
        assert len(body["items"]) == 3
        assert body["total"] == 6
        assert body["total_pages"] == 2

    async def test_filter_by_role(self, client: AsyncClient, user_factory, auth_headers):
        admin = await user_factory(role=UserRole.ADMIN)
        await user_factory(role=UserRole.TEACHER)
        await user_factory(role=UserRole.STUDENT)

        r = await client.get("/api/v1/users?role=teacher", headers=auth_headers(admin))
        assert r.json()["total"] == 1

    async def test_search_by_email(self, client: AsyncClient, user_factory, auth_headers):
        admin = await user_factory(role=UserRole.ADMIN)
        await user_factory(email="findme@test.edu")

        r = await client.get("/api/v1/users?search=findme", headers=auth_headers(admin))
        assert r.json()["total"] == 1

    async def test_promote_user(self, client: AsyncClient, user_factory, auth_headers):
        admin = await user_factory(role=UserRole.ADMIN)
        student = await user_factory(role=UserRole.STUDENT)

        r = await client.patch(
            f"/api/v1/users/{student.id}",
            headers=auth_headers(admin),
            json={"role": "teacher"},
        )
        assert r.status_code == 200
        assert r.json()["role"] == "teacher"

    async def test_role_change_revokes_sessions(
        self, client: AsyncClient, user_factory, auth_headers, seeded
    ):
        # The role is a claim inside issued access tokens, so a change must
        # invalidate them; otherwise a demoted user keeps their privileges
        # until the token expires.

        admin = await user_factory(role=UserRole.ADMIN)
        await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Target User",
                "email": "target@test.edu",
                "password": "strongpass123",
                "gender": "male",
            },
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "target@test.edu", "password": "strongpass123"},
        )
        refresh_token = login.json()["tokens"]["refresh_token"]
        target_id = login.json()["user"]["id"]

        await client.patch(
            f"/api/v1/users/{target_id}",
            headers=auth_headers(admin),
            json={"role": "teacher"},
        )

        r = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert r.status_code == 401

    async def test_admin_cannot_demote_self(self, client: AsyncClient, user_factory, auth_headers):
        # Otherwise the last administrator could lock everyone out.
        admin = await user_factory(role=UserRole.ADMIN)
        r = await client.patch(
            f"/api/v1/users/{admin.id}",
            headers=auth_headers(admin),
            json={"role": "student"},
        )
        assert r.status_code == 403

    async def test_admin_cannot_deactivate_self(
        self, client: AsyncClient, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.ADMIN)
        r = await client.patch(
            f"/api/v1/users/{admin.id}",
            headers=auth_headers(admin),
            json={"is_active": False},
        )
        assert r.status_code == 403
