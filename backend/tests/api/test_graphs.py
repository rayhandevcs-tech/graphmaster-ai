"""Graph (practice content) endpoints."""

from __future__ import annotations

import pytest

from app.models.enums import UserRole

pytestmark = pytest.mark.anyio


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
async def student(user_factory, auth_headers):
    user = await user_factory(role=UserRole.STUDENT, email="student@test.edu")
    return user, auth_headers(user)


def graph_body(chart_payload, **overrides) -> dict:
    base = {
        "title": "Solar output 2019 to 2025",
        "prompt": "Describe the chart in at least 150 words.",
        "graph_type": "line",
        "difficulty": "beginner",
        "chart_data": chart_payload(),
        "reference_description": "The line graph illustrates a steady rise.",
    }
    return base | overrides


# ── The reference description must never reach a student ─────────────────────


async def test_student_detail_omits_the_reference_description(
    client, seeded_vocabulary, graph_factory, teacher, student
):
    """It is the model answer; a student who could read it would be scored on
    their copying rather than their writing (API design §3.5)."""
    teacher_user, _ = teacher
    _, student_headers = student
    graph = await graph_factory(created_by=teacher_user.id, targets=[seeded_vocabulary["increase"]])

    resp = await client.get(f"/api/v1/graphs/{graph.id}", headers=student_headers)
    assert resp.status_code == 200

    body = resp.json()
    # Absent from the payload entirely — not merely null.
    assert "reference_description" not in body
    assert "target_vocabulary" not in body
    assert body["chart_data"]["labels"] == ["2023", "2024", "2025"]


