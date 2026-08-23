"""The provider chain (07-ocr-architecture.md §3.1).

Availability is probed once, at application start. Availability and success are
different questions: an unconfigured provider is skipped permanently, while a
configured one that *errors* on a particular image falls through to the next
and is tried again on the next upload.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.exceptions import OCRError
from app.core.logging import get_logger
from app.ocr.base import OCRProvider, OCRResult

logger = get_logger(__name__)


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    available: bool


@dataclass(frozen=True)
class ChainAttempt:
    """One provider's turn, kept for diagnostics."""

    provider: str
    ok: bool
    duration_ms: int
    error: str | None = None


@dataclass(frozen=True)
class ChainOutcome:
    result: OCRResult
    attempts: list[ChainAttempt]

    @property
    def fell_back(self) -> bool:
        """Whether a provider ahead of the winner failed on this image."""
        return len(self.attempts) > 1


class OCRChain:
    """Tries each configured provider in preference order."""

    def __init__(self, providers: list[OCRProvider]) -> None:
        self._providers = providers

    @property
    def providers(self) -> list[OCRProvider]:
        return list(self._providers)

    def statuses(self) -> list[ProviderStatus]:
        return [ProviderStatus(p.name, p.is_available()) for p in self._providers]

    @property
    def available_providers(self) -> list[OCRProvider]:
        return [p for p in self._providers if p.is_available()]

    @property
    def is_operational(self) -> bool:
        return bool(self.available_providers)

    def extract(self, image: bytes) -> ChainOutcome:
        """Recognise ``image``, falling through on failure.

        Raises ``OCRError`` only when every available provider has been tried
        and none succeeded — the caller then keeps the uploaded image and marks
        the submission failed, so the student can retry or type instead
        (FR-4.9).
        """
        attempts: list[ChainAttempt] = []
        candidates = self.available_providers

        if not candidates:
            raise OCRError(
                "No handwriting recognition engine is configured on this server. "
                "Please type your answer instead."
            )

        for provider in candidates:
            started = time.perf_counter()
            try:
                result = provider.extract(image)
            except Exception as exc:
                elapsed = int((time.perf_counter() - started) * 1000)
                attempts.append(
                    ChainAttempt(provider.name, ok=False, duration_ms=elapsed, error=str(exc))
                )
                logger.warning(
                    "OCR provider %s failed after %d ms: %s", provider.name, elapsed, exc
                )
                continue

            elapsed = int((time.perf_counter() - started) * 1000)
            attempts.append(ChainAttempt(provider.name, ok=True, duration_ms=elapsed))
            logger.info(
                "OCR provider %s succeeded in %d ms (%d chars, confidence %s)",
                provider.name,
                elapsed,
                len(result.text),
                f"{result.confidence:.2f}" if result.confidence is not None else "n/a",
            )
            # An empty extraction is a legitimate outcome — a blank or
            # unreadable page — not a provider failure, so it does not fall
            # through. Falling through would run every engine on every blank
            # photo for no benefit.
            return ChainOutcome(result=result, attempts=attempts)

        tried = ", ".join(a.provider for a in attempts)
        raise OCRError(
            f"Could not read the handwriting in that image (tried: {tried}). "
            "Try a clearer, better-lit photo, or type your answer instead."
        )


def build_chain(providers: list[OCRProvider] | None = None) -> OCRChain:
    """Assemble the chain in the configured preference order.

    The order comes from ``OCR_PROVIDER_ORDER`` so an operator can demote a
    provider without a code change — useful when a paid quota runs out.
    """
    if providers is None:
        from app.ocr.providers import (
            EasyOCRProvider,
            GoogleVisionProvider,
            TesseractProvider,
        )

        registry: dict[str, OCRProvider] = {
            GoogleVisionProvider.name: GoogleVisionProvider(),
            EasyOCRProvider.name: EasyOCRProvider(),
            TesseractProvider.name: TesseractProvider(),
        }
        ordered: list[OCRProvider] = []
        for name in get_settings().ocr_provider_order:
            provider = registry.get(name)
            if provider is None:
                logger.warning("Unknown OCR provider %r in OCR_PROVIDER_ORDER; ignoring", name)
                continue
            ordered.append(provider)
        providers = ordered

    chain = OCRChain(providers)
    logger.info(
        "OCR chain: %s",
        ", ".join(
            f"{s.name}={'available' if s.available else 'unavailable'}" for s in chain.statuses()
        )
        or "no providers configured",
    )
    return chain
