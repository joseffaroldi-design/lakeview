"""Async AI Image Generation tests — Cloudflare timeout fix verification.

Sprint 22 Phase 5: URLs realigned to the current routes.
    POST /api/ai-image/generate            (was /api/media/ai-image)
    GET  /api/ai-image/job/{job_id}        (was /api/media/ai-image/job/{job_id})

The legacy `/api/media/ai-image*` routes and `/api/ai-ads/plugins*` routes
were removed in Sprint 19+. Their 404 contract is already asserted by
`test_ai_ads.py::TestRemovedRoutes` and `test_final_launch.py::TestRemovedRoutes`,
so we don't re-cover them here.

Verifies on the live current routes:
- POST /api/ai-image/generate returns 202 + job_id in < 2s
- Auth enforced on POST + GET
- 404 on non-existent job
- Real job lifecycle (pending → processing → completed) with valid asset
- Asset accessible via /api/media/thumb/{id}
- Regression: /api/media/health, /api/menu
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://upload-stage-two.preview.emergentagent.com").rstrip("/")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Auth login failed: {r.status_code} {r.text}"
    token = r.json().get("token")
    assert token, f"No token in response: {r.json()}"
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ===== Auth tests =====

class TestAuth:
    def test_post_ai_image_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/ai-image/generate",
                          json={"prompt": "test", "count": 1, "quality": "low", "style_pack": "restaurant_food_photography"},
                          timeout=10)
        assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"

    def test_get_job_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/ai-image/job/{uuid.uuid4()}", timeout=10)
        assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"


# ===== Enqueue behavior =====

class TestEnqueue:
    def test_enqueue_returns_202_fast(self, auth_headers):
        t0 = time.time()
        r = requests.post(f"{BASE_URL}/api/ai-image/generate", headers=auth_headers,
                          json={"prompt": "Plate of beignets with powdered sugar", "count": 1, "quality": "low", "style_pack": "restaurant_food_photography"},
                          timeout=10)
        elapsed = time.time() - t0
        assert r.status_code == 202, f"expected 202 got {r.status_code}: {r.text}"
        assert elapsed < 2.0, f"enqueue took {elapsed:.2f}s — must be < 2s"
        data = r.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        # job_id should be a uuid-like string
        uuid.UUID(data["job_id"])

    def test_get_nonexistent_job_returns_404(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/ai-image/job/{uuid.uuid4()}",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 404, f"expected 404 got {r.status_code}: {r.text}"


# ===== Full lifecycle =====

class TestLifecycle:
    @pytest.mark.slow  # ≤ 3 min real generation — too slow for the fast suite
    def test_full_job_lifecycle_to_completion(self, auth_headers):
        # Enqueue
        t0 = time.time()
        r = requests.post(f"{BASE_URL}/api/ai-image/generate", headers=auth_headers,
                          json={"prompt": "Plate of beignets with powdered sugar", "count": 1, "quality": "low", "style_pack": "restaurant_food_photography"},
                          timeout=10)
        assert r.status_code == 202, f"enqueue failed: {r.status_code} {r.text}"
        job_id = r.json()["job_id"]
        print(f"\nEnqueued job {job_id} in {time.time()-t0:.2f}s")

        deadline = time.time() + 180
        last_status = None
        last_progress = None
        statuses_seen = set()
        while time.time() < deadline:
            jr = requests.get(f"{BASE_URL}/api/ai-image/job/{job_id}",
                              headers=auth_headers, timeout=30)
            assert jr.status_code == 200, f"poll failed: {jr.status_code} {jr.text}"
            jd = jr.json()
            statuses_seen.add(jd["status"])
            if jd["status"] != last_status or jd.get("progress") != last_progress:
                last_status = jd["status"]
                last_progress = jd.get("progress")
                print(f"  [{int(time.time()-t0)}s] status={last_status} progress={last_progress}")
            if jd["status"] == "completed":
                assert jd.get("result"), "completed job has no result"
                assets = jd["result"].get("assets")
                assert assets and len(assets) >= 1, f"no assets in result: {jd}"
                asset = assets[0]
                assert asset.get("id"), f"asset has no id: {asset}"
                assert asset.get("kind") == "image"

                tr = requests.get(f"{BASE_URL}/api/media/thumb/{asset['id']}",
                                  headers=auth_headers, timeout=15)
                assert tr.status_code == 200, f"thumb fetch failed: {tr.status_code}"
                ct = tr.headers.get("content-type", "")
                assert ct.startswith("image/"), f"unexpected content-type: {ct}"
                print(f"  Thumb OK: content-type={ct}, size={len(tr.content)}B")
                assert "pending" in statuses_seen or "processing" in statuses_seen
                return
            if jd["status"] == "failed":
                pytest.fail(f"job failed: {jd.get('error')}")
            time.sleep(3)
        pytest.fail(f"job did not complete in 3 minutes — last status={last_status}")


# ===== Regression =====

class TestRegression:
    def test_media_health(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/media/health", headers=auth_headers, timeout=10)
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        d = r.json()
        assert d.get("healthy") is True, f"not healthy: {d}"
        assert d.get("ffmpeg_available") is True, f"ffmpeg missing: {d}"

    def test_menu_endpoint(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/menu", headers=auth_headers, timeout=10)
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
