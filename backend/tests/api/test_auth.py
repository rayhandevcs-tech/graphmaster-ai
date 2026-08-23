"""Authentication endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"


def registration(**overrides) -> dict:
    return {
        "full_name": "Nadia Rahman",
        "email": "nadia@university.edu",
        "password": "strongpass123",
        "gender": "female",
    } | overrides


class TestRegister:
    async def test_creates_student_account(self, client: AsyncClient, seeded):
        r = await client.post(REGISTER, json=registration())
        assert r.status_code == 201

        body = r.json()
        assert body["user"]["email"] == "nadia@university.edu"
        assert body["user"]["role"] == "student"
        assert body["user"]["gender"] == "female"
        assert body["tokens"]["access_token"]
        assert body["tokens"]["token_type"] == "bearer"

    async def test_assigns_gender_matched_default_avatar(self, client: AsyncClient, seeded):
        female = await client.post(REGISTER, json=registration())
        male = await client.post(
            REGISTER, json=registration(email="arif@university.edu", gender="male")
        )

        assert female.json()["user"]["avatar"]["code"] == "girl_default"
        assert male.json()["user"]["avatar"]["code"] == "boy_default"

    async def test_new_account_starts_at_level_one(self, client: AsyncClient, seeded):
        user = (await client.post(REGISTER, json=registration())).json()["user"]
        assert user["current_level"] == 1
        assert user["total_xp"] == 0
        assert user["current_streak_days"] == 0

    async def test_duplicate_email_rejected(self, client: AsyncClient, seeded):
        await client.post(REGISTER, json=registration())
        r = await client.post(REGISTER, json=registration())
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"

    async def test_email_case_and_whitespace_normalised(self, client: AsyncClient, seeded):
        # "N@Example.com" and "n@example.com" must be one account, not two.
        await client.post(REGISTER, json=registration(email="Nadia@University.edu"))
        r = await client.post(REGISTER, json=registration(email="nadia@university.edu"))
        assert r.status_code == 409

    async def test_refresh_cookie_is_httponly(self, client: AsyncClient, seeded):
        r = await client.post(REGISTER, json=registration())
        cookie_header = r.headers.get("set-cookie", "")
        assert "graphmaster_refresh" in cookie_header
        # HttpOnly is what limits an XSS bug to the short-lived access token.
        assert "httponly" in cookie_header.lower()

    async def test_password_hash_never_returned(self, client: AsyncClient, seeded):
        r = await client.post(REGISTER, json=registration())
        assert "password" not in r.text.lower().replace("strongpass123", "")

    @pytest.mark.parametrize(
        "field,value",
        [
            ("email", "not-an-email"),
            ("password", "short1"),
            ("password", "nodigitshere"),
            ("password", "12345678"),
            ("gender", "other"),
            ("full_name", ""),
        ],
    )
    async def test_invalid_input_rejected(
        self, client: AsyncClient, seeded, field: str, value: str
    ):
        r = await client.post(REGISTER, json=registration(**{field: value}))
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_unknown_class_code_rejected(self, client: AsyncClient, seeded):
        r = await client.post(REGISTER, json=registration(class_code="NOPE99"))
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "CLASS_CODE_INVALID"

    async def test_cannot_self_assign_privileged_role(self, client: AsyncClient, seeded):
        # `role` is not part of RegisterRequest, so a supplied value must be
        # ignored rather than honoured.
        r = await client.post(REGISTER, json=registration(role="admin"))
        assert r.status_code == 201
        assert r.json()["user"]["role"] == "student"


class TestLogin:
    async def test_valid_credentials(self, client: AsyncClient, seeded):
        await client.post(REGISTER, json=registration())
        r = await client.post(
            LOGIN, json={"email": "nadia@university.edu", "password": "strongpass123"}
        )
        assert r.status_code == 200
        assert r.json()["tokens"]["access_token"]

    async def test_login_is_case_insensitive_on_email(self, client: AsyncClient, seeded):
        await client.post(REGISTER, json=registration())
        r = await client.post(
            LOGIN, json={"email": "NADIA@University.EDU", "password": "strongpass123"}
        )
        assert r.status_code == 200

    async def test_wrong_password_rejected(self, client: AsyncClient, seeded):
        await client.post(REGISTER, json=registration())
        r = await client.post(
            LOGIN, json={"email": "nadia@university.edu", "password": "wrongpass123"}
        )
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"

    async def test_unknown_email_gives_same_error_as_wrong_password(
        self, client: AsyncClient, seeded
    ):
        # Distinguishing the two would let an attacker enumerate which
        # addresses have accounts.
        r = await client.post(
            LOGIN, json={"email": "ghost@university.edu", "password": "whatever123"}
        )
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"

    async def test_deactivated_account_rejected(self, client: AsyncClient, seeded, user_factory):
        await user_factory(email="gone@test.edu", password="testpass123", is_active=False)
        r = await client.post(LOGIN, json={"email": "gone@test.edu", "password": "testpass123"})
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "ACCOUNT_INACTIVE"


class TestRefresh:
    async def test_rotates_token(self, client: AsyncClient, seeded):
        original = (await client.post(REGISTER, json=registration())).json()["tokens"][
            "refresh_token"
        ]
        r = await client.post(REFRESH, json={"refresh_token": original})
        assert r.status_code == 200
        assert r.json()["refresh_token"] != original

    async def test_old_token_dies_on_rotation(self, client: AsyncClient, seeded):
        original = (await client.post(REGISTER, json=registration())).json()["tokens"][
            "refresh_token"
        ]
        await client.post(REFRESH, json={"refresh_token": original})

        r = await client.post(REFRESH, json={"refresh_token": original})
        assert r.status_code == 401

    async def test_replay_revokes_whole_session_family(self, client: AsyncClient, seeded):
        original = (await client.post(REGISTER, json=registration())).json()["tokens"][
            "refresh_token"
        ]
        rotated = (await client.post(REFRESH, json={"refresh_token": original})).json()[
            "refresh_token"
        ]

        # Replaying the consumed token means it leaked, so the attacker's and
        # the victim's copies must both stop working.
        await client.post(REFRESH, json={"refresh_token": original})

        r = await client.post(REFRESH, json={"refresh_token": rotated})
        assert r.status_code == 401

    async def test_unknown_token_rejected(self, client: AsyncClient, seeded):
        r = await client.post(REFRESH, json={"refresh_token": "made-up"})
        assert r.status_code == 401

    async def test_missing_token_rejected(self, client: AsyncClient, seeded):
        r = await client.post(REFRESH, json={})
        assert r.status_code == 401


class TestLogout:
    async def test_revokes_session(self, client: AsyncClient, seeded):
        token = (await client.post(REGISTER, json=registration())).json()["tokens"]["refresh_token"]
        assert (await client.post(LOGOUT, json={"refresh_token": token})).status_code == 200
        assert (await client.post(REFRESH, json={"refresh_token": token})).status_code == 401

    async def test_logout_is_idempotent(self, client: AsyncClient, seeded):
        # Signing out must work even with an expired or unknown token,
        # otherwise a stale session could never be cleared.
        r = await client.post(LOGOUT, json={"refresh_token": "never-existed"})
        assert r.status_code == 200


class TestPasswordReset:
    async def test_response_identical_for_unknown_email(self, client: AsyncClient, seeded):
        await client.post(REGISTER, json=registration())

        known = await client.post(
            "/api/v1/auth/password-reset/request", json={"email": "nadia@university.edu"}
        )
        unknown = await client.post(
            "/api/v1/auth/password-reset/request", json={"email": "ghost@university.edu"}
        )
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()

    async def test_reset_token_not_leaked_in_response(self, client: AsyncClient, seeded):
        await client.post(REGISTER, json=registration())
        r = await client.post(
            "/api/v1/auth/password-reset/request", json={"email": "nadia@university.edu"}
        )
        assert "token" not in r.json()

    async def test_reset_changes_password_and_kills_sessions(self, client: AsyncClient, seeded, db):
        from app.core.security import create_password_reset_token
        from app.repositories.user import UserRepository

        old_refresh = (await client.post(REGISTER, json=registration())).json()["tokens"][
            "refresh_token"
        ]
        user = await UserRepository(db).get_by_email("nadia@university.edu")
        token = create_password_reset_token(user.id)

        r = await client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "brandnewpass456"},
        )
        assert r.status_code == 200

        # The old password stops working, the new one starts.
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

        # A reset is often prompted by suspected compromise, so existing
        # sessions must not survive it.
        assert (await client.post(REFRESH, json={"refresh_token": old_refresh})).status_code == 401

    async def test_access_token_rejected_as_reset_token(self, client: AsyncClient, seeded):
        access = (await client.post(REGISTER, json=registration())).json()["tokens"]["access_token"]
        r = await client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": access, "new_password": "brandnewpass456"},
        )
        assert r.status_code == 401


class TestRateLimiting:
    async def test_login_attempts_are_limited(self, client: AsyncClient, seeded):
        payload = {"email": "nobody@university.edu", "password": "guessing123"}
        statuses = [(await client.post(LOGIN, json=payload)).status_code for _ in range(12)]

        assert 429 in statuses, "brute-force attempts were never throttled"
        assert statuses.index(429) >= 10, "throttled earlier than the configured limit"

    async def test_rate_limited_response_has_retry_after(self, client: AsyncClient, seeded):
        payload = {"email": "nobody@university.edu", "password": "guessing123"}
        last = None
        for _ in range(12):
            last = await client.post(LOGIN, json=payload)
        assert last.status_code == 429
        assert last.headers.get("Retry-After")
