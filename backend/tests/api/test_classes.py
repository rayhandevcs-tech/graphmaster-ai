"""Class (cohort) endpoints.

The rule under test throughout: a teacher may only act on classes they own; an
administrator is unrestricted (FR-11.6).
"""

from __future__ import annotations

import pytest

from app.models.enums import UserRole
from app.schemas.class_ import CODE_ALPHABET, CODE_LENGTH

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


# ── Creation ─────────────────────────────────────────────────────────────────


async def test_teacher_creates_a_class_with_a_generated_code(client, teacher):
    _, headers = teacher
    resp = await client.post("/api/v1/classes", headers=headers, json={"name": "English 201B"})
    assert resp.status_code == 201

    body = resp.json()
    assert body["name"] == "English 201B"
    assert body["student_count"] == 0
    assert len(body["code"]) == CODE_LENGTH
    # The alphabet excludes look-alike characters, because the code is read
    # aloud in a classroom and typed off a slide.
    assert set(body["code"]) <= set(CODE_ALPHABET)
    assert not (set("O0I1L") & set(body["code"]))


async def test_teacher_supplies_their_own_course_code(client, teacher):
    _, headers = teacher
    resp = await client.post(
        "/api/v1/classes", headers=headers, json={"name": "English 201B", "code": "eng201b"}
    )
    assert resp.status_code == 201
    # Normalised to uppercase, so a student typing "eng201b" still joins.
    assert resp.json()["code"] == "ENG201B"


async def test_duplicate_code_is_rejected(client, teacher, class_factory):
    teacher_user, headers = teacher
    await class_factory(teacher_id=teacher_user.id, code="ENG201B")

    resp = await client.post(
        "/api/v1/classes", headers=headers, json={"name": "Another", "code": "ENG201B"}
    )
    assert resp.status_code == 409


async def test_generated_codes_do_not_collide(client, teacher):
    _, headers = teacher
    codes = set()
    for i in range(12):
        resp = await client.post("/api/v1/classes", headers=headers, json={"name": f"Class {i}"})
        assert resp.status_code == 201
        codes.add(resp.json()["code"])
    assert len(codes) == 12


async def test_students_may_not_create_classes(client, student):
    _, headers = student
    resp = await client.post("/api/v1/classes", headers=headers, json={"name": "Mine now"})
    assert resp.status_code == 403


# ── Ownership scoping ────────────────────────────────────────────────────────


async def test_teacher_lists_only_their_own_classes(client, teacher, other_teacher, class_factory):
    teacher_user, headers = teacher
    other_user, _ = other_teacher
    await class_factory(teacher_id=teacher_user.id, name="Mine")
    await class_factory(teacher_id=other_user.id, name="Theirs")

    resp = await client.get("/api/v1/classes", headers=headers)
    assert resp.status_code == 200
    assert [c["name"] for c in resp.json()["items"]] == ["Mine"]


async def test_admin_lists_every_class(client, teacher, other_teacher, class_factory, admin):
    teacher_user, _ = teacher
    other_user, _ = other_teacher
    _, admin_headers = admin
    await class_factory(teacher_id=teacher_user.id, name="Mine")
    await class_factory(teacher_id=other_user.id, name="Theirs")

    resp = await client.get("/api/v1/classes", headers=admin_headers)
    assert resp.json()["total"] == 2


async def test_teacher_cannot_read_another_teachers_class(
    client, other_teacher, class_factory, teacher
):
    _, headers = teacher
    other_user, _ = other_teacher
    class_ = await class_factory(teacher_id=other_user.id)

    resp = await client.get(f"/api/v1/classes/{class_.id}", headers=headers)
    assert resp.status_code == 403


async def test_teacher_cannot_update_another_teachers_class(
    client, other_teacher, class_factory, teacher
):
    _, headers = teacher
    other_user, _ = other_teacher
    class_ = await class_factory(teacher_id=other_user.id)

    resp = await client.patch(
        f"/api/v1/classes/{class_.id}", headers=headers, json={"name": "Hijacked"}
    )
    assert resp.status_code == 403


