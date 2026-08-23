"""Process-wide OCR chain."""

from __future__ import annotations

from functools import lru_cache

from app.ocr.chain import OCRChain, build_chain


@lru_cache
def get_ocr_chain() -> OCRChain:
    """The shared chain.

    Cached so provider availability is probed once per process, and so the
    EasyOCR reader's several hundred megabytes of weights are loaded once
    rather than per request.
    """
    return build_chain()
