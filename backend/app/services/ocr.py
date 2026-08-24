"""OCR orchestration.

Sequences the pipeline from 07-ocr-architecture.md §4: validate, store the
original, preprocess a copy, run the provider chain, clean the output.

The original upload is stored **before** recognition is attempted and is never
deleted on failure. When every provider fails the student still has their photo
on the server, so they can retry or switch to typing without re-photographing
the page (FR-4.9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import OCRError, OCRUnreadableError
from app.core.logging import get_logger
from app.models.enums import OCRProviderName
from app.ocr.chain import ChainAttempt, OCRChain
from app.ocr.postprocess import clean, word_count
from app.ocr.preprocess import preprocess
from app.ocr.validation import ValidatedImage, validate_upload
from app.storage.base import StorageBackend

logger = get_logger(__name__)

UPLOAD_PREFIX = "submissions/handwriting"

# Below this the preview is worth a visible warning: the student should read it
# carefully rather than accepting it. It never blocks — a low-confidence read
# that the student then corrects is exactly the intended workflow.
LOW_CONFIDENCE_THRESHOLD = 0.60


@dataclass
class ExtractionOutcome:
    """Everything an upload produced, ready to persist or return."""

    text: str
    raw_text: str
    provider: str
    confidence: float | None
    blocks: list[dict[str, Any]]
    word_count: int
    storage_key: str | None
    image_url: str | None
    width: int
    height: int
    preprocess_steps: list[str] = field(default_factory=list)
    attempts: list[ChainAttempt] = field(default_factory=list)
    warning: str | None = None

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class OCRService:
    def __init__(self, chain: OCRChain, storage: StorageBackend) -> None:
        self.chain = chain
        self.storage = storage
        self.settings = get_settings()

    def provider_statuses(self) -> list[dict[str, Any]]:
        return [{"name": s.name, "available": s.available} for s in self.chain.statuses()]

    @property
    def is_operational(self) -> bool:
        return self.chain.is_operational

    def extract(
        self,
        data: bytes,
        *,
        filename: str | None = None,
        store: bool = True,
        prefix: str = UPLOAD_PREFIX,
    ) -> ExtractionOutcome:
        """Run the full pipeline on ``data``.

        Raises ``FileTooLargeError`` / ``UnsupportedFileTypeError`` for a
        rejected upload, and ``OCRError`` when every provider fails.
        """
        validated = validate_upload(data, filename=filename)

        storage_key: str | None = None
        image_url: str | None = None
        if store:
            storage_key, image_url = self._store_original(validated, prefix=prefix)

        recognition_input, steps = self._prepare(validated)

        try:
            outcome = self.chain.extract(recognition_input)
        except OCRError as exc:
            # Deliberately no cleanup: the stored original is what lets the
            # student retry without re-photographing the page. Where it landed
            # is re-raised with the error so a caller can record it against the
            # submission — otherwise the retained image is unreachable and the
            # retry FR-4.9 promises is not actually available.
            logger.warning(
                "OCR failed for %s; original retained at %s", filename or "upload", storage_key
            )
            raise OCRUnreadableError(
                exc.message, storage_key=storage_key, image_url=image_url
            ) from exc

        result = outcome.result
        cleaned = clean(result.text)

        return ExtractionOutcome(
            text=cleaned,
            raw_text=result.text,
            provider=result.provider,
            confidence=result.confidence,
            blocks=result.blocks_as_dicts(),
            word_count=word_count(cleaned),
            storage_key=storage_key,
            image_url=image_url,
            width=validated.width,
            height=validated.height,
            preprocess_steps=steps,
            attempts=outcome.attempts,
            warning=self._warning_for(cleaned, result.confidence),
        )

    def _store_original(self, validated: ValidatedImage, *, prefix: str) -> tuple[str, str]:
        key = validated.storage_key(prefix)
        stored = self.storage.save(validated.data, key=key, content_type=validated.content_type)
        logger.info("Stored handwriting upload %s (%d bytes)", stored.key, stored.size)
        return stored.key, stored.url

    def _prepare(self, validated: ValidatedImage) -> tuple[bytes, list[str]]:
        """Preprocess unless the winning provider prefers the original.

        Google Vision does its own normalisation and reads the untouched photo
        better than an aggressively cleaned one, so when it leads the chain the
        preprocessing is skipped (07-ocr-architecture.md §4.2).
        """
        leading = next(iter(self.chain.available_providers), None)
        if leading is not None and leading.name == OCRProviderName.GOOGLE_VISION.value:
            return validated.data, ["skipped (google_vision reads the original better)"]

        try:
            prepared = preprocess(validated.data)
        except Exception as exc:
            # Preprocessing is an optimisation. If it breaks, recognising the
            # original is far better than rejecting the student's work.
            logger.warning("Preprocessing failed, using the original image: %s", exc)
            return validated.data, ["failed, using original"]

        return prepared.data, prepared.steps

    def _warning_for(self, text: str, confidence: float | None) -> str | None:
        if not text.strip():
            # An empty read is a legitimate outcome, not an error: a blank or
            # unreadable page is a real thing a student can photograph.
            return (
                "No text could be read from that image. Check the photo is in focus and "
                "well lit, or type your answer instead."
            )
        if confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
            return (
                "The handwriting was hard to read, so please check the text below carefully "
                "and correct anything wrong before continuing."
            )
        return None
