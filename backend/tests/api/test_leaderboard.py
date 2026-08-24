"""The four leaderboard scopes.

Rankings are materialised, so most of these assert what a *rebuild* produces
and who is allowed to ask for it. The ranking itself is a window function over
three aggregates, which is exactly the kind of query that is silently wrong
rather than loudly broken — so the tie-breakers and the participation filter
are asserted directly.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.models.enums import UserRole
from app.repositories.gamification import XPRepository

pytestmark = pytest.mark.anyio

LEADERBOARD = "/api/v1/leaderboard"


@pytest.fixture
async def teacher(user_factory, auth_headers):
    user = await user_factory(role=UserRole.TEACHER, email="teacher@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def admin(user_factory, auth_headers):
    user = await user_factory(role=UserRole.ADMIN, email="root@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def graph(graph_factory, teacher):
    user, _ = teacher
    return await graph_factory(created_by=user.id)


@pytest.fixture
def rank_student(db, user_factory, scored_submission_factory, graph):
    """A student with a given amount of period XP and some marked work."""
    counter = {"n": 0}

    async def make(
        *,
        xp: int,
        average_score: float = 70.0,
        submissions: int = 1,
        class_id=None,
        event_date: date | None = None,
        scored_at: datetime | None = None,
        name: str | None = None,
    ):
        counter["n"] += 1
        student = await user_factory(
            email=f"rank{counter['n']}@test.edu",
            full_name=name or f"Student {counter['n']}",
            class_id=class_id,
            total_xp=xp,
        )
        if xp:
            await XPRepository(db).record(
                user_id=student.id,
                amount=xp,
                reason="submission",
                event_date=event_date or datetime.now(UTC).date(),
            )
        for _ in range(submissions):
            await scored_submission_factory(
                user=student, graph=graph, final_score=average_score, scored_at=scored_at
            )
        return student

    return make


# ── Ranking ──────────────────────────────────────────────────────────────────


async def test_students_are_ranked_by_period_xp(client, rank_student, auth_headers):
    top = await rank_student(xp=500, name="Top")
    await rank_student(xp=300, name="Middle")
    await rank_student(xp=100, name="Bottom")

    body = (await client.get(LEADERBOARD, headers=auth_headers(top))).json()

    assert [e["full_name"] for e in body["entries"]] == ["Top", "Middle", "Bottom"]
    assert [e["rank"] for e in body["entries"]] == [1, 2, 3]


async def test_an_xp_tie_breaks_on_average_score(client, rank_student, auth_headers):
    """XP ties are common in a class of 40; an arbitrary order looks broken."""
    stronger = await rank_student(xp=200, average_score=88.0, name="Stronger")
    await rank_student(xp=200, average_score=61.0, name="Weaker")

    body = (await client.get(LEADERBOARD, headers=auth_headers(stronger))).json()

    assert [e["full_name"] for e in body["entries"]] == ["Stronger", "Weaker"]


async def test_a_student_who_has_not_practised_holds_no_rank(
    client, rank_student, user_factory, auth_headers
):
    """A board burying the few who worked under everyone who did not is useless."""
    ranked = await rank_student(xp=100)
    idle = await user_factory(email="idle@test.edu", full_name="Never Practised")

    body = (await client.get(LEADERBOARD, headers=auth_headers(ranked))).json()

    assert idle.full_name not in {e["full_name"] for e in body["entries"]}
    assert body["total"] == 1


async def test_teachers_and_admins_are_never_ranked(
    client, rank_student, teacher, scored_submission_factory, graph, db
):
    """A teacher checking an exercise must not appear above the class they mark."""
    staff, headers = teacher
    await XPRepository(db).record(
        user_id=staff.id, amount=9999, reason="submission", event_date=datetime.now(UTC).date()
    )
    await scored_submission_factory(user=staff, graph=graph, final_score=100.0)
    await rank_student(xp=10, name="Actual Student")

    body = (await client.get(LEADERBOARD, headers=headers)).json()

    assert [e["full_name"] for e in body["entries"]] == ["Actual Student"]


async def test_an_inactive_student_is_left_out(client, rank_student, auth_headers, db):
    ranked = await rank_student(xp=100, name="Active")
    gone = await rank_student(xp=900, name="Deactivated")
    gone.is_active = False
    await db.flush()

    body = (await client.get(LEADERBOARD, headers=auth_headers(ranked))).json()

    assert [e["full_name"] for e in body["entries"]] == ["Active"]


async def test_the_average_is_not_multiplied_by_the_ledger(client, rank_student, auth_headers):
    """Joining XP events and scores directly would average over their product."""
    student = await rank_student(xp=100, average_score=80.0, submissions=3)

    body = (await client.get(LEADERBOARD, headers=auth_headers(student))).json()
    entry = body["entries"][0]

    assert entry["average_score"] == 80.0
    assert entry["submission_count"] == 3
    assert entry["xp"] == 100


# ── Periods ──────────────────────────────────────────────────────────────────


async def test_the_weekly_board_ignores_xp_from_a_previous_week(client, rank_student, auth_headers):
    current = await rank_student(xp=50, name="This Week")
    await rank_student(
        xp=5000,
        name="Last Month",
        event_date=date.today() - timedelta(days=40),
        scored_at=datetime.now(UTC) - timedelta(days=40),
    )

    body = (await client.get(f"{LEADERBOARD}?scope=weekly", headers=auth_headers(current))).json()

    assert [e["full_name"] for e in body["entries"]] == ["This Week"]


async def test_the_global_board_counts_everything_ever(client, rank_student, auth_headers):
    recent = await rank_student(xp=50, name="Recent")
    await rank_student(
        xp=5000,
        name="Long Ago",
        event_date=date.today() - timedelta(days=400),
        scored_at=datetime.now(UTC) - timedelta(days=400),
    )

    body = (await client.get(f"{LEADERBOARD}?scope=global", headers=auth_headers(recent))).json()

    assert [e["full_name"] for e in body["entries"]] == ["Long Ago", "Recent"]


async def test_the_period_is_reported_alongside_the_rankings(client, rank_student, auth_headers):
    student = await rank_student(xp=10)

    body = (await client.get(f"{LEADERBOARD}?scope=monthly", headers=auth_headers(student))).json()

    assert body["period"]["scope"] == "monthly"
    assert body["period"]["period_start"] == date.today().replace(day=1).isoformat()
    assert body["period"]["generated_at"] is not None


# ── The caller's own position ────────────────────────────────────────────────


async def test_a_student_reads_their_own_rank_without_paging_to_find_it(
    client, rank_student, auth_headers
):
    for _ in range(5):
        await rank_student(xp=1000)
    me = await rank_student(xp=5, name="Me")

    body = (await client.get(f"{LEADERBOARD}/me", headers=auth_headers(me))).json()

    assert body["entry"]["rank"] == 6
    assert body["entry"]["is_you"]
    assert body["total_ranked"] == 6


async def test_a_student_with_no_activity_has_no_entry_rather_than_an_error(
    client, user_factory, auth_headers
):
    nobody = await user_factory(email="nobody@test.edu")

    response = await client.get(f"{LEADERBOARD}/me", headers=auth_headers(nobody))

    assert response.status_code == 200
    assert response.json()["entry"] is None


async def test_the_board_marks_which_row_is_the_caller(client, rank_student, auth_headers):
    me = await rank_student(xp=100, name="Me")
    await rank_student(xp=200, name="Someone Else")

    body = (await client.get(LEADERBOARD, headers=auth_headers(me))).json()

    assert [e["is_you"] for e in body["entries"]] == [False, True]


# ── Class scoping ────────────────────────────────────────────────────────────


async def test_a_student_sees_their_own_class_and_cannot_ask_for_another(
    client, rank_student, class_factory, teacher, auth_headers
):
    """A class board names identifiable classmates, so it is not browsable."""
    staff, _ = teacher
    mine = await class_factory(teacher_id=staff.id, code="MINE01")
    theirs = await class_factory(teacher_id=staff.id, code="THEM01")
    me = await rank_student(xp=100, class_id=mine.id, name="Classmate")
    await rank_student(xp=900, class_id=theirs.id, name="Stranger")

    body = (
        await client.get(
            f"{LEADERBOARD}?scope=class&class_id={theirs.id}", headers=auth_headers(me)
        )
    ).json()

    assert [e["full_name"] for e in body["entries"]] == ["Classmate"]
    assert body["period"]["class_id"] == str(mine.id)


async def test_an_unenrolled_student_is_told_why_there_is_no_class_board(
    client, user_factory, auth_headers
):
    loner = await user_factory(email="unenrolled@test.edu")

    response = await client.get(f"{LEADERBOARD}?scope=class", headers=auth_headers(loner))

    assert response.status_code == 422
    assert "class code" in response.json()["error"]["message"]


async def test_a_teacher_must_name_a_class(client, teacher):
    _, headers = teacher

    response = await client.get(f"{LEADERBOARD}?scope=class", headers=headers)

    assert response.status_code == 422


async def test_a_teacher_cannot_read_another_teacher_s_class_board(
    client, teacher, user_factory, class_factory, auth_headers
):
    other = await user_factory(role=UserRole.TEACHER, email="other-teacher@test.edu")
    theirs = await class_factory(teacher_id=other.id, code="OTHER1")
    _, headers = teacher

    response = await client.get(f"{LEADERBOARD}?scope=class&class_id={theirs.id}", headers=headers)

    assert response.status_code == 403


async def test_an_admin_may_read_any_class_board(
    client, admin, teacher, class_factory, rank_student
):
    staff, _ = teacher
    _, headers = admin
    cohort = await class_factory(teacher_id=staff.id, code="ADMIN1")
    await rank_student(xp=100, class_id=cohort.id, name="Enrolled")

    response = await client.get(f"{LEADERBOARD}?scope=class&class_id={cohort.id}", headers=headers)

    assert response.status_code == 200
    assert [e["full_name"] for e in response.json()["entries"]] == ["Enrolled"]


async def test_an_unknown_class_is_a_404(client, admin):
    import uuid

    _, headers = admin

    response = await client.get(
        f"{LEADERBOARD}?scope=class&class_id={uuid.uuid4()}", headers=headers
    )

    assert response.status_code == 404


# ── Refreshing ───────────────────────────────────────────────────────────────


async def test_a_forced_refresh_picks_up_new_activity(
    client, admin, rank_student, auth_headers, db
):
    """Rankings are cached, so new work needs either time or an explicit rebuild."""
    first = await rank_student(xp=100, name="First")
    _, admin_headers = admin
    await client.get(LEADERBOARD, headers=auth_headers(first))

    await rank_student(xp=900, name="Latecomer")
    refresh = await client.post(f"{LEADERBOARD}/refresh", headers=admin_headers)

    assert refresh.status_code == 200
    assert set(refresh.json()["rebuilt"]) == {"global", "weekly", "monthly", "class"}

    body = (await client.get(LEADERBOARD, headers=auth_headers(first))).json()
    assert [e["full_name"] for e in body["entries"]] == ["Latecomer", "First"]


async def test_a_refresh_covers_every_active_class_as_well_as_the_open_boards(
    client, admin, teacher, class_factory, rank_student, auth_headers
):
    staff, _ = teacher
    _, admin_headers = admin
    cohort = await class_factory(teacher_id=staff.id, code="REFR01")
    archived = await class_factory(teacher_id=staff.id, code="REFR02", is_active=False)
    enrolled = await rank_student(xp=100, class_id=cohort.id, name="Enrolled")
    await rank_student(xp=100, class_id=archived.id, name="Archived Cohort")

    rebuilt = (await client.post(f"{LEADERBOARD}/refresh", headers=admin_headers)).json()

    # One row from the active class. The archived one is skipped: its rankings
    # can no longer change, so rebuilding it is work whose result is on disk.
    assert rebuilt["rebuilt"]["class"] == 1
    body = (await client.get(f"{LEADERBOARD}?scope=class", headers=auth_headers(enrolled))).json()
    assert [e["full_name"] for e in body["entries"]] == ["Enrolled"]


async def test_a_reader_without_an_advisory_lock_still_gets_a_board(
    client, rank_student, auth_headers, monkeypatch
):
    """The fallback path for a backend with no advisory locks.

    The rebuild runs inside a savepoint there, so a lost race abandons it and
    serves what is stored rather than failing the request.
    """
    from app.repositories.gamification import LeaderboardRepository

    monkeypatch.setattr(
        LeaderboardRepository, "acquire_rebuild_lock", lambda self, **kwargs: _false()
    )
    student = await rank_student(xp=100, name="Unlocked")

    body = (await client.get(LEADERBOARD, headers=auth_headers(student))).json()

    assert [e["full_name"] for e in body["entries"]] == ["Unlocked"]


async def _false() -> bool:
    return False


async def test_rebuilding_replaces_a_period_rather_than_appending_to_it(
    client, admin, rank_student, auth_headers
):
    student = await rank_student(xp=100)
    _, admin_headers = admin

    for _ in range(3):
        await client.post(f"{LEADERBOARD}/refresh", headers=admin_headers)

    body = (await client.get(LEADERBOARD, headers=auth_headers(student))).json()

    assert body["total"] == 1


async def test_only_an_admin_may_force_a_rebuild(client, teacher):
    _, headers = teacher

    assert (await client.post(f"{LEADERBOARD}/refresh", headers=headers)).status_code == 403


async def test_the_board_requires_a_token(client):
    assert (await client.get(LEADERBOARD)).status_code == 401
