"""Image preprocessing (07-ocr-architecture.md §4.2).

Applied to a copy. The original upload is always retained unmodified, so a
preprocessing bug can never destroy the evidence of what the student wrote.

OpenCV and NumPy are optional at runtime: if they are absent the image is
passed through with only the Pillow-based steps applied. That keeps the module
importable in a minimal install, where the tests run.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps

from app.core.logging import get_logger

logger = get_logger(__name__)

# Downscaling past this stops helping recognition and starts destroying the
# thin strokes of handwriting; beyond it, inference cost grows with no accuracy
# gain to show for it.
MAX_EDGE_PX = 2000
MIN_EDGE_PX = 600

# A page skewed by less than this reads no better for being rotated, and every
# rotation resamples the image and softens the strokes.
MIN_DESKEW_DEGREES = 0.3
MAX_DESKEW_DEGREES = 15.0


@dataclass(frozen=True)
class PreprocessResult:
    data: bytes
    steps: list[str]
    width: int
    height: int


def _cv2():
    """OpenCV and NumPy, or ``(None, None)`` when not installed."""
    try:
        import cv2
        import numpy
    except ImportError:  # pragma: no cover - exercised only in minimal installs
        return None, None
    return cv2, numpy


def estimate_skew(gray) -> float:
    """The rotation, in degrees, that would straighten the text.

    Returns a *correction*: feed it straight to ``getRotationMatrix2D``. Uses
    the minimum-area rectangle around the dark pixels. A phone photograph of a
    page is rarely square to the paper, and a few degrees of rotation
    measurably costs line-segmentation accuracy.
    """
    cv2, _np = _cv2()
    if cv2 is None:  # pragma: no cover
        return 0.0

    inverted = cv2.bitwise_not(gray)
    threshold = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = cv2.findNonZero(threshold)
    if coords is None:
        return 0.0

    angle = float(cv2.minAreaRect(coords)[-1])

    # The reported angle identifies the rectangle's orientation only up to a
    # quarter turn, and *which* quarter OpenCV picks has changed between major
    # versions: 4.5+ reports [0, 90), 5.0 reports [-90, 0]. Reducing modulo 90
    # into (-45, 45] yields the same correction under either convention, so
    # this does not silently stop working on an OpenCV upgrade — which is
    # exactly what it did do before.
    angle %= 90
    if angle > 45:
        angle -= 90
    return angle


def preprocess(data: bytes) -> PreprocessResult:
    """Normalise an image for recognition.

    Returns PNG bytes: the pipeline is lossless from here on, and re-encoding a
    denoised image as JPEG would reintroduce exactly the artefacts the denoise
    step just removed.
    """
    steps: list[str] = []

    with Image.open(io.BytesIO(data)) as img:
        # EXIF orientation is metadata, and most engines ignore it. A photo
        # taken in portrait would otherwise be fed to the recogniser sideways.
        img = ImageOps.exif_transpose(img)
        if img.mode != "L":
            # Handwriting is monochrome; colour contributes noise, not signal.
            img = img.convert("L")
            steps.append("grayscale")

        img = _bounded_resize(img, steps)
        working = img.copy()

    cv2, np = _cv2()
    if cv2 is None:  # pragma: no cover - minimal install
        logger.debug("OpenCV unavailable; applying Pillow-only preprocessing")
        working = ImageOps.autocontrast(working)
        steps.append("autocontrast")
        return _encode(working, steps)

    array = np.array(working)

    angle = estimate_skew(array)
    if MIN_DESKEW_DEGREES < abs(angle) <= MAX_DESKEW_DEGREES:
        height, width = array.shape[:2]
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
        array = cv2.warpAffine(
            array,
            matrix,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        steps.append(f"deskew({angle:+.1f}°)")

    # CLAHE rather than a global stretch: a photographed page usually has a
    # lighting gradient across it, and one global curve either blows out the
    # bright corner or loses the shadowed one.
    array = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(array)
    steps.append("clahe")

    # Edge-preserving, because handwriting *is* edges. A Gaussian blur would
    # remove paper grain and the thin strokes together.
    array = cv2.fastNlMeansDenoising(array, None, h=7, templateWindowSize=7, searchWindowSize=21)
    steps.append("denoise")

    return _encode(Image.fromarray(array), steps)


def _bounded_resize(img: Image.Image, steps: list[str]) -> Image.Image:
    longest = max(img.size)

    if longest > MAX_EDGE_PX:
        scale = MAX_EDGE_PX / longest
        size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
        # LANCZOS on the way down: it preserves stroke contrast far better than
        # a box filter, which is what recognition depends on.
        img = img.resize(size, Image.Resampling.LANCZOS)
        steps.append(f"downscale({size[0]}x{size[1]})")

    elif longest < MIN_EDGE_PX:
        # Upscaling adds no information, but most recognisers have a minimum
        # effective text height and simply miss lines below it.
        scale = MIN_EDGE_PX / longest
        size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
        img = img.resize(size, Image.Resampling.LANCZOS)
        steps.append(f"upscale({size[0]}x{size[1]})")

    return img


def _encode(img: Image.Image, steps: list[str]) -> PreprocessResult:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=False)
    return PreprocessResult(data=buffer.getvalue(), steps=steps, width=img.width, height=img.height)
