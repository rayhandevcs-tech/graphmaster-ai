"""Class, platform and vocabulary analytics, and the student's own dashboard.

The access rules matter as much as the arithmetic here: an export or a report
is the easiest place to hand a teacher another teacher's class, because nobody
reads a table of numbers the way they read a page.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.models.enums import UserRole

pytestmark = pytest.mark.anyio

ANALYTICS = "/api/v1/analytics"
DASHBOARD = "/api/v1/users/me/dashboard"


def terms(*pairs: tuple[str, int]) -> list[dict]:
    """`detected_terms` as the analysis engine writes it."""
    return [
        {
            "term": lemma,
            "lemma": lemma,
            "category": "increase",
            "category_name": "Increase",
            "is_required": True,
            "count": count,
            "matched_forms": [lemma],
            "positions": [[0, len(lemma)]],
        }
        for lemma, count in pairs
    ]


@pytest.fixture
async def teacher(user_factory, auth_headers):
    user = await user_factory(role=UserRole.TEACHER, email="teacher@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def admin(user_factory, auth_headers):
    user = await user_factory(role=UserRole.ADMIN, email="root@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def cohort(class_factory, teacher):
    user, _ = teacher
    return await class_factory(teacher_id=user.id, code="COHORT1")


@pytest.fixture
async def graph(graph_factory, teacher):
    user, _ = teacher
    return await graph_factory(created_by=user.id)


# ── Class analytics ──────────────────────────────────────────────────────────


async def test_a_class_report_averages_only_that_class(
    client, teacher, cohort, class_factory, graph, user_factory, scored_submission_factory
):
    _, headers = teacher
    staff, _ = teacher
    mine = await user_factory(email="mine@test.edu", class_id=cohort.id)
    other_class = await class_factory(teacher_id=staff.id, code="COHORT2")
    theirs = await user_factory(email="theirs@test.edu", class_id=other_class.id)
    await scored_submission_factory(user=mine, graph=graph, final_score=80.0)
    await scored_submission_factory(user=theirs, graph=graph, final_score=20.0)

    body = (await client.get(f"{ANALYTICS}/class/{cohort.id}", headers=headers)).json()

    assert body["submission_count"] == 1
    assert body["average_final_score"] == 80.0
    assert body["class_name"] == cohort.name


async def test_the_roster_includes_students_who_never_started(
    client, teacher, cohort, graph, user_factory, scored_submission_factory
):
    """A blank average and a zero are different statements about a student."""
    _, headers = teacher
    worked = await user_factory(email="worked@test.edu", class_id=cohort.id, full_name="Worked")
    await user_factory(email="idle@test.edu", class_id=cohort.id, full_name="Never Started")
    await scored_submission_factory(user=worked, graph=graph, final_score=70.0)

    body = (await client.get(f"{ANALYTICS}/class/{cohort.id}", headers=headers)).json()
    by_name = {row["full_name"]: row for row in body["students"]}

    assert by_name["Worked"]["average_final_score"] == 70.0
    assert by_name["Never Started"]["average_final_score"] is None
    assert by_name["Never Started"]["submission_count"] == 0


async def test_engagement_counts_the_ones_who_did_not_practise(
    client, teacher, cohort, graph, user_factory, scored_submission_factory
):
    """ "Half the class never started" is the number a teacher needs shown."""
    _, headers = teacher
    worked = await user_factory(email="a@test.edu", class_id=cohort.id)
    await user_factory(email="b@test.edu", class_id=cohort.id)
    await user_factory(email="c@test.edu", class_id=cohort.id)
    for _ in range(3):
        await scored_submission_factory(user=worked, graph=graph)

    engagement = (await client.get(f"{ANALYTICS}/class/{cohort.id}", headers=headers)).json()[
        "engagement"
    ]

    assert engagement["enrolled_student_count"] == 3
    assert engagement["active_student_count"] == 1
    assert engagement["inactive_student_count"] == 2
    assert engagement["participation_rate"] == pytest.approx(33.33, abs=0.01)
    # Per *active* student, so a keen student's three attempts are not diluted
    # across the two who never appeared.
    assert engagement["submissions_per_active_student"] == 3.0


async def test_the_tier_distribution_is_reported(
    client, teacher, cohort, graph, user_factory, scored_submission_factory
):
    _, headers = teacher
    student = await user_factory(email="tiers@test.edu", class_id=cohort.id)
    for tier in ("crown", "flower", "flower", "hammer"):
        await scored_submission_factory(user=student, graph=graph, reward_tier=tier)

    body = (await client.get(f"{ANALYTICS}/class/{cohort.id}", headers=headers)).json()

    assert body["reward_tier_distribution"] == {"crown": 1, "flower": 2, "hammer": 1}


async def test_a_teacher_cannot_read_another_teacher_s_class(
    client, teacher, user_factory, class_factory, auth_headers
):
    """Refused, not emptied — an empty report and a forbidden one look alike."""
    other = await user_factory(role=UserRole.TEACHER, email="other-teacher@test.edu")
    theirs = await class_factory(teacher_id=other.id, code="THEIRS1")
    _, headers = teacher

    response = await client.get(f"{ANALYTICS}/class/{theirs.id}", headers=headers)

    assert response.status_code == 403


async def test_an_admin_may_read_any_class(client, admin, cohort):
    _, headers = admin

    assert (await client.get(f"{ANALYTICS}/class/{cohort.id}", headers=headers)).status_code == 200


async def test_an_unknown_class_is_a_404(client, teacher):
    _, headers = teacher

    response = await client.get(f"{ANALYTICS}/class/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404


async def test_a_student_cannot_read_class_analytics(client, user_factory, auth_headers, cohort):
    student = await user_factory(email="curious@test.edu", class_id=cohort.id)

    response = await client.get(f"{ANALYTICS}/class/{cohort.id}", headers=auth_headers(student))

    assert response.status_code == 403


# ── Date windows ─────────────────────────────────────────────────────────────


async def test_a_date_window_excludes_work_outside_it(
    client, teacher, cohort, graph, user_factory, scored_submission_factory
):
    _, headers = teacher
    student = await user_factory(email="dated@test.edu", class_id=cohort.id)
    await scored_submission_factory(
        user=student, graph=graph, final_score=90.0, scored_at=datetime.now(UTC)
    )
    await scored_submission_factory(
        user=student,
        graph=graph,
        final_score=10.0,
        scored_at=datetime.now(UTC) - timedelta(days=40),
    )

    today = date.today().isoformat()
    body = (
        await client.get(
            f"{ANALYTICS}/class/{cohort.id}?date_from={today}&date_to={today}", headers=headers
        )
    ).json()

    assert body["submission_count"] == 1
    assert body["average_final_score"] == 90.0


async def test_a_backwards_date_range_is_refused(client, teacher, cohort):
    _, headers = teacher

    response = await client.get(
        f"{ANALYTICS}/class/{cohort.id}?date_from=2026-08-20&date_to=2026-08-01", headers=headers
    )

    assert response.status_code == 422


# ── Vocabulary usage ─────────────────────────────────────────────────────────


async def test_vocabulary_usage_counts_what_the_engine_matched(
    client, teacher, cohort, graph, user_factory, scored_submission_factory, seeded_vocabulary
):
    _, headers = teacher
    student = await user_factory(email="vocab@test.edu", class_id=cohort.id)
    await scored_submission_factory(
        user=student, graph=graph, detected_terms=terms(("rise", 3), ("climb", 1))
    )
    await scored_submission_factory(user=student, graph=graph, detected_terms=terms(("rise", 2)))

    body = (
        await client.get(f"{ANALYTICS}/vocabulary-usage?class_id={cohort.id}", headers=headers)
    ).json()
    by_term = {row["lemma"]: row for row in body["most_used"]}

    assert by_term["rise"]["uses"] == 5
    assert by_term["rise"]["submission_count"] == 2
    assert by_term["climb"]["uses"] == 1


async def test_least_used_surfaces_terms_nobody_touched(
    client, teacher, cohort, graph, user_factory, scored_submission_factory, seeded_vocabulary
):
    """The interesting answer, and invisible to any count of what was written."""
    _, headers = teacher
    student = await user_factory(email="vocab2@test.edu", class_id=cohort.id)
    await scored_submission_factory(user=student, graph=graph, detected_terms=terms(("rise", 3)))

    body = (
        await client.get(f"{ANALYTICS}/vocabulary-usage?class_id={cohort.id}", headers=headers)
    ).json()

    assert body["used_term_count"] == 1
    assert body["unused_term_count"] == body["term_count"] - 1
    assert body["least_used"][0]["uses"] == 0
    assert "rise" not in {row["lemma"] for row in body["least_used"]}


async def test_vocabulary_usage_is_scoped_to_the_named_class(
    client,
    teacher,
    cohort,
    class_factory,
    graph,
    user_factory,
    scored_submission_factory,
    seeded_vocabulary,
):
    staff, headers = teacher
    other_class = await class_factory(teacher_id=staff.id, code="VOCAB2")
    mine = await user_factory(email="v-mine@test.edu", class_id=cohort.id)
    theirs = await user_factory(email="v-theirs@test.edu", class_id=other_class.id)
    await scored_submission_factory(user=mine, graph=graph, detected_terms=terms(("rise", 1)))
    await scored_submission_factory(user=theirs, graph=graph, detected_terms=terms(("fall", 9)))

    body = (
        await client.get(f"{ANALYTICS}/vocabulary-usage?class_id={cohort.id}", headers=headers)
    ).json()

    assert {row["lemma"] for row in body["most_used"]} == {"rise"}


async def test_vocabulary_usage_for_another_teacher_s_class_is_refused(
    client, teacher, user_factory, class_factory, seeded_vocabulary
):
    other = await user_factory(role=UserRole.TEACHER, email="v-other@test.edu")
    theirs = await class_factory(teacher_id=other.id, code="VOCAB3")
    _, headers = teacher

    response = await client.get(
        f"{ANALYTICS}/vocabulary-usage?class_id={theirs.id}", headers=headers
    )

    assert response.status_code == 403


# ── Trends ───────────────────────────────────────────────────────────────────


async def test_the_trend_has_one_point_per_day_with_work(
    client, teacher, cohort, graph, user_factory, scored_submission_factory
):
    """A gap is a day nobody practised, not a day everyone scored zero."""
    _, headers = teacher
    student = await user_factory(email="trend@test.edu", class_id=cohort.id)
    now = datetime.now(UTC)
    await scored_submission_factory(user=student, graph=graph, final_score=60.0, scored_at=now)
    await scored_submission_factory(
        user=student, graph=graph, final_score=90.0, scored_at=now - timedelta(days=2)
    )

    body = (await client.get(f"{ANALYTICS}/trends?class_id={cohort.id}", headers=headers)).json()

    assert len(body["points"]) == 2
    assert body["points"][0]["average_final_score"] == 90.0
    assert body["points"][-1]["average_final_score"] == 60.0


async def test_a_weekly_trend_collapses_the_days_into_one_point(
    client, teacher, cohort, graph, user_factory, scored_submission_factory
):
    _, headers = teacher
    student = await user_factory(email="weekly@test.edu", class_id=cohort.id)
    # Both anchored to a known Monday, so the pair cannot straddle a week
    # boundary depending on when the suite happens to run.
    monday = datetime(2026, 8, 24, 9, tzinfo=UTC)
    await scored_submission_factory(user=student, graph=graph, final_score=60.0, scored_at=monday)
    await scored_submission_factory(
        user=student, graph=graph, final_score=80.0, scored_at=monday + timedelta(days=2)
    )

    body = (
        await client.get(
            f"{ANALYTICS}/trends?class_id={cohort.id}&granularity=week", headers=headers
        )
    ).json()

    assert len(body["points"]) == 1
    assert body["points"][0]["average_final_score"] == 70.0


async def test_an_unknown_granularity_is_refused(client, teacher, cohort):
    _, headers = teacher

    response = await client.get(
        f"{ANALYTICS}/trends?class_id={cohort.id}&granularity=fortnight", headers=headers
    )

    assert response.status_code == 422


# ── Platform ─────────────────────────────────────────────────────────────────


async def test_platform_analytics_span_every_class(
    client, admin, cohort, class_factory, teacher, graph, user_factory, scored_submission_factory
):
    staff, _ = teacher
    _, headers = admin
    other_class = await class_factory(teacher_id=staff.id, code="PLAT2")
    a = await user_factory(email="p-a@test.edu", class_id=cohort.id)
    b = await user_factory(email="p-b@test.edu", class_id=other_class.id)
    await scored_submission_factory(user=a, graph=graph, final_score=60.0)
    await scored_submission_factory(user=b, graph=graph, final_score=80.0)

    body = (await client.get(f"{ANALYTICS}/platform", headers=headers)).json()

    assert body["submission_count"] == 2
    assert body["average_final_score"] == 70.0
    # No single roster to list, and enumerating every student on the
    # installation would be a different and much larger response.
    assert body["students"] == []


async def test_a_teacher_cannot_read_platform_analytics(client, teacher):
    _, headers = teacher

    assert (await client.get(f"{ANALYTICS}/platform", headers=headers)).status_code == 403


# ── The student's dashboard ──────────────────────────────────────────────────


async def test_the_dashboard_reports_the_student_s_own_totals(
    client, user_factory, auth_headers, graph, scored_submission_factory, seeded_gamification
):
    student = await user_factory(email="dash@test.edu", total_xp=350, current_level=4)
    await scored_submission_factory(user=student, graph=graph, final_score=60.0)
    await scored_submission_factory(user=student, graph=graph, final_score=90.0)

    body = (await client.get(DASHBOARD, headers=auth_headers(student))).json()

    assert body["total_attempts"] == 2
    assert body["average_score"] == 75.0
    assert body["highest_score"] == 90.0
    assert body["total_xp"] == 350
    assert body["current_level"] == 4


async def test_the_dashboard_never_shows_another_student_s_work(
    client, user_factory, auth_headers, graph, scored_submission_factory, seeded_gamification
):
    mine = await user_factory(email="d-mine@test.edu")
    theirs = await user_factory(email="d-theirs@test.edu")
    await scored_submission_factory(user=theirs, graph=graph, final_score=99.0)

    body = (await client.get(DASHBOARD, headers=auth_headers(mine))).json()

    assert body["total_attempts"] == 0
    assert body["recent_activity"] == []


async def test_the_dashboard_carries_recent_activity_newest_first(
    client,
    user_factory,
    auth_headers,
    graph_factory,
    scored_submission_factory,
    seeded_gamification,
    teacher,
):
    staff, _ = teacher
    student = await user_factory(email="recent@test.edu")
    now = datetime.now(UTC)
    for offset, title in ((2, "Older"), (0, "Newest")):
        graph = await graph_factory(created_by=staff.id, title=title)
        await scored_submission_factory(
            user=student, graph=graph, scored_at=now - timedelta(hours=offset)
        )

    body = (await client.get(DASHBOARD, headers=auth_headers(student))).json()

    assert [row["graph_title"] for row in body["recent_activity"]] == ["Newest", "Older"]


async def test_the_dashboard_lists_only_unlocked_achievements(
    client, user_factory, auth_headers, db, seeded_gamification
):
    """The locked catalogue with its progress lives on /gamification/achievements."""
    from sqlalchemy import select

    from app.models.gamification import Achievement, UserAchievement

    student = await user_factory(email="unlocked@test.edu")
    first = (
        await db.execute(select(Achievement).where(Achievement.code == "first_submission"))
    ).scalar_one()
    db.add(UserAchievement(user_id=student.id, achievement_id=first.id))
    await db.flush()

    body = (await client.get(DASHBOARD, headers=auth_headers(student))).json()

    assert [row["code"] for row in body["achievements"]] == ["first_submission"]
    assert all(row["is_unlocked"] for row in body["achievements"])


async def test_a_teacher_has_no_dashboard(client, teacher):
    """It answers a question about yourself; staff have /analytics instead."""
    _, headers = teacher

    assert (await client.get(DASHBOARD, headers=headers)).status_code == 403


async def test_the_dashboard_requires_a_token(client):
    assert (await client.get(DASHBOARD)).status_code == 401
