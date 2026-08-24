"""The submission pipeline: opening an attempt, getting text in, marking it.

The OCR chain is a deterministic fake throughout — these tests are about the
state machine and the access rules, not about how well any engine reads
handwriting, which is covered in ``test_ocr.py``.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.api.deps import get_ocr_service
from app.core.exceptions import OCRError
from app.main import app as fastapi_app
from app.models.enums import UserRole
from app.ocr.base import OCRBlock, OCRResult
from app.ocr.chain import OCRChain
from app.services.ocr import OCRService
from app.storage.local import LocalStorage

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("spacy_model")]

SUBMISSIONS = "/api/v1/submissions"

HANDWRITTEN = (
    "The line graph illustrates the amount of electricity generated from three "
    "renewable sources. Solar output rose steadily across the period while "
    "hydroelectric generation remained stable throughout."
)


# ── Fakes and fixtures ───────────────────────────────────────────────────────


class FakeProvider:
    def __init__(self, name="easyocr", *, available=True, text=HANDWRITTEN, confidence=0.91):
        self.name = name
        self._available = available
        self._text = text
        self._confidence = confidence

    def is_available(self):
        return self._available

    def extract(self, image: bytes) -> OCRResult:
        if self._text is None:
            raise OCRError("Every provider failed.")
        return OCRResult(
            text=self._text,
            provider=self.name,
            confidence=self._confidence,
            blocks=[OCRBlock(text=self._text, confidence=self._confidence, bbox=(4, 8, 400, 48))],
        )


@pytest.fixture
def ocr_override(tmp_path):
    storage = LocalStorage(str(tmp_path / "storage"), "/media")

    def use(*providers) -> OCRService:
        service = OCRService(OCRChain(list(providers) or [FakeProvider()]), storage)
        fastapi_app.dependency_overrides[get_ocr_service] = lambda: service
        return service

    use()
    yield use
    fastapi_app.dependency_overrides.pop(get_ocr_service, None)


@pytest.fixture
async def teacher(user_factory, auth_headers):
    user = await user_factory(role=UserRole.TEACHER, email="teacher@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def student(user_factory, auth_headers):
    user = await user_factory(role=UserRole.STUDENT, email="student@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def other_student(user_factory, auth_headers):
    user = await user_factory(role=UserRole.STUDENT, email="other@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def admin(user_factory, auth_headers):
    user = await user_factory(role=UserRole.ADMIN, email="admin@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def graph(graph_factory, seeded_vocabulary, teacher):
    """A published line graph with a curated required target set."""
    user, _ = teacher
    required = ["increase", "rise", "decrease", "fluctuate", "stable", "peak"]
    return await graph_factory(
        created_by=user.id,
        graph_type="line",
        targets=[seeded_vocabulary[lemma] for lemma in required],
        reference_description="The line graph illustrates a steady rise in output.",
    )


def image_bytes(fmt="PNG", size=(400, 200)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format=fmt)
    return buffer.getvalue()


def upload_file(data: bytes | None = None, name="answer.png", content_type="image/png"):
    return {"file": (name, data if data is not None else image_bytes(), content_type)}


async def open_submission(client, headers, graph, method="typed"):
    response = await client.post(
        SUBMISSIONS,
        headers=headers,
        json={"graph_id": str(graph.id), "input_method": method},
    )
    assert response.status_code == 201, response.text
    return response.json()


# ── Opening an attempt ───────────────────────────────────────────────────────


async def test_opening_a_submission_starts_it_as_a_draft(client, student, graph):
    _, headers = student
    body = await open_submission(client, headers, graph)

    assert body["status"] == "draft"
    assert body["input_method"] == "typed"
    assert body["graph_id"] == str(graph.id)
    assert body["answer_text"] is None
    assert body["word_count"] == 0
    assert body["score"] is None


async def test_opening_records_the_chosen_input_method(client, student, graph):
    _, headers = student
    body = await open_submission(client, headers, graph, method="handwriting")
    assert body["input_method"] == "handwriting"


async def test_double_tapping_start_reuses_the_pristine_draft(client, student, graph):
    """A student who taps Start twice gets one attempt, not two abandoned rows."""
    _, headers = student
    first = await open_submission(client, headers, graph)
    second = await open_submission(client, headers, graph)
    assert first["id"] == second["id"]


async def test_a_draft_with_work_in_it_is_never_reused(client, student, graph):
    """Reuse must not hand a second attempt someone's half-written answer."""
    _, headers = student
    first = await open_submission(client, headers, graph)
    await client.patch(
        f"{SUBMISSIONS}/{first['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )

    second = await open_submission(client, headers, graph)
    assert second["id"] != first["id"]
    assert second["answer_text"] is None


async def test_a_different_input_method_opens_a_new_attempt(client, student, graph):
    _, headers = student
    typed = await open_submission(client, headers, graph, method="typed")
    written = await open_submission(client, headers, graph, method="handwriting")
    assert typed["id"] != written["id"]


async def test_an_unpublished_graph_cannot_be_attempted(client, student, graph_factory, teacher):
    """A draft graph reads as absent, so it cannot be attempted or enumerated."""
    user, _ = teacher
    _, headers = student
    draft = await graph_factory(created_by=user.id, is_published=False)

    response = await client.post(SUBMISSIONS, headers=headers, json={"graph_id": str(draft.id)})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "GRAPH_NOT_FOUND"


async def test_teachers_do_not_submit(client, teacher, graph):
    """Practice is the students' surface; teachers have the preview endpoint."""
    _, headers = teacher
    response = await client.post(SUBMISSIONS, headers=headers, json={"graph_id": str(graph.id)})
    assert response.status_code == 403


async def test_opening_requires_authentication(client, graph):
    response = await client.post(SUBMISSIONS, json={"graph_id": str(graph.id)})
    assert response.status_code == 401


# ── Setting the answer text ──────────────────────────────────────────────────


async def test_setting_text_records_a_provisional_word_count(client, student, graph):
    _, headers = student
    submission = await open_submission(client, headers, graph)

    response = await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["answer_text"] == HANDWRITTEN
    assert body["word_count"] == len(HANDWRITTEN.split())
    assert body["status"] == "draft"


async def test_blank_text_is_refused(client, student, graph):
    _, headers = student
    submission = await open_submission(client, headers, graph)

    response = await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": "   \n  "}
    )
    assert response.status_code == 422


