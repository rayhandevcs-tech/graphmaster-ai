"""S3-compatible storage backend.

Kept behind the same protocol as ``LocalStorage`` so switching is a
configuration change. ``boto3`` is imported lazily: the default deployment uses
local storage and should not need the dependency installed.
"""

from __future__ import annotations

import io
from typing import Any, BinaryIO

from app.core.logging import get_logger
from app.storage.base import StoredFile

logger = get_logger(__name__)


class S3Storage:
    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        region: str | None = None,
    ) -> None:
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "STORAGE_BACKEND is 's3' but boto3 is not installed. "
                "Install it with: pip install boto3"
            ) from exc

        self.bucket = bucket
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )

    def save(self, data: bytes, *, key: str, content_type: str) -> StoredFile:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return StoredFile(key=key, url=self.url(key), size=len(data), content_type=content_type)

    def open(self, key: str) -> BinaryIO:
        return io.BytesIO(self.read(key))

    def read(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
        except self._client.exceptions.NoSuchKey as exc:
            raise FileNotFoundError(key) from exc
        return response["Body"].read()

    def url(self, key: str) -> str:
        """A time-limited presigned URL.

        Never a bare public URL: student handwriting must not be readable by
        anyone who learns the object key.
        """
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=3600
        )

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False
