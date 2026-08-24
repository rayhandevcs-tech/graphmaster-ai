"""Generating, downloading and scoping CSV / Excel / PDF exports.

An export is the easiest place to hand a teacher another teacher's class,
because nobody reads a spreadsheet the way they read a page. So most of these
are about who may ask for what, and the rest are about the file that comes back
actually containing the right rows.
"""

from __future__ import annotations

import csv
import io
import uuid

import pytest

from app.core.exceptions import ServiceUnavailableError
from app.models.enums import UserRole

pytestmark = pytest.mark.anyio

REPORTS = "/api/v1/reports"


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
    return await class_factory(teacher_id=user.id, code="REPORT1")


@pytest.fixture
async def graph(graph_factory, teacher):
    user, _ = teacher
    return await graph_factory(created_by=user.id, title="Solar output")


@pytest.fixture
async def student(user_factory, cohort):
    return await user_factory(email="pupil@test.edu", full_name="Ada Lovelace", class_id=cohort.id)


@pytest.fixture
async def marked(scored_submission_factory, student, graph):
    return await scored_submission_factory(user=student, graph=graph, final_score=82.5)


def rows_of(payload: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(payload.decode("utf-8-sig"))))


async def generate(client, headers, **body) -> dict:
    response = await client.post(REPORTS, headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


# ── Capabilities ─────────────────────────────────────────────────────────────


async def test_csv_is_always_offered(client, teacher):
    """It needs nothing beyond the standard library."""
    _, headers = teacher

    body = (await client.get(f"{REPORTS}/capabilities", headers=headers)).json()

    assert "csv" in body["formats"]
    assert set(body["types"]) == {
        "class_summary",
        "student_detail",
        "vocabulary_usage",
        "submission_export",
    }
    assert body["max_rows"] > 0


# ── Generating ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fmt", ["csv", "xlsx", "pdf"])
async def test_a_class_summary_generates_in_every_format(client, teacher, cohort, marked, fmt):
    _, headers = teacher

    report = await generate(
        client, headers, report_type="class_summary", format=fmt, class_id=str(cohort.id)
    )

    assert report["status"] == "ready"
    assert report["download_url"] is not None
    assert report["error_message"] is None
    assert report["completed_at"] is not None


async def test_a_class_summary_contains_the_class_roster(client, teacher, cohort, student, marked):
    _, headers = teacher
    report = await generate(client, headers, report_type="class_summary", class_id=str(cohort.id))

    download = await client.get(f"{REPORTS}/{report['id']}/download", headers=headers)
    rows = rows_of(download.content)

    assert rows[0] == ["Class summary"]
    assert any("Ada Lovelace" in row for row in rows)
    assert any("Marked submissions" in row for row in rows)


async def test_a_submission_export_carries_one_row_per_attempt(
    client, teacher, cohort, student, graph, scored_submission_factory
):
    _, headers = teacher
    for score in (40.0, 60.0, 80.0):
        await scored_submission_factory(user=student, graph=graph, final_score=score)

    report = await generate(
        client, headers, report_type="submission_export", class_id=str(cohort.id)
    )
    download = await client.get(f"{REPORTS}/{report['id']}/download", headers=headers)
    rows = rows_of(download.content)

    data = [row for row in rows if row and row[0] == "Ada Lovelace"]
    assert len(data) == 3


async def test_a_vocabulary_report_lists_the_terms_nobody_used(
    client, teacher, cohort, seeded_vocabulary, marked
):
    _, headers = teacher

    report = await generate(
        client, headers, report_type="vocabulary_usage", class_id=str(cohort.id)
    )
    download = await client.get(f"{REPORTS}/{report['id']}/download", headers=headers)
    rows = rows_of(download.content)

    assert any("Least used" in row for row in rows)
    assert any("Most used" in row for row in rows)


async def test_a_student_report_needs_a_student(client, teacher, cohort):
    _, headers = teacher

    response = await client.post(
        REPORTS,
        headers=headers,
        json={"report_type": "student_detail", "class_id": str(cohort.id)},
    )

    assert response.status_code == 422


async def test_a_student_report_covers_only_that_student(
    client, teacher, cohort, student, graph, user_factory, scored_submission_factory
):
    _, headers = teacher
    classmate = await user_factory(
        email="classmate@test.edu", full_name="Grace Hopper", class_id=cohort.id
    )
    await scored_submission_factory(user=student, graph=graph, final_score=50.0)
    await scored_submission_factory(user=classmate, graph=graph, final_score=95.0)

    report = await generate(
        client, headers, report_type="student_detail", student_id=str(student.id)
    )
    download = await client.get(f"{REPORTS}/{report['id']}/download", headers=headers)
    text = download.content.decode("utf-8-sig")

    assert "Ada Lovelace" in text
    assert "Grace Hopper" not in text


async def test_a_class_summary_without_a_class_is_refused_for_a_teacher(client, teacher):
    """Only an administrator exports across every class."""
    _, headers = teacher

    response = await client.post(REPORTS, headers=headers, json={"report_type": "class_summary"})

    assert response.status_code == 422


async def test_an_admin_may_export_across_every_class(client, admin, marked):
    _, headers = admin

    report = await generate(client, headers, report_type="class_summary")

    assert report["status"] == "ready"


async def test_a_backwards_date_range_is_refused(client, teacher, cohort):
    _, headers = teacher

    response = await client.post(
        REPORTS,
        headers=headers,
        json={
            "report_type": "class_summary",
            "class_id": str(cohort.id),
            "date_from": "2026-08-20",
            "date_to": "2026-08-01",
        },
    )

    assert response.status_code == 422


# ── Scoping ──────────────────────────────────────────────────────────────────


async def test_a_teacher_cannot_export_another_teacher_s_class(
    client, teacher, user_factory, class_factory
):
    other = await user_factory(role=UserRole.TEACHER, email="other-teacher@test.edu")
    theirs = await class_factory(teacher_id=other.id, code="REPORT2")
    _, headers = teacher

    response = await client.post(
        REPORTS,
        headers=headers,
        json={"report_type": "class_summary", "class_id": str(theirs.id)},
    )

    assert response.status_code == 403


async def test_a_teacher_cannot_export_a_student_they_do_not_teach(
    client, teacher, user_factory, class_factory
):
    other = await user_factory(role=UserRole.TEACHER, email="o2@test.edu")
    theirs = await class_factory(teacher_id=other.id, code="REPORT3")
    stranger = await user_factory(email="stranger@test.edu", class_id=theirs.id)
    _, headers = teacher

    response = await client.post(
        REPORTS,
        headers=headers,
        json={"report_type": "student_detail", "student_id": str(stranger.id)},
    )

    assert response.status_code == 422


async def test_a_student_cannot_generate_reports(client, student, auth_headers, cohort):
    response = await client.post(
        REPORTS,
        headers=auth_headers(student),
        json={"report_type": "class_summary", "class_id": str(cohort.id)},
    )

    assert response.status_code == 403


# ── Reading back ─────────────────────────────────────────────────────────────


async def test_a_teacher_sees_only_their_own_reports(
    client, teacher, cohort, marked, user_factory, class_factory, auth_headers
):
    _, headers = teacher
    await generate(client, headers, report_type="class_summary", class_id=str(cohort.id))

    other = await user_factory(role=UserRole.TEACHER, email="o3@test.edu")
    body = (await client.get(REPORTS, headers=auth_headers(other))).json()

    assert body["total"] == 0


async def test_someone_else_s_report_reads_as_missing_not_forbidden(
    client, teacher, cohort, marked, user_factory, auth_headers
):
    """A 403 would confirm that a guessed id names a real report."""
    _, headers = teacher
    report = await generate(client, headers, report_type="class_summary", class_id=str(cohort.id))
    other = await user_factory(role=UserRole.TEACHER, email="o4@test.edu")

    response = await client.get(f"{REPORTS}/{report['id']}", headers=auth_headers(other))

    assert response.status_code == 404


async def test_an_admin_may_read_any_report(client, teacher, admin, cohort, marked):
    _, headers = teacher
    _, admin_headers = admin
    report = await generate(client, headers, report_type="class_summary", class_id=str(cohort.id))

    response = await client.get(f"{REPORTS}/{report['id']}", headers=admin_headers)

    assert response.status_code == 200


async def test_an_unknown_report_is_a_404(client, teacher):
    _, headers = teacher

    assert (await client.get(f"{REPORTS}/{uuid.uuid4()}", headers=headers)).status_code == 404


# ── Downloading ──────────────────────────────────────────────────────────────


async def test_a_download_is_an_attachment_that_no_cache_may_keep(client, teacher, cohort, marked):
    """A shared cache holding a class's scores would defeat the access check."""
    _, headers = teacher
    report = await generate(client, headers, report_type="class_summary", class_id=str(cohort.id))

    response = await client.get(f"{REPORTS}/{report['id']}/download", headers=headers)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert "attachment" in response.headers["content-disposition"]
    assert ".csv" in response.headers["content-disposition"]


async def test_a_workbook_downloads_with_its_own_content_type(client, teacher, cohort, marked):
    _, headers = teacher
    report = await generate(
        client, headers, report_type="class_summary", format="xlsx", class_id=str(cohort.id)
    )

    response = await client.get(f"{REPORTS}/{report['id']}/download", headers=headers)

    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument"
    )
    assert response.content.startswith(b"PK")


