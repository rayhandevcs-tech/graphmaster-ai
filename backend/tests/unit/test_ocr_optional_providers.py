"""The two OCR providers that are optional extras.

Neither ``google-cloud-vision`` nor ``easyocr`` is installed in the default
environment — they are the paid tier and a several-hundred-megabyte download
respectively — so without this module the first two links of the provider
chain are code nobody has ever executed. That is the wrong half to leave
untested: Tesseract is the fallback, and these two are what a real deployment
actually runs.

Each SDK is replaced by a fake module shaped like the real one. A fake rather
than a mock, so calling the client with the wrong keyword or reading a field
the SDK does not have fails here instead of in production.
"""

from __future__ import annotations

import io
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.ocr.base import OCRResult, ProviderUnavailableError


def image_bytes(size=(400, 200)) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="PNG")
    return buffer.getvalue()


# ── Google Cloud Vision ──────────────────────────────────────────────────────


def vision_word(text: str):
    return SimpleNamespace(symbols=[SimpleNamespace(text=ch) for ch in text])


def vision_block(words: list[str], *, confidence: float, box=(10, 20, 110, 60)):
    left, top, right, bottom = box
    vertices = [
        SimpleNamespace(x=left, y=top),
        SimpleNamespace(x=right, y=top),
        SimpleNamespace(x=right, y=bottom),
        SimpleNamespace(x=left, y=bottom),
    ]
    return SimpleNamespace(
        paragraphs=[SimpleNamespace(words=[vision_word(w) for w in words])],
        bounding_box=SimpleNamespace(vertices=vertices),
        confidence=confidence,
    )


def vision_response(*, text: str, blocks: list, error: str = ""):
    return SimpleNamespace(
        error=SimpleNamespace(message=error),
        full_text_annotation=SimpleNamespace(text=text, pages=[SimpleNamespace(blocks=blocks)]),
    )


class FakeVisionClient:
    def __init__(self, response=None) -> None:
        self.response = response
        self.calls: list[dict] = []

    def document_text_detection(self, *, image, image_context):
        self.calls.append({"image": image, "image_context": image_context})
        return self.response


@pytest.fixture
def fake_vision(monkeypatch: pytest.MonkeyPatch):
    """Install a stand-in ``google.cloud.vision``."""
    client = FakeVisionClient()

    vision = ModuleType("google.cloud.vision")
    vision.Image = lambda content: SimpleNamespace(content=content)  # type: ignore[attr-defined]
    vision.ImageContext = lambda language_hints: SimpleNamespace(  # type: ignore[attr-defined]
        language_hints=language_hints
    )
    vision.ImageAnnotatorClient = lambda: client  # type: ignore[attr-defined]

    google = ModuleType("google")
    cloud = ModuleType("google.cloud")
    cloud.vision = vision  # type: ignore[attr-defined]
    google.cloud = cloud  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.vision", vision)
    return client


