"""Provider-independent persistent media storage.

The production backend is any S3-compatible service (Cloudflare R2 is the
deployment target). Callers deliberately keep the small historical interface:
``init_storage``, ``make_path``, ``put_bytes``, ``get_bytes``, ``exists``,
``download_to_tmp`` and ``health``.

Existing database paths are preserved during migration:

* paths containing ``/`` keep their object key unchanged;
* legacy bare filenames are read from the packaged local directory first, then
  from ``{STORAGE_APP_NAME}/legacy/{filename}`` in object storage.

This dual-read strategy makes the transition reversible. New writes always go
to object storage, and no function in this module deletes source data.
"""
from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import threading
from pathlib import Path, PurePosixPath
from typing import Any, Tuple

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

logger = logging.getLogger("uvicorn.error")

APP_NAME = (os.environ.get("STORAGE_APP_NAME") or "lakeview").strip().strip("/")
STORAGE_BACKEND = (os.environ.get("STORAGE_BACKEND") or "s3").strip().lower()
LOCAL_STORAGE_DIR = Path(
    os.environ.get("MEDIA_STORAGE_DIR", "/app/backend/media_storage")
)

_client: Any = None
_init_lock = threading.Lock()


def _safe_object_key(path: str) -> str:
    """Return a normalized object key or reject traversal/absolute paths."""
    raw = (path or "").strip().replace("\\", "/")
    parsed = PurePosixPath(raw)
    if not raw or raw.startswith("/") or any(part in ("", ".", "..") for part in parsed.parts):
        raise ValueError(f"invalid storage path: {path!r}")
    return str(parsed)


def is_remote_path(path: str) -> bool:
    """Historical discriminator retained for callers and migration tooling."""
    return "/" in (path or "")


def legacy_object_key(filename: str) -> str:
    """Stable R2 key used for a legacy bare-filename database value."""
    safe_name = _safe_object_key(filename)
    if "/" in safe_name:
        raise ValueError(f"legacy path must be a bare filename: {filename!r}")
    return f"{APP_NAME}/legacy/{safe_name}"


def _required_s3_settings() -> dict[str, str]:
    names = (
        "S3_ENDPOINT_URL",
        "S3_ACCESS_KEY_ID",
        "S3_SECRET_ACCESS_KEY",
        "S3_BUCKET",
    )
    missing = [name for name in names if not (os.environ.get(name) or "").strip()]
    if missing:
        raise RuntimeError(
            "S3 storage is not configured; missing " + ", ".join(sorted(missing))
        )
    return {name: os.environ[name].strip() for name in names}


def init_storage() -> str:
    """Initialize the configured backend once and return its backend name."""
    global _client
    if STORAGE_BACKEND == "local":
        if (os.environ.get("ENVIRONMENT") or "").strip().lower() == "production":
            raise RuntimeError("STORAGE_BACKEND=local is forbidden in production")
        LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        return "local"
    if STORAGE_BACKEND != "s3":
        raise RuntimeError(f"unsupported STORAGE_BACKEND={STORAGE_BACKEND!r}")
    if _client is not None:
        return "s3"
    with _init_lock:
        if _client is not None:
            return "s3"
        settings = _required_s3_settings()
        _client = boto3.client(
            "s3",
            endpoint_url=settings["S3_ENDPOINT_URL"],
            aws_access_key_id=settings["S3_ACCESS_KEY_ID"],
            aws_secret_access_key=settings["S3_SECRET_ACCESS_KEY"],
            region_name=(os.environ.get("S3_REGION") or "auto").strip(),
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 4, "mode": "standard"},
                connect_timeout=10,
                read_timeout=60,
            ),
        )
    logger.info("[storage] S3-compatible storage initialized (app=%s)", APP_NAME)
    return "s3"


def _s3_client():
    init_storage()
    return _client


def _bucket() -> str:
    return _required_s3_settings()["S3_BUCKET"]


