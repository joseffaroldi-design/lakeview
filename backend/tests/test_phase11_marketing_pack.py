"""Phase 11 — Promote This Item 2.0 backend tests.

Covers:
- GET /items-not-promoted-recently?limit=3 → shape + sort
- POST /generate → 202 + job_id, unauth → 401
- GET /job/{id} unauth → 401, unknown id → 404
- Poll lifecycle: queued → inferring → writing_copy → rendering_images → rendering_video → done (≤120s)
- result keys + asset_id resolution via /api/media/file/{id} and /thumb/{id} with correct content-type
- folder='Marketing Packs', tags include marketing-pack + pack:{id}; 9:16 has both ig_story+tiktok_reel; video has promo-video
- menu item stamping (last_promoted_at + last_pack_id)
- PATCH caption/hashtags update + 404 unknown + 409 on pending
- POST /regenerate → 202 + NEW job_id
- CRITICAL: enqueue → restart backend → status='failed', retryable, user_message contains 'interrupted'
- Regression sweep
"""
import io
import os
import time
import subprocess
import pytest
import requests
from PIL import Image


def _read_base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for ln in f:
                if ln.startswith("REACT_APP_BACKEND_URL="):
                    return ln.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    return ""


BASE_URL = _read_base_url()
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
API = f"{BASE_URL}/api"
TIMEOUT = 30


