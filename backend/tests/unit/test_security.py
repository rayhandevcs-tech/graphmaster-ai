"""Password hashing and JWT handling."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from app.core.exceptions import InvalidTokenError, TokenExpiredError
from app.core.security import (
    BCRYPT_MAX_BYTES,
    create_access_token,
    create_password_reset_token,
    decode_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_then_verify(self):
        hashed = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", hashed)

    def test_wrong_password_rejected(self):
        assert not verify_password("wrong", hash_password("right"))

    def test_hash_is_salted(self):
        # Identical passwords must not produce identical hashes, or the hash
        # database would reveal which users share a password.
        assert hash_password("same") != hash_password("same")

    def test_plaintext_never_appears_in_hash(self):
        assert "hunter2" not in hash_password("hunter2")

    def test_overlong_password_rejected_not_truncated(self):
        # bcrypt silently ignores anything past 72 bytes. Accepting such a
        # password would mean two different long passwords both unlock the
        # account, so it is rejected instead.
        with pytest.raises(ValueError, match="72 bytes"):
            hash_password("a" * (BCRYPT_MAX_BYTES + 1))

    def test_overlong_verify_returns_false(self):
        assert not verify_password("a" * 200, hash_password("short"))

    def test_corrupt_hash_reads_as_wrong_password(self):
        # Must not raise: a server error here would tell an attacker they had
        # found an interesting account.
        assert not verify_password("anything", "not-a-real-bcrypt-hash")

    def test_unicode_password(self):
        pw = "পাসওয়ার্ড-123"
        assert verify_password(pw, hash_password(pw))


class TestAccessTokens:
    def test_round_trip(self):
        uid = uuid.uuid4()
        payload = decode_token(create_access_token(uid, role="student", gender="female"))
        assert payload["sub"] == str(uid)
        assert payload["role"] == "student"
        assert payload["gender"] == "female"
        assert payload["type"] == "access"

    def test_expired_token_raises(self):
        token = create_access_token(
            uuid.uuid4(), role="student", expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(TokenExpiredError):
            decode_token(token)

    def test_tampered_token_raises(self):
        token = create_access_token(uuid.uuid4(), role="student")
        head, payload, sig = token.split(".")
        with pytest.raises(InvalidTokenError):
            decode_token(f"{head}.{payload}.{sig[:-4]}AAAA")

    def test_garbage_token_raises(self):
        with pytest.raises(InvalidTokenError):
            decode_token("not-a-jwt")

    def test_reset_token_rejected_where_access_expected(self):
        # Without the type check, a password-reset token would authenticate
        # ordinary API requests.
        reset = create_password_reset_token(uuid.uuid4())
        with pytest.raises(InvalidTokenError):
            decode_token(reset, expected_type="access")

    def test_access_token_rejected_where_reset_expected(self):
        access = create_access_token(uuid.uuid4(), role="student")
        with pytest.raises(InvalidTokenError):
            decode_token(access, expected_type="password_reset")

    def test_each_token_has_unique_jti(self):
        uid = uuid.uuid4()
        a = decode_token(create_access_token(uid, role="student"))
        b = decode_token(create_access_token(uid, role="student"))
        assert a["jti"] != b["jti"]


class TestRefreshTokens:
    def test_tokens_are_unique_and_long(self):
        tokens = {generate_refresh_token() for _ in range(100)}
        assert len(tokens) == 100
        assert all(len(t) >= 32 for t in tokens)

    def test_hash_is_deterministic(self):
        token = generate_refresh_token()
        assert hash_refresh_token(token) == hash_refresh_token(token)

    def test_hash_is_sha256_hex(self):
        assert len(hash_refresh_token(generate_refresh_token())) == 64

    def test_hash_does_not_contain_token(self):
        token = generate_refresh_token()
        assert token not in hash_refresh_token(token)


class TestTokenClaims:
    def test_a_token_with_no_subject_is_refused(self):
        """A signed token still has to say who it is for.

        The subject is what the request handler turns into a user; a token
        without one that reached `decode_token`'s caller would become a
        lookup for `None`.
        """
        from jose import jwt

        from app.core.config import get_settings
        from app.core.exceptions import InvalidTokenError
        from app.core.security import decode_token

        settings = get_settings()
        token = jwt.encode(
            {"type": "access", "role": "student", "exp": 9_999_999_999},
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

        with pytest.raises(InvalidTokenError, match="subject"):
            decode_token(token)

    def test_a_token_signed_with_another_key_is_refused(self):
        """The whole scheme rests on this one check."""
        from jose import jwt

        from app.core.exceptions import InvalidTokenError
        from app.core.security import decode_token

        token = jwt.encode(
            {"sub": "abc", "type": "access", "exp": 9_999_999_999},
            "a-different-secret-key-that-is-long-enough",
            algorithm="HS256",
        )

        with pytest.raises(InvalidTokenError):
            decode_token(token)