async def test_teacher_detail_includes_the_reference_description(
    client, seeded_vocabulary, graph_factory, teacher
):
    teacher_user, headers = teacher
    graph = await graph_factory(created_by=teacher_user.id, targets=[seeded_vocabulary["increase"]])

    resp = await client.get(f"/api/v1/graphs/{graph.id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["reference_description"] == "The line graph illustrates a steady rise."
    assert len(body["target_vocabulary"]) == 1


async def test_random_graph_also_hides_it_from_students(
    client, seeded_vocabulary, graph_factory, teacher, student
):
    teacher_user, _ = teacher
    _, student_headers = student
    await graph_factory(created_by=teacher_user.id, targets=[seeded_vocabulary["increase"]])

    resp = await client.get("/api/v1/graphs/random", headers=student_headers)
    assert resp.status_code == 200
    assert "reference_description" not in resp.json()


# ── Unpublished content is invisible to students ─────────────────────────────


async def test_students_cannot_fetch_an_unpublished_graph(client, graph_factory, teacher, student):
    """Reported as absent, not forbidden, so drafts cannot be enumerated."""
    teacher_user, _ = teacher
    _, student_headers = student
    graph = await graph_factory(created_by=teacher_user.id, is_published=False)

    resp = await client.get(f"/api/v1/graphs/{graph.id}", headers=student_headers)
    assert resp.status_code == 404


async def test_teachers_can_fetch_an_unpublished_graph(client, graph_factory, teacher):
    teacher_user, headers = teacher
    graph = await graph_factory(created_by=teacher_user.id, is_published=False)

    resp = await client.get(f"/api/v1/graphs/{graph.id}", headers=headers)
    assert resp.status_code == 200


async def test_listing_hides_unpublished_graphs_from_students(
    client, graph_factory, teacher, student
):
    teacher_user, _ = teacher
    _, student_headers = student
    await graph_factory(created_by=teacher_user.id, is_published=True, title="Published one")
    await graph_factory(created_by=teacher_user.id, is_published=False, title="Draft one")

    resp = await client.get("/api/v1/graphs", headers=student_headers)
    assert resp.status_code == 200
    assert [g["title"] for g in resp.json()["items"]] == ["Published one"]


async def test_students_cannot_opt_into_unpublished_graphs(client, graph_factory, teacher, student):
    """The flag is honoured for teachers only; a student stays pinned."""
    teacher_user, _ = teacher
    _, student_headers = student
    await graph_factory(created_by=teacher_user.id, is_published=False, title="Draft one")

    resp = await client.get("/api/v1/graphs?include_unpublished=true", headers=student_headers)
    assert resp.json()["total"] == 0


async def test_teachers_can_opt_into_unpublished_graphs(client, graph_factory, teacher):
    teacher_user, headers = teacher
    await graph_factory(created_by=teacher_user.id, is_published=False, title="Draft one")

    resp = await client.get("/api/v1/graphs?include_unpublished=true", headers=headers)
    assert resp.json()["total"] == 1


# ── Filtering and random selection ───────────────────────────────────────────


async def test_filter_by_type_and_difficulty(client, graph_factory, teacher, student):
    teacher_user, _ = teacher
    _, student_headers = student
    await graph_factory(created_by=teacher_user.id, graph_type="line", difficulty="beginner")
    await graph_factory(created_by=teacher_user.id, graph_type="bar", difficulty="advanced")

    resp = await client.get("/api/v1/graphs?graph_type=bar", headers=student_headers)
    assert resp.json()["total"] == 1
    resp = await client.get("/api/v1/graphs?difficulty=advanced", headers=student_headers)
    assert resp.json()["total"] == 1
    resp = await client.get(
        "/api/v1/graphs?graph_type=line&difficulty=advanced", headers=student_headers
    )
    assert resp.json()["total"] == 0


async def test_random_excludes_the_current_graph(client, graph_factory, teacher, student):
    """So "Try another" never hands back the graph just attempted."""
    teacher_user, _ = teacher
    _, student_headers = student
    first = await graph_factory(created_by=teacher_user.id)
    await graph_factory(created_by=teacher_user.id)

    for _ in range(8):
        resp = await client.get(
            f"/api/v1/graphs/random?exclude_id={first.id}", headers=student_headers
        )
        assert resp.status_code == 200
        assert resp.json()["id"] != str(first.id)


async def test_random_with_no_match_explains_itself(client, graph_factory, teacher, student):
    teacher_user, _ = teacher
    _, student_headers = student
    await graph_factory(created_by=teacher_user.id, graph_type="line")

    resp = await client.get("/api/v1/graphs/random?graph_type=pie", headers=student_headers)
    assert resp.status_code == 404
    assert "filter" in resp.json()["error"]["message"]


async def test_random_ignores_unpublished_graphs(client, graph_factory, teacher, student):
    teacher_user, _ = teacher
    _, student_headers = student
    await graph_factory(created_by=teacher_user.id, is_published=False)

    resp = await client.get("/api/v1/graphs/random", headers=student_headers)
    assert resp.status_code == 404


# ── Authoring ────────────────────────────────────────────────────────────────


async def test_teacher_creates_a_graph(client, chart_payload, teacher):
    _, headers = teacher
    resp = await client.post("/api/v1/graphs", headers=headers, json=graph_body(chart_payload))
    assert resp.status_code == 201

    body = resp.json()
    assert body["title"] == "Solar output 2019 to 2025"
    # Never published on creation: it has no targets yet, so it is unscoreable.
    assert body["is_published"] is False
    assert body["target_vocabulary_count"] == 0


async def test_students_may_not_create_graphs(client, chart_payload, student):
    _, headers = student
    resp = await client.post("/api/v1/graphs", headers=headers, json=graph_body(chart_payload))
    assert resp.status_code == 403


async def test_create_rejects_a_mismatched_chart(client, chart_payload, teacher):
    _, headers = teacher
    body = graph_body(
        chart_payload, chart_data=chart_payload(datasets=[{"label": "x", "data": [1, 2]}])
    )
    resp = await client.post("/api/v1/graphs", headers=headers, json=body)
    assert resp.status_code == 422


async def test_create_with_targets_in_one_call(client, seeded_vocabulary, chart_payload, teacher):
    _, headers = teacher
    body = graph_body(
        chart_payload,
        target_vocabulary=[
            {"vocabulary_item_id": str(seeded_vocabulary["increase"].id)},
            {"vocabulary_item_id": str(seeded_vocabulary["surge"].id), "is_required": False},
        ],
    )
    resp = await client.post("/api/v1/graphs", headers=headers, json=body)
    assert resp.status_code == 201
    assert len(resp.json()["target_vocabulary"]) == 2
    # Only required terms count toward the scoring denominator.
    assert resp.json()["target_vocabulary_count"] == 1


async def test_update_a_graph(client, graph_factory, teacher):
    teacher_user, headers = teacher
    graph = await graph_factory(created_by=teacher_user.id)

    resp = await client.patch(
        f"/api/v1/graphs/{graph.id}", headers=headers, json={"title": "Renamed graph"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Renamed graph"


async def test_changing_type_revalidates_the_stored_chart(client, graph_factory, teacher):
    """A pie chart must not inherit three datasets from its life as a bar chart."""
    teacher_user, headers = teacher
    graph = await graph_factory(created_by=teacher_user.id, graph_type="bar")
    await client.patch(
        f"/api/v1/graphs/{graph.id}",
        headers=headers,
        json={
            "chart_data": {
                "labels": ["a", "b"],
                "datasets": [
                    {"label": "one", "data": [1, 2]},
                    {"label": "two", "data": [3, 4]},
                ],
            }
        },
    )

    resp = await client.patch(
        f"/api/v1/graphs/{graph.id}", headers=headers, json={"graph_type": "pie"}
    )
    assert resp.status_code == 422
    assert "exactly one dataset" in resp.json()["error"]["message"]


async def test_changing_type_and_chart_together_is_validated_as_a_pair(
    client, graph_factory, teacher
):
    teacher_user, headers = teacher
    graph = await graph_factory(created_by=teacher_user.id, graph_type="bar")

    resp = await client.patch(
        f"/api/v1/graphs/{graph.id}",
        headers=headers,
        json={
            "graph_type": "pie",
            "chart_data": {
                "labels": ["a", "b"],
                "datasets": [{"label": "one", "data": [1, 2]}],
            },
        },
    )
    assert resp.status_code == 200
    assert resp.json()["graph_type"] == "pie"


# ── Publishing ───────────────────────────────────────────────────────────────


async def test_cannot_publish_without_required_targets(client, graph_factory, teacher):
    """The vocabulary percentage would divide by zero (PROJECT_PLAN §3.2)."""
    teacher_user, headers = teacher
    graph = await graph_factory(created_by=teacher_user.id, is_published=False)

    resp = await client.post(
        f"/api/v1/graphs/{graph.id}/publish", headers=headers, json={"is_published": True}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "NO_TARGET_VOCABULARY"


async def test_publishing_succeeds_once_targets_exist(
    client, seeded_vocabulary, graph_factory, teacher
):
    teacher_user, headers = teacher
    graph = await graph_factory(
        created_by=teacher_user.id,
        is_published=False,
        targets=[seeded_vocabulary["increase"]],
    )

    resp = await client.post(
        f"/api/v1/graphs/{graph.id}/publish", headers=headers, json={"is_published": True}
    )
    assert resp.status_code == 200
    assert resp.json()["is_published"] is True


async def test_unpublishing_needs_no_targets(client, graph_factory, teacher):
    teacher_user, headers = teacher
    graph = await graph_factory(created_by=teacher_user.id, is_published=True)

    resp = await client.post(
        f"/api/v1/graphs/{graph.id}/publish", headers=headers, json={"is_published": False}
    )
    assert resp.status_code == 200
    assert resp.json()["is_published"] is False


async def test_only_optional_targets_still_blocks_publishing(
    client, seeded_vocabulary, chart_payload, teacher
):
    _, headers = teacher
    body = graph_body(
        chart_payload,
        target_vocabulary=[
            {"vocabulary_item_id": str(seeded_vocabulary["increase"].id), "is_required": False}
        ],
    )
    created = await client.post("/api/v1/graphs", headers=headers, json=body)
    graph_id = created.json()["id"]

    resp = await client.post(
        f"/api/v1/graphs/{graph_id}/publish", headers=headers, json={"is_published": True}
    )
    assert resp.status_code == 409


# ── Target vocabulary curation ───────────────────────────────────────────────


async def test_replace_targets(client, seeded_vocabulary, graph_factory, teacher):
    teacher_user, headers = teacher
    graph = await graph_factory(
        created_by=teacher_user.id, is_published=False, targets=[seeded_vocabulary["increase"]]
    )

    resp = await client.put(
        f"/api/v1/graphs/{graph.id}/target-vocabulary",
        headers=headers,
        json={
            "items": [
                {"vocabulary_item_id": str(seeded_vocabulary["fluctuate"].id)},
                {"vocabulary_item_id": str(seeded_vocabulary["peak"].id), "is_required": False},
            ]
        },
    )
    assert resp.status_code == 200
    terms = {t["item"]["term"] for t in resp.json()}
    assert terms == {"fluctuate", "peak"}


async def test_targets_are_sorted_by_category_order(
    client, seeded_vocabulary, graph_factory, teacher
):
    teacher_user, headers = teacher
    graph = await graph_factory(created_by=teacher_user.id, is_published=False)

    await client.put(
        f"/api/v1/graphs/{graph.id}/target-vocabulary",
        headers=headers,
        json={
            "items": [
                {"vocabulary_item_id": str(seeded_vocabulary["trough"].id)},
                {"vocabulary_item_id": str(seeded_vocabulary["increase"].id)},
            ]
        },
    )
    resp = await client.get(f"/api/v1/graphs/{graph.id}/target-vocabulary", headers=headers)
    # "increase" is display_order 1, "lowest" is 7.
    assert [t["item"]["category_code"] for t in resp.json()] == ["increase", "lowest"]


async def test_cannot_target_a_deactivated_term(client, seeded_vocabulary, graph_factory, teacher):
    """A deactivated term is never detected, so it would be an unreachable
    entry in the scoring denominator."""
    teacher_user, headers = teacher
    graph = await graph_factory(created_by=teacher_user.id, is_published=False)
    item = seeded_vocabulary["plateau"]
    await client.delete(f"/api/v1/vocabulary/items/{item.id}", headers=headers)

    resp = await client.put(
        f"/api/v1/graphs/{graph.id}/target-vocabulary",
        headers=headers,
        json={"items": [{"vocabulary_item_id": str(item.id)}]},
    )
    assert resp.status_code == 422
    assert "deactivated" in resp.json()["error"]["message"]


async def test_cannot_target_an_unknown_term(client, graph_factory, teacher):
    teacher_user, headers = teacher
    graph = await graph_factory(created_by=teacher_user.id, is_published=False)

    resp = await client.put(
        f"/api/v1/graphs/{graph.id}/target-vocabulary",
        headers=headers,
        json={"items": [{"vocabulary_item_id": "00000000-0000-0000-0000-000000000000"}]},
    )
    assert resp.status_code == 422
    assert "do not exist" in resp.json()["error"]["message"]


async def test_duplicate_targets_are_rejected(client, seeded_vocabulary, graph_factory, teacher):
    teacher_user, headers = teacher
    graph = await graph_factory(created_by=teacher_user.id, is_published=False)
    item_id = str(seeded_vocabulary["increase"].id)

    resp = await client.put(
        f"/api/v1/graphs/{graph.id}/target-vocabulary",
        headers=headers,
        json={"items": [{"vocabulary_item_id": item_id}, {"vocabulary_item_id": item_id}]},
    )
    assert resp.status_code == 422


async def test_cannot_empty_the_targets_of_a_published_graph(
    client, seeded_vocabulary, graph_factory, teacher
):
    """It would silently break every new attempt at a live exercise."""
    teacher_user, headers = teacher
    graph = await graph_factory(
        created_by=teacher_user.id, is_published=True, targets=[seeded_vocabulary["increase"]]
    )

    resp = await client.put(
        f"/api/v1/graphs/{graph.id}/target-vocabulary", headers=headers, json={"items": []}
    )
    assert resp.status_code == 409

    # The original target set is intact.
    resp = await client.get(f"/api/v1/graphs/{graph.id}/target-vocabulary", headers=headers)
    assert len(resp.json()) == 1


async def test_students_may_not_read_the_target_set(client, graph_factory, teacher, student):
    teacher_user, _ = teacher
    _, student_headers = student
    graph = await graph_factory(created_by=teacher_user.id)

    resp = await client.get(f"/api/v1/graphs/{graph.id}/target-vocabulary", headers=student_headers)
    assert resp.status_code == 403


# ── Deletion ─────────────────────────────────────────────────────────────────


async def test_author_deletes_an_unattempted_graph(client, graph_factory, teacher):
    teacher_user, headers = teacher
    graph = await graph_factory(created_by=teacher_user.id)

    resp = await client.delete(f"/api/v1/graphs/{graph.id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/graphs/{graph.id}", headers=headers)
    assert resp.status_code == 404


async def test_another_teacher_may_not_delete_it(client, graph_factory, teacher, other_teacher):
    """Editing is shared across the practice library; deletion is not."""
    teacher_user, _ = teacher
    _, other_headers = other_teacher
    graph = await graph_factory(created_by=teacher_user.id)

    resp = await client.delete(f"/api/v1/graphs/{graph.id}", headers=other_headers)
    assert resp.status_code == 403


async def test_another_teacher_may_edit_it(client, graph_factory, teacher, other_teacher):
    teacher_user, _ = teacher
    _, other_headers = other_teacher
    graph = await graph_factory(created_by=teacher_user.id)

    resp = await client.patch(
        f"/api/v1/graphs/{graph.id}", headers=other_headers, json={"title": "Improved title"}
    )
    assert resp.status_code == 200


async def test_an_admin_may_delete_any_graph(client, graph_factory, teacher, admin):
    teacher_user, _ = teacher
    _, admin_headers = admin
    graph = await graph_factory(created_by=teacher_user.id)

    resp = await client.delete(f"/api/v1/graphs/{graph.id}", headers=admin_headers)
    assert resp.status_code == 204


async def test_an_attempted_graph_cannot_be_deleted(client, db, graph_factory, teacher, student):
    """Deleting it would orphan the student's score, so 409 and a way forward."""
    from app.models.submission import Submission

    teacher_user, headers = teacher
    student_user, _ = student
    graph = await graph_factory(created_by=teacher_user.id)

    db.add(
        Submission(
            user_id=student_user.id,
            graph_id=graph.id,
            input_method="typed",
            answer_text="The graph shows a rise.",
        )
    )
    await db.flush()

    resp = await client.delete(f"/api/v1/graphs/{graph.id}", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "GRAPH_HAS_SUBMISSIONS"
    assert "Unpublish" in resp.json()["error"]["message"]