async def test_another_students_submission_is_not_editable(client, student, other_student, graph):
    _, headers = student
    _, intruder = other_student
    submission = await open_submission(client, headers, graph)

    response = await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=intruder, json={"text": HANDWRITTEN}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SUBMISSION_NOT_FOUND"


# ── Handwriting ──────────────────────────────────────────────────────────────


async def test_upload_extracts_text_and_advances_to_extracted(client, student, graph, ocr_override):
    _, headers = student
    submission = await open_submission(client, headers, graph, method="handwriting")

    response = await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload", headers=headers, files=upload_file()
    )
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "extracted"
    assert body["ocr_text"] == HANDWRITTEN
    assert body["ocr_provider"] == "easyocr"
    assert body["ocr_confidence"] == pytest.approx(0.91, abs=1e-4)
    assert body["word_count"] == len(HANDWRITTEN.split())


async def test_the_machine_reading_survives_the_students_correction(
    client, student, graph, ocr_override
):
    """`ocr_text` and `answer_text` are kept apart so recognition accuracy stays
    measurable after the student has fixed it."""
    _, headers = student
    submission = await open_submission(client, headers, graph, method="handwriting")
    await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload", headers=headers, files=upload_file()
    )

    corrected = HANDWRITTEN.replace("rose steadily", "rose sharply")
    response = await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": corrected}
    )

    body = response.json()
    assert body["answer_text"] == corrected
    assert body["ocr_text"] == HANDWRITTEN
    assert body["was_ocr_edited"] is True


