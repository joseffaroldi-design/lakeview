"""Phase 10 — Persistence + Janitor backend tests (trimmed Sprint 16B.3).

Original file covered upload/file/thumb/AI-image/edit/export-social/video-
render persistence + AI-image janitor + health. Sprint 15B removed:

  /api/media/ai-image (now /api/ai-image/generate, owned by ai_image router)
  /api/media/edit
  /api/media/export-social
  /api/media/video/render + /video/jobs/*
  /api/ai-ads/plugins, /api/ai-ads/plugins/restaurant

This file now covers the surviving persistence path only:
  • Upload → /file → /thumb roundtrip + storage_path prefix
  • Duplicate clones bytes + gets new storage_path
  • Soft-delete: DELETE /api/media/assets/{id} → status=archived
  • /api/media/health storage + queue shape
  • A bogus asset id on /file returns 404 (legacy-fallback negative path)
  • Removed routes regression
  • Public-route regression smokes (menu, specials, root)

Restart-survival tests for AI image jobs are removed — the AI image
pipeline moved to /api/ai-image/* and is covered by
test_ai_image_async.py / test_ai_image_generation.py.
"""
import io
import os
import uuid

import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://food-graphics-lab.preview.emergentagent.com",
).rstrip("/")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
TIMEOUT = 30


def _fresh_ip() -> str:
    return f"198.51.100.{uuid.uuid4().int % 250 + 1}"


def _login():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": ADMIN_PASSWORD},
        headers={"X-Forwarded-For": _fresh_ip()},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _make_test_png(size=(64, 64), color=(220, 80, 40)):
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def auth_token():
    return _login()


