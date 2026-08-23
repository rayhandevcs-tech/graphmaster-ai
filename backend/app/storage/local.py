"""Local filesystem storage backend."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from app.core.logging import get_logger
from app.storage.base import StoredFile

logger = get_logger(__name__)


class LocalStorage:
    """Stores files under a configured root directory.

    The root is deliberately outside any statically served directory: files are
    streamed through an authenticated endpoint rather than exposed by path, so
    one student cannot read another's handwriting by guessing a URL.
    """

    def __init__(self, root: str | Path, public_url_prefix: str = "/media") -> None:
        self.root = Path(root).resolve()
        self.public_url_prefix = public_url_prefix.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        """Resolve ``key`` inside the root, refusing anything that escapes it.

        Without this check a key like ``../../etc/passwd`` would let a caller
        read or overwrite arbitrary files.
        """
        candidate = (self.root / key.lstrip("/")).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError(f"Storage key escapes the storage root: {key!r}")
        return candidate

    def save(self, data: bytes, *, key: str, content_type: str) -> StoredFile:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to a temporary name and rename into place, so a crash mid-write
        # cannot leave a truncated file that later reads as valid.
        tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
        try:
            tmp.write_bytes(data)
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)

        logger.debug("Stored %s (%d bytes)", key, len(data))
        return StoredFile(key=key, url=self.url(key), size=len(data), content_type=content_type)

    def open(self, key: str) -> BinaryIO:
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.open("rb")

    def read(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def url(self, key: str) -> str:
        return f"{self.public_url_prefix}/{key.lstrip('/')}"

    def delete(self, key: str) -> None:
        try:
            self._resolve(key).unlink(missing_ok=True)
        except ValueError:
            logger.warning("Refused to delete out-of-root key %r", key)

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).is_file()
        except ValueError:
            return False

    def clear(self) -> None:
        """Remove everything under the root. Test-suite helper only."""
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
