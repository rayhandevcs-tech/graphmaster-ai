"""The contract every OCR provider implements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class OCRBlock:
    """One recognised region.

    Persisted for research and debugging: blocks are what make it possible to
    answer *why* a particular word was misread, rather than only observing that
    the score was low (07-ocr-architecture.md §6).
    """

    text: str
    confidence: float | None = None
    bbox: tuple[int, int, int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "bbox": list(self.bbox) if self.bbox else None,
        }


@dataclass(frozen=True)
class OCRResult:
    """What a provider returns on success."""

    text: str
    provider: str
    confidence: float | None = None
    blocks: list[OCRBlock] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()

    def blocks_as_dicts(self) -> list[dict[str, Any]]:
        return [b.to_dict() for b in self.blocks]


@runtime_checkable
class OCRProvider(Protocol):
    """A single engine.

    ``is_available`` answers a configuration question and is probed once at
    startup; ``extract`` answers a per-image question and may fail at any time.
    Keeping them separate is what lets the chain skip an unconfigured provider
    without treating a transient failure as permanent.
    """

    name: str

    def is_available(self) -> bool: ...

    def extract(self, image: bytes) -> OCRResult: ...


class ProviderUnavailableError(RuntimeError):
    """Raised when a provider is asked to extract but is not configured."""
