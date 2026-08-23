"""Storage backend selection."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.storage.base import StorageBackend
from app.storage.local import LocalStorage


@lru_cache
def get_storage() -> StorageBackend:
    settings = get_settings()

    if settings.STORAGE_BACKEND == "s3":
        from app.storage.s3 import S3Storage

        return S3Storage(
            bucket=settings.S3_BUCKET or "",
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key_id=settings.S3_ACCESS_KEY_ID,
            secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region=settings.S3_REGION,
        )

    return LocalStorage(settings.STORAGE_LOCAL_PATH, settings.STORAGE_PUBLIC_URL)
