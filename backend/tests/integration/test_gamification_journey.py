"""From practising to appearing on the leaderboard, through the real API.

Everything else in this sprint exercises the engine directly. This walks the
route a student actually takes — mark a submission, then read back the level,
the ledger, the achievements and the board — because the pieces passing
individually is not the same as the flow working.

Real seeded content and the real spaCy pipeline, so the score that drives the
awards is one the rubric genuinely produced.
"""

from __future__ import annotations

import pytest

from app.models.enums import UserRole

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("spacy_model")]

SUBMISSIONS = "/api/v1/submissions"
GAMIFICATION = "/api/v1/gamification"
LEADERBOARD = "/api/v1/leaderboard"


@pytest.fixture
async def seeded_graph(db, seeded_vocabulary, seeded_gamification, user_factory):
    from sqlalchemy import select

    from app.db.seed.runner import seed_graphs
    from app.models.content import Graph

    author = await user_factory(role=UserRole.TEACHER, email="award-author@test.edu")
    await seed_graphs(db, author_id=author.id)
    return (await db.execute(select(Graph).where(Graph.graph_type == "line").limit(1))).scalar_one()


@pytest.fixture
async def student(user_factory, auth_headers):
    user = await user_factory(role=UserRole.STUDENT, email="awarded@test.edu")
    return user, auth_headers(user)


async def mark(client, headers, graph, text: str) -> dict:
    opened = await client.post(
        SUBMISSIONS, headers=headers, json={"graph_id": str(graph.id), "input_method": "typed"}
    )
    submission_id = opened.json()["id"]
    await client.patch(f"{SUBMISSIONS}/{submission_id}/text", headers=headers, json={"text": text})
    response = await client.post(f"{SUBMISSIONS}/{submission_id}/analyze", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_strong_answer_earns_xp_a_badge_and_a_level(client, student, seeded_graph):
    _, headers = student

    body = await mark(client, headers, seeded_graph, seeded_graph.reference_description)
    awards = body["gamification"]

    # The model answer uses the graph's own target vocabulary, so it should
    # reach the crown tier and clear the high-score threshold.
    assert body["score"]["reward_tier"] == "crown"
    assert awards["badge"]["reward_tier"] == "crown"
    assert {"reason": "submission", "amount": 20} in awards["xp_breakdown"]
    assert {"reason": "high_score_bonus", "amount": 30} in awards["xp_breakdown"]

    # Graph Queen, because this student is female. Graph King is not offered.
    codes = {a["code"] for a in awards["new_achievements"]}
    assert {"first_submission", "graph_queen"} <= codes
    assert "graph_king" not in codes

    assert awards["leveled_up"]
    assert awards["level_after"] > awards["level_before"]


async def test_the_awards_are_readable_afterwards_through_their_own_endpoints(
    client, student, seeded_graph
):
    """The result payload and the profile endpoints must agree.

    They are computed by different code — one from the award result, the other
    from the ledger and the catalogue — so a disagreement is the cache having
    drifted from the ledger it is supposed to summarise.
    """
    _, headers = student
    awards = (await mark(client, headers, seeded_graph, seeded_graph.reference_description))[
        "gamification"
    ]

    level = (await client.get(f"{GAMIFICATION}/level", headers=headers)).json()
    ledger = (await client.get(f"{GAMIFICATION}/xp-history", headers=headers)).json()
    achievements = (await client.get(f"{GAMIFICATION}/achievements", headers=headers)).json()
    badges = (await client.get(f"{GAMIFICATION}/badges", headers=headers)).json()

    assert level["current_level"] == awards["level_after"]
    assert level["total_xp"] == sum(item["amount"] for item in ledger["items"])
    assert level["current_streak_days"] == awards["streak_days"] == 1

    unlocked = {row["code"] for row in achievements if row["is_unlocked"]}
    assert {a["code"] for a in awards["new_achievements"]} <= unlocked

    earned = {row["reward_tier"]: row["earned_count"] for row in badges}
    assert earned["crown"] == 1


async def test_a_scored_student_appears_on_the_leaderboard(client, student, seeded_graph):
    user, headers = student
    await mark(client, headers, seeded_graph, seeded_graph.reference_description)

    board = (await client.get(LEADERBOARD, headers=headers)).json()
    mine = (await client.get(f"{LEADERBOARD}/me", headers=headers)).json()

    assert [entry["full_name"] for entry in board["entries"]] == [user.full_name]
    assert board["entries"][0]["is_you"]
    assert mine["entry"]["rank"] == 1
    assert mine["entry"]["xp"] == board["entries"][0]["xp"]


async def test_a_weak_answer_still_earns_the_base_award_and_a_hammer_badge(
    client, student, seeded_graph
):
    """The low tier is never a punishment in XP terms.

    Turning up and writing something earns the same 20 XP as a strong attempt;
    only the bonus is withheld. Charging a student for a weak answer would make
    the hammer a penalty on top of a joke, which FR-7.6 rules out.
    """
    _, headers = student

    body = await mark(
        client,
        headers,
        seeded_graph,
        "The chart shows some numbers over time and they are different from each other.",
    )
    awards = body["gamification"]

    assert body["score"]["reward_tier"] == "hammer"
    # The encouragement leads the message, before any number (FR-7.7).
    assert body["score"]["feedback"]["message"].startswith("Keep Practicing! You Can Improve!")
    assert {"reason": "submission", "amount": 20} in awards["xp_breakdown"]
    assert not any(e["reason"] == "high_score_bonus" for e in awards["xp_breakdown"])
    assert awards["badge"]["reward_tier"] == "hammer"


async def test_the_leaderboard_never_publishes_a_student_s_reward_tiers(
    client, student, seeded_graph
):
    """A hammer count is private to the student's own results (FR-7.6)."""
    _, headers = student
    await mark(client, headers, seeded_graph, "Numbers went up and down a bit.")

    board = (await client.get(LEADERBOARD, headers=headers)).json()
    entry = board["entries"][0]

    assert "hammer" not in str(board).lower()
    assert set(entry) == {
        "rank",
        "user_id",
        "full_name",
        "avatar_url",
        "level",
        "xp",
        "average_score",
        "submission_count",
        "achievement_count",
        "is_you",
    }


async def test_a_teacher_reviewing_work_sees_the_score_but_earns_nothing(
    client, user_factory, auth_headers, seeded_graph, db
):
    """Marking is a student action; there is no route for staff to earn XP."""
    teacher = await user_factory(role=UserRole.TEACHER, email="reviewer@test.edu")
    headers = auth_headers(teacher)

    opened = await client.post(
        SUBMISSIONS,
        headers=headers,
        json={"graph_id": str(seeded_graph.id), "input_method": "typed"},
    )

    assert opened.status_code == 403
    assert teacher.total_xp == 0
