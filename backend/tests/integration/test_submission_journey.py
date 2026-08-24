"""The whole student journey, on real seeded content.

Every other test stubs something. This one seeds the actual vocabulary library
and the actual sample graphs, then walks a student through both routes end to
end — because the pieces passing individually is not the same as the flow
working.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.api.deps import get_ocr_service
from app.main import app as fastapi_app
from app.models.enums import UserRole
from app.ocr.base import OCRBlock, OCRResult
from app.ocr.chain import OCRChain
from app.services.ocr import OCRService
from app.storage.local import LocalStorage

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("spacy_model")]

SUBMISSIONS = "/api/v1/submissions"

# Deliberately misread. "rows" for "rose" matters: `rise` is one of this
# graph's target terms, so the misreading silently costs the student a mark
# they earned. Correcting it is the whole point of the step FR-4.7 requires.
MISREAD = (
    "The line graph illustrates the amount of electricity generated from three "
    "renewable sources between 2010 and 2022. Solar output rows steadily across "
    "the whole period, reaching its peak in the final year. Hydroelectric "
    "generation remained stabel throughout, while wind power fluctuated a little "
    "before increasing towards the end of the period shown."
)
CORRECTED = MISREAD.replace("rows steadily", "rose steadily").replace("stabel", "stable")


class ReplayProvider:
    name = "easyocr"

    def is_available(self):
        return True

    def extract(self, image: bytes) -> OCRResult:
        return OCRResult(
            text=MISREAD,
            provider=self.name,
            confidence=0.52,
            blocks=[OCRBlock(text=MISREAD, confidence=0.52, bbox=(0, 0, 800, 300))],
        )


@pytest.fixture
def ocr_override(tmp_path):
    service = OCRService(OCRChain([ReplayProvider()]), LocalStorage(str(tmp_path), "/media"))
    fastapi_app.dependency_overrides[get_ocr_service] = lambda: service
    yield service
    fastapi_app.dependency_overrides.pop(get_ocr_service, None)


@pytest.fixture
async def seeded_graph(db, seeded_vocabulary, user_factory):
    """A real sample graph, with the target set the seed data actually ships."""
    from sqlalchemy import select

    from app.db.seed.runner import seed_graphs
    from app.models.content import Graph

    author = await user_factory(role=UserRole.TEACHER, email="seed-author@test.edu")
    await seed_graphs(db, author_id=author.id)

    graph = (
        await db.execute(select(Graph).where(Graph.graph_type == "line").limit(1))
    ).scalar_one()
    return graph


@pytest.fixture
async def student(user_factory, auth_headers):
    user = await user_factory(role=UserRole.STUDENT, email="journey@test.edu")
    return user, auth_headers(user)


def image_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (800, 300), "white").save(buffer, format="PNG")
    return buffer.getvalue()


async def test_the_typed_route_end_to_end(client, student, seeded_graph, db):
    """Open, write, mark — and the model answer arrives only at the end."""
    _, headers = student

    opened = await client.post(
        SUBMISSIONS,
        headers=headers,
        json={"graph_id": str(seeded_graph.id), "input_method": "typed"},
    )
    assert opened.status_code == 201
    submission_id = opened.json()["id"]

    written = await client.patch(
        f"{SUBMISSIONS}/{submission_id}/text",
        headers=headers,
        json={"text": seeded_graph.reference_description},
    )
    assert written.status_code == 200
    assert written.json()["status"] == "draft"

    marked = await client.post(f"{SUBMISSIONS}/{submission_id}/analyze", headers=headers)
    assert marked.status_code == 200
    body = marked.json()

    # The seeded model answer is curated to use its own target list, so it
    # should reach the top tier. If this ever fails, the seed content and the
    # target list have drifted apart — which is a content bug, not a test bug.
    assert body["score"]["vocabulary_percentage"] == 100.0
    assert body["score"]["reward_tier"] == "crown"
    assert body["submission"]["status"] == "scored"
    assert body["reference_description"] == seeded_graph.reference_description
    assert body["score"]["feedback"]["headline"]

    listed = (await client.get(f"{SUBMISSIONS}?scored_only=true", headers=headers)).json()
    assert listed["total"] == 1
    assert listed["items"][0]["reward_tier"] == "crown"


async def test_the_handwriting_route_end_to_end(client, student, seeded_graph, ocr_override):
    """Photograph, read, correct, mark — with the raw reading preserved."""
    _, headers = student

    opened = await client.post(
        SUBMISSIONS,
        headers=headers,
        json={"graph_id": str(seeded_graph.id), "input_method": "handwriting"},
    )
    submission_id = opened.json()["id"]

    extracted = await client.post(
        f"{SUBMISSIONS}/{submission_id}/upload",
        headers=headers,
        files={"file": ("page.png", image_bytes(), "image/png")},
    )
    assert extracted.status_code == 200
    preview = extracted.json()
    assert preview["status"] == "extracted"
    assert preview["ocr_text"] == MISREAD
    # Under the low-confidence threshold, so the student is told to read it
    # carefully rather than accept it — which is what makes the fix likely.
    assert "check the text below carefully" in preview["warning"]

    corrected = await client.patch(
        f"{SUBMISSIONS}/{submission_id}/text", headers=headers, json={"text": CORRECTED}
    )
    assert corrected.json()["was_ocr_edited"] is True

    marked = await client.post(f"{SUBMISSIONS}/{submission_id}/analyze", headers=headers)
    assert marked.status_code == 200
    body = marked.json()
    assert body["submission"]["status"] == "scored"

    # The correction earned a mark: `rise` is a target term, and the misreading
    # ("rows") does not match it. The companion test below shows the same text
    # uncorrected scoring lower, so this is the fix paying off, not a fluke.
    detected = {term["term"].lower() for term in body["score"]["detected_terms"]}
    assert "rise" in detected

    # And the machine's own reading survives for the accuracy analysis.
    detail = (await client.get(f"{SUBMISSIONS}/{submission_id}", headers=headers)).json()
    assert detail["ocr_text"] == MISREAD
    assert detail["answer_text"] == CORRECTED
    assert detail["was_ocr_edited"] is True
    assert detail["has_image"] is True


async def test_the_uncorrected_reading_would_have_scored_lower(client, student, seeded_graph):
    """The other half of the claim above: submitting what the recogniser
    produced, without fixing it, misses the term the correction recovered.

    This is what the editable preview is worth in marks — and why a pipeline
    that scored `ocr_text` directly would systematically under-credit students
    whose handwriting is merely untidy.
    """
    _, headers = student

    opened = (
        await client.post(SUBMISSIONS, headers=headers, json={"graph_id": str(seeded_graph.id)})
    ).json()
    await client.patch(
        f"{SUBMISSIONS}/{opened['id']}/text", headers=headers, json={"text": MISREAD}
    )
    body = (await client.post(f"{SUBMISSIONS}/{opened['id']}/analyze", headers=headers)).json()

    detected = {term["term"].lower() for term in body["score"]["detected_terms"]}
    assert "rise" not in detected
    assert "rise" in {term["term"].lower() for term in body["score"]["missing_terms"]}


async def test_a_second_attempt_is_a_second_submission(client, student, seeded_graph):
    """History is never overwritten — improvement across attempts is the data
    the project's evaluation depends on."""
    _, headers = student

    first = (
        await client.post(SUBMISSIONS, headers=headers, json={"graph_id": str(seeded_graph.id)})
    ).json()
    await client.patch(
        f"{SUBMISSIONS}/{first['id']}/text",
        headers=headers,
        json={"text": "The graph go up. Then it go down a lot. That is all I can see here."},
    )
    weak = (await client.post(f"{SUBMISSIONS}/{first['id']}/analyze", headers=headers)).json()

    second = (
        await client.post(SUBMISSIONS, headers=headers, json={"graph_id": str(seeded_graph.id)})
    ).json()
    assert second["id"] != first["id"]

    await client.patch(
        f"{SUBMISSIONS}/{second['id']}/text",
        headers=headers,
        json={"text": seeded_graph.reference_description},
    )
    strong = (await client.post(f"{SUBMISSIONS}/{second['id']}/analyze", headers=headers)).json()

    assert strong["score"]["final_score"] > weak["score"]["final_score"]

    history = (await client.get(f"{SUBMISSIONS}?scored_only=true", headers=headers)).json()
    assert history["total"] == 2
