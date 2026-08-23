"""Handwriting extraction endpoints.

The provider chain is replaced with a deterministic fake throughout: these
tests are about the endpoint's contract — validation, rate limiting, failure
shape — not about how well any particular engine reads handwriting.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.api.deps import get_ocr_service
from app.main import app as fastapi_app
from app.ocr.base import OCRBlock, OCRResult
from app.ocr.chain import OCRChain
from app.services.ocr import OCRService
from app.storage.local import LocalStorage

pytestmark = pytest.mark.anyio

SAMPLE_TEXT = "The line graph illustrates a steady increase in solar output."


class FakeProvider:
    def __init__(
        self, name="easyocr", *, available=True, text=SAMPLE_TEXT, confidence=0.91, error=None
    ):
        self.name = name
        self._available = available
        self._text = text
        self._confidence = confidence
        self._error = error

    def is_available(self):
        return self._available

    def extract(self, image: bytes) -> OCRResult:
        if self._error:
            raise self._error
        return OCRResult(
            text=self._text,
            provider=self.name,
            confidence=self._confidence,
            blocks=[OCRBlock(text=self._text, confidence=self._confidence, bbox=(4, 8, 400, 48))],
        )


@pytest.fixture
def ocr_override(tmp_path):
    """Install a fake OCR service, returning a setter the test can call."""
    storage = LocalStorage(str(tmp_path / "storage"), "/media")

    def use(*providers) -> OCRService:
        service = OCRService(OCRChain(list(providers) or [FakeProvider()]), storage)
        fastapi_app.dependency_overrides[get_ocr_service] = lambda: service
        return service

    use()
    yield use
    fastapi_app.dependency_overrides.pop(get_ocr_service, None)


@pytest.fixture
async def student(user_factory, auth_headers):
    user = await user_factory(email="student@test.edu")
    return user, auth_headers(user)


def image_bytes(fmt="PNG", size=(400, 200)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format=fmt)
    return buffer.getvalue()


def upload(data: bytes, name="answer.png", content_type="image/png"):
    return {"file": (name, data, content_type)}


# ── Status ───────────────────────────────────────────────────────────────────


async def test_status_lists_every_provider(client, ocr_override, student):
    _, headers = student
    ocr_override(FakeProvider("google_vision", available=False), FakeProvider("easyocr"))

    resp = await client.get("/api/v1/ocr/status", headers=headers)
    assert resp.status_code == 200

    body = resp.json()
    assert body["operational"] is True
    assert body["providers"] == [
        {"name": "google_vision", "available": False},
        {"name": "easyocr", "available": True},
    ]


async def test_status_reports_a_server_with_no_engine(client, ocr_override, student):
    """The client hides the upload option rather than letting a student
    photograph a page and only then discover it cannot be read."""
    _, headers = student
    ocr_override(FakeProvider("easyocr", available=False))

    resp = await client.get("/api/v1/ocr/status", headers=headers)
    assert resp.json()["operational"] is False


async def test_status_requires_authentication(client, ocr_override):
    assert (await client.get("/api/v1/ocr/status")).status_code == 401


# ── Extraction ───────────────────────────────────────────────────────────────


async def test_extracts_text_from_an_upload(client, ocr_override, student):
    _, headers = student
    resp = await client.post("/api/v1/ocr/extract", headers=headers, files=upload(image_bytes()))
    assert resp.status_code == 200

    body = resp.json()
    assert body["text"] == SAMPLE_TEXT
    assert body["provider"] == "easyocr"
    assert body["confidence"] == pytest.approx(0.91)
    assert body["word_count"] == 10
    assert body["warning"] is None
    assert body["image_url"].startswith("/media/submissions/handwriting/")
    assert body["blocks"][0]["bbox"] == [4, 8, 400, 48]


async def test_extraction_requires_authentication(client, ocr_override):
    resp = await client.post("/api/v1/ocr/extract", files=upload(image_bytes()))
    assert resp.status_code == 401


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
async def test_accepts_each_allowed_format(client, ocr_override, student, fmt):
    _, headers = student
    resp = await client.post("/api/v1/ocr/extract", headers=headers, files=upload(image_bytes(fmt)))
    assert resp.status_code == 200


async def test_the_original_is_stored(client, ocr_override, student):
    _, headers = student
    service = ocr_override(FakeProvider())

    resp = await client.post("/api/v1/ocr/extract", headers=headers, files=upload(image_bytes()))
    key = resp.json()["image_url"].removeprefix("/media/")
    assert service.storage.exists(key)


# ── Rejected uploads ─────────────────────────────────────────────────────────


async def test_rejects_a_non_image(client, ocr_override, student):
    """The declared content type is not trusted; the bytes are checked."""
    _, headers = student
    resp = await client.post(
        "/api/v1/ocr/extract",
        headers=headers,
        files=upload(b"%PDF-1.7 not an image", "answer.png", "image/png"),
    )
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


async def test_rejects_a_truncated_image(client, ocr_override, student):
    _, headers = student
    data = image_bytes("PNG", (600, 600))
    resp = await client.post(
        "/api/v1/ocr/extract", headers=headers, files=upload(data[: len(data) // 2])
    )
    assert resp.status_code == 415


async def test_rejects_an_oversized_upload(client, ocr_override, student, monkeypatch):
    from app.core.config import get_settings

    _, headers = student
    monkeypatch.setattr(get_settings(), "MAX_UPLOAD_SIZE_MB", 1)

    buffer = io.BytesIO()
    Image.effect_noise((1400, 1400), 128).convert("RGB").save(buffer, format="PNG")
    resp = await client.post(
        "/api/v1/ocr/extract", headers=headers, files=upload(buffer.getvalue())
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


async def test_nothing_is_stored_for_a_rejected_upload(client, ocr_override, student):
    """Validation runs before a byte reaches storage."""
    _, headers = student
    service = ocr_override(FakeProvider())

    resp = await client.post(
        "/api/v1/ocr/extract", headers=headers, files=upload(b"definitely not an image")
    )
    assert resp.status_code == 415
    assert list(service.storage.root.rglob("*")) == []


# ── Failure and degraded reads ───────────────────────────────────────────────


async def test_every_provider_failing_returns_422(client, ocr_override, student):
    _, headers = student
    ocr_override(FakeProvider("easyocr", error=RuntimeError("model exploded")))

    resp = await client.post("/api/v1/ocr/extract", headers=headers, files=upload(image_bytes()))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "OCR_FAILED"


async def test_the_image_is_kept_when_recognition_fails(client, ocr_override, student):
    """FR-4.9: the student retries or types instead, without re-photographing."""
    _, headers = student
    service = ocr_override(FakeProvider("easyocr", error=RuntimeError("boom")))

    await client.post("/api/v1/ocr/extract", headers=headers, files=upload(image_bytes()))

    stored = list((service.storage.root).rglob("*.png"))
    assert len(stored) == 1, "the uploaded original should have been retained"


async def test_no_engine_configured_returns_422(client, ocr_override, student):
    _, headers = student
    ocr_override(FakeProvider("easyocr", available=False))

    resp = await client.post("/api/v1/ocr/extract", headers=headers, files=upload(image_bytes()))
    assert resp.status_code == 422
    assert "type your answer" in resp.json()["error"]["message"]


async def test_an_empty_read_warns_rather_than_failing(client, ocr_override, student):
    """A blank page is a legitimate outcome, not an error."""
    _, headers = student
    ocr_override(FakeProvider("easyocr", text="", confidence=0.0))

    resp = await client.post("/api/v1/ocr/extract", headers=headers, files=upload(image_bytes()))
    assert resp.status_code == 200

    body = resp.json()
    assert body["text"] == ""
    assert body["word_count"] == 0
    assert "No text could be read" in body["warning"]


async def test_a_low_confidence_read_warns_but_succeeds(client, ocr_override, student):
    """Low confidence never blocks; it tells the student to read carefully."""
    _, headers = student
    ocr_override(FakeProvider("easyocr", confidence=0.31))

    resp = await client.post("/api/v1/ocr/extract", headers=headers, files=upload(image_bytes()))
    assert resp.status_code == 200

    body = resp.json()
    assert body["text"] == SAMPLE_TEXT
    assert "check the text below carefully" in body["warning"]


async def test_a_confident_read_carries_no_warning(client, ocr_override, student):
    _, headers = student
    ocr_override(FakeProvider("easyocr", confidence=0.95))
    resp = await client.post("/api/v1/ocr/extract", headers=headers, files=upload(image_bytes()))
    assert resp.json()["warning"] is None


# ── Rate limiting ────────────────────────────────────────────────────────────


async def test_uploads_are_rate_limited(client, ocr_override, student):
    """Recognition is the most expensive thing an authenticated caller can
    trigger, so it is metered per user."""
    from app.core.rate_limit import UPLOAD_LIMIT

    _, headers = student
    for _ in range(UPLOAD_LIMIT.limit):
        resp = await client.post(
            "/api/v1/ocr/extract", headers=headers, files=upload(image_bytes())
        )
        assert resp.status_code == 200

    resp = await client.post("/api/v1/ocr/extract", headers=headers, files=upload(image_bytes()))
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
