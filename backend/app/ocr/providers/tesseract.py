"""Tesseract provider.

Weakest of the three on cursive handwriting, so it sits last in the chain — a
last resort rather than a peer. It earns its place by being the only engine
that needs neither a paid account nor a multi-hundred-megabyte model download.
"""

from __future__ import annotations

import io
import shutil

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.enums import OCRProviderName
from app.ocr.base import OCRBlock, OCRResult, ProviderUnavailableError

logger = get_logger(__name__)

# Page segmentation 6 — "a single uniform block of text". A handwritten answer
# is one block; the default (3, fully automatic) tends to hunt for columns that
# are not there and fragments the paragraph.
PSM = 6
MIN_BLOCK_CONFIDENCE = 30.0


class TesseractProvider:
    name = OCRProviderName.TESSERACT.value

    def __init__(self) -> None:
        self._settings = get_settings()
        self._available: bool | None = None

    def is_available(self) -> bool:
        if self._available is None:
            self._available = self._probe()
        return self._available

    def _probe(self) -> bool:
        try:
            import pytesseract
        except ImportError:
            logger.debug("Tesseract unavailable: pytesseract is not installed")
            return False

        command = self._settings.TESSERACT_CMD
        resolved = shutil.which(command)
        if resolved is None:
            logger.debug("Tesseract unavailable: %r not found on PATH", command)
            return False

        pytesseract.pytesseract.tesseract_cmd = resolved
        return True

    def extract(self, image: bytes) -> OCRResult:
        if not self.is_available():
            raise ProviderUnavailableError("Tesseract is not installed.")

        import pytesseract
        from PIL import Image

        with Image.open(io.BytesIO(image)) as img:
            data = pytesseract.image_to_data(
                img,
                config=f"--psm {PSM}",
                output_type=pytesseract.Output.DICT,
            )

        blocks: list[OCRBlock] = []
        confidences: list[float] = []
        lines: dict[tuple[int, int, int], list[str]] = {}

        for index, word in enumerate(data["text"]):
            word = word.strip()
            if not word:
                continue
            confidence = float(data["conf"][index])
            if confidence < 0:
                # Tesseract reports -1 for regions it did not actually score.
                continue

            key = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
            lines.setdefault(key, []).append(word)

            if confidence >= MIN_BLOCK_CONFIDENCE:
                confidences.append(confidence / 100.0)

            blocks.append(
                OCRBlock(
                    text=word,
                    confidence=confidence / 100.0,
                    bbox=(
                        int(data["left"][index]),
                        int(data["top"][index]),
                        int(data["left"][index] + data["width"][index]),
                        int(data["top"][index] + data["height"][index]),
                    ),
                )
            )

        text = "\n".join(" ".join(words) for words in lines.values())
        mean_confidence = sum(confidences) / len(confidences) if confidences else None

        return OCRResult(text=text, provider=self.name, confidence=mean_confidence, blocks=blocks)
