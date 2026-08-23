"""EasyOCR provider — the default working path.

Models are baked into the Docker image at build time. A first-request download
would blow the 10-second budget of NFR-1.3 and would fail outright on hosts
with no runtime egress, so availability means *models already on disk*, not
*models obtainable*.
"""

from __future__ import annotations

import io
import threading

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.enums import OCRProviderName
from app.ocr.base import OCRBlock, OCRResult, ProviderUnavailableError

logger = get_logger(__name__)


class EasyOCRProvider:
    name = OCRProviderName.EASYOCR.value

    def __init__(self) -> None:
        self._settings = get_settings()
        self._available: bool | None = None
        self._reader = None
        # Reader construction loads several hundred megabytes of weights. Two
        # concurrent first-requests would otherwise each build their own.
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        if self._available is None:
            self._available = self._probe()
        return self._available

    def _probe(self) -> bool:
        try:
            import easyocr  # noqa: F401
        except ImportError:
            logger.debug("EasyOCR unavailable: package is not installed")
            return False
        return True

    def _get_reader(self):
        """Build the reader once and reuse it.

        Constructing it per request would add several seconds of model loading
        to every upload (07-ocr-architecture.md §7).
        """
        if self._reader is not None:
            return self._reader

        with self._lock:
            if self._reader is None:
                import easyocr

                self._reader = easyocr.Reader(
                    self._settings.easyocr_languages,
                    gpu=False,
                    model_storage_directory=self._settings.EASYOCR_MODEL_DIR,
                    # Never reach for the network at request time: on a host
                    # without egress this would hang rather than fail over.
                    download_enabled=False,
                    verbose=False,
                )
                logger.info("EasyOCR reader initialised (%s)", self._settings.EASYOCR_LANGUAGES)

        return self._reader

    def warm_up(self) -> None:
        """Load the model ahead of the first request.

        Called at application start so the cost lands during boot rather than
        on whichever student happens to upload first.
        """
        if self.is_available():
            self._get_reader()

    def extract(self, image: bytes) -> OCRResult:
        if not self.is_available():
            raise ProviderUnavailableError("EasyOCR is not installed.")

        import numpy as np
        from PIL import Image

        with Image.open(io.BytesIO(image)) as img:
            array = np.array(img.convert("RGB"))

        rows = self._get_reader().readtext(array, detail=1, paragraph=False)

        blocks: list[OCRBlock] = []
        confidences: list[float] = []
        for box, text, confidence in rows:
            text = str(text).strip()
            if not text:
                continue
            xs = [int(point[0]) for point in box]
            ys = [int(point[1]) for point in box]
            blocks.append(
                OCRBlock(
                    text=text,
                    confidence=float(confidence),
                    bbox=(min(xs), min(ys), max(xs), max(ys)),
                )
            )
            confidences.append(float(confidence))

        # EasyOCR returns boxes in reading order already, but sorting by the
        # top edge makes the joined text robust to the occasional out-of-order
        # detection on a skewed page.
        blocks.sort(key=lambda b: (b.bbox[1] if b.bbox else 0, b.bbox[0] if b.bbox else 0))

        return OCRResult(
            text="\n".join(b.text for b in blocks),
            provider=self.name,
            confidence=sum(confidences) / len(confidences) if confidences else None,
            blocks=blocks,
        )