@pytest.fixture
def credentials_file(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """A credentials path that exists, without shipping a credentials file."""
    from app.core.config import get_settings

    path = tmp_path / "service-account.json"
    path.write_text('{"type": "service_account"}')
    monkeypatch.setattr(get_settings(), "GOOGLE_APPLICATION_CREDENTIALS", str(path))
    # The provider publishes the path to the SDK through the environment;
    # left set, it would leak into every later test in the session.
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    return path


def vision_provider():
    from app.ocr.providers.google_vision import GoogleVisionProvider

    return GoogleVisionProvider()


class TestGoogleVisionAvailability:
    def test_unconfigured_is_unavailable(self, monkeypatch):
        """The platform is fully functional with no paid service configured."""
        from app.core.config import get_settings

        monkeypatch.setattr(get_settings(), "GOOGLE_APPLICATION_CREDENTIALS", None)
        assert vision_provider().is_available() is False

    def test_a_credentials_path_that_does_not_exist_is_unavailable(self, monkeypatch, tmp_path):
        """A typo in a deployment variable must not become a per-upload crash."""
        from app.core.config import get_settings

        monkeypatch.setattr(
            get_settings(), "GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "absent.json")
        )
        assert vision_provider().is_available() is False

    def test_credentials_without_the_library_are_unavailable(self, credentials_file, monkeypatch):
        monkeypatch.setitem(sys.modules, "google.cloud.vision", None)
        assert vision_provider().is_available() is False

    def test_credentials_and_library_together_are_available(self, credentials_file, fake_vision):
        provider = vision_provider()
        assert provider.is_available() is True
        # Published for the SDK, which reads it from the environment.
        import os

        assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == str(credentials_file)

    def test_availability_is_probed_once(self, credentials_file, fake_vision, monkeypatch):
        """A billed account must not be probed per upload."""
        provider = vision_provider()
        assert provider.is_available() is True

        probes = {"n": 0}
        original = provider._probe

        def counting():
            probes["n"] += 1
            return original()

        monkeypatch.setattr(provider, "_probe", counting)
        provider.is_available()
        provider.is_available()
        assert probes["n"] == 0

    def test_extract_refuses_when_unconfigured(self, monkeypatch):
        from app.core.config import get_settings

        monkeypatch.setattr(get_settings(), "GOOGLE_APPLICATION_CREDENTIALS", None)
        with pytest.raises(ProviderUnavailableError):
            vision_provider().extract(image_bytes())


class TestGoogleVisionExtraction:
    def test_it_reads_the_handwriting_model(self, credentials_file, fake_vision):
        """document_text_detection, not text_detection.

        The dense-document model is the one trained on handwriting; the plain
        one is markedly worse on cursive, and the two differ only by method
        name — exactly the kind of change nothing else would catch.
        """
        fake_vision.response = vision_response(
            text="The chart shows a rise.",
            blocks=[vision_block(["The", "chart"], confidence=0.9)],
        )
        vision_provider().extract(image_bytes())
        assert len(fake_vision.calls) == 1
        assert fake_vision.calls[0]["image_context"].language_hints == ["en"]

    def test_blocks_and_confidence_are_flattened_from_the_response(
        self, credentials_file, fake_vision
    ):
        fake_vision.response = vision_response(
            text="The chart shows\na steady rise.",
            blocks=[
                vision_block(["The", "chart", "shows"], confidence=0.8, box=(10, 20, 200, 60)),
                vision_block(["a", "steady", "rise."], confidence=0.6, box=(10, 70, 220, 110)),
            ],
        )
        result = vision_provider().extract(image_bytes())

        assert isinstance(result, OCRResult)
        assert result.text == "The chart shows\na steady rise."
        assert [b.text for b in result.blocks] == ["The chart shows", "a steady rise."]
        assert result.blocks[0].bbox == (10, 20, 200, 60)
        assert result.confidence == pytest.approx(0.7)

    def test_an_empty_block_is_dropped(self, credentials_file, fake_vision):
        """A block with no words would otherwise contribute a blank line and a confidence."""
        empty = SimpleNamespace(
            paragraphs=[SimpleNamespace(words=[])],
            bounding_box=SimpleNamespace(vertices=[]),
            confidence=0.1,
        )
        fake_vision.response = vision_response(
            text="Real text.",
            blocks=[empty, vision_block(["Real", "text."], confidence=0.9)],
        )
        result = vision_provider().extract(image_bytes())
        assert len(result.blocks) == 1
        assert result.confidence == pytest.approx(0.9)

    def test_a_response_with_no_text_reports_no_confidence(self, credentials_file, fake_vision):
        """None, not zero: nothing was read, which is not the same as reading badly."""
        fake_vision.response = vision_response(text="", blocks=[])
        result = vision_provider().extract(image_bytes())
        assert result.text == ""
        assert result.confidence is None
        assert result.is_empty

    def test_an_api_error_raises_so_the_chain_falls_through(self, credentials_file, fake_vision):
        """Returning an empty result would store a failed read as a successful one."""
        fake_vision.response = vision_response(text="", blocks=[], error="Quota exceeded")
        with pytest.raises(RuntimeError, match="Quota exceeded"):
            vision_provider().extract(image_bytes())

    def test_the_client_is_built_once(self, credentials_file, fake_vision):
        fake_vision.response = vision_response(text="x", blocks=[])
        provider = vision_provider()
        provider.extract(image_bytes())
        first = provider._client
        provider.extract(image_bytes())
        assert provider._client is first


# ── EasyOCR ──────────────────────────────────────────────────────────────────


class FakeReader:
    instances: list[FakeReader] = []

    def __init__(self, languages, **kwargs) -> None:
        self.languages = languages
        self.kwargs = kwargs
        self.rows: list = []
        FakeReader.instances.append(self)

    def readtext(self, array, *, detail, paragraph):
        self.last = SimpleNamespace(shape=getattr(array, "shape", None), detail=detail)
        return self.rows


@pytest.fixture
def fake_easyocr(monkeypatch: pytest.MonkeyPatch):
    FakeReader.instances = []
    module = ModuleType("easyocr")
    module.Reader = FakeReader  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "easyocr", module)
    return FakeReader


def easyocr_provider():
    from app.ocr.providers.easyocr_provider import EasyOCRProvider

    return EasyOCRProvider()


