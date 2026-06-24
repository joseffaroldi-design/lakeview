"""Phase 8 — Media Studio backend tests (trimmed Sprint 16B.2).

The bulk of the Phase 8 surface was removed in the post-Sprint-15B
slimming: /api/media/edit, /api/media/export-social, /api/media/video/*,
/api/media/social-formats are all gone. This file now covers ONLY the
endpoints that survived:

  • POST /api/media/upload — image upload + mime validation
  • GET  /api/media/stats   — counts surface

A small regression class asserts the deleted endpoints stay deleted.
"""
from __future__ import annotations

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


def _fresh_ip() -> str:
    return f"198.51.100.{uuid.uuid4().int % 250 + 1}"


# ---------- Fixtures ----------

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": ADMIN_PASSWORD},
        headers={"X-Forwarded-For": _fresh_ip()},
        timeout=15,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("token")
    assert token, f"No token in login response: {r.json()}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def _make_jpg(w=1600, h=1200, color=(180, 120, 90)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    for i in range(0, w, 80):
        for j in range(0, h, 80):
            patch = Image.new("RGB", (40, 40), (50 + (i + j) % 200, 100, 200))
            img.paste(patch, (i, j))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


# ---------- Upload (still active) ----------

class TestUpload:
    def test_upload_jpg_success(self, session):
        files = {"file": ("TEST_phase8.jpg", _make_jpg(), "image/jpeg")}
        data = {"folder": "Custom", "tags": "TEST_phase8"}
        r = session.post(f"{BASE_URL}/api/media/upload", files=files, data=data, timeout=30)
        assert r.status_code == 200, f"Upload failed: {r.status_code} {r.text}"
        a = r.json()
        assert a["id"] and a["kind"] == "image"
        assert a["mime"] == "image/jpeg"
        assert a["size_bytes"] > 1000
        assert a["folder"] == "Custom"
        assert a["source"] == "upload"
        assert a["width"] and a["height"]

    def test_upload_rejects_unsupported_mime(self, session):
        files = {"file": ("TEST_p8.txt", b"hello", "text/plain")}
        r = session.post(
            f"{BASE_URL}/api/media/upload",
            files=files, data={"folder": "Custom"}, timeout=15,
        )
        assert r.status_code == 400
        assert "Unsupported" in r.text or "content_type" in r.text


# ---------- Stats (still active) ----------

class TestStats:
    def test_stats_responds(self, session):
        r = session.get(f"{BASE_URL}/api/media/stats", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        # Shape changed across sprints; just assert it returns a dict with
        # at least one int counter. Don't pin specific keys — the surface
        # has churned (videos_rendered, ai_images_generated were removed
        # alongside the underlying endpoints).
        assert any(isinstance(v, int) for v in data.values()), data


# ---------- Removed endpoints regression ----------

REMOVED_POST = [
    "/api/media/edit",
    "/api/media/export-social",
    "/api/media/video/render",
]

REMOVED_GET = [
    "/api/media/social-formats",
    "/api/media/video/jobs",
    "/api/media/video/jobs/anything",
]


class TestRemovedRoutes:
    """Sprint 15B+ trimmed the Media Studio surface — these must stay gone."""

    @pytest.mark.parametrize("path", REMOVED_POST)
    def test_removed_post(self, session, path):
        r = session.post(f"{BASE_URL}{path}", json={}, timeout=15)
        assert r.status_code in (404, 405), f"POST {path} returned {r.status_code}"

    @pytest.mark.parametrize("path", REMOVED_GET)
    def test_removed_get(self, session, path):
        r = session.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code in (404, 405), f"GET {path} returned {r.status_code}"
