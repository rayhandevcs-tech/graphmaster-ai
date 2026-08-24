"""The session-management endpoints, and what happens when an account changes.

`test_auth.py` covers signing in and the happy paths around a token. This
module covers the two endpoints that end a session deliberately — changing a
password and signing out everywhere — and the cases where a refresh token
outlives the account it belongs to. Those are the paths a compromised account
takes, so "untested" is not a state they should be in.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from app.models.identity import AuthSession, User

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
LOGOUT_ALL = "/api/v1/auth/logout-all"
CHANGE_PASSWORD = "/api/v1/auth/change-password"
CONFIRM_RESET = "/api/v1/auth/password-reset/confirm"


def registration(**overrides) -> dict:
    return {
        "full_name": "Nadia Rahman",
        "email": "nadia@university.edu",
        "password": "strongpass123",
        "gender": "female",
    } | overrides


async def register(client: AsyncClient, **overrides) -> dict:
    response = await client.post(REGISTER, json=registration(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def bearer(session: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {session['tokens']['access_token']}"}


class TestChangePassword:
    async def test_the_new_password_replaces_the_old_one(self, client: AsyncClient, seeded):
        session = await register(client)

        response = await client.post(
            CHANGE_PASSWORD,
            json={"current_password": "strongpass123", "new_password": "brandnewpass456"},
            headers=bearer(session),
        )
        assert response.status_code == 200

        assert (
            await client.post(
                LOGIN, json={"email": "nadia@university.edu", "password": "strongpass123"}
            )
        ).status_code == 401
        assert (
            await client.post(
                LOGIN, json={"email": "nadia@university.edu", "password": "brandnewpass456"}
            )
        ).status_code == 200

    async def test_the_wrong_current_password_changes_nothing(self, client: AsyncClient, seeded):
        """Otherwise a borrowed access token is enough to take the account over.

        An access token can be lifted from a shared machine; requiring the
        current password is what stops that becoming permanent ownership.
        """
        session = await register(client)

        response = await client.post(
            CHANGE_PASSWORD,
            json={"current_password": "not-the-password", "new_password": "brandnewpass456"},
            headers=bearer(session),
        )
        assert response.status_code == 401

        assert (
            await client.post(
                LOGIN, json={"email": "nadia@university.edu", "password": "strongpass123"}
            )
        ).status_code == 200

    async def test_every_other_session_dies_with_the_old_password(
        self, client: AsyncClient, seeded
    ):
        """A password change is how a student responds to a suspected compromise."""
        first = await register(client)
        second = (
            await client.post(
                LOGIN, json={"email": "nadia@university.edu", "password": "strongpass123"}
            )
        ).json()

        await client.post(
            CHANGE_PASSWORD,
            json={"current_password": "strongpass123", "new_password": "brandnewpass456"},
            headers=bearer(first),
        )

        for tokens in (first["tokens"], second["tokens"]):
            response = await client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})
            assert response.status_code == 401

    async def test_the_refresh_cookie_is_cleared(self, client: AsyncClient, seeded):
        """The browser must not keep sending a token the server has revoked."""
        session = await register(client)
        response = await client.post(
            CHANGE_PASSWORD,
            json={"current_password": "strongpass123", "new_password": "brandnewpass456"},
            headers=bearer(session),
        )
        assert "graphmaster_refresh=" in response.headers.get("set-cookie", "")

    async def test_it_requires_the_current_password_to_be_supplied(
        self, client: AsyncClient, seeded
    ):
        session = await register(client)
        response = await client.post(
            CHANGE_PASSWORD, json={"new_password": "brandnewpass456"}, headers=bearer(session)
        )
        assert response.status_code == 422


class TestLogoutEverywhere:
    async def test_it_revokes_every_session_and_says_how_many(self, client: AsyncClient, seeded):
        first = await register(client)
        second = (
            await client.post(
                LOGIN, json={"email": "nadia@university.edu", "password": "strongpass123"}
            )
        ).json()

        response = await client.post(LOGOUT_ALL, headers=bearer(first))
        assert response.status_code == 200
        # The count is what tells a student whether the device they were
        # worried about was signed in at all.
        assert "2 session(s)" in response.json()["message"]

        for tokens in (first["tokens"], second["tokens"]):
            assert (
                await client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})
            ).status_code == 401

    async def test_signing_out_everywhere_twice_is_not_an_error(self, client: AsyncClient, seeded):
        session = await register(client)
        await client.post(LOGOUT_ALL, headers=bearer(session))

        response = await client.post(LOGOUT_ALL, headers=bearer(session))
        assert response.status_code == 200
        assert "0 session(s)" in response.json()["message"]

    async def test_it_needs_a_token(self, client: AsyncClient, seeded):
        assert (await client.post(LOGOUT_ALL)).status_code == 401


class TestLogout:
    async def test_a_request_with_no_token_at_all_succeeds(self, client: AsyncClient, seeded):
        """Signing out is idempotent, and the caller ends up signed out either way."""
        response = await client.post(LOGOUT, json={})
        assert response.status_code == 200


class TestARefreshTokenThatOutlivesItsAccount:
    async def test_an_expired_session_is_refused(self, client: AsyncClient, seeded, db):
        """Rotation is what keeps a leaked token useful for minutes, not months."""
        session = await register(client)
        row = (await db.execute(select(AuthSession))).scalars().one()
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.flush()

        response = await client.post(
            REFRESH, json={"refresh_token": session["tokens"]["refresh_token"]}
        )
        assert response.status_code == 401
        assert "expired" in response.json()["error"]["message"].lower()

    async def test_a_naive_expiry_is_read_as_utc(self, client: AsyncClient, seeded, db):
        """A column written without an offset must not read as "far future".

        PostgreSQL returns an aware value, but a database restored from a dump
        taken without timezone support does not — and comparing a naive
        datetime against an aware one raises rather than refusing the token.
        """
        session = await register(client)
        row = (await db.execute(select(AuthSession))).scalars().one()
        row.expires_at = (datetime.now(UTC) + timedelta(days=30)).replace(tzinfo=None)
        await db.flush()
        db.expunge(row)

        response = await client.post(
            REFRESH, json={"refresh_token": session["tokens"]["refresh_token"]}
        )
        assert response.status_code == 200

    async def test_a_deactivated_account_cannot_refresh(self, client: AsyncClient, seeded, db):
        """Suspension has to take effect before the access token expires."""
        session = await register(client)
        user = (await db.execute(select(User))).scalars().one()
        user.is_active = False
        await db.flush()

        response = await client.post(
            REFRESH, json={"refresh_token": session["tokens"]["refresh_token"]}
        )
        # 401 rather than 403, matching a deactivated sign-in: from the
        # caller's side the session is simply no longer usable, and the
        # distinction between "wrong credentials" and "suspended" is not one
        # an unauthenticated caller is owed.
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "ACCOUNT_INACTIVE"

    async def test_a_deleted_account_cannot_refresh(self, client: AsyncClient, seeded, db):
        """The session row cascades away with the user, so this is the unknown-token path."""
        session = await register(client)
        user = (await db.execute(select(User))).scalars().one()
        await db.delete(user)
        await db.flush()

        response = await client.post(
            REFRESH, json={"refresh_token": session["tokens"]["refresh_token"]}
        )
        assert response.status_code == 401


class TestResettingAPasswordOnAClosedAccount:
    async def test_a_deactivated_account_cannot_complete_a_reset(
        self, client: AsyncClient, seeded, db
    ):
        """A suspended student must not be able to let themselves back in."""
        from app.core.security import create_password_reset_token

        await register(client)
        user = (await db.execute(select(User))).scalars().one()
        token = create_password_reset_token(user.id)
        user.is_active = False
        await db.flush()

        response = await client.post(
            CONFIRM_RESET, json={"token": token, "new_password": "brandnewpass456"}
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "ACCOUNT_INACTIVE"

    async def test_a_reset_token_for_a_deleted_account_is_refused(
        self, client: AsyncClient, seeded, db
    ):
        from app.core.security import create_password_reset_token

        await register(client)
        user = (await db.execute(select(User))).scalars().one()
        token = create_password_reset_token(user.id)
        await db.delete(user)
        await db.flush()

        response = await client.post(
            CONFIRM_RESET, json={"token": token, "new_password": "brandnewpass456"}
        )
        assert response.status_code == 404


class TestRegisteringWithoutAnAvatarCatalogue:
    async def test_the_account_is_still_created(self, client: AsyncClient, db):
        """A database missing its seed data must not lock students out.

        Deliberately run without the `seeded` fixture: the avatar is cosmetic,
        the account is not, and refusing to register anyone until an operator
        notices would be a far worse failure than an avatar-less profile.
        """
        response = await client.post(REGISTER, json=registration())
        assert response.status_code == 201
        assert response.json()["user"]["avatar"] is None


class TestExpiredSessionHousekeeping:
    """`delete_expired` has no scheduler yet — see PROJECT_PLAN §1.4 #4.

    It is tested rather than deleted because the row it removes is a real
    liability: an expired refresh token is unusable but still identifies a
    student's device, and the table grows by one row per sign-in forever.
    """

    async def test_it_drops_expired_sessions_and_keeps_live_ones(self, client, seeded, db):
        from app.repositories.auth_session import AuthSessionRepository

        live = await register(client)
        expired_owner = await register(client, email="other@university.edu")

        rows = (await db.execute(select(AuthSession))).scalars().all()
        assert len(rows) == 2
        for row in rows:
            if str(row.user_id) == expired_owner["user"]["id"]:
                row.expires_at = datetime.now(UTC) - timedelta(days=1)
        await db.flush()

        assert await AuthSessionRepository(db).delete_expired() == 1

        remaining = (await db.execute(select(AuthSession))).scalars().all()
        assert len(remaining) == 1
        assert str(remaining[0].user_id) == live["user"]["id"]

    async def test_it_is_harmless_when_nothing_has_expired(self, client, seeded, db):
        from app.repositories.auth_session import AuthSessionRepository

        await register(client)
        assert await AuthSessionRepository(db).delete_expired() == 0
