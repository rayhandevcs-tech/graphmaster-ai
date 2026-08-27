"""Assignment endpoints.

Two rules run through every test here. A class you do not teach is **refused,
not returned empty** (rule 33) — an empty task list and a forbidden one look
identical, and the first is a lie. And an assignment changes nothing about
marking: it is a deadline and a label, so a passed due date records lateness
and never refuses work.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import UserRole

pytestmark = pytest.mark.anyio

ASSIGNMENTS = "/api/v1/assignments"


@pytest.fixture
async def teacher(user_factory, auth_headers):
    user = await user_factory(role=UserRole.TEACHER, email="teacher@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def other_teacher(user_factory, auth_headers):
    user = await user_factory(role=UserRole.TEACHER, email="other@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def admin(user_factory, auth_headers):
    user = await user_factory(role=UserRole.ADMIN, email="admin@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def section(class_factory, teacher):
    owner, _ = teacher
    return await class_factory(teacher_id=owner.id, name="English 201, Section A")


@pytest.fixture
async def graph(graph_factory, teacher):
    owner, _ = teacher
    return await graph_factory(created_by=owner.id, title="Rainfall by month")


@pytest.fixture
async def student(user_factory, auth_headers, section):
    user = await user_factory(role=UserRole.STUDENT, email="student@test.edu", class_id=section.id)
    return user, auth_headers(user)


@pytest.fixture
async def outsider(user_factory, auth_headers, class_factory, other_teacher):
    """A student in a different section, taught by a different teacher."""
    owner, _ = other_teacher
    elsewhere = await class_factory(teacher_id=owner.id, name="English 201, Section B")
    user = await user_factory(
        role=UserRole.STUDENT, email="outsider@test.edu", class_id=elsewhere.id
    )
    return user, auth_headers(user)


# ── Setting work ─────────────────────────────────────────────────────────────


async def test_teacher_sets_a_graph_as_work_for_their_section(client, teacher, section, graph):
    _, headers = teacher
    due = datetime.now(UTC) + timedelta(days=7)
    resp = await client.post(
        ASSIGNMENTS,
        headers=headers,
        json={
            "class_id": str(section.id),
            "graph_id": str(graph.id),
            "title": "Week 3 · rainfall",
            "instructions": "Use the slide from Tuesday.",
            "due_at": due.isoformat(),
        },
    )
    assert resp.status_code == 201

    body = resp.json()
    assert body["title"] == "Week 3 · rainfall"
    assert body["class_name"] == "English 201, Section A"
    assert body["graph_title"] == "Rainfall by month"
    assert body["is_active"] is True


async def test_a_teacher_cannot_set_work_for_a_section_they_do_not_teach(
    client, other_teacher, section, graph
):
    _, headers = other_teacher
    resp = await client.post(
        ASSIGNMENTS,
        headers=headers,
        json={"class_id": str(section.id), "graph_id": str(graph.id), "title": "Not yours"},
    )
    # Refused, not silently accepted against someone else's class.
    assert resp.status_code == 403


async def test_an_unpublished_graph_cannot_be_set_as_work(client, teacher, section, graph_factory):
    owner, headers = teacher
    draft = await graph_factory(created_by=owner.id, is_published=False)
    resp = await client.post(
        ASSIGNMENTS,
        headers=headers,
        json={"class_id": str(section.id), "graph_id": str(draft.id), "title": "Draft work"},
    )
    # A draft is invisible to students, so setting it would hand the class a
    # task they cannot open.
    assert resp.status_code == 422


async def test_a_student_cannot_set_work(client, student, section, graph):
    _, headers = student
    resp = await client.post(
        ASSIGNMENTS,
        headers=headers,
        json={"class_id": str(section.id), "graph_id": str(graph.id), "title": "Mine now"},
    )
    assert resp.status_code == 403


# ── Reading the list ─────────────────────────────────────────────────────────


async def test_a_student_sees_the_work_set_for_their_own_section(
    client, student, assignment_factory, section, graph
):
    await assignment_factory(class_=section, graph=graph, title="Week 3 · rainfall")
    _, headers = student

    resp = await client.get(ASSIGNMENTS, headers=headers)
    assert resp.status_code == 200
    assert [row["title"] for row in resp.json()["items"]] == ["Week 3 · rainfall"]


async def test_a_student_in_another_section_sees_none_of_it(
    client, outsider, assignment_factory, section, graph
):
    await assignment_factory(class_=section, graph=graph)
    _, headers = outsider

    resp = await client.get(ASSIGNMENTS, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_a_student_does_not_see_work_that_has_been_closed(
    client, student, assignment_factory, section, graph
):
    await assignment_factory(class_=section, graph=graph, is_active=False)
    _, headers = student

    resp = await client.get(ASSIGNMENTS, headers=headers)
    assert resp.json()["items"] == []


async def test_a_teacher_still_sees_work_they_closed(
    client, teacher, assignment_factory, section, graph
):
    await assignment_factory(class_=section, graph=graph, is_active=False)
    _, headers = teacher

    resp = await client.get(ASSIGNMENTS, headers=headers)
    assert len(resp.json()["items"]) == 1


async def test_dated_work_comes_before_undated_work(
    client, student, assignment_factory, section, graph
):
    soon = datetime.now(UTC) + timedelta(days=1)
    later = datetime.now(UTC) + timedelta(days=30)
    await assignment_factory(class_=section, graph=graph, title="No deadline")
    await assignment_factory(class_=section, graph=graph, title="Later", due_at=later)
    await assignment_factory(class_=section, graph=graph, title="Soon", due_at=soon)
    _, headers = student

    resp = await client.get(ASSIGNMENTS, headers=headers)
    # Undated work is never the most urgent thing on the list.
    assert [row["title"] for row in resp.json()["items"]] == ["Soon", "Later", "No deadline"]


async def test_an_unenrolled_student_sees_an_empty_list_not_an_error(
    client, user_factory, auth_headers, assignment_factory, section, graph
):
    await assignment_factory(class_=section, graph=graph)
    loner = await user_factory(role=UserRole.STUDENT, email="loner@test.edu")

    resp = await client.get(ASSIGNMENTS, headers=auth_headers(loner))
    # Correct, not a bug: nobody has set them anything.
    assert resp.status_code == 200
    assert resp.json()["items"] == []


# ── Reading one ──────────────────────────────────────────────────────────────


async def test_a_student_reading_their_own_assignment_learns_whether_they_started(
    client, student, assignment_factory, section, graph, scored_submission_factory
):
    assignment = await assignment_factory(class_=section, graph=graph)
    user, headers = student
    submission = await scored_submission_factory(user=user, graph=graph, assignment=assignment)

    resp = await client.get(f"{ASSIGNMENTS}/{assignment.id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["submission_id"] == str(submission.id)
    assert resp.json()["submission_status"] == "scored"


async def test_an_assignment_from_another_section_reads_as_absent_to_a_student(
    client, outsider, assignment_factory, section, graph
):
    assignment = await assignment_factory(class_=section, graph=graph)
    _, headers = outsider

    resp = await client.get(f"{ASSIGNMENTS}/{assignment.id}", headers=headers)
    # 404, not 403: telling a student that work exists in another section is
    # itself a disclosure.
    assert resp.status_code == 404


async def test_another_teachers_assignment_is_refused_not_hidden(
    client, other_teacher, assignment_factory, section, graph
):
    assignment = await assignment_factory(class_=section, graph=graph)
    _, headers = other_teacher

    resp = await client.get(f"{ASSIGNMENTS}/{assignment.id}", headers=headers)
    assert resp.status_code == 403


async def test_an_administrator_reads_any_assignment(
    client, admin, assignment_factory, section, graph
):
    assignment = await assignment_factory(class_=section, graph=graph)
    _, headers = admin

    resp = await client.get(f"{ASSIGNMENTS}/{assignment.id}", headers=headers)
    assert resp.status_code == 200


# ── Updating ─────────────────────────────────────────────────────────────────


async def test_a_teacher_moves_the_deadline(client, teacher, assignment_factory, section, graph):
    assignment = await assignment_factory(class_=section, graph=graph)
    _, headers = teacher
    new_due = datetime.now(UTC) + timedelta(days=3)

    resp = await client.patch(
        f"{ASSIGNMENTS}/{assignment.id}", headers=headers, json={"due_at": new_due.isoformat()}
    )
    assert resp.status_code == 200
    assert resp.json()["due_at"] is not None


async def test_the_graph_cannot_be_swapped_after_the_work_is_set(
    client, teacher, assignment_factory, section, graph, graph_factory
):
    assignment = await assignment_factory(class_=section, graph=graph)
    owner, headers = teacher
    other = await graph_factory(created_by=owner.id)

    resp = await client.patch(
        f"{ASSIGNMENTS}/{assignment.id}", headers=headers, json={"graph_id": str(other.id)}
    )
    # Ignored rather than applied: moving an assignment to another graph would
    # silently change what the submissions already filed against it answered.
    assert resp.status_code == 200
    assert resp.json()["graph_id"] == str(graph.id)


async def test_only_the_owning_teacher_may_update(
    client, other_teacher, assignment_factory, section, graph
):
    assignment = await assignment_factory(class_=section, graph=graph)
    _, headers = other_teacher

    resp = await client.patch(
        f"{ASSIGNMENTS}/{assignment.id}", headers=headers, json={"title": "Mine now"}
    )
    assert resp.status_code == 403


# ── Progress ─────────────────────────────────────────────────────────────────


async def test_progress_counts_against_enrolment_not_against_who_submitted(
    client,
    teacher,
    student,
    user_factory,
    assignment_factory,
    section,
    graph,
    scored_submission_factory,
):
    assignment = await assignment_factory(class_=section, graph=graph)
    submitter, _ = student
    await user_factory(role=UserRole.STUDENT, email="quiet@test.edu", class_id=section.id)
    await scored_submission_factory(user=submitter, graph=graph, assignment=assignment)
    _, headers = teacher

    resp = await client.get(f"{ASSIGNMENTS}/{assignment.id}/progress", headers=headers)
    assert resp.status_code == 200

    body = resp.json()
    # Half the class never started, and the report says so rather than letting
    # it hide behind the half that did (rule 35).
    assert body["enrolled_count"] == 2
    assert body["submitted_count"] == 1
    assert len(body["students"]) == 2


async def test_a_student_who_has_not_started_scores_null_not_zero(
    client, teacher, user_factory, assignment_factory, section, graph
):
    assignment = await assignment_factory(class_=section, graph=graph)
    await user_factory(role=UserRole.STUDENT, email="quiet@test.edu", class_id=section.id)
    _, headers = teacher

    resp = await client.get(f"{ASSIGNMENTS}/{assignment.id}/progress", headers=headers)
    row = resp.json()["students"][0]
    # A zero would sort them below someone genuinely struggling (rule 32).
    assert row["final_score"] is None
    assert row["status"] is None


async def test_the_average_is_null_before_anything_is_marked(
    client, teacher, assignment_factory, section, graph, student
):
    assignment = await assignment_factory(class_=section, graph=graph)
    _, headers = teacher

    resp = await client.get(f"{ASSIGNMENTS}/{assignment.id}/progress", headers=headers)
    assert resp.json()["average_score"] is None


async def test_work_filed_after_the_deadline_is_marked_late_not_refused(
    client, teacher, student, assignment_factory, section, graph, scored_submission_factory
):
    passed = datetime.now(UTC) - timedelta(days=2)
    assignment = await assignment_factory(class_=section, graph=graph, due_at=passed)
    submitter, _ = student
    await scored_submission_factory(user=submitter, graph=graph, assignment=assignment)
    _, headers = teacher

    resp = await client.get(f"{ASSIGNMENTS}/{assignment.id}/progress", headers=headers)
    body = resp.json()
    assert body["late_count"] == 1
    assert body["students"][0]["is_late"] is True
    # And the mark itself is untouched — lateness is recorded, never punished.
    assert body["students"][0]["final_score"] == 75.0


async def test_a_teacher_cannot_read_another_sections_progress(
    client, other_teacher, assignment_factory, section, graph
):
    assignment = await assignment_factory(class_=section, graph=graph)
    _, headers = other_teacher

    resp = await client.get(f"{ASSIGNMENTS}/{assignment.id}/progress", headers=headers)
    # Refused, not returned empty: the two look identical and the second lies.
    assert resp.status_code == 403


async def test_a_student_cannot_read_the_class_progress(
    client, student, assignment_factory, section, graph
):
    assignment = await assignment_factory(class_=section, graph=graph)
    _, headers = student

    resp = await client.get(f"{ASSIGNMENTS}/{assignment.id}/progress", headers=headers)
    assert resp.status_code == 403


# ── Filing work against an assignment ────────────────────────────────────────

SUBMISSIONS = "/api/v1/submissions"


async def test_a_submission_started_from_an_assignment_carries_it(
    client, student, assignment_factory, section, graph
):
    assignment = await assignment_factory(class_=section, graph=graph)
    _, headers = student

    resp = await client.post(
        SUBMISSIONS,
        headers=headers,
        json={"graph_id": str(graph.id), "assignment_id": str(assignment.id)},
    )
    assert resp.status_code == 201
    assert resp.json()["assignment_id"] == str(assignment.id)
    assert resp.json()["assignment_title"] == assignment.title


async def test_free_practice_still_carries_no_assignment(client, student, graph):
    _, headers = student
    resp = await client.post(SUBMISSIONS, headers=headers, json={"graph_id": str(graph.id)})
    # The core loop is unchanged: a student who picked the graph out of the
    # library files against nothing, exactly as before assignments existed.
    assert resp.status_code == 201
    assert resp.json()["assignment_id"] is None


async def test_a_student_cannot_file_against_another_sections_assignment(
    client, outsider, assignment_factory, section, graph
):
    assignment = await assignment_factory(class_=section, graph=graph)
    _, headers = outsider

    resp = await client.post(
        SUBMISSIONS,
        headers=headers,
        json={"graph_id": str(graph.id), "assignment_id": str(assignment.id)},
    )
    # The id in the body is checked rather than trusted.
    assert resp.status_code == 404


async def test_an_assignment_set_on_a_different_graph_is_refused(
    client, student, assignment_factory, section, graph, graph_factory, teacher
):
    owner, _ = teacher
    other = await graph_factory(created_by=owner.id, title="Something else")
    assignment = await assignment_factory(class_=section, graph=other)
    _, headers = student

    resp = await client.post(
        SUBMISSIONS,
        headers=headers,
        json={"graph_id": str(graph.id), "assignment_id": str(assignment.id)},
    )
    # Accepting it would file this answer against a question nobody asked.
    assert resp.status_code == 422


async def test_a_passed_deadline_does_not_refuse_the_work(
    client, student, assignment_factory, section, graph
):
    passed = datetime.now(UTC) - timedelta(days=5)
    assignment = await assignment_factory(class_=section, graph=graph, due_at=passed)
    _, headers = student

    resp = await client.post(
        SUBMISSIONS,
        headers=headers,
        json={"graph_id": str(graph.id), "assignment_id": str(assignment.id)},
    )
    # Refusing the answer a student finally sat down to write is the opposite
    # of what the platform is for.
    assert resp.status_code == 201


async def test_a_free_practice_draft_is_not_handed_to_assigned_work(
    client, student, assignment_factory, section, graph
):
    assignment = await assignment_factory(class_=section, graph=graph)
    _, headers = student

    first = await client.post(SUBMISSIONS, headers=headers, json={"graph_id": str(graph.id)})
    second = await client.post(
        SUBMISSIONS,
        headers=headers,
        json={"graph_id": str(graph.id), "assignment_id": str(assignment.id)},
    )
    # `assignment_id` is set once and never updated, so reusing the pristine
    # free-practice draft would leave the task reading as not started after
    # the student had done it.
    assert first.json()["id"] != second.json()["id"]
    assert second.json()["assignment_id"] == str(assignment.id)


async def test_opening_the_same_assignment_twice_reuses_the_draft(
    client, student, assignment_factory, section, graph
):
    assignment = await assignment_factory(class_=section, graph=graph)
    _, headers = student
    body = {"graph_id": str(graph.id), "assignment_id": str(assignment.id)}

    first = await client.post(SUBMISSIONS, headers=headers, json=body)
    second = await client.post(SUBMISSIONS, headers=headers, json=body)
    # A double-tap on "Start" still does not litter the table.
    assert first.json()["id"] == second.json()["id"]


# ── Two audiences, one response model ────────────────────────────────────────


async def test_a_teachers_card_carries_the_class_counts(
    client,
    teacher,
    student,
    user_factory,
    assignment_factory,
    section,
    graph,
    scored_submission_factory,
):
    assignment = await assignment_factory(class_=section, graph=graph)
    submitter, _ = student
    await user_factory(role=UserRole.STUDENT, email="quiet@test.edu", class_id=section.id)
    await scored_submission_factory(user=submitter, graph=graph, assignment=assignment)
    _, headers = teacher

    row = (await client.get(ASSIGNMENTS, headers=headers)).json()["items"][0]
    assert row["submitted_count"] == 1
    assert row["enrolled_count"] == 2


async def test_a_students_card_carries_their_own_state_and_not_the_classs(
    client, student, user_factory, assignment_factory, section, graph, scored_submission_factory
):
    assignment = await assignment_factory(class_=section, graph=graph)
    me, headers = student
    classmate = await user_factory(
        role=UserRole.STUDENT, email="classmate@test.edu", class_id=section.id
    )
    await scored_submission_factory(user=classmate, graph=graph, assignment=assignment)
    mine = await scored_submission_factory(user=me, graph=graph, assignment=assignment)

    row = (await client.get(ASSIGNMENTS, headers=headers)).json()["items"][0]
    assert row["submission_id"] == str(mine.id)
    assert row["submission_status"] == "scored"
    # Telling a student how many classmates have finished is the comparison
    # FR-7.6 keeps off the leaderboard, arriving by another door.
    assert row["submitted_count"] is None
    assert row["enrolled_count"] is None


async def test_a_student_who_has_not_started_gets_a_card_with_no_submission(
    client, student, assignment_factory, section, graph
):
    await assignment_factory(class_=section, graph=graph)
    _, headers = student

    row = (await client.get(ASSIGNMENTS, headers=headers)).json()["items"][0]
    assert row["submission_id"] is None
    assert row["submission_status"] is None
