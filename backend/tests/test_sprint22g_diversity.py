"""Sprint 22G — Variation Diversity for AI Designer.

For each theme in [luxury, cajun, modern, vintage, burger_classic]:
    Run 3 generation jobs (identical inputs), each producing 3 variants.
    Download every variant's PNG and sha256-hash the bytes.
    Assert 9/9 unique hashes per theme (no byte-identical duplicates).

Total: 5 themes x 3 runs x 3 variants = 45 renders.
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import List

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

THEMES = ["luxury", "cajun", "modern", "vintage", "burger_classic"]
RUNS_PER_THEME = 3
VARIATIONS_PER_RUN = 3


# --------------------------- fixtures
@pytest.fixture(scope="module")
def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def token(session: requests.Session) -> str:
    r = session.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, f"No token in login response: {r.json()}"
    session.headers.update({"Authorization": f"Bearer {tok}"})
    return tok


@pytest.fixture(scope="module")
def source_asset_id(session: requests.Session, token: str) -> str:
    r = session.get(f"{BASE_URL}/api/media/assets", params={"kind": "image", "limit": 200}, timeout=20)
    assert r.status_code == 200, f"Assets list failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    items = data.get("assets") or data.get("items") or []
    upload = None
    for a in items:
        if a.get("source") == "upload" and a.get("status", "active") == "active":
            upload = a
            break
    assert upload, f"No upload-source asset found in {len(items)} assets"
    return upload["id"]


# --------------------------- helpers
def _start_job(session: requests.Session, source_asset_id: str, theme: str) -> str:
    payload = {
        "source_asset_id": source_asset_id,
        "item_name": "Sprint 22G Diversity Test Dish",
        "features": ["Crispy", "Spicy", "House Special"],
        "price": "$18.95",
        "theme": theme,
        "auto_copy": False,
        "remove_background": False,
        "variations": VARIATIONS_PER_RUN,
    }
    t0 = time.time()
    r = session.post(f"{BASE_URL}/api/ai-designer/generate", json=payload, timeout=15)
    elapsed_ms = (time.time() - t0) * 1000
    assert r.status_code in (200, 202), f"Generate {theme}: {r.status_code} {r.text[:300]}"
    assert elapsed_ms < 2000, f"Generate {theme} took {elapsed_ms:.0f}ms (expected <500ms, allow <2000ms tolerance)"
    job_id = r.json()["job_id"]
    return job_id


def _wait_job(session: requests.Session, job_id: str, timeout: int = 240) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        r = session.get(f"{BASE_URL}/api/ai-designer/job/{job_id}", timeout=15)
        if r.status_code != 200:
            time.sleep(2)
            continue
        last = r.json()
        status = last.get("status")
        if status == "completed":
            return last
        if status == "failed":
            pytest.fail(f"Job {job_id} failed: {last.get('error') or last}")
        time.sleep(3)
    pytest.fail(f"Job {job_id} did not complete in {timeout}s. Last: {last}")


def _hash_asset_png(session: requests.Session, asset_id: str) -> str:
    r = session.get(f"{BASE_URL}/api/media/file/{asset_id}", timeout=60)
    assert r.status_code == 200, f"media/file/{asset_id}: {r.status_code}"
    body = r.content
    assert len(body) > 1000, f"Asset {asset_id} body too small: {len(body)} bytes"
    # PNG magic
    assert body[:8] == b"\x89PNG\r\n\x1a\n", f"Asset {asset_id} is not a PNG (got {body[:8]!r})"
    return hashlib.sha256(body).hexdigest()


def _gather_theme_hashes(session: requests.Session, source_asset_id: str, theme: str) -> List[str]:
    hashes: List[str] = []
    for run_idx in range(RUNS_PER_THEME):
        job_id = _start_job(session, source_asset_id, theme)
        job = _wait_job(session, job_id)
        variations = [v for v in (job.get("variations") or []) if v.get("status") == "completed"]
        assert len(variations) == VARIATIONS_PER_RUN, (
            f"{theme} run {run_idx}: expected {VARIATIONS_PER_RUN} completed variants, "
            f"got {len(variations)} (job={job_id})"
        )
        for v in variations:
            aid = v.get("asset_id")
            assert aid, f"{theme} run {run_idx} variant {v.get('variant')}: missing asset_id"
            h = _hash_asset_png(session, aid)
            hashes.append(h)
            print(f"  {theme} run{run_idx} variant={v.get('variant')} asset={aid[:8]} sha256={h[:12]}")
    return hashes


# --------------------------- tests
@pytest.mark.parametrize("theme", THEMES)
def test_variation_diversity_per_theme(session, token, source_asset_id, theme):
    """For each theme: 3 runs x 3 variants = 9 byte-unique PNGs."""
    print(f"\n=== Theme: {theme} (source_asset_id={source_asset_id}) ===")
    hashes = _gather_theme_hashes(session, source_asset_id, theme)
    unique = set(hashes)
    expected = RUNS_PER_THEME * VARIATIONS_PER_RUN
    print(f"  {theme}: {len(unique)}/{expected} unique hashes")
    assert len(hashes) == expected, f"{theme}: got {len(hashes)} hashes, expected {expected}"
    assert len(unique) == expected, (
        f"{theme}: only {len(unique)}/{expected} unique hashes — duplicates found.\n"
        f"  All hashes: {hashes}"
    )
