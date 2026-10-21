from __future__ import annotations

import io

import pytest
from botocore.exceptions import ClientError

import storage


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.put_calls = 0
        self.head_bucket_calls = 0

    def put_object(self, **kwargs):
        self.put_calls += 1
        data = kwargs["Body"]
        self.objects[kwargs["Key"]] = {
            "data": data,
            "content_type": kwargs["ContentType"],
            "metadata": kwargs.get("Metadata", {}),
        }
        return {"ETag": '"test-etag"'}

    def get_object(self, **kwargs):
        if kwargs["Key"] not in self.objects:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
                "GetObject",
            )
        item = self.objects[kwargs["Key"]]
        return {"Body": io.BytesIO(item["data"]), "ContentType": item["content_type"]}

    def head_object(self, **kwargs):
        if kwargs["Key"] not in self.objects:
            raise ClientError(
                {"Error": {"Code": "NotFound"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
                "HeadObject",
            )
        item = self.objects[kwargs["Key"]]
        return {"ContentLength": len(item["data"]), "Metadata": item["metadata"]}

    def head_bucket(self, **kwargs):
        self.head_bucket_calls += 1
        return {}


@pytest.fixture
def fake_storage(monkeypatch, tmp_path):
    fake = FakeS3()
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage, "APP_NAME", "lakeview")
    monkeypatch.setattr(storage, "LOCAL_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(storage, "_client", fake)
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://example.invalid")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    return fake, tmp_path


def test_make_path_preserves_existing_key_shape():
    assert storage.make_path("uploads", "abc-123", "PNG") == "lakeview/uploads/abc-123.png"


@pytest.mark.parametrize("bad", ("../secret", "/absolute", "folder/../../secret"))
def test_storage_rejects_unsafe_paths(bad):
    with pytest.raises(ValueError):
        storage.get_bytes(bad)


def test_put_and_get_s3_object_with_checksum_metadata(fake_storage):
    fake, _ = fake_storage
    result = storage.put_bytes("lakeview/uploads/one.jpg", b"image", "image/jpeg")
    assert result["path"] == "lakeview/uploads/one.jpg"
    assert result["sha256"] == "6105d6cc76af400325e94d588ce511be5bfdbb73b437dc51eca43917d7a43e3d"
    assert storage.get_bytes(result["path"]) == (b"image", "image/jpeg")
    assert fake.objects[result["path"]]["metadata"]["sha256"] == result["sha256"]


def test_legacy_path_prefers_local_then_falls_back_to_stable_s3_key(fake_storage):
    fake, local_dir = fake_storage
    (local_dir / "old.jpg").write_bytes(b"local")
    assert storage.get_bytes("old.jpg") == (b"local", "image/jpeg")

    fake.objects["lakeview/legacy/remote.jpg"] = {
        "data": b"remote",
        "content_type": "image/jpeg",
        "metadata": {},
    }
    assert storage.get_bytes("remote.jpg") == (b"remote", "image/jpeg")
    assert storage.exists("remote.jpg") is True


def test_health_is_read_only(fake_storage):
    fake, _ = fake_storage
    assert storage.health() == {
        "backend": "s3",
        "app_name": "lakeview",
        "configured": True,
        "reachable": True,
        "error": None,
    }
    assert fake.head_bucket_calls == 1
    assert fake.put_calls == 0
