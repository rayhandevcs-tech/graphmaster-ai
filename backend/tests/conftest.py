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
async def seeded_gamification(db: AsyncSession):
    """The badge and achievement catalogues.

    Kept opt-in rather than autouse so the unseeded path stays exercised: a
    database without a badge catalogue must still mark a submission, and only a
    test that never seeds one can prove it.
    """
    from app.db.seed.runner import seed_achievements, seed_badges

    await seed_badges(db)
    await seed_achievements(db)
    return db


@pytest.fixture
async def seeded_vocabulary(db: AsyncSession):
    """The seven categories and the full term library.

    Returned as a lemma -> item mapping so a test can pick target terms by
    name instead of by position.
    """
    from app.db.seed.runner import seed_vocabulary

    await seed_vocabulary(db)

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.content import VocabularyItem

    # The category is eager-loaded: a test reading `item.category.code` off a
    # lazily loaded relationship gets a MissingGreenlet, because the async
    # driver cannot service a lazy load raised from synchronous attribute
    # access.
    rows = (
        (await db.execute(select(VocabularyItem).options(selectinload(VocabularyItem.category))))
        .scalars()
        .all()
    )
    return {item.lemma: item for item in rows}


@pytest.fixture
def chart_payload():
    """A minimal, valid Chart.js payload."""

    def make(**overrides) -> dict:
        base = {
            "labels": ["2023", "2024", "2025"],
            "datasets": [{"label": "Output (MWh)", "data": [120, 190, 260]}],
            "x_axis_label": "Year",
            "y_axis_label": "Output (MWh)",
        }
        return base | overrides

    return make


@pytest.fixture
def graph_factory(db: AsyncSession, chart_payload):
    """Build and persist a graph directly, bypassing the API."""
    from app.models.content import Graph, GraphTargetVocabulary

    counter = {"n": 0}

    async def make(
        *,
        created_by,
        title: str | None = None,
        graph_type: str = "line",
        difficulty: str = "beginner",
        is_published: bool = True,
        reference_description: str | None = "The line graph illustrates a steady rise.",
        targets: list = (),
        optional_targets: list = (),
    ) -> Graph:
        counter["n"] += 1
        graph = Graph(
            title=title or f"Test graph {counter['n']}",
            prompt="Describe this chart in at least 150 words.",
            graph_type=graph_type,
            difficulty=difficulty,
            chart_data=chart_payload(),
            reference_description=reference_description,
            is_published=is_published,
            created_by=created_by,
        )
        db.add(graph)
        await db.flush()
        for item in targets:
            db.add(
                GraphTargetVocabulary(
                    graph_id=graph.id, vocabulary_item_id=item.id, is_required=True
                )
            )
        for item in optional_targets:
            db.add(
                GraphTargetVocabulary(
                    graph_id=graph.id, vocabulary_item_id=item.id, is_required=False
                )
            )
        await db.flush()
        return graph

    return make


@pytest.fixture
def scored_submission_factory(db: AsyncSession):
    """Persist an already-marked submission and its score.

    Written directly rather than driven through the analysis endpoint: these
    tests are about what a *history* of scores earns, and building one through
    the real engine would mean a spaCy parse per attempt and would tie
    assertions about XP to whatever the rubric happens to award today.
    """
    from datetime import UTC, datetime

    from app.models.enums import InputMethod, SubmissionStatus
    from app.models.submission import Score, Submission

    async def make(
        *,
        user,
        graph,
        final_score: float = 75.0,
        vocabulary_percentage: float = 70.0,
        reward_tier: str = "flower",
        scored_at: datetime | None = None,
        detected_terms: list | None = None,
        word_count: int = 7,
    ) -> Submission:
        moment = scored_at or datetime.now(UTC)
        submission = Submission(
            user_id=user.id,
            graph_id=graph.id,
            input_method=InputMethod.TYPED.value,
            answer_text="A description written for a test.",
            word_count=word_count,
            status=SubmissionStatus.SCORED.value,
            submitted_at=moment,
            scored_at=moment,
        )
        db.add(submission)
        await db.flush()

        score = Score(
            submission_id=submission.id,
            vocabulary_score=vocabulary_percentage,
            writing_score=final_score,
            final_score=final_score,
            vocabulary_percentage=vocabulary_percentage,
            detected_count=3,
            unique_detected_count=3,
            total_target_count=5,
            detected_terms=detected_terms or [],
            missing_terms=[],
            category_breakdown={},
            writing_breakdown={},
            reward_tier=reward_tier,
            feedback={},
            engine_version="test-1",
        )
        db.add(score)
        await db.flush()
        return submission

    return make


@pytest.fixture
def class_factory(db: AsyncSession):
    """Build and persist a class directly."""
    from app.models.identity import Class

    counter = {"n": 0}

    async def make(
        *, teacher_id, name: str | None = None, code: str | None = None, is_active: bool = True
    ) -> Class:
        counter["n"] += 1
        class_ = Class(
            name=name or f"Test class {counter['n']}",
            code=code or f"TESTC{counter['n']:03d}",
            teacher_id=teacher_id,
            is_active=is_active,
        )
        db.add(class_)
        await db.flush()
        return class_

    return make


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


# ── Analysis engine ──────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def spacy_model():
    """Skip a test that needs the language model when it is not installed.

    Only the tests that genuinely parse text depend on this. Normalisation,
    inflection, the scoring arithmetic and the feedback templates are pure
    functions and run unconditionally, so a machine without the model still
    exercises most of the engine rather than reporting a green run that
    checked nothing.
    """
    from app.nlp.pipeline import is_available

    if not is_available():
        pytest.skip("spaCy model not installed — run: python -m spacy download en_core_web_sm")
    return True


@pytest.fixture
def term_factory():
    """Build :class:`TargetTerm` values without touching the database."""
    from app.nlp.terms import TargetTerm

    def make(
        term: str,
        lemma: str | None = None,
        *,
        category: str = "increase",
        category_name: str | None = None,
        is_phrase: bool | None = None,
        is_required: bool = True,
        weight: float = 1.0,
    ):
        return TargetTerm(
            term=term,
            lemma=lemma if lemma is not None else term,
            category_code=category,
            category_name=category_name or category.title(),
            is_phrase=(" " in term) if is_phrase is None else is_phrase,
            is_required=is_required,
            weight=weight,
        )

    return make


@pytest.fixture
def strong_answer() -> str:
    """A competent 165-word description using most of the target vocabulary."""
    return (
        "Overall, the line graph illustrates the amount of electricity generated from "
        "three renewable sources between 2010 and 2022. It is clear that solar generation "
        "grew far more quickly than the other two sources, while hydroelectric output "
        "remained stable throughout. In 2010 hydroelectric power was the dominant source "
        "at roughly 230 gigawatt hours, which was considerably higher than solar and wind "
        "combined. Over the following six years it fluctuated between 220 and 250 gigawatt "
        "hours, showing no clear trend. Solar generation, which began from a negligible "
        "base, climbed steadily after 2014 and then surged from 2018 onwards, reaching its "
        "highest point of approximately 410 gigawatt hours in 2022. Wind energy followed a "
        "similar but gentler trajectory, rising from 15 to about 90 gigawatt hours. "
        "Hydroelectric output bottomed out in 2016 before a modest increase. The most "
        "striking feature is the point in 2019 at which solar overtook hydroelectricity, "
        "whereas wind remained the smallest contributor throughout the period shown."
    )


@pytest.fixture
def weak_answer() -> str:
    """Three short sentences with almost no target vocabulary."""
    return "The graph go up. Then it go down a lot. Sales increase in 2015 and that is all."