def box(left, top, right, bottom):
    return [[left, top], [right, top], [right, bottom], [left, bottom]]


class TestEasyOCRAvailability:
    def test_absent_package_is_unavailable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "easyocr", None)
        assert easyocr_provider().is_available() is False

    def test_extract_refuses_when_the_package_is_absent(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "easyocr", None)
        with pytest.raises(ProviderUnavailableError):
            easyocr_provider().extract(image_bytes())

    def test_an_installed_package_is_available(self, fake_easyocr):
        assert easyocr_provider().is_available() is True

    def test_warm_up_loads_the_model_before_the_first_request(self, fake_easyocr):
        """NFR-1.3's budget cannot absorb a model load on top of recognition."""
        provider = easyocr_provider()
        provider.warm_up()
        assert len(fake_easyocr.instances) == 1

    def test_warm_up_is_a_no_op_when_unavailable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "easyocr", None)
        easyocr_provider().warm_up()  # must not raise

    def test_the_reader_never_reaches_for_the_network(self, fake_easyocr):
        """A download at request time hangs on a host with no egress.

        The image bakes the weights in; asking for them again would turn a
        missing model into a timeout instead of a clean fallback.
        """
        provider = easyocr_provider()
        provider.warm_up()
        assert fake_easyocr.instances[0].kwargs["download_enabled"] is False
        assert fake_easyocr.instances[0].kwargs["gpu"] is False

    def test_the_reader_is_built_once_across_requests(self, fake_easyocr):
        provider = easyocr_provider()
        provider.warm_up()
        provider.extract(image_bytes())
        provider.extract(image_bytes())
        assert len(fake_easyocr.instances) == 1


class TestEasyOCRExtraction:
    def test_rows_become_blocks_with_boxes_and_confidence(self, fake_easyocr):
        provider = easyocr_provider()
        provider.warm_up()
        fake_easyocr.instances[0].rows = [
            (box(10, 10, 200, 40), "The chart shows", 0.9),
            (box(10, 50, 220, 80), "a steady rise.", 0.7),
        ]

        result = provider.extract(image_bytes())

        assert result.text == "The chart shows\na steady rise."
        assert result.blocks[0].bbox == (10, 10, 200, 40)
        assert result.confidence == pytest.approx(0.8)

    def test_out_of_order_detections_are_read_top_to_bottom(self, fake_easyocr):
        """A skewed photograph is the normal case, not the exception.

        Joined in detection order, a page photographed at an angle would come
        back with its sentences shuffled — and the analysis engine would mark
        a perfectly good answer as incoherent.
        """
        provider = easyocr_provider()
        provider.warm_up()
        fake_easyocr.instances[0].rows = [
            (box(10, 90, 220, 120), "Third line", 0.8),
            (box(10, 10, 200, 40), "First line", 0.8),
            (box(10, 50, 210, 80), "Second line", 0.8),
        ]

        result = provider.extract(image_bytes())

        assert result.text == "First line\nSecond line\nThird line"

    def test_two_detections_on_one_line_read_left_to_right(self, fake_easyocr):
        provider = easyocr_provider()
        provider.warm_up()
        fake_easyocr.instances[0].rows = [
            (box(120, 10, 220, 40), "second", 0.8),
            (box(10, 10, 100, 40), "first", 0.8),
        ]

        result = provider.extract(image_bytes())

        assert result.text == "first\nsecond"

    def test_blank_detections_are_dropped(self, fake_easyocr):
        """Whitespace-only rows are common on ruled paper, and are not text."""
        provider = easyocr_provider()
        provider.warm_up()
        fake_easyocr.instances[0].rows = [
            (box(10, 10, 200, 40), "   ", 0.2),
            (box(10, 50, 200, 80), "Real text", 0.9),
        ]

        result = provider.extract(image_bytes())

        assert [b.text for b in result.blocks] == ["Real text"]
        assert result.confidence == pytest.approx(0.9)

    def test_nothing_recognised_reports_no_confidence(self, fake_easyocr):
        provider = easyocr_provider()
        provider.warm_up()
        fake_easyocr.instances[0].rows = []

        result = provider.extract(image_bytes())

        assert result.is_empty
        assert result.confidence is None

    def test_the_image_reaches_the_reader_as_rgb_pixels(self, fake_easyocr):
        """A palette or greyscale photograph must not change the array's shape."""
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("L", (120, 60), 200).save(buffer, format="PNG")

        provider = easyocr_provider()
        provider.warm_up()
        provider.extract(buffer.getvalue())

        assert fake_easyocr.instances[0].last.shape == (60, 120, 3)
