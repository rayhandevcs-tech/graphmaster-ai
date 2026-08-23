"""Storage backend protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Protocol, runtime_checkable


@dataclass(frozen=True)
class StoredFile:
    """A file that has been written to storage."""

    key: str
    """Backend-relative path. This is what gets persisted on the model."""

    url: str
    """Address a client can fetch the file from."""

    size: int
    content_type: str


@runtime_checkable
class StorageBackend(Protocol):
    """The narrow surface business logic is allowed to depend on."""

    def save(self, data: bytes, *, key: str, content_type: str) -> StoredFile:
        """Write bytes under ``key``, overwriting any existing object."""
        ...

    def open(self, key: str) -> BinaryIO:
        """Open a stored file for reading. Raises ``FileNotFoundError`` if absent."""
        ...

    def read(self, key: str) -> bytes: ...

    def url(self, key: str) -> str:
        """A client-fetchable address for ``key``."""
        ...

    def delete(self, key: str) -> None:
        """Remove ``key``. Absent keys are not an error — deletion is idempotent."""
        ...

    def exists(self, key: str) -> bool: ...