async def test_admin_may_manage_any_class(client, other_teacher, class_factory, admin):
    _, admin_headers = admin
    other_user, _ = other_teacher
    class_ = await class_factory(teacher_id=other_user.id)

    resp = await client.patch(
        f"/api/v1/classes/{class_.id}", headers=admin_headers, json={"name": "Renamed"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


async def test_unknown_class_is_404(client, teacher):
    _, headers = teacher
    resp = await client.get("/api/v1/classes/00000000-0000-0000-0000-000000000000", headers=headers)
    assert resp.status_code == 404


# ── Roster ───────────────────────────────────────────────────────────────────


async def test_roster_lists_enrolled_students(client, teacher, class_factory, user_factory):
    teacher_user, headers = teacher
    class_ = await class_factory(teacher_id=teacher_user.id)
    await user_factory(email="a@test.edu", full_name="Ayesha", class_id=class_.id)
    await user_factory(email="b@test.edu", full_name="Bilal", class_id=class_.id)
    await user_factory(email="c@test.edu", full_name="Not enrolled")

    resp = await client.get(f"/api/v1/classes/{class_.id}/students", headers=headers)
    assert resp.status_code == 200
    assert [s["full_name"] for s in resp.json()] == ["Ayesha", "Bilal"]


async def test_enrol_a_student_by_email(client, teacher, class_factory, user_factory):
    teacher_user, headers = teacher
    class_ = await class_factory(teacher_id=teacher_user.id)
    await user_factory(email="newbie@test.edu", full_name="Newbie")

    resp = await client.post(
        f"/api/v1/classes/{class_.id}/students",
        headers=headers,
        json={"email": "NEWBIE@test.edu"},
    )
    assert resp.status_code == 201
    assert resp.json()["full_name"] == "Newbie"

    resp = await client.get(f"/api/v1/classes/{class_.id}/students", headers=headers)
    assert len(resp.json()) == 1


async def test_enrolling_an_unknown_email_is_404(client, teacher, class_factory):
    teacher_user, headers = teacher
    class_ = await class_factory(teacher_id=teacher_user.id)

    resp = await client.post(
        f"/api/v1/classes/{class_.id}/students",
        headers=headers,
        json={"email": "nobody@test.edu"},
    )
    assert resp.status_code == 404


async def test_only_students_can_be_enrolled(client, teacher, class_factory, user_factory):
    teacher_user, headers = teacher
    class_ = await class_factory(teacher_id=teacher_user.id)
    await user_factory(email="colleague@test.edu", role=UserRole.TEACHER)

    resp = await client.post(
        f"/api/v1/classes/{class_.id}/students",
        headers=headers,
        json={"email": "colleague@test.edu"},
    )
    assert resp.status_code == 422


async def test_enrolling_twice_is_a_conflict(client, teacher, class_factory, user_factory):
    teacher_user, headers = teacher
    class_ = await class_factory(teacher_id=teacher_user.id)
    await user_factory(email="dup@test.edu", class_id=class_.id)

    resp = await client.post(
        f"/api/v1/classes/{class_.id}/students", headers=headers, json={"email": "dup@test.edu"}
    )
    assert resp.status_code == 409


async def test_unenrol_a_student(client, teacher, class_factory, user_factory):
    teacher_user, headers = teacher
    class_ = await class_factory(teacher_id=teacher_user.id)
    student_user = await user_factory(email="leaver@test.edu", class_id=class_.id)

    resp = await client.delete(
        f"/api/v1/classes/{class_.id}/students/{student_user.id}", headers=headers
    )
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/classes/{class_.id}/students", headers=headers)
    assert resp.json() == []


async def test_unenrolling_a_student_from_another_class_is_404(
    client, teacher, class_factory, user_factory
):
    """Reported against the class, so a teacher cannot probe for accounts."""
    teacher_user, headers = teacher
    class_ = await class_factory(teacher_id=teacher_user.id)
    outsider = await user_factory(email="outsider@test.edu")

    resp = await client.delete(
        f"/api/v1/classes/{class_.id}/students/{outsider.id}", headers=headers
    )
    assert resp.status_code == 404


async def test_teacher_cannot_read_another_teachers_roster(
    client, teacher, other_teacher, class_factory
):
    _, headers = teacher
    other_user, _ = other_teacher
    class_ = await class_factory(teacher_id=other_user.id)

    resp = await client.get(f"/api/v1/classes/{class_.id}/students", headers=headers)
    assert resp.status_code == 403


# ── Student self-enrolment ───────────────────────────────────────────────────


async def test_student_joins_with_a_code(client, teacher, class_factory, student):
    teacher_user, _ = teacher
    _, student_headers = student
    await class_factory(teacher_id=teacher_user.id, code="ENG201B", name="English 201B")

    resp = await client.post(
        "/api/v1/classes/join", headers=student_headers, json={"code": "eng201b"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "English 201B"
    assert resp.json()["student_count"] == 1


async def test_joining_with_a_bad_code_fails(client, student):
    _, headers = student
    resp = await client.post("/api/v1/classes/join", headers=headers, json={"code": "NOSUCH01"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CLASS_CODE_INVALID"


async def test_an_inactive_class_reads_as_a_bad_code(client, teacher, class_factory, student):
    """Otherwise a guessed code would confirm that the class exists."""
    teacher_user, _ = teacher
    _, student_headers = student
    await class_factory(teacher_id=teacher_user.id, code="ENG201B", is_active=False)

    resp = await client.post(
        "/api/v1/classes/join", headers=student_headers, json={"code": "ENG201B"}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CLASS_CODE_INVALID"


async def test_teachers_may_not_join_a_class_as_a_student(client, teacher, class_factory):
    teacher_user, headers = teacher
    await class_factory(teacher_id=teacher_user.id, code="ENG201B")

    resp = await client.post("/api/v1/classes/join", headers=headers, json={"code": "ENG201B"})
    assert resp.status_code == 403


async def test_joining_a_second_class_moves_the_student(client, teacher, class_factory, student):
    teacher_user, _ = teacher
    _, student_headers = student
    await class_factory(teacher_id=teacher_user.id, code="FIRST001", name="First")
    second = await class_factory(teacher_id=teacher_user.id, code="SECOND01", name="Second")

    await client.post("/api/v1/classes/join", headers=student_headers, json={"code": "FIRST001"})
    resp = await client.post(
        "/api/v1/classes/join", headers=student_headers, json={"code": "SECOND01"}
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(second.id)
    assert resp.json()["student_count"] == 1


# ── Counts ───────────────────────────────────────────────────────────────────


async def test_student_count_ignores_deactivated_accounts(
    client, teacher, class_factory, user_factory
):
    teacher_user, headers = teacher
    class_ = await class_factory(teacher_id=teacher_user.id)
    await user_factory(email="active@test.edu", class_id=class_.id)
    await user_factory(email="gone@test.edu", class_id=class_.id, is_active=False)

    resp = await client.get(f"/api/v1/classes/{class_.id}", headers=headers)
    assert resp.json()["student_count"] == 1