@pytest.fixture(scope="module")
def H(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def uploaded_asset(H):
    """One image uploaded once for the whole module."""
    png = _make_test_png()
    files = {"file": ("phase10_seed.png", png, "image/png")}
    data = {"folder": "Custom", "tags": "phase10"}
    r = requests.post(f"{BASE_URL}/api/media/upload",
                      headers=H, files=files, data=data, timeout=TIMEOUT)
    assert r.status_code == 200, f"upload failed: {r.status_code} {r.text}"
    asset = r.json()
    assert asset["storage_path"].startswith("lakeview/uploads/"), \
        f"upload storage_path not in object storage: {asset['storage_path']}"
    return {"asset": asset, "bytes": png}


# ===================== 1. Upload + roundtrip =====================

class TestUploadAndAccess:
    def test_upload_returns_remote_storage_path(self, uploaded_asset):
        a = uploaded_asset["asset"]
        assert "id" in a and a["id"]
        assert a["storage_path"].startswith("lakeview/uploads/")
        assert "/" in a["storage_path"]

    def test_get_file_returns_same_bytes(self, uploaded_asset):
        a = uploaded_asset["asset"]
        r = requests.get(f"{BASE_URL}/api/media/file/{a['id']}", timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.content == uploaded_asset["bytes"], "bytes mismatch via /file"

    def test_thumb_returns_jpeg(self, uploaded_asset):
        a = uploaded_asset["asset"]
        r = requests.get(f"{BASE_URL}/api/media/thumb/{a['id']}", timeout=TIMEOUT)
        assert r.status_code == 200
        assert "image/jpeg" in (r.headers.get("Content-Type") or "")
        Image.open(io.BytesIO(r.content)).verify()


# ===================== 2. Duplicate =====================

class TestDuplicate:
    def test_duplicate_clones_bytes_and_path(self, H, uploaded_asset):
        src_id = uploaded_asset["asset"]["id"]
        r = requests.post(f"{BASE_URL}/api/media/assets/{src_id}/duplicate",
                          headers=H, timeout=TIMEOUT)
        assert r.status_code == 200, f"duplicate: {r.status_code} {r.text}"
        clone = r.json()
        assert clone["id"] != src_id
        assert "/" in clone["storage_path"]
        assert clone["storage_path"] != uploaded_asset["asset"]["storage_path"]
        r2 = requests.get(f"{BASE_URL}/api/media/file/{clone['id']}", timeout=TIMEOUT)
        assert r2.status_code == 200
        assert r2.content == uploaded_asset["bytes"], "cloned bytes mismatch"


# ===================== 3. Soft delete =====================

class TestSoftDelete:
    def test_delete_is_soft(self, H):
        png = _make_test_png(color=(10, 10, 10))
        files = {"file": ("p10_del.png", png, "image/png")}
        up = requests.post(f"{BASE_URL}/api/media/upload",
                           headers=H, files=files, data={"folder": "Custom"},
                           timeout=TIMEOUT).json()
        aid = up["id"]
        r = requests.delete(f"{BASE_URL}/api/media/assets/{aid}", headers=H, timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        # The delete handler returns either {"mode": "soft"} or {"status": "archived"}
        # depending on whether the row was referenced elsewhere — accept either.
        assert body.get("mode") == "soft" or body.get("status") == "archived" or body.get("ok") is True, \
            f"unexpected delete response: {body}"
        # No longer in default listing
        ar = requests.get(f"{BASE_URL}/api/media/assets",
                          headers=H, params={"limit": 500}, timeout=TIMEOUT).json()
        ids = {x["id"] for x in ar.get("assets", [])}
        assert aid not in ids, "soft-deleted asset still in default listing"


# ===================== 4. Health =====================

class TestHealth:
    def test_health_storage_reachable(self, H):
        r = requests.get(f"{BASE_URL}/api/media/health", headers=H, timeout=TIMEOUT)
        assert r.status_code == 200, f"health: {r.status_code} {r.text}"
        h = r.json()
        st = h.get("storage", {})
        assert st.get("reachable") is True, f"storage not reachable: {st}"
        assert st.get("backend") == "emergent_object_storage", f"wrong backend: {st}"
        assert st.get("initialized") is True, f"storage not initialized: {st}"
        # Queues
        for k in ("pending", "processing", "completed_recent", "failed_recent"):
            assert k in h.get("ai_image_queue", {}), f"ai_image_queue missing {k}"
        for k in ("queued", "processing"):
            assert k in h.get("render_queue", {}), f"render_queue missing {k}"
        assert h.get("asset_count", 0) > 0, "asset_count should be > 0"


# ===================== 5. Legacy fallback negative =====================

class TestLegacyFallback:
    def test_missing_legacy_returns_404(self):
        """A non-existent asset id on /file must return 404, not 500."""
        r = requests.get(f"{BASE_URL}/api/media/file/{uuid.uuid4()}", timeout=TIMEOUT)
        assert r.status_code == 404


# ===================== 6. Public-route regression =====================

class TestRegression:
    @pytest.mark.parametrize("path,need_auth", [
        ("/api/menu", False),
        ("/api/specials", False),
        ("/", False),
    ])
    def test_endpoint_200(self, path, need_auth, H):
        headers = H if need_auth else None
        r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=TIMEOUT)
        assert r.status_code == 200, f"{path}: {r.status_code}"


# ===================== 7. Removed-routes regression =====================

REMOVED_POST = [
    "/api/media/edit",
    "/api/media/export-social",
    "/api/media/video/render",
    "/api/media/ai-image",
]

REMOVED_GET = [
    "/api/media/video/jobs",
    "/api/media/video/jobs/anything",
    "/api/media/ai-image/job/anything",
    "/api/media/social-formats",
    "/api/ai-ads/plugins",
    "/api/ai-ads/plugins/restaurant",
]


class TestRemovedRoutes:
    @pytest.mark.parametrize("path", REMOVED_POST)
    def test_removed_post(self, H, path):
        r = requests.post(f"{BASE_URL}{path}", headers=H, json={}, timeout=15)
        assert r.status_code in (404, 405), f"POST {path} returned {r.status_code}"

    @pytest.mark.parametrize("path", REMOVED_GET)
    def test_removed_get(self, H, path):
        r = requests.get(f"{BASE_URL}{path}", headers=H, timeout=15)
        assert r.status_code in (404, 405), f"GET {path} returned {r.status_code}"
