"""Upload validation.

The uploaded file is entirely untrusted, so these tests care most about the
cases where the client *lies*: a name, an extension or a declared content type
that disagrees with the actual bytes.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.exceptions import FileTooLargeError, UnsupportedFileTypeError
from app.ocr.validation import sniff_format, validate_upload


def make_image(
    fmt: str = "PNG", size: tuple[int, int] = (200, 120), colour: str = "white"
) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format=fmt)
    return buffer.getvalue()


# ── Signature sniffing ───────────────────────────────────────────────────────


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_accepts_every_allowed_format(fmt: str) -> None:
    validated = validate_upload(make_image(fmt))
    assert validated.image_format == fmt
    assert validated.width == 200
    assert validated.height == 120


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_sniff_matches_the_real_format(fmt: str) -> None:
    assert sniff_format(make_image(fmt)) == fmt


def test_sniff_returns_none_for_non_images() -> None:
    assert sniff_format(b"not an image at all") is None
    assert sniff_format(b"") is None


def test_rejects_a_pdf_named_as_a_png() -> None:
    """The extension is not consulted; only the bytes are."""
    with pytest.raises(UnsupportedFileTypeError, match="not a JPG, PNG or WEBP"):
        validate_upload(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n", filename="answer.png")


def test_rejects_a_gif() -> None:
    """GIF is a real image format, but not one the specification allows."""
    buffer = io.BytesIO()
    Image.new("RGB", (50, 50)).save(buffer, format="GIF")
    with pytest.raises(UnsupportedFileTypeError):
        validate_upload(buffer.getvalue())


def test_rejects_a_script_with_an_image_extension() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        validate_upload(b"<?php system($_GET['c']); ?>", filename="photo.jpg")


def test_error_message_does_not_echo_the_filename() -> None:
    """Repeating what the client claimed invites the reader to trust it."""
    with pytest.raises(UnsupportedFileTypeError) as excinfo:
        validate_upload(b"junk bytes here", filename="<script>alert(1)</script>.png")
    assert "script" not in str(excinfo.value)


# ── Size ─────────────────────────────────────────────────────────────────────


def test_rejects_an_empty_file() -> None:
    with pytest.raises(UnsupportedFileTypeError, match="empty"):
        validate_upload(b"")


def test_rejects_an_oversized_file(monkeypatch) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    # Noise, so PNG compression cannot shrink it back under the limit.
    buffer = io.BytesIO()
    Image.effect_noise((1400, 1400), 128).convert("RGB").save(buffer, format="PNG")
    big = buffer.getvalue()
    assert len(big) > 1_048_576, "test fixture is not actually over the limit"

    with pytest.raises(FileTooLargeError, match="maximum is 1 MB"):
        validate_upload(big)


def test_size_is_checked_before_decoding(monkeypatch) -> None:
    """An oversized file must be refused without a decoder ever parsing it."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "MAX_UPLOAD_SIZE_MB", 1)
    # Not a valid image at all — if the size check runs first, the format
    # check never gets the chance to complain.
    with pytest.raises(FileTooLargeError):
        validate_upload(b"\xff\xd8\xff" + b"\x00" * 2_000_000)


# ── Decodability and dimensions ──────────────────────────────────────────────


def test_rejects_a_truncated_image() -> None:
    """A valid header does not mean a valid file."""
    data = make_image("PNG", (400, 400))
    with pytest.raises(UnsupportedFileTypeError, match="corrupt or incompletely uploaded"):
        validate_upload(data[: len(data) // 2])


def test_rejects_a_decompression_bomb(monkeypatch) -> None:
    """Rejected on the header's pixel count, before any pixel is decoded."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "MAX_IMAGE_PIXELS", 10_000)
    with pytest.raises(UnsupportedFileTypeError, match="too large to process"):
        validate_upload(make_image("PNG", (500, 500)))


def test_accepts_an_image_at_the_pixel_limit(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "MAX_IMAGE_PIXELS", 200 * 120)
    validate_upload(make_image("PNG", (200, 120)))


# ── Storage keys ─────────────────────────────────────────────────────────────


def test_storage_key_is_generated_not_derived() -> None:
    """A client-supplied name can carry traversal or a double extension."""
    validated = validate_upload(make_image("PNG"), filename="../../etc/passwd.png")
    key = validated.storage_key("submissions/handwriting")
    assert ".." not in key
    assert "passwd" not in key
    assert key.startswith("submissions/handwriting/")
    assert key.endswith(".png")


def test_storage_keys_are_unique_per_upload() -> None:
    """Two students uploading at once must not collide."""
    data = make_image("PNG")
    keys = {validate_upload(data).storage_key("p") for _ in range(20)}
    assert len(keys) == 20


@pytest.mark.parametrize(
    ("fmt", "extension", "content_type"),
    [("PNG", ".png", "image/png"), ("JPEG", ".jpg", "image/jpeg"), ("WEBP", ".webp", "image/webp")],
)
def test_extension_and_content_type_come_from_the_bytes(
    fmt: str, extension: str, content_type: str
) -> None:
    validated = validate_upload(make_image(fmt), filename="whatever.txt")
    assert validated.extension == extension
    assert validated.content_type == content_type
