"""Two readers finding the leaderboard stale at the same moment.

A rebuild is delete-then-insert, so without the advisory lock two of them
running together both clear the period and then collide on
``uq_leaderboard_entry`` — one reader gets a 500 for doing nothing worse than
loading a page at a busy moment. That failure only appears across real
connections, so like the submission race this runs on its own engine rather
than the rolled-back ``db`` fixture.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.security import hash_password
from app.gamification.periods import ALL_TIME_START, platform_today
from app.models.content import Graph
from app.models.enums import Gender, InputMethod, LeaderboardScope, SubmissionStatus, UserRole
from app.models.gamification import LeaderboardEntry, XPEvent
from app.models.identity import User
from app.models.submission import Score, Submission
from app.repositories.class_ import ClassRepository
from app.repositories.gamification import LeaderboardRepository
from app.services.leaderboard import LeaderboardService

pytestmark = pytest.mark.anyio


def build_service(session) -> LeaderboardService:
    return LeaderboardService(LeaderboardRepository(session), ClassRepository(session))


@pytest.fixture
async def committed_cohort() -> AsyncGenerator[list[uuid.UUID], None]:
    """Three students with genuinely committed XP and marked work."""
    engine = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    marker = uuid.uuid4().hex[:8]
    today = platform_today(get_settings().PLATFORM_TIMEZONE)
    ids: dict[str, list[uuid.UUID]] = {"users": [], "graphs": [], "submissions": []}

    try:
        async with factory() as session:
            teacher = User(
                email=f"lb-teacher-{marker}@test.edu",
                password_hash=hash_password("testpass123"),
                full_name="Board Teacher",
                role=UserRole.TEACHER.value,
                gender=Gender.FEMALE.value,
            )
            session.add(teacher)
            await session.flush()
            ids["users"].append(teacher.id)

            graph = Graph(
                title=f"Board graph {marker}",
                prompt="Describe this chart in at least 150 words.",
                graph_type="line",
                difficulty="beginner",
                chart_data={"labels": ["2023"], "datasets": [{"label": "x", "data": [1]}]},
                is_published=True,
                created_by=teacher.id,
            )
            session.add(graph)
            await session.flush()
            ids["graphs"].append(graph.id)

            for n in range(3):
                student = User(
                    email=f"lb-student-{marker}-{n}@test.edu",
                    password_hash=hash_password("testpass123"),
                    full_name=f"Board Student {n}",
                    role=UserRole.STUDENT.value,
                    gender=Gender.MALE.value,
                    total_xp=(n + 1) * 100,
                )
                session.add(student)
                await session.flush()
                ids["users"].append(student.id)

                submission = Submission(
                    user_id=student.id,
                    graph_id=graph.id,
                    input_method=InputMethod.TYPED.value,
                    answer_text="An answer.",
                    word_count=2,
                    status=SubmissionStatus.SCORED.value,
                    scored_at=func.now(),
                )
                session.add(submission)
                await session.flush()
                ids["submissions"].append(submission.id)

                session.add(
                    Score(
                        submission_id=submission.id,
                        vocabulary_score=70,
                        writing_score=70,
                        final_score=70,
                        vocabulary_percentage=70,
                        detected_terms=[],
                        missing_terms=[],
                        category_breakdown={},
                        writing_breakdown={},
                        reward_tier="flower",
                        feedback={},
                        engine_version="test-1",
                    )
                )
                session.add(
                    XPEvent(
                        user_id=student.id,
                        amount=(n + 1) * 100,
                        reason="submission",
                        event_date=today,
                        submission_id=submission.id,
                    )
                )
            await session.commit()

        yield ids["users"][1:]

    finally:
        async with factory() as session:
            await session.execute(
                delete(LeaderboardEntry).where(LeaderboardEntry.user_id.in_(ids["users"]))
            )
            await session.execute(delete(XPEvent).where(XPEvent.user_id.in_(ids["users"])))
            await session.execute(delete(Score).where(Score.submission_id.in_(ids["submissions"])))
            await session.execute(delete(Submission).where(Submission.id.in_(ids["submissions"])))
            await session.execute(delete(Graph).where(Graph.id.in_(ids["graphs"])))
            await session.execute(delete(User).where(User.id.in_(ids["users"])))
            await session.commit()
        await engine.dispose()


async def test_two_readers_rebuilding_at_once_produce_one_set_of_rankings(committed_cohort):
    student_ids = committed_cohort
    engine = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    async def read() -> int:
        async with factory() as session:
            viewer = await session.get(User, student_ids[0])
            service = build_service(session)
            _, total, _ = await service.page(
                scope=LeaderboardScope.GLOBAL,
                class_id=None,
                viewer=viewer,
                page=1,
                page_size=50,
            )
            await session.commit()
            return total

    try:
        # Both find the period unbuilt and both try to build it. The advisory
        # lock serialises them, and the second re-checks staleness once it has
        # the lock rather than rebuilding on top of the first.
        totals = await asyncio.gather(read(), read())

        async with factory() as session:
            rows = (
                await session.execute(
                    select(func.count())
                    .select_from(LeaderboardEntry)
                    .where(
                        LeaderboardEntry.scope == LeaderboardScope.GLOBAL.value,
                        LeaderboardEntry.period_start == ALL_TIME_START,
                        LeaderboardEntry.user_id.in_(student_ids),
                    )
                )
            ).scalar_one()
            ranks = (
                (
                    await session.execute(
                        select(LeaderboardEntry.rank)
                        .where(LeaderboardEntry.user_id.in_(student_ids))
                        .order_by(LeaderboardEntry.rank)
                    )
                )
                .scalars()
                .all()
            )
    finally:
        await engine.dispose()

    assert all(total >= 3 for total in totals)
    # One row per student, not two. A duplicated period would also mean the
    # same student appearing twice on the board.
    assert rows == 3
    assert len(set(ranks)) == 3
