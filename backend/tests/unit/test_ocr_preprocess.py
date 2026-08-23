"""Image preprocessing."""

from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.ocr.preprocess import (
    MAX_EDGE_PX,
    MIN_EDGE_PX,
    estimate_skew,
    preprocess,
)

cv2 = pytest.importorskip("cv2", reason="OpenCV is optional; skipped in a minimal install")
np = pytest.importorskip("numpy")


def _font(size: int = 34):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def text_page(rotation: float = 0.0, size: tuple[int, int] = (900, 300)) -> Image.Image:
    img = Image.new("L", size, 255)
    draw = ImageDraw.Draw(img)
    font = _font()
    for index, line in enumerate(["The line graph illustrates", "a steady increase in output"]):
        draw.text((30, 40 + index * 80), line, fill=0, font=font)
    return img.rotate(rotation, expand=True, fillcolor=255) if rotation else img


def as_png(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    img.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


# ── Skew estimation ──────────────────────────────────────────────────────────


def test_flat_page_needs_no_correction() -> None:
    assert abs(estimate_skew(np.array(text_page()))) < 0.5


@pytest.mark.parametrize("rotation", [-8.0, -5.0, -3.0, 3.0, 5.0, 8.0])
def test_estimates_the_correcting_rotation(rotation: float) -> None:
    """Returns the angle that *undoes* the skew, so it negates the rotation.

    Regression guard: OpenCV reports the rectangle angle in a different
    quadrant between major versions (4.5+ uses [0, 90), 5.0 uses [-90, 0]).
    Before this was normalised modulo 90, deskew silently never fired.
    """
    estimated = estimate_skew(np.array(text_page(rotation)))
    assert estimated == pytest.approx(-rotation, abs=0.6)


def test_estimate_is_zero_for_a_blank_page() -> None:
    assert estimate_skew(np.array(Image.new("L", (400, 400), 255))) == 0.0


# ── The pipeline ─────────────────────────────────────────────────────────────


def test_converts_to_grayscale() -> None:
    result = preprocess(as_png(text_page()))
    assert "grayscale" in result.steps
    with Image.open(io.BytesIO(result.data)) as img:
        assert img.mode == "L"


def test_deskews_a_rotated_page() -> None:
    result = preprocess(as_png(text_page(4.0)))
    assert any(step.startswith("deskew") for step in result.steps)


def test_does_not_deskew_a_nearly_straight_page() -> None:
    """Every rotation resamples and softens the strokes; a 0.1° tilt is not
    worth paying that for."""
    result = preprocess(as_png(text_page(0.1)))
    assert not any(step.startswith("deskew") for step in result.steps)


def test_downscales_an_oversized_photo() -> None:
    big = Image.new("L", (MAX_EDGE_PX * 2, 800), 255)
    result = preprocess(as_png(big))
    assert max(result.width, result.height) <= MAX_EDGE_PX
    assert any(step.startswith("downscale") for step in result.steps)


def test_upscales_a_tiny_image() -> None:
    """Most recognisers simply miss text below a minimum effective height."""
    result = preprocess(as_png(Image.new("L", (200, 120), 255)))
    assert max(result.width, result.height) >= MIN_EDGE_PX
    assert any(step.startswith("upscale") for step in result.steps)


def test_leaves_a_reasonably_sized_image_alone() -> None:
    result = preprocess(as_png(text_page(size=(1200, 800))))
    assert not any(s.startswith(("upscale", "downscale")) for s in result.steps)


def test_output_is_png() -> None:
    """Re-encoding as JPEG would reintroduce the artefacts denoise removed."""
    result = preprocess(as_png(text_page()))
    with Image.open(io.BytesIO(result.data)) as img:
        assert img.format == "PNG"


def test_honours_exif_orientation() -> None:
    """A portrait phone photo would otherwise be recognised sideways."""
    img = text_page(size=(900, 300))
    buffer = io.BytesIO()
    exif = Image.Exif()
    exif[274] = 6  # Rotate 90° clockwise
    img.convert("RGB").save(buffer, format="JPEG", exif=exif)

    result = preprocess(buffer.getvalue())
    # The transpose swaps the axes, so a landscape source becomes portrait.
    assert result.height > result.width


def test_preserves_the_original_bytes() -> None:
    """Preprocessing works on a copy; the stored original stays untouched."""
    original = as_png(text_page())
    snapshot = bytes(original)
    preprocess(original)
    assert original == snapshot