async def test_a_download_requires_a_token(client, teacher, cohort, marked):
    _, headers = teacher
    report = await generate(client, headers, report_type="class_summary", class_id=str(cohort.id))

    assert (await client.get(f"{REPORTS}/{report['id']}/download")).status_code == 401


async def test_downloading_another_teacher_s_report_reads_as_missing(
    client, teacher, cohort, marked, user_factory, auth_headers
):
    _, headers = teacher
    report = await generate(client, headers, report_type="class_summary", class_id=str(cohort.id))
    other = await user_factory(role=UserRole.TEACHER, email="o5@test.edu")

    response = await client.get(f"{REPORTS}/{report['id']}/download", headers=auth_headers(other))

    assert response.status_code == 404


# ── Deleting ─────────────────────────────────────────────────────────────────


async def test_deleting_a_report_removes_the_file_too(client, teacher, cohort, marked):
    _, headers = teacher
    report = await generate(client, headers, report_type="class_summary", class_id=str(cohort.id))

    assert (await client.delete(f"{REPORTS}/{report['id']}", headers=headers)).status_code == 204
    assert (await client.get(f"{REPORTS}/{report['id']}", headers=headers)).status_code == 404
    assert (
        await client.get(f"{REPORTS}/{report['id']}/download", headers=headers)
    ).status_code == 404


