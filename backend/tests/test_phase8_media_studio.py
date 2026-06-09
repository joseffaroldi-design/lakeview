"""Phase 8 — Media Studio backend tests.

Tests:
  • POST /api/media/upload  (image upload, mime validation)
  • POST /api/media/edit    (brightness/contrast/text, crop/rotate/flip, bg-removal)
  • POST /api/media/export-social  (cover/contain across 6 formats)
  • GET  /api/media/social-formats
  • POST /api/media/video/render + GET /api/media/video/jobs/{id}
  • GET  /api/media/stats
"""
from __future__ import annotations

import io
import os
import time
from pathlib import Path

import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://lakeview-admin-dash.preview.emergentagent.com").rstrip("/")
ADMIN_PASSWORD = "Lakeview872"

EXPECTED_FORMAT_DIMS = {
    "ig_post_1_1": (1080, 1080),
    "ig_reel_9_16": (1080, 1920),
    "fb_post": (1200, 630),
    "tiktok_9_16": (1080, 1920),
    "gbp_image": (1200, 900),
    "flyer_8_5_11": (2550, 3300),
}


# ---------- Fixtures ----------

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("token")
    assert token, f"No token in login response: {r.json()}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def _make_jpg(w=1600, h=1200, color=(180, 120, 90)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    # Add some structure to make brightness/contrast measurable
    for i in range(0, w, 80):
        for j in range(0, h, 80):
            patch = Image.new("RGB", (40, 40), (50 + (i + j) % 200, 100, 200))
            img.paste(patch, (i, j))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


@pytest.fixture(scope="module")
def uploaded_image(session) -> dict:
    files = {"file": ("TEST_phase8.jpg", _make_jpg(), "image/jpeg")}
    data = {"folder": "Custom", "tags": "TEST_phase8"}
    r = session.post(f"{BASE_URL}/api/media/upload", files=files, data=data, timeout=30)
    assert r.status_code == 200, f"Upload failed: {r.status_code} {r.text}"
    asset = r.json()
    return asset


@pytest.fixture(scope="module")
def three_uploads(session) -> list:
    out = []
    for i in range(3):
        files = {"file": (f"TEST_p8_seq_{i}.jpg", _make_jpg(800, 600, (40 + 50 * i, 100, 200 - 40 * i)), "image/jpeg")}
        r = session.post(f"{BASE_URL}/api/media/upload", files=files, data={"folder": "Custom", "tags": "TEST_phase8"}, timeout=30)
        assert r.status_code == 200, r.text
        out.append(r.json())
    return out


# ---------- Upload tests ----------

class TestUpload:
    def test_upload_jpg_success(self, uploaded_image):
        a = uploaded_image
        assert a["id"] and a["kind"] == "image"
        assert a["mime"] == "image/jpeg"
        assert a["size_bytes"] > 1000
        assert a["folder"] == "Custom"
        assert a["source"] == "upload"
        assert a["width"] and a["height"]

    def test_upload_rejects_unsupported_mime(self, session):
        files = {"file": ("TEST_p8.txt", b"hello", "text/plain")}
        r = session.post(f"{BASE_URL}/api/media/upload", files=files, data={"folder": "Custom"}, timeout=15)
        assert r.status_code == 400
        assert "Unsupported" in r.text or "content_type" in r.text


# ---------- Edit tests ----------

