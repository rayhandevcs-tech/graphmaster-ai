"""Two properties of the submission pipeline that only a real database shows.

Both are about transaction behaviour the ORM cannot be asked about in
isolation: one path deliberately commits inside a service, and the other
depends on PostgreSQL actually holding a row lock across two connections.

The race below cannot use the ``db`` fixture. That session is bound to a
connection whose transaction is already open, so its ``commit`` releases a
savepoint rather than publishing anything — which is exactly what keeps the
suite isolated, and exactly why a second connection would never see the row.
Everything here is therefore set up on its own engine and torn down by hand.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.exceptions import SubmissionAlreadyScoredError
from app.core.security import hash_password
from app.models.content import Graph, GraphTargetVocabulary, VocabularyItem
from app.models.enums import Gender, InputMethod, SubmissionStatus, UserRole
from app.models.gamification import UserAchievement, UserBadge, XPEvent
from app.models.identity import User
from app.models.submission import Score, Submission
from app.repositories.gamification import (
    AchievementRepository,
    BadgeRepository,
    XPRepository,
)
from app.repositories.graph import GraphRepository
from app.repositories.submission import SubmissionRepository
from app.repositories.user import UserRepository
from app.repositories.vocabulary import VocabularyItemRepository
from app.services.analysis import AnalysisService
from app.services.gamification import GamificationService
from app.services.graph import GraphService
from app.services.submission import SubmissionService

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("spacy_model")]

ANSWER = (
    "The line graph illustrates the amount of electricity generated from three "
    "renewable sources. Solar output rose steadily across the whole period, while "
    "hydroelectric generation remained stable and wind power fluctuated a little "
    "before reaching its peak in the final year shown."
)


def build_service(session: AsyncSession) -> SubmissionService:
    """Assemble the service by hand against an arbitrary session.

    The DI graph is request-scoped; these tests need it bound to a session
    whose transaction they control, so it is wired up directly. ``ocr`` is
    ``None`` because no path exercised here touches it.
    """
    graphs = GraphRepository(session)
    vocabulary = VocabularyItemRepository(session)
    submissions = SubmissionRepository(session)
    graph_service = GraphService(graphs, vocabulary)
    gamification = GamificationService(
        XPRepository(session),
        AchievementRepository(session),
        BadgeRepository(session),
        submissions,
        UserRepository(session),
    )
    return SubmissionService(
        submissions,
        graph_service,
        AnalysisService(graphs, vocabulary, graph_service),
        ocr=None,  # type: ignore[arg-type]
        gamification=gamification,
    )


# ── The deliberate commit ────────────────────────────────────────────────────


async def test_committing_inside_a_service_stays_inside_the_test_transaction(db, user_factory):
    """The upload path commits so a recognition failure survives the error that
    reports it. That must not cost the suite its per-test isolation.

    It does not, because the test session joins an already-open transaction and
    its commit releases a savepoint. If this ever regresses, every test after a
    failed upload starts seeing rows left behind by the one before it.
    """
    await user_factory(email="commit-probe@test.edu")
    await db.commit()

    engine = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    try:
        async with async_sessionmaker(bind=engine)() as outside:
            visible = (
                await outside.execute(
                    select(func.count())
                    .select_from(User)
                    .where(User.email == "commit-probe@test.edu")
                )
            ).scalar_one()
    finally:
        await engine.dispose()

    assert visible == 0, "a service commit escaped the test transaction"


# ── Exactly-once scoring ─────────────────────────────────────────────────────


@pytest.fixture
async def committed_attempt() -> AsyncGenerator[tuple[uuid.UUID, uuid.UUID], None]:
    """A student, a graph and a submission with text, genuinely committed."""
    from app.db.seed.runner import seed_vocabulary

    engine = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    marker = uuid.uuid4().hex[:8]
    ids: dict[str, uuid.UUID] = {}

    try:
        async with factory() as session:
            await seed_vocabulary(session)
            teacher = User(
                email=f"race-teacher-{marker}@test.edu",
                password_hash=hash_password("testpass123"),
                full_name="Race Teacher",
                role=UserRole.TEACHER.value,
                gender=Gender.FEMALE.value,
            )
            student = User(
                email=f"race-student-{marker}@test.edu",
                password_hash=hash_password("testpass123"),
                full_name="Race Student",
                role=UserRole.STUDENT.value,
                gender=Gender.MALE.value,
            )
            session.add_all([teacher, student])
            await session.flush()

            graph = Graph(
                title=f"Race graph {marker}",
                prompt="Describe this chart in at least 150 words.",
                graph_type="line",
                difficulty="beginner",
                chart_data={"labels": ["2023"], "datasets": [{"label": "x", "data": [1]}]},
                is_published=True,
                created_by=teacher.id,
            )
            session.add(graph)
            await session.flush()

            wanted = ("increase", "rise", "stable", "peak")
            items = (
                (
                    await session.execute(
                        select(VocabularyItem).where(VocabularyItem.lemma.in_(wanted))
                    )
                )
                .scalars()
                .all()
            )
            for item in items:
                session.add(
                    GraphTargetVocabulary(
                        graph_id=graph.id, vocabulary_item_id=item.id, is_required=True
                    )
                )
            await session.flush()

            service = build_service(session)
            submission = await service.start(
                graph_id=graph.id, input_method=InputMethod.TYPED, student=student
            )
            await service.set_text(submission.id, ANSWER, student=student)
            await session.commit()

            ids = {
                "student": student.id,
                "teacher": teacher.id,
                "graph": graph.id,
                "submission": submission.id,
            }

        yield ids["student"], ids["submission"]

    finally:
        if ids:
            async with factory() as session:
                # The gamification rows go first. `xp_events.user_id` is
                # ON DELETE RESTRICT — deliberately, so a ledger entry cannot be
                # orphaned — which means the users cannot be removed until the
                # XP they earned in the race has been.
                people = [ids["student"], ids["teacher"]]
                await session.execute(delete(XPEvent).where(XPEvent.user_id.in_(people)))
                await session.execute(delete(UserBadge).where(UserBadge.user_id.in_(people)))
                await session.execute(
                    delete(UserAchievement).where(UserAchievement.user_id.in_(people))
                )
                await session.execute(delete(Score).where(Score.submission_id == ids["submission"]))
                await session.execute(delete(Submission).where(Submission.id == ids["submission"]))
                await session.execute(
                    delete(GraphTargetVocabulary).where(
                        GraphTargetVocabulary.graph_id == ids["graph"]
                    )
                )
                await session.execute(delete(Graph).where(Graph.id == ids["graph"]))
                await session.execute(
                    delete(User).where(User.id.in_([ids["student"], ids["teacher"]]))
                )
                await session.commit()
        await engine.dispose()


async def test_two_racing_analyze_calls_produce_exactly_one_score(committed_attempt):
    """The row lock is what makes marking exactly-once.

    Without it both callers read a not-yet-scored row, both run the engine, and
    both insert a score — one dying on the unique constraint with a 500, and
    both paying out XP for one piece of work, which is a straightforward way to
    farm the leaderboard. So the XP ledger is asserted here too: one score and
    one award, from two simultaneous requests.
    """
    student_id, submission_id = committed_attempt
    engine = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    async def attempt() -> str:
        async with factory() as session:
            student = await session.get(User, student_id)
            service = build_service(session)
            try:
                await service.analyse(submission_id, student=student)
                await session.commit()
                return "scored"
            except SubmissionAlreadyScoredError:
                await session.rollback()
                return "refused"

    try:
        outcomes = await asyncio.gather(attempt(), attempt())

        async with factory() as session:
            scores = (
                await session.execute(
                    select(func.count())
                    .select_from(Score)
                    .where(Score.submission_id == submission_id)
                )
            ).scalar_one()
            status = (
                await session.execute(
                    select(Submission.status).where(Submission.id == submission_id)
                )
            ).scalar_one()
            awards = (
                await session.execute(
                    select(func.count())
                    .select_from(XPEvent)
                    .where(XPEvent.submission_id == submission_id)
                )
            ).scalar_one()
            paid = (
                await session.execute(
                    select(func.coalesce(func.sum(XPEvent.amount), 0)).where(
                        XPEvent.user_id == student_id
                    )
                )
            ).scalar_one()
    finally:
        await engine.dispose()

    assert sorted(outcomes) == ["refused", "scored"]
    assert scores == 1
    assert status == SubmissionStatus.SCORED.value
    # One submission's worth of XP, not two. The badge and achievement
    # catalogues are unseeded on this ad-hoc database, so the only awards are
    # the base 20 and — if the answer scored well — the 30-point bonus.
    assert awards >= 1
    assert paid in (20, 50)
