"""Handwriting OCR: validation, provider chain, pre- and post-processing.

OCR runs against the *student's handwritten answer*, never against the graph
image — graphs are structured `chart_data` rendered by Chart.js. See
docs/architecture/07-ocr-architecture.md.
"""

from __future__ import annotations

from app.ocr.base import OCRBlock, OCRProvider, OCRResult
from app.ocr.chain import OCRChain, ProviderStatus

__all__ = ["OCRBlock", "OCRChain", "OCRProvider", "OCRResult", "ProviderStatus"]