class TestEdit:
    def test_edit_brightness_contrast_text(self, session, uploaded_image):
        payload = {
            "source_asset_id": uploaded_image["id"],
            "brightness": 1.2,
            "contrast": 1.15,
            "text_overlay": {
                "text": "FRIDAY SPECIAL",
                "y_pct": 0.85,
                "size_pct": 0.08,
                "color": "#FFFFFF",
                "background": "#000000",
            },
        }
        r = session.post(f"{BASE_URL}/api/media/edit", json=payload, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        a = r.json()
        assert a["source"] == "image_edit"
        assert "edited" in a["tags"]
        assert a["source_asset_id"] == uploaded_image["id"]
        # File should be retrievable
        r2 = session.get(f"{BASE_URL}/api/media/file/{a['id']}", timeout=15)
        assert r2.status_code == 200

    def test_edit_crop_rotate_flip_changes_dims(self, session, uploaded_image):
        # Source is 1600x1200. crop 600x400, rotate 90 → expect 400x600
        payload = {
            "source_asset_id": uploaded_image["id"],
            "crop": {"x": 100, "y": 100, "w": 600, "h": 400},
            "rotate": 90,
            "flip_horizontal": True,
        }
        r = session.post(f"{BASE_URL}/api/media/edit", json=payload, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        a = r.json()
        # After rotate 90, width and height swap
        assert a["width"] == 400 and a["height"] == 600, f"Unexpected dims: {a['width']}x{a['height']}"
        assert a["source"] == "image_edit"

    def test_edit_remove_background(self, session, uploaded_image):
        payload = {
            "source_asset_id": uploaded_image["id"],
            "remove_background": True,
            "bg_color": "#FFFFFF",
        }
        # First call may download ~170MB rembg model — allow long timeout
        r = session.post(f"{BASE_URL}/api/media/edit", json=payload, timeout=240)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        a = r.json()
        assert a["source"] == "image_edit"
        assert "bg-removed" in a["tags"]


# ---------- Social export tests ----------

class TestSocialExport:
    def test_social_formats_list(self, session):
        r = session.get(f"{BASE_URL}/api/media/social-formats", timeout=15)
        assert r.status_code == 200
        body = r.json()
        formats = body.get("formats", [])
        assert len(formats) == 8, f"Expected 8 formats, got {len(formats)}"
        ids = {f["id"] for f in formats}
        for fid in EXPECTED_FORMAT_DIMS.keys():
            assert fid in ids
            # Verify dims match
            f = next(x for x in formats if x["id"] == fid)
            ew, eh = EXPECTED_FORMAT_DIMS[fid]
            assert f["width"] == ew and f["height"] == eh
            assert f["label"]

    def test_export_six_formats_cover(self, session, uploaded_image):
        target_ids = list(EXPECTED_FORMAT_DIMS.keys())
        r = session.post(
            f"{BASE_URL}/api/media/export-social",
            json={"source_asset_id": uploaded_image["id"], "formats": target_ids, "fit": "cover"},
            timeout=90,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body["count"] == 6
        assets = body["assets"]
        for a, fid in zip(assets, target_ids):
            ew, eh = EXPECTED_FORMAT_DIMS[fid]
            assert a["width"] == ew and a["height"] == eh, f"{fid}: got {a['width']}x{a['height']}"
            assert a["folder"] == "Social Media"
            assert a["source"] == "social_export"
            assert "social-export" in a["tags"]
            assert fid in a["tags"]

    def test_export_contain_with_bg_color(self, session, uploaded_image):
        r = session.post(
            f"{BASE_URL}/api/media/export-social",
            json={"source_asset_id": uploaded_image["id"], "formats": ["fb_post"], "fit": "contain", "bg_color": "#FFCC00"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        a = r.json()["assets"][0]
        assert a["width"] == 1200 and a["height"] == 630
        assert "contain" in a["tags"]


# ---------- Video render tests ----------

class TestVideoRender:
    def test_video_render_lifecycle(self, session, three_uploads):
        ids = [a["id"] for a in three_uploads]
        r = session.post(
            f"{BASE_URL}/api/media/video/render",
            json={"asset_ids": ids, "duration_seconds": 15, "aspect": "9:16",
                  "title": "Test", "cta": "Order Now"},
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        job = r.json()
        assert job["status"] == "queued"
        assert job["id"]
        job_id = job["id"]

        deadline = time.time() + 180
        final = None
        while time.time() < deadline:
            r2 = session.get(f"{BASE_URL}/api/media/video/jobs/{job_id}", timeout=15)
            assert r2.status_code == 200
            j = r2.json()
            if j["status"] in ("completed", "failed"):
                final = j
                break
            time.sleep(3)

        assert final, "Render job did not finish within 180s"
        assert final["status"] == "completed", f"Render failed: {final.get('error')}"
        assert final["progress"] == 1.0
        assert final["output_asset_id"]

        # Verify output asset exists with source='video_render'
        r3 = session.get(f"{BASE_URL}/api/media/assets", params={"kind": "video"}, timeout=15)
        assert r3.status_code == 200
        assets = r3.json()["assets"]
        match = [x for x in assets if x["id"] == final["output_asset_id"]]
        assert match, "Rendered asset not found in /assets"
        assert match[0]["source"] == "video_render"
        assert match[0]["kind"] == "video"

    def test_video_jobs_list_sorted(self, session):
        r = session.get(f"{BASE_URL}/api/media/video/jobs", timeout=15)
        assert r.status_code == 200
        jobs = r.json()["jobs"]
        assert isinstance(jobs, list)
        # Sorted desc by created_at
        if len(jobs) >= 2:
            assert jobs[0]["created_at"] >= jobs[-1]["created_at"]


# ---------- Stats ----------

class TestStats:
    def test_stats_contains_required_keys(self, session):
        r = session.get(f"{BASE_URL}/api/media/stats", timeout=15)
        assert r.status_code == 200
        data = r.json()
        for k in ("images_uploaded", "ai_images_generated", "videos_rendered",
                  "videos_uploaded", "active_render_jobs", "total_assets"):
            assert k in data, f"missing key {k}"
            assert isinstance(data[k], int)
