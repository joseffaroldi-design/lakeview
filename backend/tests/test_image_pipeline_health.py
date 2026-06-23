"""Sprint 15B.7 — image-generation pipeline + health-endpoint regression.

Locks in:
  * /api/media/health returns healthy=true when storage + ffmpeg are up,
    EVEN IF rembg is intentionally not loaded (Sprint 15B.3 opt-in design).
  * The previously-misleading rembg-coupled `healthy=false` is gone.
  * AI Designer /generate produces 3 PIL-composed variations end-to-end.
  * Newly-generated assets are persisted and retrievable as thumbnails.

Run with REACT_APP_BACKEND_URL + ADMIN_PASSWORD env vars set.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def _fresh_ip() -> str:
    return f"198.51.100.{uuid.uuid4().int % 250 + 1}"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": ADMIN_PASSWORD},
        headers={"X-Forwarded-For": _fresh_ip()},
        timeout=10,
    )
    assert r.status_code == 200, r.text[:200]
    return r.json()["token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestMediaHealth:
    def test_healthy_true_when_storage_and_ffmpeg_up(self, token):
        r = requests.get(
            f"{BASE_URL}/api/media/health", headers=_headers(token), timeout=15,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["healthy"] is True, (
            f"healthy should be True when storage+ffmpeg are up, regardless of rembg state. Got: {d}"
        )
        assert d["ffmpeg_available"] is True
        assert d["storage"]["reachable"] is True
        assert d["storage"]["initialized"] is True

    def test_rembg_state_still_reported(self, token):
        """rembg is opt-in (Sprint 15B.3) but its state must still appear in
        the response for admin visibility — just not gate `healthy`."""
        r = requests.get(
            f"{BASE_URL}/api/media/health", headers=_headers(token), timeout=15,
        )
        d = r.json()
        assert "rembg_available" in d
        assert "rembg_model_ready" in d


class TestImageGenerationPipeline:
    """End-to-end test for AI Designer image generation."""

    def test_generate_completes_three_variations(self, token):
        # 1. Find a source asset.
        r = requests.get(
            f"{BASE_URL}/api/media/assets?kind=image&limit=1",
            headers=_headers(token), timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        assets = body.get("assets", body) if isinstance(body, dict) else body
        assert assets, "Need at least one image asset for this regression"
        source_id = assets[0]["id"]

        # 2. Enqueue a generate run (no auto_copy → zero LLM cost).
        r = requests.post(
            f"{BASE_URL}/api/ai-designer/generate",
            headers=_headers(token),
            json={
                "source_asset_id": source_id,
                "item_name": "Regression Smoke",
                "features": ["feat 1", "feat 2"],
                "price": "$1.00",
                "theme": "modern",
                "auto_copy": False,
                "remove_background": False,
            },
            timeout=45,
        )
        assert r.status_code == 202, r.text[:300]
        job_id = r.json()["job_id"]
        assert job_id

        # 3. Poll up to 60 seconds.
        deadline = time.time() + 60
        job = None
        while time.time() < deadline:
            r = requests.get(
                f"{BASE_URL}/api/ai-designer/job/{job_id}",
                headers=_headers(token), timeout=15,
            )
            assert r.status_code == 200
            job = r.json()
            if job.get("status") in ("completed", "failed"):
                break
            time.sleep(2)

        assert job is not None
        assert job["status"] == "completed", (
            f"Expected completed, got {job.get('status')} with error={job.get('error')}"
        )
        variations = job.get("variations", [])
        assert len(variations) == 3, f"Expected 3 variations, got {len(variations)}"
        for v in variations:
            assert v["status"] == "completed", v
            assert v.get("asset_id"), f"Variation missing asset_id: {v}"

    def test_generated_thumbnails_retrievable(self, token):
        # Find the most recent completed job and try fetching its thumbnails.
        r = requests.get(
            f"{BASE_URL}/api/ai-designer/jobs/recent?limit=1",
            headers=_headers(token), timeout=15,
        )
        jobs = r.json().get("jobs", [])
        assert jobs, "No recent jobs to probe"
        recent = jobs[0]

        # Pull full job for variation asset_ids.
        r = requests.get(
            f"{BASE_URL}/api/ai-designer/job/{recent['id']}",
            headers=_headers(token), timeout=15,
        )
        variations = r.json().get("variations", [])
        completed = [v for v in variations if v.get("status") == "completed" and v.get("asset_id")]
        assert completed, "Recent job has no completed variations"

        for v in completed:
            r = requests.get(
                f"{BASE_URL}/api/media/thumb/{v['asset_id']}",
                headers=_headers(token), timeout=15,
            )
            assert r.status_code == 200, (
                f"Thumb for variation asset {v['asset_id']} returned {r.status_code}: {r.text[:200]}"
            )
            assert len(r.content) > 1000, "Thumbnail suspiciously small"