async def test_reflowing_whitespace_is_not_counted_as_a_correction(
    client, student, graph, ocr_override
):
    """The flag measures how often recognition needed fixing; counting cosmetic
    changes would make the OCR look worse than it is."""
    _, headers = student
    submission = await open_submission(client, headers, graph, method="handwriting")
    await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload", headers=headers, files=upload_file()
    )

    reflowed = HANDWRITTEN.replace(" ", "\n  ")
    response = await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": reflowed}
    )
    assert response.json()["was_ocr_edited"] is False


async def test_accepting_the_reading_unchanged_is_not_an_edit(client, student, graph, ocr_override):
    _, headers = student
    submission = await open_submission(client, headers, graph, method="handwriting")
    response = await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload", headers=headers, files=upload_file()
    )
    assert response.json()["status"] == "extracted"

    detail = await client.get(f"{SUBMISSIONS}/{submission['id']}", headers=headers)
    assert detail.json()["was_ocr_edited"] is False


async def test_typing_over_an_empty_reading_is_not_a_correction(
    client, student, graph, ocr_override
):
    """A blank page reads as empty-but-successful, so the student types the whole
    answer. That is recognition *failing*, not recognition being *inaccurate* —
    counting it as an edit would conflate two different findings about the OCR
    chain when the accuracy figures are computed.
    """
    _, headers = student
    ocr_override(FakeProvider(text="   "))
    submission = await open_submission(client, headers, graph, method="handwriting")

    extracted = await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload", headers=headers, files=upload_file()
    )
    assert extracted.status_code == 200
    assert extracted.json()["warning"]

    # Nothing was read, so there is nothing to score yet.
    empty = await client.post(f"{SUBMISSIONS}/{submission['id']}/analyze", headers=headers)
    assert empty.status_code == 409
    assert empty.json()["error"]["code"] == "SUBMISSION_NOT_READY"

    typed = await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )
    assert typed.json()["was_ocr_edited"] is False
    assert typed.json()["answer_text"] == HANDWRITTEN


async def test_a_typed_submission_has_no_image_to_read(client, student, graph, ocr_override):
    _, headers = student
    submission = await open_submission(client, headers, graph, method="typed")

    response = await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload", headers=headers, files=upload_file()
    )
    assert response.status_code == 422


async def test_upload_is_refused_when_no_engine_is_configured(client, student, graph, ocr_override):
    _, headers = student
    ocr_override(FakeProvider(available=False))
    submission = await open_submission(client, headers, graph, method="handwriting")

    response = await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload", headers=headers, files=upload_file()
    )
    assert response.status_code == 503


async def test_a_failed_reading_is_persisted_with_the_image(client, student, graph, ocr_override):
    """The failure has to survive the error that reports it — otherwise the
    request-scoped rollback erases the `failed` status and the retained image
    is never recorded against the submission."""
    _, headers = student
    ocr_override(FakeProvider(text=None))
    submission = await open_submission(client, headers, graph, method="handwriting")

    response = await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload", headers=headers, files=upload_file()
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "OCR_FAILED"

    detail = (await client.get(f"{SUBMISSIONS}/{submission['id']}", headers=headers)).json()
    assert detail["status"] == "failed"
    assert detail["error_message"]
    assert detail["has_image"] is True


async def test_the_storage_key_is_never_leaked_to_the_client(client, student, graph, ocr_override):
    _, headers = student
    ocr_override(FakeProvider(text=None))
    submission = await open_submission(client, headers, graph, method="handwriting")

    response = await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload", headers=headers, files=upload_file()
    )
    assert response.json()["error"]["details"] == {}


async def test_a_student_can_type_their_way_out_of_a_failed_reading(
    client, student, graph, ocr_override
):
    """FR-4.9: recovery must not require photographing the page again."""
    _, headers = student
    ocr_override(FakeProvider(text=None))
    submission = await open_submission(client, headers, graph, method="handwriting")
    await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload", headers=headers, files=upload_file()
    )

    response = await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "draft"
    assert body["error_message"] is None
    # The research record still shows that handwriting was attempted.
    assert body["input_method"] == "handwriting"


