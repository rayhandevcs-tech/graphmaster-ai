"""The provider chain.

Availability and success are different questions: an unconfigured provider is
skipped permanently, while a configured one that errors on a particular image
falls through and is tried again on the next upload.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import OCRError
from app.ocr.base import OCRBlock, OCRResult
from app.ocr.chain import OCRChain, build_chain


class FakeProvider:
    """A provider whose behaviour the test dictates."""

    def __init__(
        self,
        name: str,
        *,
        available: bool = True,
        text: str = "recognised text",
        confidence: float | None = 0.9,
        error: Exception | None = None,
    ) -> None:
        self.name = name
        self._available = available
        self._text = text
        self._confidence = confidence
        self._error = error
        self.calls = 0

    def is_available(self) -> bool:
        return self._available

    def extract(self, image: bytes) -> OCRResult:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return OCRResult(
            text=self._text,
            provider=self.name,
            confidence=self._confidence,
            blocks=[OCRBlock(text=self._text, confidence=self._confidence, bbox=(0, 0, 10, 10))],
        )


IMAGE = b"pretend image bytes"


def test_uses_the_first_available_provider() -> None:
    first = FakeProvider("google_vision")
    second = FakeProvider("easyocr")
    outcome = OCRChain([first, second]).extract(IMAGE)

    assert outcome.result.provider == "google_vision"
    assert second.calls == 0, "the second provider should never have been reached"


def test_skips_unavailable_providers_without_calling_them() -> None:
    unavailable = FakeProvider("google_vision", available=False)
    available = FakeProvider("easyocr")
    outcome = OCRChain([unavailable, available]).extract(IMAGE)

    assert outcome.result.provider == "easyocr"
    assert unavailable.calls == 0


def test_falls_through_when_a_provider_errors() -> None:
    """A runtime failure is not a configuration failure."""
    broken = FakeProvider("google_vision", error=RuntimeError("quota exceeded"))
    working = FakeProvider("easyocr")
    outcome = OCRChain([broken, working]).extract(IMAGE)

    assert outcome.result.provider == "easyocr"
    assert broken.calls == 1
    assert outcome.fell_back is True


def test_falls_through_the_whole_chain() -> None:
    chain = OCRChain(
        [
            FakeProvider("google_vision", error=RuntimeError("no credentials")),
            FakeProvider("easyocr", error=RuntimeError("model missing")),
            FakeProvider("tesseract"),
        ]
    )
    assert chain.extract(IMAGE).result.provider == "tesseract"


def test_records_every_attempt() -> None:
    chain = OCRChain(
        [FakeProvider("google_vision", error=RuntimeError("boom")), FakeProvider("easyocr")]
    )
    attempts = chain.extract(IMAGE).attempts

    assert [a.provider for a in attempts] == ["google_vision", "easyocr"]
    assert [a.ok for a in attempts] == [False, True]
    assert attempts[0].error == "boom"


def test_all_providers_failing_raises_and_names_them() -> None:
    chain = OCRChain(
        [
            FakeProvider("google_vision", error=RuntimeError("a")),
            FakeProvider("tesseract", error=RuntimeError("b")),
        ]
    )
    with pytest.raises(OCRError) as excinfo:
        chain.extract(IMAGE)

    message = str(excinfo.value)
    assert "google_vision" in message and "tesseract" in message
    # The student is always told what to do next.
    assert "type your answer" in message


def test_no_providers_configured_is_a_distinct_message() -> None:
    chain = OCRChain([FakeProvider("tesseract", available=False)])
    with pytest.raises(OCRError, match="No handwriting recognition engine is configured"):
        chain.extract(IMAGE)


def test_an_empty_extraction_does_not_fall_through() -> None:
    """A blank page is a legitimate outcome, not a provider failure.

    Falling through would run every engine on every blank photo for nothing.
    """
    first = FakeProvider("google_vision", text="", confidence=0.0)
    second = FakeProvider("easyocr", text="something")
    outcome = OCRChain([first, second]).extract(IMAGE)

    assert outcome.result.provider == "google_vision"
    assert outcome.result.is_empty
    assert second.calls == 0


def test_is_operational_reflects_availability() -> None:
    assert OCRChain([FakeProvider("tesseract")]).is_operational is True
    assert OCRChain([FakeProvider("tesseract", available=False)]).is_operational is False
    assert OCRChain([]).is_operational is False


def test_statuses_report_every_provider() -> None:
    chain = OCRChain([FakeProvider("google_vision", available=False), FakeProvider("easyocr")])
    assert [(s.name, s.available) for s in chain.statuses()] == [
        ("google_vision", False),
        ("easyocr", True),
    ]


# ── Assembly from configuration ──────────────────────────────────────────────


def test_build_chain_follows_the_configured_order(monkeypatch) -> None:
    """An operator can demote a provider without a code change — useful when a
    paid quota runs out."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "OCR_PROVIDER_ORDER", "tesseract,easyocr,google_vision")
    assert [p.name for p in build_chain().providers] == [
        "tesseract",
        "easyocr",
        "google_vision",
    ]


def test_build_chain_ignores_an_unknown_provider_name(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "OCR_PROVIDER_ORDER", "tesseract,nonsense")
    assert [p.name for p in build_chain().providers] == ["tesseract"]
