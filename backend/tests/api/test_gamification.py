"""XP, level, achievement and badge endpoints.

Nothing here awards anything — awarding happens only while a submission is
being marked. These are about what a student can read back, and about the one
administrative path that may write.
"""

from __future__ import annotations

import pytest

from app.models.enums import Gender, UserRole

pytestmark = pytest.mark.anyio

GAMIFICATION = "/api/v1/gamification"


@pytest.fixture
async def student(user_factory, auth_headers):
    user = await user_factory(role=UserRole.STUDENT, email="learner@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def admin(user_factory, auth_headers):
    user = await user_factory(role=UserRole.ADMIN, email="root@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def teacher(user_factory, auth_headers):
    user = await user_factory(role=UserRole.TEACHER, email="staff@test.edu")
    return user, auth_headers(user)


# ── Level ────────────────────────────────────────────────────────────────────


async def test_a_new_student_starts_at_level_one_with_nothing_earned(client, student):
    _, headers = student

    body = (await client.get(f"{GAMIFICATION}/level", headers=headers)).json()

    assert body["current_level"] == 1
    assert body["total_xp"] == 0
    assert body["xp_into_level"] == 0
    assert body["xp_for_next_level"] == 50
    assert not body["is_max_level"]


async def test_the_level_follows_the_curve_from_total_xp(client, user_factory, auth_headers, db):
    """Level 5 costs 500 XP; 499 is still level 4."""
    user = await user_factory(email="nearly@test.edu", total_xp=499, current_level=4)

    body = (await client.get(f"{GAMIFICATION}/level", headers=auth_headers(user))).json()

    assert body["current_level"] == 4
    assert body["xp_into_level"] == 499 - 300
    assert body["xp_for_next_level"] == 500 - 300


async def test_the_level_endpoint_carries_the_streak_for_the_dashboard(
    client, user_factory, auth_headers, db
):
    user = await user_factory(email="streaky@test.edu")
    user.current_streak_days = 6
    user.longest_streak_days = 11
    await db.flush()

    body = (await client.get(f"{GAMIFICATION}/level", headers=auth_headers(user))).json()

    assert body["current_streak_days"] == 6
    assert body["longest_streak_days"] == 11


async def test_reading_a_level_requires_a_token(client):
    assert (await client.get(f"{GAMIFICATION}/level")).status_code == 401


# ── XP history ───────────────────────────────────────────────────────────────


async def test_the_ledger_reads_back_in_the_order_it_was_written(client, student, db):
    """Including entries appended within one transaction.

    Scoring appends up to four in a single request. `created_at` defaults to
    `clock_timestamp()` rather than `now()` for exactly this reason: `now()` is
    the transaction timestamp, so all four would share one value and the order
    would fall back to a random UUID.
    """
    from datetime import date

    from app.repositories.gamification import XPRepository

    user, headers = student
    xp = XPRepository(db)
    written = ["submission", "high_score_bonus", "streak_bonus", "achievement"]
    for reason in written:
        await xp.record(user_id=user.id, amount=10, reason=reason, event_date=date(2026, 8, 24))

    body = (await client.get(f"{GAMIFICATION}/xp-history", headers=headers)).json()

    assert body["total"] == 4
    assert [item["reason"] for item in body["items"]] == list(reversed(written))


async def test_a_student_never_sees_another_student_s_ledger(
    client, student, user_factory, auth_headers, db
):
    from datetime import date

    from app.repositories.gamification import XPRepository

    user, _ = student
    other = await user_factory(email="someone-else@test.edu")
    await XPRepository(db).record(
        user_id=user.id, amount=20, reason="submission", event_date=date(2026, 8, 24)
    )

    body = (await client.get(f"{GAMIFICATION}/xp-history", headers=auth_headers(other))).json()

    # There is no `user_id` parameter to abuse — the ledger endpoint is scoped
    # to the caller and nothing else.
    assert body["total"] == 0


# ── Achievements ─────────────────────────────────────────────────────────────


async def test_the_catalogue_shows_progress_towards_locked_achievements(
    client, student, seeded_gamification
):
    _, headers = student

    rows = (await client.get(f"{GAMIFICATION}/achievements", headers=headers)).json()
    by_code = {row["code"]: row for row in rows}

    assert not by_code["ten_submissions"]["is_unlocked"]
    assert by_code["ten_submissions"]["progress"] == 0
    assert by_code["ten_submissions"]["target"] == 10


async def test_progress_tracks_real_history(
    client, student, graph_factory, user_factory, scored_submission_factory, seeded_gamification
):
    user, headers = student
    teacher = await user_factory(role=UserRole.TEACHER, email="author@test.edu")
    graph = await graph_factory(created_by=teacher.id)
    for _ in range(4):
        await scored_submission_factory(user=user, graph=graph)

    rows = (await client.get(f"{GAMIFICATION}/achievements", headers=headers)).json()
    by_code = {row["code"]: row for row in rows}

    assert by_code["ten_submissions"]["progress"] == 4
    assert by_code["ten_submissions"]["progress_percent"] == 40.0


async def test_a_student_is_offered_exactly_one_crown_achievement(
    client, user_factory, auth_headers, seeded_gamification
):
    """Graph King for a male student, Graph Queen for a female one — never both.

    The unreachable one is absent rather than shown locked: displaying a goal a
    student can never meet misrepresents how much of the catalogue is open to
    them.
    """
    she = await user_factory(gender=Gender.FEMALE, email="her@test.edu")
    he = await user_factory(gender=Gender.MALE, email="him@test.edu")

    hers = {
        row["code"]
        for row in (
            await client.get(f"{GAMIFICATION}/achievements", headers=auth_headers(she))
        ).json()
    }
    his = {
        row["code"]
        for row in (
            await client.get(f"{GAMIFICATION}/achievements", headers=auth_headers(he))
        ).json()
    }

    assert "graph_queen" in hers and "graph_king" not in hers
    assert "graph_king" in his and "graph_queen" not in his


async def test_an_unlocked_achievement_stays_complete_after_its_statistic_falls(
    client, student, db, seeded_gamification
):
    """A broken streak does not un-earn Consistency Champion."""
    from sqlalchemy import select

    from app.models.gamification import Achievement, UserAchievement

    user, headers = student
    champion = (
        await db.execute(select(Achievement).where(Achievement.code == "consistency_champion"))
    ).scalar_one()
    db.add(UserAchievement(user_id=user.id, achievement_id=champion.id))
    user.current_streak_days = 0
    await db.flush()

    rows = (await client.get(f"{GAMIFICATION}/achievements", headers=headers)).json()
    row = next(r for r in rows if r["code"] == "consistency_champion")

    assert row["is_unlocked"]
    assert row["progress_percent"] == 100.0


# ── Badges ───────────────────────────────────────────────────────────────────


async def test_badges_are_listed_with_a_tally_not_a_flag(
    client,
    student,
    graph_factory,
    user_factory,
    scored_submission_factory,
    seeded_gamification,
    db,
):
    from app.repositories.gamification import BadgeRepository

    user, headers = student
    teacher = await user_factory(role=UserRole.TEACHER, email="author2@test.edu")
    graph = await graph_factory(created_by=teacher.id)
    badges = BadgeRepository(db)
    flower = await badges.for_tier("flower")
    for _ in range(2):
        submission = await scored_submission_factory(user=user, graph=graph)
        await badges.award(user_id=user.id, badge_id=flower.id, submission_id=submission.id)

    rows = (await client.get(f"{GAMIFICATION}/badges", headers=headers)).json()
    by_tier = {row["reward_tier"]: row for row in rows}

    assert by_tier["flower"]["earned_count"] == 2
    assert by_tier["crown"]["earned_count"] == 0
    # All four tiers are always listed, so the client can render the full set
    # with the unearned ones dimmed rather than missing.
    assert set(by_tier) == {"crown", "flower", "steady", "hammer"}


# ── Administrative corrections ───────────────────────────────────────────────


async def test_an_admin_can_offset_an_over_award(client, admin, user_factory, db):
    _, headers = admin
    student = await user_factory(email="overpaid@test.edu", total_xp=200, current_level=2)
    from datetime import date

    from app.repositories.gamification import XPRepository

    await XPRepository(db).record(
        user_id=student.id, amount=200, reason="submission", event_date=date(2026, 8, 24)
    )

    response = await client.post(
        f"{GAMIFICATION}/adjustments",
        headers=headers,
        json={"user_id": str(student.id), "amount": -50, "note": "Duplicate award"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["amount"] == -50
    assert body["reason"] == "manual_adjustment"
    assert body["note"] == "Duplicate award"
    assert student.total_xp == 150


async def test_an_adjustment_without_a_reason_is_refused(client, admin, user_factory):
    _, headers = admin
    student = await user_factory(email="target@test.edu")

    response = await client.post(
        f"{GAMIFICATION}/adjustments",
        headers=headers,
        json={"user_id": str(student.id), "amount": -10, "note": "   "},
    )

    assert response.status_code == 422


async def test_an_adjustment_below_zero_is_refused_with_an_explanation(client, admin, user_factory):
    _, headers = admin
    student = await user_factory(email="broke@test.edu")

    response = await client.post(
        f"{GAMIFICATION}/adjustments",
        headers=headers,
        json={"user_id": str(student.id), "amount": -10, "note": "Cannot go negative"},
    )

    assert response.status_code == 422
    assert "below zero" in response.json()["error"]["message"]


async def test_a_teacher_cannot_adjust_xp(client, teacher, user_factory):
    _, headers = teacher
    student = await user_factory(email="pupil@test.edu")

    response = await client.post(
        f"{GAMIFICATION}/adjustments",
        headers=headers,
        json={"user_id": str(student.id), "amount": 500, "note": "A gift"},
    )

    assert response.status_code == 403


async def test_a_student_cannot_award_themselves_xp(client, student):
    user, headers = student

    response = await client.post(
        f"{GAMIFICATION}/adjustments",
        headers=headers,
        json={"user_id": str(user.id), "amount": 100_000, "note": "Level 100 please"},
    )

    assert response.status_code == 403


async def test_adjusting_an_unknown_user_is_a_404(client, admin):
    import uuid

    _, headers = admin

    response = await client.post(
        f"{GAMIFICATION}/adjustments",
        headers=headers,
        json={"user_id": str(uuid.uuid4()), "amount": 10, "note": "Who?"},
    )

    assert response.status_code == 404
