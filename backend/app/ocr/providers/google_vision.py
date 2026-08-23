"""Google Cloud Vision provider.

Best handwriting accuracy of the three, and first in the chain — but it needs a
billed GCP account, so it is optional. The platform is fully functional with no
paid service configured; see docs/PROJECT_PLAN.md §3.4.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.enums import OCRProviderName
from app.ocr.base import OCRBlock, OCRResult, ProviderUnavailableError

logger = get_logger(__name__)


class GoogleVisionProvider:
    name = OCRProviderName.GOOGLE_VISION.value

    def __init__(self) -> None:
        self._settings = get_settings()
        self._available: bool | None = None
        self._client = None

    def is_available(self) -> bool:
        if self._available is None:
            self._available = self._probe()
        return self._available

    def _probe(self) -> bool:
        """Credentials present and the client library importable.

        Probed once at startup rather than per upload: it is a configuration
        question, and the answer cannot change within a process lifetime.
        Sending a real API call here would bill the account just to boot.
        """
        credentials = self._settings.GOOGLE_APPLICATION_CREDENTIALS
        if not credentials:
            logger.debug("Google Vision unavailable: no credentials configured")
            return False

        if not Path(credentials).is_file():
            logger.warning(
                "Google Vision unavailable: credentials file %r does not exist", credentials
            )
            return False

        try:
            from google.cloud import vision  # noqa: F401
        except ImportError:
            logger.debug("Google Vision unavailable: google-cloud-vision is not installed")
            return False

        # The library reads this from the environment; setting it from our own
        # settings keeps the credential path in one place.
        os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", credentials)
        return True

    def _get_client(self):
        if self._client is None:
            from google.cloud import vision

            self._client = vision.ImageAnnotatorClient()
        return self._client

    def extract(self, image: bytes) -> OCRResult:
        if not self.is_available():
            raise ProviderUnavailableError("Google Vision is not configured.")

        from google.cloud import vision

        # document_text_detection, not text_detection: the former is the
        # handwriting/dense-document model and is markedly better on cursive.
        response = self._get_client().document_text_detection(
            image=vision.Image(content=image),
            image_context=vision.ImageContext(language_hints=["en"]),
        )

        if response.error.message:
            # Surfaced as an exception so the chain falls through to the next
            # provider rather than storing an empty extraction as a success.
            raise RuntimeError(f"Google Vision error: {response.error.message}")

        annotation = response.full_text_annotation
        blocks: list[OCRBlock] = []
        confidences: list[float] = []

        for page in annotation.pages:
            for block in page.blocks:
                words: list[str] = []
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        words.append("".join(symbol.text for symbol in word.symbols))
                if not words:
                    continue
                vertices = [(v.x, v.y) for v in block.bounding_box.vertices]
                xs = [v[0] for v in vertices]
                ys = [v[1] for v in vertices]
                blocks.append(
                    OCRBlock(
                        text=" ".join(words),
                        confidence=float(block.confidence),
                        bbox=(min(xs), min(ys), max(xs), max(ys)),
                    )
                )
                confidences.append(float(block.confidence))

        return OCRResult(
            text=annotation.text or "",
            provider=self.name,
            confidence=sum(confidences) / len(confidences) if confidences else None,
            blocks=blocks,
        )
