"""The performance budgets in the SRS, measured rather than asserted on paper.

NFR-1.1 and NFR-1.2 are numbers a reader can check, and a number nobody
measures is a number that quietly stops being true. These are marked `perf`
and deselected from the default run — they are the only tests here whose
result depends on the machine, and a developer running the suite on a laptop
with a build going should not get a red run because of it.

    make perf          # or: pytest -m perf

On a shared CI runner the measurement is indicative, not authoritative: the
job that runs them there is advisory for exactly that reason.
"""

from __future__ import annotations

import asyncio
import statistics
import time
import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.session import engine as app_engine
from app.main import app as fastapi_app
from app.models.content import Graph
from app.models.enums import Gender, UserRole
from app.models.identity import User

pytestmark = [pytest.mark.anyio, pytest.mark.perf]

# NFR-1.1: non-OCR API responses within 500 ms at the 95th percentile under a
# load of 50 concurrent users.
#
# That figure describes a *deployment*: several uvicorn workers across several
# cores behind a proxy. This harness runs one worker in one event loop, and
# the client shares its core, so fifty simultaneous callers queue behind each
# other by construction — the number it would produce says more about the
# runner's core count than about the code. What it can measure exactly, and
# what a regression actually shows up in, is service time: how long one
# request occupies the server. So the budget is asserted per request, and the
# concurrent run asserts that fifty callers are all served and that the
# per-request cost does not inflate under contention.
CONCURRENT_USERS = 50
LATENCY_BUDGET_MS = 500.0

# Ten minutes of headroom against the observed ~20 ms, and tight enough that
# an N+1 query or a dropped index — the regressions NFR-1.1 exists to catch —
# takes it over.
SERVICE_TIME_BUDGET_MS = 100.0

# NFR-1.2: analysis of a 300-word response within 2 seconds.
ANALYSIS_BUDGET_S = 2.0


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(int(len(ordered) * fraction), len(ordered) - 1)
    return ordered[index]


def report(name: str, samples: list[float]) -> str:
    return (
        f"{name}: n={len(samples)} "
        f"min={min(samples):.1f}ms median={statistics.median(samples):.1f}ms "
        f"p95={percentile(samples, 0.95):.1f}ms max={max(samples):.1f}ms"
    )


@pytest.fixture(autouse=True)
async def fresh_engine_pool():
    """The process-wide engine pools connections across event loops.

    Each test gets its own loop, so a pooled connection from the previous one
    belongs to a loop that has stopped. Disposing with ``close=False``
    abandons them rather than closing them from the wrong loop.
    """
    await app_engine.dispose(close=False)
    yield
    await app_engine.dispose(close=False)


@pytest.fixture
async def committed_student(database_schema) -> AsyncGenerator[tuple[dict, str], None]:
    """A real student and a published graph, committed for other connections to read.

    The load test deliberately does not use the rolled-back ``db`` fixture:
    fifty concurrent requests through one shared session would serialise on
    it, and would measure the fixture rather than the application.
    """
    engine = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    marker = uuid.uuid4().hex[:8]

    async with factory() as session:
        teacher = User(
            email=f"perf-teacher-{marker}@test.edu",
            password_hash=hash_password("testpass123"),
            full_name="Perf Teacher",
            role=UserRole.TEACHER.value,
            gender=Gender.MALE.value,
        )
        student = User(
            email=f"perf-student-{marker}@test.edu",
            password_hash=hash_password("testpass123"),
            full_name="Perf Student",
            role=UserRole.STUDENT.value,
            gender=Gender.FEMALE.value,
        )
        session.add_all([teacher, student])
        await session.flush()

        session.add(
            Graph(
                title=f"Perf graph {marker}",
                prompt="Describe this chart in at least 150 words.",
                graph_type="line",
                difficulty="beginner",
                chart_data={"labels": ["2023"], "datasets": [{"label": "x", "data": [1]}]},
                is_published=True,
                created_by=teacher.id,
            )
        )
        await session.commit()
        headers = {
            "Authorization": "Bearer "
            + create_access_token(student.id, role=student.role, gender=student.gender)
        }
        ids = [teacher.id, student.id]

    try:
        yield headers, marker
    finally:
        async with factory() as session:
            await session.execute(delete(Graph).where(Graph.title == f"Perf graph {marker}"))
            await session.execute(delete(User).where(User.id.in_(ids)))
            await session.commit()
        await engine.dispose()


async def measure_sequential(path: str, headers: dict, *, requests: int = 30) -> list[float]:
    """One request at a time: the latency a single user actually sees."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        async def once() -> float:
            started = time.perf_counter()
            response = await client.get(path, headers=headers)
            elapsed = (time.perf_counter() - started) * 1000
            assert response.status_code == 200, response.text
            return elapsed

        # Warm the pool and the route's first-call costs, so what follows
        # measures steady state rather than process start.
        await once()
        return [await once() for _ in range(requests)]


async def measure_concurrent(path: str, headers: dict, *, users: int) -> tuple[float, int]:
    """Fire `users` requests at once; return the wall time in ms and how many succeeded."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # A full burst first, discarded. The pool opens a connection per
        # waiting caller on the first burst, and counting thirty TCP
        # handshakes would measure the pool warming up rather than the
        # application serving.
        await asyncio.gather(*(client.get(path, headers=headers) for _ in range(users)))

        started = time.perf_counter()
        responses = await asyncio.gather(*(client.get(path, headers=headers) for _ in range(users)))
        wall = (time.perf_counter() - started) * 1000
        return wall, sum(r.status_code == 200 for r in responses)