async def test_something_that_is_not_an_image_is_refused(client, student, graph, ocr_override):
    """Validated by signature bytes, not by the filename the client claimed."""
    _, headers = student
    submission = await open_submission(client, headers, graph, method="handwriting")

    response = await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload",
        headers=headers,
        files=upload_file(b"not an image at all"),
    )
    assert response.status_code == 415

    detail = (await client.get(f"{SUBMISSIONS}/{submission['id']}", headers=headers)).json()
    assert detail["has_image"] is False


# ── Analysis ─────────────────────────────────────────────────────────────────


async def test_analyzing_scores_the_submission_and_freezes_it(client, student, graph):
    _, headers = student
    submission = await open_submission(client, headers, graph)
    await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )

    response = await client.post(f"{SUBMISSIONS}/{submission['id']}/analyze", headers=headers)
    assert response.status_code == 200

    body = response.json()
    assert body["submission"]["status"] == "scored"
    assert body["submission"]["scored_at"]
    assert 0 <= body["score"]["final_score"] <= 100
    assert body["score"]["reward_tier"] in {"crown", "flower", "steady", "hammer"}
    assert body["score"]["engine_version"]


async def test_the_word_count_becomes_the_one_that_was_scored(client, student, graph):
    """The provisional count is replaced by what the parser actually counted, so
    the number beside the length component is the number it was computed from."""
    _, headers = student
    submission = await open_submission(client, headers, graph)
    await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )

    body = (await client.post(f"{SUBMISSIONS}/{submission['id']}/analyze", headers=headers)).json()
    assert body["submission"]["word_count"] == body["score"]["writing_breakdown"]["word_count"]


async def test_the_denominator_is_frozen_at_the_time_of_scoring(client, student, graph):
    """A teacher adding a target term next week must not move a stored score."""
    _, headers = student
    submission = await open_submission(client, headers, graph)
    await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )

    body = (await client.post(f"{SUBMISSIONS}/{submission['id']}/analyze", headers=headers)).json()
    assert body["score"]["total_target_count"] == 6


async def test_the_model_answer_is_released_once_the_attempt_is_marked(client, student, graph):
    _, headers = student
    submission = await open_submission(client, headers, graph)

    before = (await client.get(f"{SUBMISSIONS}/{submission['id']}", headers=headers)).json()
    assert before.get("reference_description") is None

    await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )
    after = (await client.post(f"{SUBMISSIONS}/{submission['id']}/analyze", headers=headers)).json()
    assert after["reference_description"] == graph.reference_description


async def test_re_analysis_is_refused(client, student, graph):
    """Re-marking would award a second score — and, from Sprint 7, second XP —
    for one piece of work."""
    _, headers = student
    submission = await open_submission(client, headers, graph)
    await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )
    await client.post(f"{SUBMISSIONS}/{submission['id']}/analyze", headers=headers)

    again = await client.post(f"{SUBMISSIONS}/{submission['id']}/analyze", headers=headers)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "SUBMISSION_ALREADY_SCORED"


async def test_a_scored_submission_cannot_be_rewritten(client, student, graph):
    _, headers = student
    submission = await open_submission(client, headers, graph)
    await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )
    await client.post(f"{SUBMISSIONS}/{submission['id']}/analyze", headers=headers)

    response = await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": "Rewritten."}
    )
    assert response.status_code == 409


async def test_analyzing_an_empty_submission_is_refused(client, student, graph):
    _, headers = student
    submission = await open_submission(client, headers, graph)

    response = await client.post(f"{SUBMISSIONS}/{submission['id']}/analyze", headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SUBMISSION_NOT_READY"


async def test_analyzing_someone_elses_submission_reads_as_missing(
    client, student, other_student, graph
):
    _, headers = student
    _, intruder = other_student
    submission = await open_submission(client, headers, graph)
    await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )

    response = await client.post(f"{SUBMISSIONS}/{submission['id']}/analyze", headers=intruder)
    assert response.status_code == 404


