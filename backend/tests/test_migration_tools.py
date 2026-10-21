from __future__ import annotations

import hashlib
import io

from scripts import migrate_media, migrate_mongodb


def test_local_media_inventory_is_deterministic_and_checksum_backed(tmp_path):
    (tmp_path / "b.jpg").write_bytes(b"second")
    (tmp_path / "a.png").write_bytes(b"first")

    first = migrate_media._local_inventory(tmp_path)
    second = migrate_media._local_inventory(tmp_path)

    assert first == second
    assert first["files"] == 2
    assert first["bytes"] == 11
    assert [item["path"] for item in first["manifest"]] == ["a.png", "b.jpg"]
    assert first["manifest"][0]["sha256"] == hashlib.sha256(b"first").hexdigest()


def test_media_target_keys_preserve_remote_and_namespace_legacy():
    assert migrate_media._target_key("lakeview/uploads/one.jpg", "lakeview") == "lakeview/uploads/one.jpg"
    assert migrate_media._target_key("old.jpg", "lakeview") == "lakeview/legacy/old.jpg"


class _ExistingObjectClient:
    def __init__(self):
        self.downloads = 0

    def head_object(self, **kwargs):
        return {
            "ContentLength": len(b"actual-bytes"),
            "Metadata": {"sha256": hashlib.sha256(b"wrong-bytes").hexdigest()},
        }

    def get_object(self, **kwargs):
        self.downloads += 1
        return {"Body": io.BytesIO(b"actual-bytes")}


def test_media_verification_hashes_remote_bytes_instead_of_trusting_metadata():
    client = _ExistingObjectClient()
    digest, size = migrate_media._existing_digest(
        client, "bucket", "lakeview/uploads/one.jpg", verify_existing=True
    )

    assert client.downloads == 1
    assert size == len(b"actual-bytes")
    assert digest == hashlib.sha256(b"actual-bytes").hexdigest()


class _CountOnlyCollection:
    def count_documents(self, query):
        return 3


class _SourceDatabase:
    name = "source"

    def list_collection_names(self):
        return ["content"]

    def __getitem__(self, name):
        assert name == "content"
        return _CountOnlyCollection()


class _TargetDatabase:
    name = "target"

    def __getitem__(self, name):
        raise AssertionError("dry-run must not access or write target collections")


def test_mongo_sync_defaults_to_non_mutating_plan():
    report = migrate_mongodb.sync_databases(
        _SourceDatabase(), _TargetDatabase(), selected=None, apply=False, batch_size=250
    )
    assert report["mode"] == "dry-run"
    assert report["deletes_performed"] == 0
    assert report["collections"]["content"]["upserts_planned"] == 3