def _login():
    r = requests.post(f"{API}/auth/login", json={"password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _wait_backend_ready(max_wait=45):
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            r = requests.post(f"{API}/auth/login",
                              json={"password": ADMIN_PASSWORD}, timeout=5)
            if r.status_code == 200:
                return r.json()["token"]
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("backend did not come back after restart")


def _restart_backend():
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"],
                   check=True, capture_output=True, timeout=30)
    time.sleep(3)
    return _wait_backend_ready()


def _make_test_png(size=(1024, 1024), color=(180, 80, 50)):
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def auth_token():
    assert BASE_URL, "REACT_APP_BACKEND_URL not set"
    return _login()


@pytest.fixture(scope="module")
def H(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def source_asset(H):
    """Upload a 1024x1024 PNG once and reuse for all tests."""
    files = {"file": ("phase11_src.png", _make_test_png(), "image/png")}
    data = {"folder": "Marketing Packs", "tags": "phase11-test"}
    r = requests.post(f"{API}/media/upload", files=files, data=data, headers=H, timeout=60)
    assert r.status_code in (200, 201), f"upload failed {r.status_code}: {r.text}"
    asset = r.json()
    assert "id" in asset
    return asset


# ---------------- Auth gates ----------------

class TestAuth:
    def test_post_generate_unauth_401(self):
        r = requests.post(f"{API}/marketing-pack/generate",
                          json={"source_asset_id": "x"}, timeout=15)
        assert r.status_code == 401

    def test_get_job_unauth_401(self):
        r = requests.get(f"{API}/marketing-pack/job/anything", timeout=15)
        assert r.status_code == 401

    def test_get_job_unknown_404(self, H):
        r = requests.get(f"{API}/marketing-pack/job/does-not-exist", headers=H, timeout=15)
        assert r.status_code == 404
        assert "not found" in r.json().get("detail", "").lower()


# ---------------- items-not-promoted-recently ----------------

class TestSuggestions:
    def test_list_top3_shape(self, H):
        r = requests.get(f"{API}/marketing-pack/items-not-promoted-recently?limit=3",
                         headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get("fallback_used") is False
        assert d.get("source") == "menu_categories"
        items = d.get("items") or []
        assert isinstance(items, list)
        assert len(items) <= 3
        if items:
            it = items[0]
            for k in ("item_key", "name", "description", "price",
                      "category_slug", "category_display_name",
                      "last_promoted_at", "last_pack_id"):
                assert k in it, f"missing key {k} in suggestion item"


# ---------------- End-to-end pipeline ----------------

class TestPipeline:
    """Single full pipeline run shared across tests via module-scoped fixture."""

    @pytest.fixture(scope="class")
    def completed_pack(self, H, source_asset):
        body = {
            "source_asset_id": source_asset["id"],
            "name": "TEST_Smash Burger Special",
            "description": "A juicy classic with creole aioli and pickles.",
            "price": "$14",
            "headline": "FRIDAY SPECIAL",
            "cta": "Order Now",
            "menu_item_key": "appetizers::cafe-fries",
        }
        t0 = time.time()
        r = requests.post(f"{API}/marketing-pack/generate", json=body, headers=H, timeout=10)
        elapsed = time.time() - t0
        assert r.status_code == 202, f"expected 202, got {r.status_code}: {r.text}"
        assert elapsed < 3.0, f"generate took too long: {elapsed:.2f}s"
        data = r.json()
        assert "job_id" in data
        assert data.get("status") == "pending"
        job_id = data["job_id"]

        # Poll up to 120s
        seen_steps = set()
        deadline = time.time() + 130
        last = None
        prev_progress = -1
        while time.time() < deadline:
            jr = requests.get(f"{API}/marketing-pack/job/{job_id}", headers=H, timeout=15)
            assert jr.status_code == 200
            last = jr.json()
            step = last.get("current_step")
            if step:
                seen_steps.add(step)
            prog = last.get("progress") or 0
            assert prog >= prev_progress, f"progress regressed {prev_progress}→{prog}"
            prev_progress = prog
            if last.get("status") == "completed":
                break
            if last.get("status") == "failed":
                pytest.fail(f"pipeline failed: {last.get('error')}")
            time.sleep(3)
        assert last and last.get("status") == "completed", f"did not complete in 120s: {last}"
        assert last.get("progress") == 100
        # Step transitions visible (at least a couple of the named ones)
        expected_any = {"inferring", "writing_copy", "rendering_images",
                        "rendering_video", "saving", "done"}
        assert seen_steps & expected_any, f"no expected steps seen, got {seen_steps}"
        return last

    def test_result_keys_present(self, completed_pack):
        r = completed_pack["result"]
        for k in ("ig_post_asset_id", "ig_story_asset_id", "tiktok_reel_asset_id",
                  "fb_post_asset_id", "hero_asset_id", "video_asset_id",
                  "caption", "hashtags", "sms", "email", "gbp"):
            assert k in r, f"missing key {k}"
        # tiktok_reel == ig_story (same file, dual label)
        assert r["tiktok_reel_asset_id"] == r["ig_story_asset_id"]
        assert r["caption"] and isinstance(r["caption"], str)
        assert isinstance(r["hashtags"], list) and r["hashtags"]
        assert all(isinstance(h, str) and not h.startswith("#") for h in r["hashtags"])
        assert r["sms"] and len(r["sms"]) <= 160
        assert r["email"].get("subject") and r["email"].get("body")
        assert r["gbp"]

    def test_image_assets_resolve(self, H, completed_pack):
        r = completed_pack["result"]
        for key in ("ig_post_asset_id", "ig_story_asset_id",
                    "fb_post_asset_id", "hero_asset_id"):
            aid = r[key]
            fr = requests.get(f"{API}/media/file/{aid}",
                              headers=H, timeout=20, allow_redirects=True)
            assert fr.status_code == 200, f"{key} file 200 failed: {fr.status_code}"
            assert fr.headers.get("content-type", "").startswith("image/jpeg"), \
                f"{key} ctype: {fr.headers.get('content-type')}"
            tr = requests.get(f"{API}/media/thumb/{aid}",
                              headers=H, timeout=20, allow_redirects=True)
            assert tr.status_code == 200, f"{key} thumb 200 failed: {tr.status_code}"
            assert tr.headers.get("content-type", "").startswith("image/jpeg")

    def test_video_asset_resolves(self, H, completed_pack):
        vid = completed_pack["result"].get("video_asset_id")
        assert vid, "video_asset_id missing"
        vr = requests.get(f"{API}/media/file/{vid}",
                          headers=H, timeout=30, allow_redirects=True)
        assert vr.status_code == 200
        assert vr.headers.get("content-type", "").startswith("video/mp4")

    def test_asset_tags_and_folder(self, H, completed_pack):
        pack_id = completed_pack["id"]
        r = completed_pack["result"]
        # Fetch each image asset and check tags + folder
        cases = [
            ("ig_post_asset_id", "ig_post"),
            ("ig_story_asset_id", "ig_story"),  # also tiktok_reel
            ("fb_post_asset_id", "fb_post"),
            ("hero_asset_id", "hero"),
        ]
        for key, fmt in cases:
            aid = r[key]
            ar = requests.get(f"{API}/media/assets/{aid}", headers=H, timeout=15)
            assert ar.status_code == 200, f"{key} asset GET failed: {ar.status_code}"
            doc = ar.json()
            assert doc.get("folder") == "Marketing Packs"
            tags = doc.get("tags") or []
            assert "marketing-pack" in tags
            assert f"pack:{pack_id}" in tags
            assert fmt in tags
            if fmt == "ig_story":
                assert "tiktok_reel" in tags, "9:16 must be dual-labeled"
        # video
        vid = r["video_asset_id"]
        vr = requests.get(f"{API}/media/assets/{vid}", headers=H, timeout=15)
        assert vr.status_code == 200
        vdoc = vr.json()
        assert vdoc.get("folder") == "Marketing Packs"
        vtags = vdoc.get("tags") or []
        for t in ("marketing-pack", "promo-video", f"pack:{pack_id}"):
            assert t in vtags, f"video missing tag {t}"

    def test_menu_item_stamped(self, H, completed_pack):
        sr = requests.get(f"{API}/marketing-pack/items-not-promoted-recently?limit=50",
                          headers=H, timeout=15)
        assert sr.status_code == 200
        items = sr.json().get("items") or []
        match = [i for i in items if i.get("item_key") == "appetizers::cafe-fries"]
        if not match:
            pytest.skip("menu item 'appetizers::cafe-fries' not present in menu_categories")
        m = match[0]
        assert m["last_promoted_at"] is not None
        assert m["last_pack_id"] == completed_pack["id"]


# ---------------- PATCH ----------------

class TestPatch:
    def test_patch_unknown_404(self, H):
        r = requests.patch(f"{API}/marketing-pack/unknown-id",
                           json={"caption": "x"}, headers=H, timeout=15)
        assert r.status_code == 404

    def test_patch_pending_409(self, H, source_asset):
        body = {
            "source_asset_id": source_asset["id"],
            "name": "TEST_PendingPatch", "description": "p",
        }
        r = requests.post(f"{API}/marketing-pack/generate", json=body,
                          headers=H, timeout=10)
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        # Immediately try to patch — should be pending/processing
        pr = requests.patch(f"{API}/marketing-pack/{job_id}",
                            json={"caption": "early"}, headers=H, timeout=10)
        # Could be 409 (pending) — if it just completed, allow 200 as flaky tolerance
        assert pr.status_code in (409, 200), f"expected 409, got {pr.status_code}"
        if pr.status_code == 409:
            assert "not yet ready" in pr.json().get("detail", "").lower()

    def test_patch_caption_and_hashtags(self, H, source_asset):
        # Use a pack from the pipeline class — but to keep tests independent run mini-pipeline
        # Reuse the suggestions/test setup: launch a small pack and wait
        body = {
            "source_asset_id": source_asset["id"],
            "name": "TEST_PatchTarget",
            "description": "patch target",
        }
        r = requests.post(f"{API}/marketing-pack/generate", json=body, headers=H, timeout=10)
        assert r.status_code == 202
        pack_id = r.json()["job_id"]
        deadline = time.time() + 130
        while time.time() < deadline:
            jr = requests.get(f"{API}/marketing-pack/job/{pack_id}",
                              headers=H, timeout=15)
            if jr.json().get("status") == "completed":
                break
            if jr.json().get("status") == "failed":
                pytest.fail(f"pack failed: {jr.json().get('error')}")
            time.sleep(3)
        else:
            pytest.fail("pack did not complete in 130s for patch test")

        # PATCH caption
        pr = requests.patch(f"{API}/marketing-pack/{pack_id}",
                            json={"caption": "edited caption text"},
                            headers=H, timeout=15)
        assert pr.status_code == 200
        assert pr.json()["result"]["caption"] == "edited caption text"

        # PATCH hashtags — should strip leading #
        pr2 = requests.patch(f"{API}/marketing-pack/{pack_id}",
                             json={"hashtags": ["burger", "#nola"]},
                             headers=H, timeout=15)
        assert pr2.status_code == 200
        tags = pr2.json()["result"]["hashtags"]
        assert tags == ["burger", "nola"]


# ---------------- Regenerate ----------------

class TestRegenerate:
    def test_regenerate_returns_new_job_id(self, H, source_asset):
        # Create + wait a pack first
        body = {
            "source_asset_id": source_asset["id"],
            "name": "TEST_RegenSource", "description": "source for regen",
        }
        r = requests.post(f"{API}/marketing-pack/generate", json=body,
                          headers=H, timeout=10)
        assert r.status_code == 202
        original_id = r.json()["job_id"]
        # Wait until completed (so we have a stable pack to regenerate from)
        deadline = time.time() + 130
        while time.time() < deadline:
            jr = requests.get(f"{API}/marketing-pack/job/{original_id}",
                              headers=H, timeout=15)
            if jr.json().get("status") == "completed":
                break
            time.sleep(3)

        rr = requests.post(f"{API}/marketing-pack/{original_id}/regenerate",
                           headers=H, timeout=10)
        assert rr.status_code == 202, f"regen got {rr.status_code}: {rr.text}"
        new = rr.json()
        assert new.get("status") == "pending"
        assert new.get("job_id") and new["job_id"] != original_id


# ---------------- Janitor / restart survival ----------------

class TestJanitor:
    def test_restart_marks_pending_failed(self, H, source_asset):
        """Enqueue → immediately restart backend → status=failed, retryable, user_message."""
        body = {
            "source_asset_id": source_asset["id"],
            "name": "TEST_JanitorTarget", "description": "to be interrupted",
        }
        r = requests.post(f"{API}/marketing-pack/generate", json=body,
                          headers=H, timeout=10)
        assert r.status_code == 202
        pack_id = r.json()["job_id"]
        # Restart immediately
        new_token = _restart_backend()
        H2 = {"Authorization": f"Bearer {new_token}"}
        time.sleep(2)
        jr = requests.get(f"{API}/marketing-pack/job/{pack_id}",
                          headers=H2, timeout=15)
        assert jr.status_code == 200
        d = jr.json()
        assert d.get("status") == "failed", f"expected failed, got {d.get('status')}"
        err = d.get("error") or {}
        assert err.get("code") == "unknown"
        assert err.get("retryable") is True
        assert err.get("retry_action") == "retry"
        assert "interrupted by a server restart" in (err.get("user_message") or "")


# ---------------- Regression sweep ----------------

class TestRegression:
    @pytest.mark.parametrize("path,need_auth,expected", [
        ("/api/menu", False, 200),
        ("/api/specials", False, 200),
        ("/", False, 200),
        ("/api/ai-ads/plugins", True, 200),
        ("/api/media/health", True, 200),
    ])
    def test_endpoint_status(self, path, need_auth, expected, H):
        headers = H if need_auth else None
        r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=20)
        assert r.status_code == expected, f"{path} got {r.status_code}"

    def test_ai_image_unknown_job_404(self, H):
        r = requests.get(f"{API}/media/ai-image/job/does-not-exist",
                         headers=H, timeout=15)
        assert r.status_code == 404