async def test_the_gamification_block_is_present_before_the_engine_lands(client, student, graph):
    """The result screen's contract must not change when Sprint 7 fills this in."""
    _, headers = student
    submission = await open_submission(client, headers, graph)
    await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )

    body = (await client.post(f"{SUBMISSIONS}/{submission['id']}/analyze", headers=headers)).json()
    assert body["gamification"] == {
        "xp_awarded": 0,
        "xp_breakdown": [],
        "level_before": 1,
        "level_after": 1,
        "leveled_up": False,
        "badge": None,
        "new_achievements": [],
        "streak_days": 0,
    }


# ── Reading ──────────────────────────────────────────────────────────────────


async def test_a_student_sees_only_their_own_attempts(client, student, other_student, graph):
    _, headers = student
    _, other = other_student
    await open_submission(client, headers, graph)
    await open_submission(client, other, graph)

    body = (await client.get(SUBMISSIONS, headers=headers)).json()
    assert body["total"] == 1


async def test_a_student_cannot_read_another_students_submission(
    client, student, other_student, graph
):
    _, headers = student
    _, intruder = other_student
    submission = await open_submission(client, headers, graph)

    response = await client.get(f"{SUBMISSIONS}/{submission['id']}", headers=intruder)
    assert response.status_code == 404


async def test_a_teacher_sees_their_own_classes_work(
    client, student, other_student, teacher, graph, class_factory, db
):
    teacher_user, teacher_headers = teacher
    enrolled, enrolled_headers = student
    _, outsider_headers = other_student

    cohort = await class_factory(teacher_id=teacher_user.id)
    enrolled.class_id = cohort.id
    await db.flush()

    await open_submission(client, enrolled_headers, graph)
    await open_submission(client, outsider_headers, graph)

    body = (await client.get(SUBMISSIONS, headers=teacher_headers)).json()
    assert body["total"] == 1
    assert body["items"][0]["user_id"] == str(enrolled.id)


async def test_a_teacher_with_no_classes_sees_nothing(client, student, teacher, graph):
    _, student_headers = student
    _, teacher_headers = teacher
    await open_submission(client, student_headers, graph)

    body = (await client.get(SUBMISSIONS, headers=teacher_headers)).json()
    assert body["total"] == 0


async def test_an_administrator_sees_everything(client, student, other_student, admin, graph):
    _, first = student
    _, second = other_student
    _, admin_headers = admin
    await open_submission(client, first, graph)
    await open_submission(client, second, graph)

    body = (await client.get(SUBMISSIONS, headers=admin_headers)).json()
    assert body["total"] == 2


async def test_a_student_cannot_widen_the_listing_with_a_filter(
    client, student, other_student, graph
):
    """The scoping is applied before any filter, so `student_id` cannot be used
    to read someone else's work."""
    _, headers = student
    other, other_headers = other_student
    await open_submission(client, headers, graph)
    await open_submission(client, other_headers, graph)

    body = (await client.get(f"{SUBMISSIONS}?student_id={other.id}", headers=headers)).json()
    assert body["total"] == 1
    assert body["items"][0]["user_id"] != str(other.id)


async def test_the_listing_can_be_narrowed_to_marked_attempts(client, student, graph):
    _, headers = student
    scored = await open_submission(client, headers, graph)
    await client.patch(
        f"{SUBMISSIONS}/{scored['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )
    await client.post(f"{SUBMISSIONS}/{scored['id']}/analyze", headers=headers)

    body = (await client.get(f"{SUBMISSIONS}?scored_only=true", headers=headers)).json()
    assert body["total"] == 1
    assert body["items"][0]["reward_tier"]
    assert body["items"][0]["final_score"] is not None


async def test_the_listing_can_be_narrowed_by_reward_tier(client, student, graph):
    _, headers = student
    submission = await open_submission(client, headers, graph)
    await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )
    tier = (await client.post(f"{SUBMISSIONS}/{submission['id']}/analyze", headers=headers)).json()[
        "score"
    ]["reward_tier"]

    match = (await client.get(f"{SUBMISSIONS}?reward_tier={tier}", headers=headers)).json()
    assert match["total"] == 1

    others = {"crown", "flower", "steady", "hammer"} - {tier}
    for other in others:
        empty = (await client.get(f"{SUBMISSIONS}?reward_tier={other}", headers=headers)).json()
        assert empty["total"] == 0


