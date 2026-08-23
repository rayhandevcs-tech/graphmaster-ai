"""Vocabulary library endpoints."""

from __future__ import annotations

import pytest

from app.models.enums import UserRole

pytestmark = pytest.mark.anyio


@pytest.fixture
async def teacher(user_factory, auth_headers):
    user = await user_factory(role=UserRole.TEACHER, email="teacher@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def student(user_factory, auth_headers):
    user = await user_factory(role=UserRole.STUDENT, email="student@test.edu")
    return user, auth_headers(user)


# ── Reading ──────────────────────────────────────────────────────────────────


async def test_categories_list_with_counts(client, seeded_vocabulary, student):
    _, headers = student
    resp = await client.get("/api/v1/vocabulary/categories", headers=headers)
    assert resp.status_code == 200

    categories = resp.json()
    assert len(categories) == 7
    # Ordered by display_order, so a client can render them without sorting.
    assert [c["code"] for c in categories][:3] == ["increase", "decrease", "fluctuation"]
    assert sum(c["item_count"] for c in categories) == len(seeded_vocabulary)


async def test_students_may_read_the_library(client, seeded_vocabulary, student):
    """Students need the term list to see what they are scored against."""
    _, headers = student
    resp = await client.get("/api/v1/vocabulary/items", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == len(seeded_vocabulary)


async def test_anonymous_may_not_read_the_library(client, seeded_vocabulary):
    resp = await client.get("/api/v1/vocabulary/items")
    assert resp.status_code == 401


async def test_filter_by_category(client, seeded_vocabulary, student):
    _, headers = student
    resp = await client.get("/api/v1/vocabulary/items?category=fluctuation", headers=headers)
    assert resp.status_code == 200
    codes = {i["category_code"] for i in resp.json()["items"]}
    assert codes == {"fluctuation"}


async def test_search_matches_term_and_lemma(client, seeded_vocabulary, student):
    _, headers = student
    resp = await client.get("/api/v1/vocabulary/items?search=incre", headers=headers)
    assert resp.status_code == 200
    assert {i["term"] for i in resp.json()["items"]} == {"increase"}


async def test_phrases_are_flagged(client, seeded_vocabulary, student):
    _, headers = student
    resp = await client.get("/api/v1/vocabulary/items?search=higher than", headers=headers)
    item = resp.json()["items"][0]
    assert item["is_phrase"] is True
    assert item["lemma"] == "high than"


# ── Creating ─────────────────────────────────────────────────────────────────


async def test_teacher_creates_a_term(client, seeded_vocabulary, teacher):
    _, headers = teacher
    resp = await client.post(
        "/api/v1/vocabulary/items",
        headers=headers,
        json={"category_code": "increase", "term": "escalate", "weight": 1.25},
    )
    assert resp.status_code == 201

    body = resp.json()
    assert body["term"] == "escalate"
    # The lemma defaults to the lowercased term when not supplied.
    assert body["lemma"] == "escalate"
    assert body["is_phrase"] is False
    assert body["weight"] == 1.25
    assert body["is_active"] is True


async def test_is_phrase_is_derived_not_supplied(client, seeded_vocabulary, teacher):
    """The flag cannot disagree with the term, because it is never sent."""
    _, headers = teacher
    resp = await client.post(
        "/api/v1/vocabulary/items",
        headers=headers,
        json={
            "category_code": "comparison",
            "term": "in comparison with",
            "lemma": "in comparison with",
            "is_phrase": False,  # ignored: not a field on the model
        },
    )
    assert resp.status_code == 201
    assert resp.json()["is_phrase"] is True


async def test_students_may_not_create_terms(client, seeded_vocabulary, student):
    _, headers = student
    resp = await client.post(
        "/api/v1/vocabulary/items",
        headers=headers,
        json={"category_code": "increase", "term": "escalate"},
    )
    assert resp.status_code == 403


async def test_duplicate_lemma_is_rejected(client, seeded_vocabulary, teacher):
    _, headers = teacher
    resp = await client.post(
        "/api/v1/vocabulary/items",
        headers=headers,
        json={"category_code": "increase", "term": "Increase"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DUPLICATE_VOCABULARY_TERM"


async def test_unknown_category_lists_the_valid_ones(client, seeded_vocabulary, teacher):
    _, headers = teacher
    resp = await client.post(
        "/api/v1/vocabulary/items",
        headers=headers,
        json={"category_code": "nonsense", "term": "escalate"},
    )
    assert resp.status_code == 422
    assert "increase" in resp.json()["error"]["message"]


async def test_lemma_whitespace_is_normalised(client, seeded_vocabulary, teacher):
    _, headers = teacher
    resp = await client.post(
        "/api/v1/vocabulary/items",
        headers=headers,
        json={"category_code": "peak", "term": "  Reach   A  High  ", "lemma": "  Reach   A High "},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["term"] == "Reach A High"
    assert body["lemma"] == "reach a high"


# ── Bulk import ──────────────────────────────────────────────────────────────


async def test_bulk_import_skips_duplicates_without_failing(client, seeded_vocabulary, teacher):
    """A teacher pasting a list should not lose the new terms to the old ones."""
    _, headers = teacher
    resp = await client.post(
        "/api/v1/vocabulary/items/bulk",
        headers=headers,
        json={
            "items": [
                {"category_code": "increase", "term": "escalate"},
                {"category_code": "increase", "term": "increase"},  # already exists
                {"category_code": "decrease", "term": "dwindle"},
            ]
        },
    )
    assert resp.status_code == 201

    body = resp.json()
    assert body["created_count"] == 2
    assert body["skipped_count"] == 1
    assert {i["term"] for i in body["created"]} == {"escalate", "dwindle"}
    assert body["skipped"][0]["term"] == "increase"


async def test_bulk_import_catches_duplicates_within_the_batch(client, seeded_vocabulary, teacher):
    """Two rows resolving to one lemma would otherwise abort the whole flush."""
    _, headers = teacher
    resp = await client.post(
        "/api/v1/vocabulary/items/bulk",
        headers=headers,
        json={
            "items": [
                {"category_code": "increase", "term": "escalate"},
                {"category_code": "increase", "term": "Escalate"},
            ]
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["created_count"] == 1
    assert "Duplicated within this request" in body["skipped"][0]["reason"]


async def test_bulk_import_rejects_an_empty_list(client, seeded_vocabulary, teacher):
    _, headers = teacher
    resp = await client.post("/api/v1/vocabulary/items/bulk", headers=headers, json={"items": []})
    assert resp.status_code == 422


# ── Updating ─────────────────────────────────────────────────────────────────


async def test_teacher_updates_a_term(client, seeded_vocabulary, teacher):
    _, headers = teacher
    item = seeded_vocabulary["surge"]
    resp = await client.patch(
        f"/api/v1/vocabulary/items/{item.id}",
        headers=headers,
        json={"weight": 2.0, "category_code": "peak"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["weight"] == 2.0
    assert body["category_code"] == "peak"


async def test_changing_the_term_leaves_a_hand_set_lemma_alone(client, seeded_vocabulary, teacher):
    """Re-deriving would silently break detection for irregular phrases."""
    _, headers = teacher
    item = seeded_vocabulary["high than"]
    resp = await client.patch(
        f"/api/v1/vocabulary/items/{item.id}",
        headers=headers,
        json={"term": "much higher than"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["term"] == "much higher than"
    assert body["lemma"] == "high than"


async def test_lemma_clash_on_update_is_rejected(client, seeded_vocabulary, teacher):
    _, headers = teacher
    item = seeded_vocabulary["surge"]
    resp = await client.patch(
        f"/api/v1/vocabulary/items/{item.id}", headers=headers, json={"lemma": "climb"}
    )
    assert resp.status_code == 409


async def test_updating_a_term_to_its_own_lemma_is_allowed(client, seeded_vocabulary, teacher):
    _, headers = teacher
    item = seeded_vocabulary["surge"]
    resp = await client.patch(
        f"/api/v1/vocabulary/items/{item.id}", headers=headers, json={"lemma": "surge"}
    )
    assert resp.status_code == 200


async def test_unknown_item_is_404(client, seeded_vocabulary, teacher):
    _, headers = teacher
    resp = await client.patch(
        "/api/v1/vocabulary/items/00000000-0000-0000-0000-000000000000",
        headers=headers,
        json={"weight": 1.5},
    )
    assert resp.status_code == 404


# ── Soft delete ──────────────────────────────────────────────────────────────


async def test_delete_deactivates_rather_than_removing(client, seeded_vocabulary, teacher):
    """Historical scores reference terms, so the row must survive."""
    _, headers = teacher
    item = seeded_vocabulary["plateau"]

    resp = await client.delete(f"/api/v1/vocabulary/items/{item.id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Still fetchable by id — it was deactivated, not deleted.
    resp = await client.get(f"/api/v1/vocabulary/items/{item.id}", headers=headers)
    assert resp.status_code == 200


async def test_deactivated_terms_are_hidden_from_the_default_listing(
    client, seeded_vocabulary, teacher
):
    _, headers = teacher
    item = seeded_vocabulary["plateau"]
    await client.delete(f"/api/v1/vocabulary/items/{item.id}", headers=headers)

    resp = await client.get("/api/v1/vocabulary/items?search=plateau", headers=headers)
    assert resp.json()["total"] == 0

    resp = await client.get(
        "/api/v1/vocabulary/items?search=plateau&is_active=false", headers=headers
    )
    assert resp.json()["total"] == 1


async def test_a_deactivated_lemma_stays_reserved(client, seeded_vocabulary, teacher):
    """Recreating it would collide with the surviving row's unique lemma."""
    _, headers = teacher
    item = seeded_vocabulary["plateau"]
    await client.delete(f"/api/v1/vocabulary/items/{item.id}", headers=headers)

    resp = await client.post(
        "/api/v1/vocabulary/items",
        headers=headers,
        json={"category_code": "stability", "term": "plateau"},
    )
    assert resp.status_code == 409
    assert "deactivated" in resp.json()["error"]["message"]


async def test_a_term_can_be_reactivated(client, seeded_vocabulary, teacher):
    _, headers = teacher
    item = seeded_vocabulary["plateau"]
    await client.delete(f"/api/v1/vocabulary/items/{item.id}", headers=headers)

    resp = await client.patch(
        f"/api/v1/vocabulary/items/{item.id}", headers=headers, json={"is_active": True}
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True
