"""The S3 backend, and the promise that the two backends are interchangeable.

NFR-6.4 says storage is reached through an abstraction so a deployment can
move from local disk to object storage without touching business logic. That
is a claim about *behaviour*, not about type signatures, so the same
assertions run against both backends here.

``boto3`` is an optional dependency the default deployment does not install,
so the client is a fake standing in for it. A fake rather than a mock: a mock
would agree with whatever the code did, including calling ``get_object`` with
the wrong keyword, while this reproduces the real interface closely enough to
disagree.
"""

from __future__ import annotations

import io
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.storage.base import StorageBackend, StoredFile
from app.storage.local import LocalStorage


class NoSuchKey(Exception):  # noqa: N818 — boto3's own name; the code catches it by attribute
    """The error boto3 generates per client, reproduced under its real name."""


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.exceptions = SimpleNamespace(NoSuchKey=NoSuchKey)
        self.calls: list[str] = []

    # The capitalised keywords are boto3's own. A fake that accepted
    # lowercase ones would pass while the real client raised TypeError.
    def put_object(self, *, Bucket, Key, Body, ContentType):  # noqa: N803
        self.calls.append("put_object")
        self.objects[Key] = (Body, ContentType)
        return {"ETag": "fake"}

    def get_object(self, *, Bucket, Key):  # noqa: N803
        self.calls.append("get_object")
        if Key not in self.objects:
            raise NoSuchKey(Key)
        return {"Body": io.BytesIO(self.objects[Key][0])}

    def delete_object(self, *, Bucket, Key):  # noqa: N803
        self.calls.append("delete_object")
        self.objects.pop(Key, None)
        return {}

    def head_object(self, *, Bucket, Key):  # noqa: N803
        self.calls.append("head_object")
        if Key not in self.objects:
            raise NoSuchKey(Key)
        return {"ContentLength": len(self.objects[Key][0])}

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):  # noqa: N803
        self.calls.append("generate_presigned_url")
        return (
            f"https://fake-s3.test/{Params['Bucket']}/{Params['Key']}"
            f"?X-Amz-Expires={ExpiresIn}&X-Amz-Signature=deadbeef"
        )


@pytest.fixture
def fake_boto3(monkeypatch: pytest.MonkeyPatch) -> FakeS3Client:
    """Install a stand-in ``boto3`` for the lazy import inside S3Storage."""
    client = FakeS3Client()
    module = ModuleType("boto3")
    module.client = lambda service, **kwargs: client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", module)
    return client


@pytest.fixture
def s3(fake_boto3):
    from app.storage.s3 import S3Storage

    return S3Storage(
        bucket="graphmaster-test",
        endpoint_url="https://fake-s3.test",
        access_key_id="key",
        secret_access_key="secret",
        region="eu-west-1",
    )


@pytest.fixture(params=["local", "s3"])
def backend(request, tmp_path, fake_boto3):
    """Each behaviour test runs once per backend."""
    if request.param == "local":
        return LocalStorage(tmp_path / "store")

    from app.storage.s3 import S3Storage

    return S3Storage(bucket="graphmaster-test")


class TestBackendsBehaveAlike:
    """What business logic is entitled to assume, whichever backend is configured."""

    def test_satisfies_the_protocol(self, backend):
        assert isinstance(backend, StorageBackend)

    def test_saving_returns_the_key_and_the_size(self, backend):
        stored = backend.save(b"handwritten answer", key="hw/2026/a.png", content_type="image/png")
        assert isinstance(stored, StoredFile)
        assert stored.key == "hw/2026/a.png"
        assert stored.size == len(b"handwritten answer")
        assert stored.content_type == "image/png"
        assert stored.url

    def test_what_was_saved_reads_back_byte_for_byte(self, backend):
        backend.save(b"\x89PNG\r\n\x1a\n binary", key="hw/b.png", content_type="image/png")
        assert backend.read("hw/b.png") == b"\x89PNG\r\n\x1a\n binary"

    def test_open_streams_the_same_bytes(self, backend):
        backend.save(b"streamed", key="hw/c.png", content_type="image/png")
        with backend.open("hw/c.png") as handle:
            assert handle.read() == b"streamed"

    def test_a_missing_key_raises_file_not_found(self, backend):
        """The submission service catches this one exception, whatever the backend."""
        with pytest.raises(FileNotFoundError):
            backend.read("hw/never-written.png")

    def test_exists_reports_both_answers(self, backend):
        assert backend.exists("hw/d.png") is False
        backend.save(b"x", key="hw/d.png", content_type="image/png")
        assert backend.exists("hw/d.png") is True

    def test_deleting_is_idempotent(self, backend):
        """A rollback may delete a key the failed write never created."""
        backend.save(b"x", key="hw/e.png", content_type="image/png")
        backend.delete("hw/e.png")
        backend.delete("hw/e.png")
        assert backend.exists("hw/e.png") is False

    def test_overwriting_a_key_replaces_it(self, backend):
        backend.save(b"first", key="hw/f.png", content_type="image/png")
        backend.save(b"second", key="hw/f.png", content_type="image/png")
        assert backend.read("hw/f.png") == b"second"


class TestS3Specifics:
    def test_the_url_is_presigned_and_expires(self, s3, fake_boto3):
        """Never a bare public URL.

        Handwriting is a student's own work; an object key that grants access
        to anyone who learns it is the same leak the authenticated streaming
        endpoint exists to prevent.
        """
        s3.save(b"x", key="hw/g.png", content_type="image/png")
        url = s3.url("hw/g.png")
        assert "generate_presigned_url" in fake_boto3.calls
        assert "X-Amz-Signature" in url
        assert "X-Amz-Expires=3600" in url

    def test_the_content_type_is_stored_with_the_object(self, s3, fake_boto3):
        """Served back without it, a browser sniffs — and X-Content-Type-Options blocks it."""
        s3.save(b"x", key="hw/h.png", content_type="image/jpeg")
        assert fake_boto3.objects["hw/h.png"][1] == "image/jpeg"

    def test_a_head_failure_is_not_an_exists_failure(self, s3, monkeypatch):
        """A network error means "cannot tell", and the caller asked a yes/no question.

        Reported as False so a transient outage cannot take down a request
        that only wanted to know whether to bother reading.
        """

        def unreachable(**kwargs):
            raise ConnectionError("endpoint unreachable")

        monkeypatch.setattr(s3._client, "head_object", unreachable)
        assert s3.exists("hw/i.png") is False


class TestFactory:
    def test_the_configured_backend_is_the_one_built(self, monkeypatch, fake_boto3):
        """A deployment switches backend by configuration alone."""
        from app.core.config import get_settings
        from app.storage.factory import get_storage
        from app.storage.s3 import S3Storage

        settings = get_settings()
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
        monkeypatch.setattr(settings, "S3_BUCKET", "graphmaster-prod", raising=False)
        get_storage.cache_clear()
        try:
            assert isinstance(get_storage(), S3Storage)
        finally:
            get_storage.cache_clear()

    def test_local_is_the_default(self, monkeypatch):
        from app.core.config import get_settings
        from app.storage.factory import get_storage

        monkeypatch.setattr(get_settings(), "STORAGE_BACKEND", "local")
        get_storage.cache_clear()
        try:
            assert isinstance(get_storage(), LocalStorage)
        finally:
            get_storage.cache_clear()