async def test_the_listing_can_be_narrowed_by_graph_and_status(
    client, student, graph, graph_factory, teacher, seeded_vocabulary
):
    user, _ = teacher
    _, headers = student
    other_graph = await graph_factory(created_by=user.id, targets=[seeded_vocabulary["increase"]])
    await open_submission(client, headers, graph)
    await open_submission(client, headers, other_graph)

    by_graph = (await client.get(f"{SUBMISSIONS}?graph_id={graph.id}", headers=headers)).json()
    assert by_graph["total"] == 1
    assert by_graph["items"][0]["graph_id"] == str(graph.id)

    by_status = (await client.get(f"{SUBMISSIONS}?status=draft", headers=headers)).json()
    assert by_status["total"] == 2
    assert (await client.get(f"{SUBMISSIONS}?status=scored", headers=headers)).json()["total"] == 0


async def test_a_teacher_can_narrow_to_one_student_and_one_class(
    client, student, other_student, teacher, graph, class_factory, db
):
    teacher_user, teacher_headers = teacher
    first, first_headers = student
    second, second_headers = other_student

    cohort = await class_factory(teacher_id=teacher_user.id, code="COHORT1")
    other_cohort = await class_factory(teacher_id=teacher_user.id, code="COHORT2")
    first.class_id = cohort.id
    second.class_id = other_cohort.id
    await db.flush()

    await open_submission(client, first_headers, graph)
    await open_submission(client, second_headers, graph)

    assert (await client.get(SUBMISSIONS, headers=teacher_headers)).json()["total"] == 2

    by_student = (
        await client.get(f"{SUBMISSIONS}?student_id={first.id}", headers=teacher_headers)
    ).json()
    assert by_student["total"] == 1
    assert by_student["items"][0]["user_id"] == str(first.id)

    by_class = (
        await client.get(f"{SUBMISSIONS}?class_id={other_cohort.id}", headers=teacher_headers)
    ).json()
    assert by_class["total"] == 1
    assert by_class["items"][0]["user_id"] == str(second.id)


async def test_a_teacher_can_open_their_own_students_submission(
    client, student, teacher, graph, class_factory, db
):
    teacher_user, teacher_headers = teacher
    enrolled, enrolled_headers = student
    cohort = await class_factory(teacher_id=teacher_user.id)
    enrolled.class_id = cohort.id
    await db.flush()

    submission = await open_submission(client, enrolled_headers, graph)

    response = await client.get(f"{SUBMISSIONS}/{submission['id']}", headers=teacher_headers)
    assert response.status_code == 200
    assert response.json()["student_name"] == enrolled.full_name


async def test_a_teacher_cannot_open_another_teachers_students_work(
    client, student, teacher, user_factory, auth_headers, graph, class_factory, db
):
    """Teaching nobody, or teaching a different cohort, means seeing nothing."""
    teacher_user, _ = teacher
    enrolled, enrolled_headers = student
    cohort = await class_factory(teacher_id=teacher_user.id)
    enrolled.class_id = cohort.id
    await db.flush()

    stranger = await user_factory(role=UserRole.TEACHER, email="stranger@test.edu")
    submission = await open_submission(client, enrolled_headers, graph)

    response = await client.get(f"{SUBMISSIONS}/{submission['id']}", headers=auth_headers(stranger))
    assert response.status_code == 404


async def test_an_administrator_can_open_any_submission(client, student, admin, graph):
    _, headers = student
    _, admin_headers = admin
    submission = await open_submission(client, headers, graph)

    response = await client.get(f"{SUBMISSIONS}/{submission['id']}", headers=admin_headers)
    assert response.status_code == 200