async def test_a_teacher_cannot_delete_another_teacher_s_report(
    client, teacher, cohort, marked, user_factory, auth_headers
):
    _, headers = teacher
    report = await generate(client, headers, report_type="class_summary", class_id=str(cohort.id))
    other = await user_factory(role=UserRole.TEACHER, email="o6@test.edu")

    response = await client.delete(f"{REPORTS}/{report['id']}", headers=auth_headers(other))

    assert response.status_code == 404


# ── Failure ──────────────────────────────────────────────────────────────────


async def test_a_failed_generation_is_recorded_rather_than_vanishing(
    client, teacher, cohort, marked, monkeypatch
):
    """`failed` has to be a state the code can actually reach.

    The request-scoped session rolls back on any exception, so a status written
    the ordinary way would be erased by the very error reporting it — and the
    teacher would get a bare 500 with no trace of what they asked for. The
    service commits that one record deliberately, exactly as a failed
    handwriting extraction does.
    """
    import app.services.report as module

    def explode(document, fmt):
        # The realistic failure: a format whose optional library is not
        # installed on this server.
        raise ServiceUnavailableError("Excel export is not available on this server.")

    monkeypatch.setattr(module, "render", explode)
    _, headers = teacher

    response = await client.post(
        REPORTS,
        headers=headers,
        json={"report_type": "class_summary", "format": "xlsx", "class_id": str(cohort.id)},
    )
    assert response.status_code == 503

    monkeypatch.undo()
    listing = (await client.get(REPORTS, headers=headers)).json()

    assert listing["total"] == 1
    failed = listing["items"][0]
    assert failed["status"] == "failed"
    assert failed["format"] == "xlsx"
    assert "not available" in failed["error_message"]
    # No file was produced, so there is nothing to offer a download of.
    assert failed["download_url"] is None


async def test_a_failed_report_cannot_be_downloaded(client, teacher, cohort, marked, monkeypatch):
    import app.services.report as module

    def explode(document, fmt):
        raise ServiceUnavailableError("PDF export is not available on this server.")

    monkeypatch.setattr(module, "render", explode)
    _, headers = teacher
    await client.post(
        REPORTS,
        headers=headers,
        json={"report_type": "class_summary", "class_id": str(cohort.id)},
    )
    monkeypatch.undo()

    report_id = (await client.get(REPORTS, headers=headers)).json()["items"][0]["id"]
    response = await client.get(f"{REPORTS}/{report_id}/download", headers=headers)

    assert response.status_code == 404
    assert "failed" in response.json()["error"]["message"]


async def test_a_report_whose_file_has_vanished_reads_as_missing(
    client, teacher, cohort, marked, db
):
    """A restored database without its storage volume, usually.

    Reported as missing rather than as a 500, because nothing is going to fix
    it by retrying.
    """
    from sqlalchemy import select

    from app.models.reporting import TeacherReport

    _, headers = teacher
    report = await generate(client, headers, report_type="class_summary", class_id=str(cohort.id))

    row = (
        await db.execute(select(TeacherReport).where(TeacherReport.id == uuid.UUID(report["id"])))
    ).scalar_one()
    row.file_path = "reports/does-not-exist.csv"
    await db.flush()

    response = await client.get(f"{REPORTS}/{report['id']}/download", headers=headers)

    assert response.status_code == 404
