"""Handwriting extraction endpoints (FR-4.x).

This is the standalone preview surface: it recognises an image and hands the
text back without binding it to a submission. Sprint 6 wires the same service
into `POST /submissions/{id}/upload`, where the result is persisted and the
submission advances to `extracted`.

Keeping recognition callable on its own is what lets a teacher check how well
the configured engine reads their students' handwriting before setting an
assignment.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile

from app.api.deps import CurrentUser, OCRSvc
from app.core.exceptions import FileTooLargeError
from app.core.rate_limit import UPLOAD_LIMIT, enforce
from app.schemas.ocr import OCRExtractionResponse, OCRStatusResponse

router = APIRouter(tags=["ocr"])


@router.get(
    "/status",
    response_model=OCRStatusResponse,
    summary="Which recognition engines this server can use",
)
async def ocr_status(_: CurrentUser, ocr: OCRSvc) -> OCRStatusResponse:
    return OCRStatusResponse(
        operational=ocr.is_operational,
        providers=ocr.provider_statuses(),
    )


@router.post(
    "/extract",
    response_model=OCRExtractionResponse,
    summary="Read handwriting from an image",
    description=(
        "Validates the upload by its signature bytes, stores the original, and runs the "
        "provider chain. The returned text is a **preview**: it is meant to be shown to "
        "the student and edited before anything is scored. Returns 413 for an oversized "
        "file, 415 for anything that is not a JPG, PNG or WEBP image, and 422 when every "
        "engine fails — in which case the uploaded image is still retained."
    ),
)
async def extract_text(
    request: Request,
    user: CurrentUser,
    ocr: OCRSvc,
    file: UploadFile = File(description="JPG, PNG or WEBP photograph of handwriting"),
) -> OCRExtractionResponse:
    # Metered per user: recognition is the most expensive thing an
    # authenticated caller can trigger, and it is the natural target for anyone
    # wanting to burn the server's CPU.
    enforce(request, UPLOAD_LIMIT)

    data = await _read_within_limit(file, ocr.settings.max_upload_bytes)

    outcome = ocr.extract(data, filename=file.filename)
    return OCRExtractionResponse(
        text=outcome.text,
        provider=outcome.provider,
        confidence=outcome.confidence,
        word_count=outcome.word_count,
        image_url=outcome.image_url,
        warning=outcome.warning,
        blocks=outcome.blocks,
    )


async def _read_within_limit(file: UploadFile, limit: int) -> bytes:
    """Read the upload, refusing to buffer more than the limit.

    Read in chunks and stop at the first byte past the maximum. Calling
    `await file.read()` outright would pull an arbitrarily large body into
    memory before any size check could reject it, which turns the size limit
    into exactly the resource-exhaustion vector it exists to prevent.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(64 * 1024):
        total += len(chunk)
        if total > limit:
            raise FileTooLargeError(f"The image exceeds the {limit // 1_048_576} MB limit.")
        chunks.append(chunk)
    return b"".join(chunks)