async def test_a_teacher_sees_the_model_answer_before_marking(
    client, student, teacher, graph, class_factory, db
):
    """Withholding it is about not handing a student the answer mid-exercise;
    it was never a secret from staff."""
    teacher_user, teacher_headers = teacher
    enrolled, enrolled_headers = student
    cohort = await class_factory(teacher_id=teacher_user.id)
    enrolled.class_id = cohort.id
    await db.flush()

    submission = await open_submission(client, enrolled_headers, graph)

    body = (await client.get(f"{SUBMISSIONS}/{submission['id']}", headers=teacher_headers)).json()
    assert body["reference_description"] == graph.reference_description


async def test_listing_requires_authentication(client):
    assert (await client.get(SUBMISSIONS)).status_code == 401


# ── The uploaded image ───────────────────────────────────────────────────────


async def test_the_image_streams_back_to_its_owner(client, student, graph, ocr_override):
    _, headers = student
    submission = await open_submission(client, headers, graph, method="handwriting")
    await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload", headers=headers, files=upload_file()
    )

    response = await client.get(f"{SUBMISSIONS}/{submission['id']}/image", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"


async def test_one_students_handwriting_is_not_readable_by_another(
    client, student, other_student, graph, ocr_override
):
    _, headers = student
    _, intruder = other_student
    submission = await open_submission(client, headers, graph, method="handwriting")
    await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload", headers=headers, files=upload_file()
    )

    response = await client.get(f"{SUBMISSIONS}/{submission['id']}/image", headers=intruder)
    assert response.status_code == 404


async def test_the_image_endpoint_requires_a_token(client, student, graph, ocr_override):
    """It is not a static path — a browser `<img src>` will not carry the token,
    and that is what stops one student reading another's page by URL."""
    _, headers = student
    submission = await open_submission(client, headers, graph, method="handwriting")
    await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload", headers=headers, files=upload_file()
    )

    assert (await client.get(f"{SUBMISSIONS}/{submission['id']}/image")).status_code == 401


async def test_a_row_pointing_at_a_missing_file_reports_absent_not_broken(
    client, student, graph, ocr_override, tmp_path
):
    """A database restored without its storage volume. Nothing is going to fix
    that by retrying, so it is 404 rather than a 500."""
    _, headers = student
    submission = await open_submission(client, headers, graph, method="handwriting")
    await client.post(
        f"{SUBMISSIONS}/{submission['id']}/upload", headers=headers, files=upload_file()
    )

    for stored in (tmp_path / "storage").rglob("*.png"):
        stored.unlink()

    response = await client.get(f"{SUBMISSIONS}/{submission['id']}/image", headers=headers)
    assert response.status_code == 404


async def test_a_typed_submission_has_no_image(client, student, graph):
    _, headers = student
    submission = await open_submission(client, headers, graph)

    response = await client.get(f"{SUBMISSIONS}/{submission['id']}/image", headers=headers)
    assert response.status_code == 404


# ── Discarding ───────────────────────────────────────────────────────────────


async def test_an_unscored_draft_can_be_discarded(client, student, graph):
    _, headers = student
    submission = await open_submission(client, headers, graph)

    assert (
        await client.delete(f"{SUBMISSIONS}/{submission['id']}", headers=headers)
    ).status_code == 204
    assert (
        await client.get(f"{SUBMISSIONS}/{submission['id']}", headers=headers)
    ).status_code == 404


async def test_a_scored_submission_cannot_be_discarded(client, student, graph):
    """It carries awarded XP and counts towards achievements; deleting it would
    leave the ledger describing work that no longer exists."""
    _, headers = student
    submission = await open_submission(client, headers, graph)
    await client.patch(
        f"{SUBMISSIONS}/{submission['id']}/text", headers=headers, json={"text": HANDWRITTEN}
    )
    await client.post(f"{SUBMISSIONS}/{submission['id']}/analyze", headers=headers)

    response = await client.delete(f"{SUBMISSIONS}/{submission['id']}", headers=headers)
    assert response.status_code == 409


async def test_one_student_cannot_discard_anothers_attempt(client, student, other_student, graph):
    _, headers = student
    _, intruder = other_student
    submission = await open_submission(client, headers, graph)

    response = await client.delete(f"{SUBMISSIONS}/{submission['id']}", headers=intruder)
    assert response.status_code == 404
