"""Iteration 31 — Independent verification of:

  A) SHA-256 daily rotation fix for GET /api/html-template/featured
     (deterministic across processes / restarts / PYTHONHASHSEED).
  B) Full Photo→Flyer E2E for library + fresh-upload paths, hidden-theme
     backward compat, and instagram_square / instagram_story dimensions.

Runs against the LIVE preview backend via REACT_APP_BACKEND_URL. Read-only
where possible; media assets are NEVER modified or deleted.
"""
import io
import os
import re
import subprocess
import time
from pathlib import Path

import pytest
import requests
from PIL import Image

# --- Config ------------------------------------------------------------------

FRONTEND_ENV = Path("/app/frontend/.env").read_text()
_m = re.search(r"^REACT_APP_BACKEND_URL=(.+)$", FRONTEND_ENV, re.M)
assert _m, "REACT_APP_BACKEND_URL missing from /app/frontend/.env"
BASE = _m.group(1).strip().rstrip("/")
API = f"{BASE}/api"

# Admin password loaded from ADMIN_PASSWORD env (falling back to
# /app/backend/.env). The plaintext password is no longer stored in
# memory/test_credentials.md — never logged.
def _load_admin_pw():
    pw = os.environ.get("ADMIN_PASSWORD", "")
    if pw:
        return pw
    try:
        for line in Path("/app/backend/.env").read_text().splitlines():
            if line.startswith("ADMIN_PASSWORD="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return ""
_ADMIN_PW = _load_admin_pw()
assert _ADMIN_PW, "ADMIN_PASSWORD not available (env or backend/.env)"

LIB_ASSET_ID = "c3e26d02-b0a6-465f-84f2-deebe2ccf143"
LOGO_URL = ("https://customer-assets.emergentagent.com/job_703dcc6a-aa7a-4633-a18d-a8d37a8eb209/"
            "artifacts/y3vh8170_5D695FC6-4513-41E6-8C85-02DA2EA2EF08.png")

TIMEOUT = 30
POLL_TIMEOUT = 240  # seconds
POLL_INTERVAL = 4


# --- Session fixtures --------------------------------------------------------

@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"password": _ADMIN_PW}, timeout=TIMEOUT)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("token") or r.json().get("session_token")
    assert token, f"no token in login response: {r.json()}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# --- A) Featured rotation SHA-256 --------------------------------------------

