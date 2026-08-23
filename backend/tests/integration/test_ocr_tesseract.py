"""End-to-end recognition against a real engine.

Skipped unless Tesseract is actually installed, so a minimal developer install
still gets a green suite. The Docker image installs it, so this does run in the
built environment — which is the point: every other OCR test uses a fake, and
something has to prove the real adapter works.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.ocr.chain import OCRChain
from app.ocr.providers.tesseract import TesseractProvider
from app.services.ocr import OCRService
from app.storage.local import LocalStorage

provider = TesseractProvider()
pytestmark = pytest.mark.skipif(
    not provider.is_available(), reason="Tesseract is not installed in this environment"
)

ANSWER_LINES = [
    "The line graph illustrates the solar energy",
    "generated between 2019 and 2025. Overall,",
    "output rose substantially, climbing from",
    "120 MWh to 410 MWh. Figures fluctuated",
    "slightly in 2023 before reaching a peak.",
]


def _font(size: int = 34):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def answer_page(rotation: float = 0.0) -> bytes:
    img = Image.new("RGB", (1000, 400), "white")
    draw = ImageDraw.Draw(img)
    font = _font()
    for index, line in enumerate(ANSWER_LINES):
        draw.text((40, 30 + index * 68), line, fill="black", font=font)
    if rotation:
        img = img.rotate(rotation, expand=True, fillcolor="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def service(tmp_path) -> OCRService:
    return OCRService(OCRChain([TesseractProvider()]), LocalStorage(str(tmp_path), "/media"))


def test_reads_a_straight_page(service: OCRService) -> None:
    outcome = service.extract(answer_page(), filename="answer.png")

    assert outcome.provider == "tesseract"
    assert outcome.confidence is not None and outcome.confidence > 0.7
    # The vocabulary terms this platform actually scores on must survive the
    # whole pipeline, not merely "some text was returned".
    for term in ("rose", "climbing", "fluctuated", "peak"):
        assert term in outcome.text.lower(), f"{term!r} was lost"


def test_reads_a_skewed_page(service: OCRService) -> None:
    """A phone photograph of paper is rarely square to the page."""
    outcome = service.extract(answer_page(rotation=-2.5), filename="answer.png")

    assert any(step.startswith("deskew") for step in outcome.preprocess_steps)
    assert "fluctuated" in outcome.text.lower()


def test_line_breaks_are_joined_into_prose(service: OCRService) -> None:
    """The answer is five printed lines but one flowing paragraph."""
    outcome = service.extract(answer_page(), filename="answer.png")

    assert "\n" not in outcome.text
    assert outcome.word_count > 25


def test_the_original_is_stored_unmodified(service: OCRService) -> None:
    original = answer_page()
    outcome = service.extract(original, filename="answer.png")

    assert outcome.storage_key is not None
    assert service.storage.read(outcome.storage_key) == original


def test_a_blank_page_warns_rather_than_failing(service: OCRService) -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (800, 400), "white").save(buffer, format="PNG")

    outcome = service.extract(buffer.getvalue(), filename="blank.png")
    assert outcome.is_empty
    assert outcome.warning is not None and "No text could be read" in outcome.warning
