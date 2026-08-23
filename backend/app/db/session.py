"""Async engine, session factory and the request-scoped session dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

_engine_kwargs: dict = {"echo": settings.DB_ECHO, "pool_pre_ping": True}
if not settings.DATABASE_URL.startswith("sqlite"):
    # SQLite (used by the test suite) rejects pool sizing arguments.
    _engine_kwargs |= {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
    }

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keeps ORM objects usable after commit in responses
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """One request, one transaction.

    Committed on clean exit, rolled back on any exception. This is what makes
    scoring atomic: the score row, XP events, badge and achievements either all
    land or none do.
    """
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