def make_path(subdir: str, asset_id: str, ext: str) -> str:
    """Canonical object key: ``{APP_NAME}/{subdir}/{asset_id}.{ext}``."""
    subdir = _safe_object_key(subdir).strip("/")
    asset_id = _safe_object_key(asset_id)
    ext = (ext or "bin").strip().lower().lstrip(".")
    if "/" in asset_id or not ext.isalnum():
        raise ValueError("asset_id and extension must not contain path separators")
    return _safe_object_key(f"{APP_NAME}/{subdir}/{asset_id}.{ext}")


def _local_path(key: str) -> Path:
    safe = _safe_object_key(key)
    target = (LOCAL_STORAGE_DIR / safe).resolve()
    root = LOCAL_STORAGE_DIR.resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"storage path escapes local root: {key!r}")
    return target


def put_bytes(path: str, data: bytes, content_type: str) -> dict:
    """Write a canonical object. Bare filenames are intentionally rejected."""
    if not is_remote_path(path):
        raise ValueError(f"put_bytes requires an object key containing '/': {path!r}")
    key = _safe_object_key(path)
    if STORAGE_BACKEND == "local":
        init_storage()
        target = _local_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {"path": key, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    digest = hashlib.sha256(data).hexdigest()
    response = _s3_client().put_object(
        Bucket=_bucket(),
        Key=key,
        Body=data,
        ContentType=content_type or "application/octet-stream",
        Metadata={"sha256": digest},
    )
    return {
        "path": key,
        "size": len(data),
        "sha256": digest,
        "etag": str(response.get("ETag", "")).strip('"'),
    }


def _read_object(key: str) -> Tuple[bytes, str]:
    if STORAGE_BACKEND == "local":
        init_storage()
        local = _local_path(key)
        if not local.is_file():
            raise FileNotFoundError(f"object not in local storage: {key}")
        return local.read_bytes(), mimetypes.guess_type(local.name)[0] or "application/octet-stream"
    try:
        response = _s3_client().get_object(Bucket=_bucket(), Key=_safe_object_key(key))
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        code = exc.response.get("Error", {}).get("Code")
        if status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
            raise FileNotFoundError(f"object not in storage: {key}") from exc
        raise
    return (
        response["Body"].read(),
        response.get("ContentType") or "application/octet-stream",
    )


def get_bytes(path: str) -> Tuple[bytes, str]:
    """Read bytes and content type with the legacy local-to-R2 fallback."""
    if is_remote_path(path):
        return _read_object(_safe_object_key(path))

    local = _local_path(path)
    if local.is_file():
        return local.read_bytes(), mimetypes.guess_type(local.name)[0] or "application/octet-stream"
    return _read_object(legacy_object_key(path))


def _object_exists(key: str) -> bool:
    if STORAGE_BACKEND == "local":
        init_storage()
        return _local_path(key).is_file()
    try:
        _s3_client().head_object(Bucket=_bucket(), Key=_safe_object_key(key))
        return True
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        code = exc.response.get("Error", {}).get("Code")
        if status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
            return False
        logger.warning("[storage] head_object failed for %s: %s", key, exc)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("[storage] existence check failed for %s: %s", key, exc)
        return False


def exists(path: str) -> bool:
    """Check presence without downloading the object."""
    if is_remote_path(path):
        return _object_exists(path)
    if _local_path(path).is_file():
        return True
    return _object_exists(legacy_object_key(path))


def download_to_tmp(path: str, dest: Path) -> None:
    """Copy an object to scratch space. The caller owns destination cleanup."""
    data, _ = get_bytes(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def health() -> dict:
    """Read-only reachability probe suitable for readiness diagnostics."""
    info = {
        "backend": STORAGE_BACKEND,
        "app_name": APP_NAME,
        "configured": False,
        "reachable": False,
        "error": None,
    }
    try:
        backend = init_storage()
        info["configured"] = True
        if backend == "local":
            info["reachable"] = LOCAL_STORAGE_DIR.is_dir() and os.access(LOCAL_STORAGE_DIR, os.R_OK | os.W_OK)
        else:
            _s3_client().head_bucket(Bucket=_bucket())
            info["reachable"] = True
    except Exception as exc:  # noqa: BLE001
        info["error"] = str(exc)[:200]
    return info
