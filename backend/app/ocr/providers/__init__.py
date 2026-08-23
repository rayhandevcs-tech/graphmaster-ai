"""Concrete OCR engines."""

from __future__ import annotations

from app.ocr.providers.easyocr_provider import EasyOCRProvider
from app.ocr.providers.google_vision import GoogleVisionProvider
from app.ocr.providers.tesseract import TesseractProvider

__all__ = ["EasyOCRProvider", "GoogleVisionProvider", "TesseractProvider"]
