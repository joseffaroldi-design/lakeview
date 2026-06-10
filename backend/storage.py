"""Persistent media storage — Emergent Object Storage with legacy local fallback.

All NEW media (uploads, AI images, edits, exports, rendered videos) is written
to Emergent Object Storage so it survives pod restarts, deploys, and scaling
events. The canonical path shape is `{APP_NAME}/{subdir}/{uuid}.{ext}` (always
contains '/'). Legacy `media_assets` rows whose `storage_path` is just a bare
filename (no '/') still resolve via the local /app/backend/media_storage fallback
so old test data keeps working in preview.

The storage backend is opaque to callers: `put_bytes`, `get_bytes`, `exists`,
`download_to_tmp`, `make_path`, `health` are the only public functions.
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Optional, Tuple

import requests

logger = logging.getLogger("uvicorn.error")

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = os.environ.get("STORAGE_APP_NAME", "lakeview")

# Local fallback (still used for legacy paths AND as a tmp scratch dir for
# ffmpeg pipelines that need filesystem inputs).
LOCAL_STORAGE_DIR = Path(os.environ.get("MEDIA_STORAGE_DIR", "/app/backend/media_storage"))
LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

_storage_key: Optional[str] = None
_init_lock = threading.Lock()


def is_remote_path(path: str) -> bool:
    """New paths live in object storage (contain '/'); legacy paths are bare filenames."""
    return "/" in (path or "")


def init_storage() -> Optional[str]:
    """Call once at startup. Returns session-scoped storage_key or None if init failed.
    Thread-safe so concurrent first-requests don't fight."""
    global _storage_key
    if _storage_key:
        return _storage_key
    with _init_lock:
        if _storage_key:
            return _storage_key
        key = os.environ.get("EMERGENT_LLM_KEY")
        if not key:
            logger.error("[storage] EMERGENT_LLM_KEY not set — object storage disabled")
            return None
        try:
            r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": key}, timeout=30)
            r.raise_for_status()
            _storage_key = r.json()["storage_key"]
            logger.info("[storage] Emergent Object Storage initialized (app=%s)", APP_NAME)
            return _storage_key
        except Exception as e:  # noqa: BLE001
            logger.error("[storage] init failed: %s", e)
            return None


def _storage_key_or_raise() -> str:
    k = init_storage()
    if not k:
        raise RuntimeError("Object storage unavailable: init failed or EMERGENT_LLM_KEY missing")
    return k


def make_path(subdir: str, asset_id: str, ext: str) -> str:
    """Canonical object-storage path: `{APP_NAME}/{subdir}/{uuid}.{ext}`."""
    return f"{APP_NAME}/{subdir}/{asset_id}.{ext}"


def put_bytes(path: str, data: bytes, content_type: str) -> dict:
    """Upload bytes to object storage. `path` must be a remote path (contains '/').

    Re-initializes the session key once on 403 (expired token)."""
    if not is_remote_path(path):
        raise ValueError(f"put_bytes requires remote path with '/' — got {path!r}")
    key = _storage_key_or_raise()
    headers = {"X-Storage-Key": key, "Content-Type": content_type}
    r = requests.put(f"{STORAGE_URL}/objects/{path}", headers=headers, data=data, timeout=180)
    if r.status_code == 403:
        # Storage key expired — re-init and retry once
        logger.warning("[storage] 403 on put — re-initializing session key")
        global _storage_key
        _storage_key = None
        key = _storage_key_or_raise()
        headers["X-Storage-Key"] = key
        r = requests.put(f"{STORAGE_URL}/objects/{path}", headers=headers, data=data, timeout=180)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return {"path": path, "size": len(data)}


def get_bytes(path: str) -> Tuple[bytes, str]:
    """Download bytes + content-type. Legacy local paths fall back to disk."""
    if not is_remote_path(path):
        local = LOCAL_STORAGE_DIR / path
        if not local.exists():
            raise FileNotFoundError(f"legacy local file missing: {local}")
        return local.read_bytes(), "application/octet-stream"

    key = _storage_key_or_raise()
    headers = {"X-Storage-Key": key}
    r = requests.get(f"{STORAGE_URL}/objects/{path}", headers=headers, timeout=60)
    if r.status_code == 403:
        logger.warning("[storage] 403 on get — re-initializing session key")
        global _storage_key
        _storage_key = None
        key = _storage_key_or_raise()
        headers["X-Storage-Key"] = key
        r = requests.get(f"{STORAGE_URL}/objects/{path}", headers=headers, timeout=60)
    if r.status_code == 404:
        raise FileNotFoundError(f"object not in storage: {path}")
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")


def exists(path: str) -> bool:
    """Cheap presence check. Legacy local paths check disk."""
    if not is_remote_path(path):
        return (LOCAL_STORAGE_DIR / path).exists()
    try:
        key = _storage_key_or_raise()
        # No HEAD endpoint in the API — use a 1-byte ranged GET as a cheap probe.
        r = requests.get(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Range": "bytes=0-0"},
            timeout=10,
        )
        return r.status_code in (200, 206)
    except Exception:  # noqa: BLE001
        return False


def download_to_tmp(path: str, dest: Path) -> None:
    """Download an object to a local path. Used by ffmpeg / PIL pipelines that
    require an actual file on disk. Caller is responsible for cleanup."""
    data, _ = get_bytes(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def health() -> dict:
    """Probe storage reachability. Returns a dict suitable for /api/media/health."""
    info = {
        "backend": "emergent_object_storage",
        "app_name": APP_NAME,
        "reachable": False,
        "initialized": _storage_key is not None,
        "error": None,
    }
    try:
        _storage_key_or_raise()
        # End-to-end probe: PUT a tiny key, GET it back. Proves auth + reachability.
        probe_path = f"{APP_NAME}/_health/probe.txt"
        put_bytes(probe_path, b"ok", "text/plain")
        data, _ = get_bytes(probe_path)
        info["reachable"] = data == b"ok"
        if not info["reachable"]:
            info["error"] = "probe roundtrip mismatch"
    except Exception as e:  # noqa: BLE001
        info["error"] = str(e)[:200]
    return info