class TestFeaturedRotation:
    def test_default_call_returns_200_and_pool_gte_2(self):
        r = requests.get(f"{API}/html-template/featured", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        b = r.json()
        for key in ("asset_id", "item_name", "theme", "uploaded_at",
                    "image_url", "pool_size", "rotated_for"):
            assert key in b, f"missing '{key}' in {b}"
        assert isinstance(b["pool_size"], int) and b["pool_size"] >= 2, \
            f"pool_size should be >=2, got {b['pool_size']}"
        assert b["image_url"] == f"/api/media/file/{b['asset_id']}"
        # rotated_for is today's UTC date
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", b["rotated_for"])

    def test_two_sequential_calls_same_day_return_same_asset(self):
        r1 = requests.get(f"{API}/html-template/featured", timeout=TIMEOUT).json()
        r2 = requests.get(f"{API}/html-template/featured", timeout=TIMEOUT).json()
        assert r1["asset_id"] == r2["asset_id"]
        assert r1["rotated_for"] == r2["rotated_for"]
        assert r1["pool_size"] == r2["pool_size"]

    def test_window_days_14_filters_recent(self):
        r = requests.get(f"{API}/html-template/featured?window_days=14",
                         timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        b = r.json()
        assert "asset_id" in b and "pool_size" in b
        # legacy 14-day behavior may collapse to 1 in older pools — that's fine
        assert b["pool_size"] >= 1

    def test_window_days_0_equals_default(self):
        a = requests.get(f"{API}/html-template/featured", timeout=TIMEOUT).json()
        b = requests.get(f"{API}/html-template/featured?window_days=0",
                         timeout=TIMEOUT).json()
        assert a["pool_size"] == b["pool_size"]
        assert a["asset_id"] == b["asset_id"]

    def test_image_url_serves_png_or_jpeg(self):
        b = requests.get(f"{API}/html-template/featured", timeout=TIMEOUT).json()
        r = requests.get(f"{BASE}{b['image_url']}", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:200]
        assert len(r.content) > 100
        ctype = r.headers.get("content-type", "")
        assert ctype.startswith("image/"), f"unexpected content-type {ctype}"
        # magic bytes check
        head = r.content[:8]
        assert head.startswith(b"\x89PNG") or head[:3] == b"\xff\xd8\xff", \
            f"bytes not PNG/JPEG: {head!r}"

    def test_daily_index_cross_process_determinism(self):
        """The specific SHA-256 regression check — two subprocesses with
        random PYTHONHASHSEED must return the same _daily_index result."""
        script = (
            "import sys; sys.path.insert(0,'/app/backend'); "
            "from routers.html_template import _daily_index; "
            "print(_daily_index('2026-07-15', 57))"
        )
        outs = []
        for _ in range(3):
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = "random"
            r = subprocess.run(["python3", "-c", script],
                               capture_output=True, text=True,
                               env=env, timeout=20)
            assert r.returncode == 0, r.stderr
            outs.append(r.stdout.strip())
        assert len(set(outs)) == 1, f"cross-process drift: {outs}"
        # sanity: index in range
        assert 0 <= int(outs[0]) < 57


# --- B) Photo→Flyer E2E ------------------------------------------------------

def _poll_job(session, job_id):
    """Poll /api/ai-designer/job/<id> until completed or timeout."""
    deadline = time.time() + POLL_TIMEOUT
    last = None
    while time.time() < deadline:
        r = session.get(f"{API}/ai-designer/job/{job_id}", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        last = r.json()
        if last.get("status") in ("completed", "failed"):
            return last
        time.sleep(POLL_INTERVAL)
    raise AssertionError(f"job {job_id} did not finish within "
                         f"{POLL_TIMEOUT}s. Last state: {last}")


def _assert_variant_dims(session, variation, expected_wh):
    asset_id = variation.get("asset_id") or variation.get("id")
    assert asset_id, f"variation has no asset_id: {variation}"
    r = session.get(f"{API}/media/file/{asset_id}", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:200]
    im = Image.open(io.BytesIO(r.content))
    assert im.size == expected_wh, f"expected {expected_wh}, got {im.size}"


def _generate_and_verify(session, source_asset_id, theme, platform,
                         expected_wh, with_logo=False):
    payload = {
        "source_asset_id": source_asset_id,
        "theme": theme,
        "platform": platform,
        "variations": 3,
        "item_name": "Test Dish",
    }
    if with_logo:
        payload["logo_url"] = LOGO_URL
        payload["logo_placement"] = "bottom_right"

    # retry once on transient 500 (per review-request instruction)
    for attempt in range(2):
        r = session.post(f"{API}/ai-designer/generate", json=payload, timeout=TIMEOUT)
        if r.status_code == 202:
            break
        if r.status_code >= 500 and attempt == 0:
            time.sleep(3)
            continue
        pytest.fail(f"generate returned {r.status_code}: {r.text[:300]}")
    job_id = r.json()["job_id"]

    job = _poll_job(session, job_id)
    assert job["status"] == "completed", f"job failed: {job}"

    variations = job.get("variations") or []
    completed = [v for v in variations if v.get("status") == "completed"]
    assert len(completed) == 3, \
        f"expected 3 completed variants, got {len(completed)}: " \
        f"{[v.get('status') for v in variations]}"

    _assert_variant_dims(session, completed[0], expected_wh)
    return job_id, completed


class TestPhotoFlyerE2E:

    def test_a_library_path_cajun_fb_post_with_logo(self, session):
        # analyze-existing on the known Lakeview library asset
        r = session.post(f"{API}/photo-flyer/analyze-existing",
                         json={"asset_id": LIB_ASSET_ID}, timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        an = r.json()
        assert an.get("vision_ok") is True, f"vision failed: {an}"
        eid = an["enhanced_asset_id"]

        job_id, variants = _generate_and_verify(
            session, eid, theme="cajun",
            platform="facebook_post", expected_wh=(1200, 630),
            with_logo=True,
        )

        # persistence check — reopen the job
        r2 = session.get(f"{API}/ai-designer/job/{job_id}", timeout=TIMEOUT)
        assert r2.status_code == 200
        assert r2.json()["status"] == "completed"
        assert len(r2.json().get("variations") or []) == 3

    def test_b_fresh_upload_luxury_fb_post(self, session):
        # build a small JPEG in-memory
        buf = io.BytesIO()
        img = Image.new("RGB", (1024, 768), (180, 90, 60))
        img.save(buf, format="JPEG", quality=85)
        buf.seek(0)

        files = {"file": ("upload.jpg", buf, "image/jpeg")}
        data = {"folder": "Custom"}
        r = session.post(f"{API}/photo-flyer/analyze",
                         files=files, data=data, timeout=90)
        assert r.status_code == 200, r.text[:300]
        an = r.json()
        eid = an.get("enhanced_asset_id") or an.get("original_asset_id")
        assert eid, f"no asset id in analyze response: {an}"

        _generate_and_verify(
            session, eid, theme="luxury",
            platform="facebook_post", expected_wh=(1200, 630),
            with_logo=True,
        )

    def test_c_hidden_theme_burger_neon_diner_backward_compat(self, session):
        r = session.get(f"{API}/ai-designer/themes", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        themes = r.json().get("themes") or []
        by_id = {t["id"]: t for t in themes}
        assert "burger_neon_diner" in by_id, \
            "burger_neon_diner missing from /themes"
        assert by_id["burger_neon_diner"].get("hidden") is True, \
            "burger_neon_diner should be hidden=true"

        # legacy compat: generation must still succeed
        _generate_and_verify(
            session, LIB_ASSET_ID, theme="burger_neon_diner",
            platform="facebook_post", expected_wh=(1200, 630),
        )

    def test_d_instagram_square_1080(self, session):
        _generate_and_verify(
            session, LIB_ASSET_ID, theme="modern",
            platform="instagram_square", expected_wh=(1080, 1080),
        )

    def test_d_instagram_story_1080x1920(self, session):
        _generate_and_verify(
            session, LIB_ASSET_ID, theme="vintage_diner",
            platform="instagram_story", expected_wh=(1080, 1920),
        )
