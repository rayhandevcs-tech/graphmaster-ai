"""Upload validation (FR-4.1 – FR-4.3, NFR-2.8).

Every check here runs **before a byte is written to storage**. The uploaded
file is entirely untrusted: its name, its declared ``Content-Type`` and its
extension are all attacker-controlled, so none of them is used to decide what
the file is.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.core.exceptions import FileTooLargeError, UnsupportedFileTypeError
from app.core.logging import get_logger

logger = get_logger(__name__)

# The specification allows JPG, JPEG, PNG and WEBP. Keyed by the signature
# ("magic") bytes each format begins with, because that is the only part of an
# upload the client cannot trivially lie about.
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
RIFF_MAGIC = b"RIFF"
WEBP_MAGIC = b"WEBP"

ALLOWED_FORMATS: dict[str, str] = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}

EXTENSION_FOR_FORMAT: dict[str, str] = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}

# Pillow's own decompression-bomb guard. Set to None so our explicit,
# configurable check below is the single place the limit is expressed;
# leaving Pillow's default active would raise a different, unhandled error at
# a different threshold.
Image.MAX_IMAGE_PIXELS = None


@dataclass(frozen=True)
class ValidatedImage:
    """An upload that passed every check."""

    data: bytes
    image_format: str
    content_type: str
    width: int
    height: int
    size: int

    @property
    def extension(self) -> str:
        return EXTENSION_FOR_FORMAT[self.image_format]

    def storage_key(self, prefix: str) -> str:
        """A generated key under ``prefix``.

        Never derived from the upload's own filename: a client-supplied name
        can carry path traversal, a double extension, or a name that collides
        with another student's file (NFR-2.8).
        """
        return f"{prefix.strip('/')}/{uuid.uuid4().hex}{self.extension}"


def sniff_format(data: bytes) -> str | None:
    """The image format implied by the leading bytes, or None."""
    if data.startswith(JPEG_MAGIC):
        return "JPEG"
    if data.startswith(PNG_MAGIC):
        return "PNG"
    # WEBP is a RIFF container: "RIFF" + 4 size bytes + "WEBP".
    if data.startswith(RIFF_MAGIC) and data[8:12] == WEBP_MAGIC:
        return "WEBP"
    return None


def validate_upload(data: bytes, *, filename: str | None = None) -> ValidatedImage:
    """Check size, signature, decodability and dimensions, in that order.

    Ordered cheapest-first and, more importantly, safest-first: the size and
    signature checks are pure byte inspection, so a hostile file is rejected
    before any decoder is asked to parse it.
    """
    settings = get_settings()
    size = len(data)

    if size == 0:
        raise UnsupportedFileTypeError("The uploaded file is empty.")

    if size > settings.max_upload_bytes:
        raise FileTooLargeError(
            f"The image is {size / 1_048_576:.1f} MB. "
            f"The maximum is {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    image_format = sniff_format(data)
    if image_format is None:
        # Deliberately does not echo the filename or declared content type:
        # reporting what the client claimed invites the reader to trust it.
        raise UnsupportedFileTypeError(
            "That file is not a JPG, PNG or WEBP image. "
            "The file's actual contents are checked, not its name."
        )

    try:
        with Image.open(io.BytesIO(data)) as probe:
            # `Image.open` is lazy — it reads the header only, so the pixel
            # count is known before any pixel data is decoded. That ordering is
            # the whole point: it lets a decompression bomb be rejected without
            # ever allocating its uncompressed size.
            width, height = probe.size
            detected = probe.format or image_format

            if width * height > settings.MAX_IMAGE_PIXELS:
                raise UnsupportedFileTypeError(
                    f"The image is {width}×{height} pixels, which is too large to process. "
                    f"The limit is {settings.MAX_IMAGE_PIXELS:,} pixels."
                )

            if detected not in ALLOWED_FORMATS:
                # The signature said one thing and the decoder another: a
                # polyglot or a mislabelled container. Refuse it.
                raise UnsupportedFileTypeError(
                    f"The file's signature and contents disagree ({image_format} vs {detected})."
                )

            # `verify()` walks the full file and is what catches truncation and
            # internal corruption that a header read alone would accept. It
            # leaves the instance unusable, which is fine — nothing reads pixels
            # from `probe` after this point.
            probe.verify()

    except UnsupportedFileTypeError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        logger.info("Rejected undecodable upload (%s): %s", filename or "unnamed", exc)
        raise UnsupportedFileTypeError(
            "The image could not be read. It may be corrupt or incompletely uploaded."
        ) from exc

    return ValidatedImage(
        data=data,
        image_format=detected,
        content_type=ALLOWED_FORMATS[detected],
        width=width,
        height=height,
        size=size,
    )
