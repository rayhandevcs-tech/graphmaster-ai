"""Analytics over work a real student actually did.

Every other analytics test writes scores directly. This one drives the
submission endpoint with the real spaCy pipeline and the real seeded
vocabulary, then asks whether the reports describe what happened — because the
vocabulary figures are counted out of ``scores.detected_terms``, and that field
is only trustworthy if the thing writing it and the thing reading it agree.
"""

from __future__ import annotations

import csv
import io

import pytest

from app.models.enums import UserRole

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("spacy_model")]

SUBMISSIONS = "/api/v1/submissions"
ANALYTICS = "/api/v1/analytics"
REPORTS = "/api/v1/reports"
DASHBOARD = "/api/v1/users/me/dashboard"


@pytest.fixture
async def teacher(user_factory, auth_headers):
    user = await user_factory(role=UserRole.TEACHER, email="analytics-teacher@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def cohort(class_factory, teacher):
    user, _ = teacher
    return await class_factory(teacher_id=user.id, code="JOURNEY1")


@pytest.fixture
async def seeded_graph(db, seeded_vocabulary, seeded_gamification, teacher):
    from sqlalchemy import select

    from app.db.seed.runner import seed_graphs
    from app.models.content import Graph

    author, _ = teacher
    await seed_graphs(db, author_id=author.id)
    return (await db.execute(select(Graph).where(Graph.graph_type == "line").limit(1))).scalar_one()


@pytest.fixture
async def student(user_factory, auth_headers, cohort):
    user = await user_factory(
        email="analytics-student@test.edu", full_name="Journey Student", class_id=cohort.id
    )
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


async def test_the_class_report_describes_the_work_that_was_done(
    client, teacher, student, cohort, seeded_graph
):
    _, teacher_headers = teacher
    _, headers = student

    strong = await mark(client, headers, seeded_graph, seeded_graph.reference_description)
    weak = await mark(client, headers, seeded_graph, "The chart shows some numbers.")

    body = (await client.get(f"{ANALYTICS}/class/{cohort.id}", headers=teacher_headers)).json()

    assert body["submission_count"] == 2
    assert body["active_student_count"] == 1
    expected = round((strong["score"]["final_score"] + weak["score"]["final_score"]) / 2, 2)
    assert body["average_final_score"] == pytest.approx(expected, abs=0.01)
    assert body["highest_final_score"] == pytest.approx(strong["score"]["final_score"], abs=0.01)
    assert sum(body["reward_tier_distribution"].values()) == 2


async def test_vocabulary_usage_agrees_with_the_scores_students_were_given(
    client, teacher, student, cohort, seeded_graph
):
    """Counted from what the engine matched, not from a second detector."""
    _, teacher_headers = teacher
    _, headers = student

    result = await mark(client, headers, seeded_graph, seeded_graph.reference_description)
    detected = {term["lemma"] for term in result["score"]["detected_terms"]}

    # A limit well under the number of unused terms, so the two ends of the
    # ordering cannot overlap. Asking for more terms than the library holds
    # would return the same set twice, reversed — correct, but it proves
    # nothing about the ordering.
    body = (
        await client.get(
            f"{ANALYTICS}/vocabulary-usage?class_id={cohort.id}&limit=10",
            headers=teacher_headers,
        )
    ).json()
    counted = {row["lemma"] for row in body["most_used"]}

    assert detected
    assert detected <= counted
    assert all(row["uses"] > 0 for row in body["most_used"])
    # Every term the student did not reach for is still listed, which is the
    # half of the picture a count of what was written cannot show.
    assert body["unused_term_count"] > 10
    assert not (detected & {row["lemma"] for row in body["least_used"]})
    assert all(row["uses"] == 0 for row in body["least_used"])


async def test_the_dashboard_and_the_class_report_agree_about_one_student(
    client, teacher, student, cohort, seeded_graph
):
    """They are computed by different code, so a disagreement is a real bug."""
    user, headers = student
    _, teacher_headers = teacher
    await mark(client, headers, seeded_graph, seeded_graph.reference_description)

    dashboard = (await client.get(DASHBOARD, headers=headers)).json()
    roster = (await client.get(f"{ANALYTICS}/class/{cohort.id}", headers=teacher_headers)).json()[
        "students"
    ]
    row = next(entry for entry in roster if entry["user_id"] == str(user.id))

    assert dashboard["total_attempts"] == row["submission_count"]
    assert dashboard["average_score"] == pytest.approx(row["average_final_score"], abs=0.01)
    assert dashboard["highest_score"] == pytest.approx(row["highest_final_score"], abs=0.01)
    assert dashboard["total_xp"] == row["total_xp"]


async def test_an_export_carries_the_real_rows(client, teacher, student, cohort, seeded_graph):
    _, teacher_headers = teacher
    _, headers = student
    result = await mark(client, headers, seeded_graph, seeded_graph.reference_description)

    report = await client.post(
        REPORTS,
        headers=teacher_headers,
        json={"report_type": "submission_export", "class_id": str(cohort.id)},
    )
    assert report.status_code == 201
    download = await client.get(
        f"{REPORTS}/{report.json()['id']}/download", headers=teacher_headers
    )
    rows = list(csv.reader(io.StringIO(download.content.decode("utf-8-sig"))))

    data = [row for row in rows if row and row[0] == "Journey Student"]
    assert len(data) == 1
    assert seeded_graph.title in data[0]
    assert f"{result['score']['final_score']:g}" in data[0]


async def test_an_export_never_carries_the_answers_themselves(
    client, teacher, student, cohort, seeded_graph
):
    """A submission export is scores and metadata, not a corpus dump.

    The full text is one screen away for a teacher who wants it, but a file
    circulated by email should not carry every student's writing verbatim.
    """
    _, teacher_headers = teacher
    _, headers = student
    marker = "quokkas industriously enumerate"
    await mark(
        client,
        headers,
        seeded_graph,
        f"{seeded_graph.reference_description} And also {marker}.",
    )

    report = await client.post(
        REPORTS,
        headers=teacher_headers,
        json={"report_type": "submission_export", "class_id": str(cohort.id)},
    )
    download = await client.get(
        f"{REPORTS}/{report.json()['id']}/download", headers=teacher_headers
    )

    assert marker not in download.content.decode("utf-8-sig")
