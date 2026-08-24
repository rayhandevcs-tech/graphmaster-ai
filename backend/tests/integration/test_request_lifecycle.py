"""The request-scoped transaction, and what happens at boot.

Every other test in the suite replaces `get_db` with a session that is rolled
back afterwards, so the real dependency — the one that decides whether a
student's score and the XP it earned land together — is never executed. It
runs here, against the real engine, and cleans up after itself.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import engine, get_db
from app.models.enums import Gender, UserRole
from app.models.identity import User

pytestmark = pytest.mark.anyio


def build_user(marker: str) -> User:
    return User(
        email=f"lifecycle-{marker}@test.edu",
        password_hash=hash_password("testpass123"),
        full_name="Lifecycle User",
        role=UserRole.STUDENT.value,
        gender=Gender.FEMALE.value,
    )


@pytest.fixture(autouse=True)
async def fresh_engine_pool():
    """Stop the process-wide engine handing this test a stale connection.

    `app.db.session.engine` is built once at import and pools its connections.
    pytest-asyncio gives each test its own event loop, so a connection opened
    by the previous test belongs to a loop that no longer runs — and the
    second test to reuse it dies with "attached to a different loop". Disposal
    with `close=False` abandons those connections rather than trying to close
    them from the wrong loop.
    """
    await engine.dispose(close=False)
    yield
    await engine.dispose(close=False)


@pytest.fixture
async def inspector(database_schema):
    """A second connection, so what the dependency committed can be seen."""
    engine = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    marker = uuid.uuid4().hex[:8]
    try:
        yield factory, marker
    finally:
        async with factory() as session:
            await session.execute(delete(User).where(User.email == f"lifecycle-{marker}@test.edu"))
            await session.commit()
        await engine.dispose()


async def written(factory, marker: str) -> bool:
    async with factory() as session:
        found = await session.execute(
            select(User).where(User.email == f"lifecycle-{marker}@test.edu")
        )
        return found.scalar_one_or_none() is not None


class TestOneRequestOneTransaction:
    async def test_a_clean_request_commits(self, inspector):
        factory, marker = inspector

        generator = get_db()
        session = await anext(generator)
        session.add(build_user(marker))
        with pytest.raises(StopAsyncIteration):
            await anext(generator)

        assert await written(factory, marker) is True

    async def test_a_failed_request_writes_nothing(self, inspector):
        """This is what makes scoring atomic.

        A submission's score, its XP events, its badge and its achievement
        unlocks are written across four repositories in one request. If a
        failure after the third left the first three behind, a student would
        hold XP for a score that does not exist.
        """
        factory, marker = inspector

        generator = get_db()
        session = await anext(generator)
        session.add(build_user(marker))
        await session.flush()

        with pytest.raises(RuntimeError, match="scoring blew up"):
            await generator.athrow(RuntimeError("scoring blew up"))

        assert await written(factory, marker) is False

    async def test_the_connection_goes_back_to_the_pool_either_way(self, inspector):
        """A leaked checkout is invisible until the pool starves under load.

        Counted at the pool rather than asserted on the session: a session
        that was never closed still reports plausibly, while a connection it
        is holding does not come back.
        """
        _factory, marker = inspector

        generator = get_db()
        await anext(generator)
        with pytest.raises(StopAsyncIteration):
            await anext(generator)
        assert engine.pool.checkedout() == 0

        generator = get_db()
        session = await anext(generator)
        session.add(build_user(marker))
        await session.flush()
        with pytest.raises(RuntimeError):
            await generator.athrow(RuntimeError("boom"))
        assert engine.pool.checkedout() == 0


class TestStartup:
    """A dependency that is missing must produce a warning, never a dead server."""

    @pytest.fixture(autouse=True)
    def captured_logs(self, capsys):
        """Read the warnings from stdout, and hand the root logger back.

        Startup calls `configure_logging`, which clears the root handlers —
        pytest's own capture handler among them. That is why these assertions
        read stdout rather than `caplog`, and why the handlers are restored:
        without it every later test in the session would log into nothing.
        """
        import logging

        root = logging.getLogger()
        handlers, level = list(root.handlers), root.level
        yield lambda: capsys.readouterr().out
        root.handlers, root.level = handlers, level

    async def test_it_starts_with_no_ocr_provider_at_all(self, monkeypatch, captured_logs):
        """Typed answers are unaffected, so refusing to boot would help nobody."""
        from app import main

        monkeypatch.setattr(
            main, "get_ocr_chain", lambda: type("Chain", (), {"is_operational": False})()
        )
        monkeypatch.setattr(main, "warm_up_nlp", lambda: True)

        async with main.lifespan(main.app):
            pass

        assert "No OCR provider is available" in captured_logs()

    async def test_it_starts_with_no_language_model(self, monkeypatch, captured_logs):
        """Students can still sign in, read their history and write.

        The operator gets one actionable warning instead of every submission
        failing at 500 with no explanation.
        """
        from app import main

        monkeypatch.setattr(
            main,
            "get_ocr_chain",
            lambda: type("Chain", (), {"is_operational": True, "available_providers": []})(),
        )
        monkeypatch.setattr(main, "warm_up_nlp", lambda: False)

        async with main.lifespan(main.app):
            pass

        assert "analysis engine is unavailable" in captured_logs()

    async def test_available_providers_are_warmed_up(self, monkeypatch):
        """NFR-1.3's ten seconds cannot also absorb a model load."""
        from app import main

        warmed: list[str] = []

        class Provider:
            name = "easyocr"

            def warm_up(self) -> None:
                warmed.append(self.name)

        class Bare:
            """A provider with nothing to load — Tesseract has no warm-up."""

            name = "tesseract"

        monkeypatch.setattr(
            main,
            "get_ocr_chain",
            lambda: type(
                "Chain",
                (),
                {"is_operational": True, "available_providers": [Provider(), Bare()]},
            )(),
        )
        monkeypatch.setattr(main, "warm_up_nlp", lambda: True)

        async with main.lifespan(main.app):
            pass

        assert warmed == ["easyocr"]

    async def test_a_provider_that_fails_to_warm_up_does_not_stop_the_server(
        self, monkeypatch, captured_logs
    ):
        """Corrupt weights on disk are a reason to fall through, not to refuse traffic."""
        from app import main

        class Broken:
            name = "easyocr"

            def warm_up(self) -> None:
                raise RuntimeError("model file is truncated")

        monkeypatch.setattr(
            main,
            "get_ocr_chain",
            lambda: type(
                "Chain", (), {"is_operational": True, "available_providers": [Broken()]}
            )(),
        )
        monkeypatch.setattr(main, "warm_up_nlp", lambda: True)

        async with main.lifespan(main.app):
            pass

        assert "Could not warm up OCR provider easyocr" in captured_logs()