class TestApiLatency:
    @pytest.mark.parametrize(
        "path",
        [
            # The first call every authenticated page makes: a single row and
            # its eager-loaded avatar.
            "/api/v1/users/me",
            # A list with a join, a filter and pagination — where an N+1 shows.
            "/api/v1/graphs",
        ],
    )
    async def test_a_read_is_well_inside_the_budget(self, committed_student, path):
        """NFR-1.1's 500 ms, asserted where it is measurable: one request at a time."""
        headers, _ = committed_student
        samples = await measure_sequential(path, headers)
        assert percentile(samples, 0.95) < LATENCY_BUDGET_MS, report(f"GET {path}", samples)

    async def test_fifty_callers_are_all_served(self, committed_student):
        """Nothing is dropped when the pool holds fewer connections than callers.

        DB_POOL_SIZE is 10 with 20 of overflow, so fifty simultaneous requests
        genuinely queue. Queuing is fine; failing, or holding a connection
        that never comes back, is not.

        The service-time budget is measured under that contention on purpose:
        a per-request cost that climbs when callers queue is the signature of
        a lock held across I/O, which looks perfect in every single-user test
        and falls over on a lab full of students. Alone a request costs about
        6 ms and under fifty concurrent callers about 20 ms, most of the
        difference being the client sharing this process's event loop.
        """
        headers, _ = committed_student
        wall, served = await measure_concurrent("/api/v1/users/me", headers, users=CONCURRENT_USERS)
        assert served == CONCURRENT_USERS

        service_time = wall / CONCURRENT_USERS
        assert service_time < SERVICE_TIME_BUDGET_MS, (
            f"{CONCURRENT_USERS} concurrent requests took {wall:.0f}ms "
            f"({service_time:.1f}ms of server time each)"
        )


class TestAnalysisLatency:
    @pytest.fixture
    def three_hundred_words(self) -> str:
        """A realistic answer, not 300 repetitions of one word.

        Repetition would let the pipeline's caches answer a question the real
        workload never asks.
        """
        sentences = [
            "The line graph illustrates the amount of electricity generated by "
            "three renewable sources between 2010 and 2024.",
            "Overall, output from solar power increased dramatically over the "
            "period, whereas hydroelectric generation remained relatively stable.",
            "In 2010, hydroelectric power accounted for the largest share, at "
            "approximately 320 terawatt hours.",
            "Solar generation, by contrast, stood at just under 40 terawatt "
            "hours, the lowest figure of the three.",
            "Between 2010 and 2016, solar output rose steadily, reaching a peak "
            "of around 180 terawatt hours.",
            "This upward trend accelerated sharply after 2018, when generation "
            "surged to nearly 400 terawatt hours.",
            "Wind power followed a similar pattern, although the rise was more "
            "gradual and fluctuated between 2014 and 2019.",
            "Hydroelectric generation, meanwhile, plateaued at roughly 340 "
            "terawatt hours and showed only a slight decline thereafter.",
            "There was a marked drop in wind generation in 2020, followed by a "
            "rapid recovery the following year.",
            "By the end of the period, solar had overtaken both other sources "
            "and stood at well over 500 terawatt hours.",
        ]
        text = " ".join(sentences)
        while len(text.split()) < 300:
            text = text + " " + " ".join(sentences)
        return " ".join(text.split()[:300])

    async def test_a_three_hundred_word_answer_is_analysed_within_two_seconds(
        self, spacy_model, seeded_vocabulary, three_hundred_words
    ):
        """NFR-1.2. A student watches this one happen."""
        from app.nlp.analyzer import analyse
        from app.nlp.terms import TargetTerm

        targets = [
            TargetTerm(
                term=item.term,
                lemma=item.lemma,
                category_code=item.category.code,
                category_name=item.category.name,
                is_phrase=bool(item.is_phrase),
                is_required=True,
                weight=float(item.weight),
            )
            for item in list(seeded_vocabulary.values())[:12]
        ]

        assert len(three_hundred_words.split()) == 300

        # Warmed the way a running server is: `main.py` calls this during
        # startup, so a budget measured without it describes a process that has
        # just booted rather than one serving students.
        #
        # It is not, on its own, what makes this pass. The measurement was six
        # seconds until the spelling analyzer stopped asking the dictionary the
        # same question once per *occurrence* of a word — an answer about
        # terawatt hours contains "terawatt" a dozen times, and each one paid
        # the full half-second edit-distance-2 expansion. See `_correction`.
        from app.assessment.registry import warm_up as warm_up_assessment

        warm_up_assessment()
        analyse("A short warm-up sentence about a rising trend.", targets)

        started = time.perf_counter()
        result = analyse(three_hundred_words, targets)
        elapsed = time.perf_counter() - started

        assert result.score.final_score >= 0
        assert elapsed < ANALYSIS_BUDGET_S, f"analysis took {elapsed:.2f}s"
