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
