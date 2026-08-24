"""Local storage backend."""

from __future__ import annotations

import pytest

from app.storage.base import StorageBackend
from app.storage.local import LocalStorage


@pytest.fixture
def storage(tmp_path) -> LocalStorage:
    return LocalStorage(tmp_path / "store")


class TestLocalStorage:
    def test_satisfies_protocol(self, storage):
        assert isinstance(storage, StorageBackend)

    def test_save_and_read(self, storage):
        stored = storage.save(b"handwriting", key="a/b.png", content_type="image/png")
        assert stored.key == "a/b.png"
        assert stored.size == len(b"handwriting")
        assert storage.read("a/b.png") == b"handwriting"

    def test_nested_directories_created(self, storage):
        storage.save(b"x", key="2026/08/23/deep/file.png", content_type="image/png")
        assert storage.exists("2026/08/23/deep/file.png")

    def test_overwrite_replaces_content(self, storage):
        storage.save(b"first", key="k.png", content_type="image/png")
        storage.save(b"second", key="k.png", content_type="image/png")
        assert storage.read("k.png") == b"second"

    def test_open_returns_stream(self, storage):
        storage.save(b"stream me", key="s.png", content_type="image/png")
        with storage.open("s.png") as fh:
            assert fh.read() == b"stream me"

    def test_missing_key_raises(self, storage):
        with pytest.raises(FileNotFoundError):
            storage.read("nope.png")

    def test_delete_is_idempotent(self, storage):
        storage.save(b"x", key="d.png", content_type="image/png")
        storage.delete("d.png")
        storage.delete("d.png")  # must not raise
        assert not storage.exists("d.png")

    def test_url_uses_public_prefix(self, tmp_path):
        s = LocalStorage(tmp_path, public_url_prefix="/media")
        assert s.url("a/b.png") == "/media/a/b.png"

    @pytest.mark.parametrize(
        "key",
        ["../escape.txt", "../../etc/passwd", "a/../../../outside.png"],
    )
    def test_path_traversal_refused(self, storage, key):
        # A key that escapes the root would let a caller read or overwrite
        # arbitrary files on the host.
        with pytest.raises(ValueError, match="escapes"):
            storage.save(b"bad", key=key, content_type="text/plain")

    def test_traversal_key_reports_absent_rather_than_leaking(self, storage):
        assert storage.exists("../../etc/passwd") is False

    def test_no_temp_files_left_behind(self, storage):
        storage.save(b"x", key="t.png", content_type="image/png")
        leftovers = list(storage.root.rglob("*.tmp"))
        assert leftovers == []

    def test_a_traversal_key_deletes_nothing(self, storage, tmp_path):
        """Deletion refuses an escaping key without raising.

        The caller is usually a rollback path, and a rollback that raises
        leaves the transaction it was cleaning up after in a worse state than
        the failure it was handling. Refusing quietly — and logging — is the
        behaviour that keeps the outer failure the one reported.
        """
        outsider = tmp_path / "not-ours.txt"
        outsider.write_text("someone else's file")

        storage.delete(f"../{outsider.name}")

        assert outsider.exists()

    def test_clear_empties_the_root_but_keeps_it_usable(self, storage):
        storage.save(b"x", key="a/b.png", content_type="image/png")
        storage.clear()
        assert storage.exists("a/b.png") is False
        # Still writable afterwards: clear() recreates the root rather than
        # leaving the next save to fail on a missing directory.
        storage.save(b"y", key="a/c.png", content_type="image/png")
        assert storage.read("a/c.png") == b"y"
