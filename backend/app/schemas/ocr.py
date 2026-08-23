"""OCR extraction schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import OCRProviderName


class OCRProviderStatus(BaseModel):
    name: OCRProviderName
    available: bool


class OCRStatusResponse(BaseModel):
    """Which engines this server can actually use.

    Surfaced so the client can hide the handwriting-upload option entirely
    when no engine is configured, rather than letting a student photograph a
    page and only then discover it cannot be read.
    """

    operational: bool = Field(description="Whether any engine is available")
    providers: list[OCRProviderStatus]


class OCRExtractionResponse(BaseModel):
    """The editable preview handed back to the student (FR-4.6, FR-4.7)."""

    text: str = Field(description="Cleaned text, ready to be edited and confirmed")
    provider: OCRProviderName
    confidence: float | None = Field(
        default=None, description="Mean provider confidence, 0.0–1.0, when reported"
    )
    word_count: int
    image_url: str | None = Field(
        default=None, description="The stored original, retained even when recognition fails"
    )
    warning: str | None = Field(
        default=None,
        description="Set for an empty or low-confidence read; never blocks the flow",
    )
    blocks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-region text, confidence and bounding box, for debugging and research",
    )
