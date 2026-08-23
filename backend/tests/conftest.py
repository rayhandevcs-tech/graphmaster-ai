"""Shared pytest fixtures.

Environment variables are set before any application module is imported,
because ``Settings`` is validated eagerly at import time and would otherwise
pick up the developer's own ``.env``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long-xyz")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://graphmaster:graphmaster@localhost:5432/graphmaster_test",
)
os.environ.setdefault("STORAGE_LOCAL_PATH", "./.test-storage")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401  registers every table on Base.metadata
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session", autouse=True)
def database_schema():
    """Create the test schema once, synchronously.

    Deliberately not async: an async engine is bound to the event loop that
    created it, and pytest-asyncio gives each test its own loop, so a
    session-scoped async engine would fail every test after the first with
    "attached to a different loop". Doing the DDL over a plain synchronous
    connection sidesteps the question entirely.
    """
    sync_engine = create_engine(get_settings().sync_database_url)
    Base.metadata.drop_all(sync_engine)
    Base.metadata.create_all(sync_engine)
    yield
    Base.metadata.drop_all(sync_engine)
    sync_engine.dispose()


@pytest.fixture
async def db(database_schema) -> AsyncGenerator[AsyncSession, None]:
    """A per-test session inside a transaction that is always rolled back.

    Each test starts from the same clean schema without paying to recreate it,
    and no test can leak state into another.
    """
    engine = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    connection = await engine.connect()
    transaction = await connection.begin()
    factory = async_sessionmaker(bind=connection, expire_on_commit=False, autoflush=False)
    session = factory()
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """An HTTP client whose requests share the test's rolled-back session."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()


# ── Seed data and user factories ─────────────────────────────────────────────


@pytest.fixture
async def seeded(db: AsyncSession):
    """Reference data every test that touches users needs.

    Registration assigns an avatar from gender, so without seeded avatars every
    registration test would exercise the unseeded-database path instead of the
    real one.
    """
    from app.db.seed.runner import seed_avatars, seed_badges

    await seed_avatars(db)
    await seed_badges(db)
    return db


@pytest.fixture
def user_factory(db: AsyncSession):
    """Build and persist a user directly, bypassing the registration endpoint."""
    from app.core.security import hash_password
    from app.models.enums import Gender, UserRole
    from app.models.identity import User

    counter = {"n": 0}

    async def make(
        *,
        email: str | None = None,
        password: str = "testpass123",
        role: UserRole = UserRole.STUDENT,
        gender: Gender = Gender.FEMALE,
        full_name: str = "Test User",
        is_active: bool = True,
        total_xp: int = 0,
        current_level: int = 1,
        avatar_id=None,
        class_id=None,
    ) -> User:
        counter["n"] += 1
        user = User(
            email=email or f"user{counter['n']}@test.edu",
            password_hash=hash_password(password),
            full_name=full_name,
            role=role.value,
            gender=gender.value,
            is_active=is_active,
            total_xp=total_xp,
            current_level=current_level,
            avatar_id=avatar_id,
            class_id=class_id,
        )
        db.add(user)
        await db.flush()
        return user

    return make


@pytest.fixture
def auth_headers():
    """Build an Authorization header for a user."""
    from app.core.security import create_access_token

    def make(user) -> dict[str, str]:
        token = create_access_token(user.id, role=user.role, gender=user.gender)
        return {"Authorization": f"Bearer {token}"}

    return make


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear rate-limit state between tests.

    The limiter is a process-wide singleton, so without this the auth tests
    would exhaust the 10-per-5-minutes budget and later tests would fail with
    429 for reasons unrelated to what they assert.
    """
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()
