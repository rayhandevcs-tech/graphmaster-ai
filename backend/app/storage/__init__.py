"""File storage abstraction.

Business logic depends on the ``StorageBackend`` protocol only, so moving from
local disk to cloud object storage is a configuration change rather than a code
change (NFR-6.4).
"""

from app.storage.base import StorageBackend, StoredFile
from app.storage.factory import get_storage

__all__ = ["StorageBackend", "StoredFile", "get_storage"]
