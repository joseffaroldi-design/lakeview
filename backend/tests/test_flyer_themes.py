"""Sprint 16A — Flyer-grade themes regression.

Locks in:
  * All 10 themes (5 legacy + 5 new flyer-grade) appear in /api/ai-designer/themes
  * Each new flyer theme renders 3 variations end-to-end without crashing
  * Generated assets are retrievable as thumbnails
  * Legacy themes still render (no regression)
  * Decorative primitives can be imported without raising
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

NEW_FLYER_THEMES = [
    "comic_pop",
    "vintage_diner",
    "bold_purple_pop",
    "casual_teal",
    "distressed_orange",
]
LEGACY_THEMES = ["luxury", "vintage", "modern", "social", "cajun"]


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


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def source_asset_id(token):
    r = requests.get(
        f"{BASE_URL}/api/media/assets?kind=image&limit=1",
        headers=_h(token), timeout=15,
    )
    body = r.json()
    assets = body.get("assets", body) if isinstance(body, dict) else body
    assert assets, "Need at least one source image asset"
    return assets[0]["id"]


class TestFlyerThemes:
    def test_decorative_primitives_importable(self):
        """The new PIL primitives must import without raising — even if
        they're never called from a route."""
        import sys
        sys.path.insert(0, "/app/backend")
        from routers.ai_designer import (  # noqa: F401
            _halftone_dots,
            _lightning_bolt,
            _speed_lines,
            _star,
            _squiggle,
            _sparks,
            _distressed_grain,
            _brush_stamp,
        )

    def test_all_ten_themes_registered(self, token):
        r = requests.get(
            f"{BASE_URL}/api/ai-designer/themes",
            headers=_h(token), timeout=10,
        )
        body = r.json()
        themes = body.get("themes", body) if isinstance(body, dict) else body
        ids = {t["id"] for t in themes}
        for t in LEGACY_THEMES + NEW_FLYER_THEMES:
            assert t in ids, f"Theme {t} missing from /api/ai-designer/themes"

    @pytest.mark.parametrize("theme", NEW_FLYER_THEMES)
    def test_each_new_flyer_theme_completes(self, token, source_asset_id, theme):
        r = requests.post(
            f"{BASE_URL}/api/ai-designer/generate",
            headers=_h(token),
            json={
                "source_asset_id": source_asset_id,
                "item_name": "SMASH BURGER",
                "features": [
                    "2 Burger Patties",
                    "American Cheese",
                    "Garlic Aioli",
                    "Pickled & Fried Onions",
                    "Comes With Fries",
                ],
                "price": "$20.95",
                "theme": theme,
                "auto_copy": False,
                "remove_background": False,
            },
            timeout=30,
        )
        assert r.status_code == 202, r.text[:300]
        jid = r.json()["job_id"]

        deadline = time.time() + 45
        job = None
        while time.time() < deadline:
            r = requests.get(
                f"{BASE_URL}/api/ai-designer/job/{jid}",
                headers=_h(token), timeout=10,
            )
            job = r.json()
            if job.get("status") in ("completed", "failed"):
                break
            time.sleep(2)

        assert job and job["status"] == "completed", (
            f"theme={theme} did not complete: {job.get('error')}"
        )
        assert len(job["variations"]) == 3
        for v in job["variations"]:
            assert v["status"] == "completed", v
            assert v.get("asset_id")

    def test_generated_thumbs_retrievable(self, token):
        r = requests.get(
            f"{BASE_URL}/api/ai-designer/jobs/recent?limit=1",
            headers=_h(token), timeout=10,
        )
        jobs = r.json().get("jobs", [])
        assert jobs
        # Pull full job for variation asset_ids
        full = requests.get(
            f"{BASE_URL}/api/ai-designer/job/{jobs[0]['id']}",
            headers=_h(token), timeout=10,
        ).json()
        for v in full.get("variations", []):
            if v.get("status") != "completed":
                continue
            r = requests.get(
                f"{BASE_URL}/api/media/thumb/{v['asset_id']}",
                headers=_h(token), timeout=15,
            )
            assert r.status_code == 200
            assert len(r.content) > 1000

    def test_price_and_features_required_for_flyer(self, token, source_asset_id):
        """A flyer with NEITHER price NOR features still renders cleanly —
        the composer must not crash on missing data."""
        r = requests.post(
            f"{BASE_URL}/api/ai-designer/generate",
            headers=_h(token),
            json={
                "source_asset_id": source_asset_id,
                "item_name": "Bare Test",
                "features": [],
                "price": "",
                "theme": "comic_pop",
                "auto_copy": False,
                "remove_background": False,
            },
            timeout=30,
        )
        assert r.status_code == 202
        jid = r.json()["job_id"]
        deadline = time.time() + 30
        while time.time() < deadline:
            d = requests.get(
                f"{BASE_URL}/api/ai-designer/job/{jid}",
                headers=_h(token), timeout=10,
            ).json()
            if d.get("status") in ("completed", "failed"):
                assert d["status"] == "completed", d.get("error")
                return
            time.sleep(2)
        pytest.fail("Bare flyer did not complete in 30s")


class TestLegacyThemesStillWork:
    """Ensure none of the 5 legacy themes regressed."""

    @pytest.mark.parametrize("theme", LEGACY_THEMES)
    def test_legacy_theme_still_completes(self, token, source_asset_id, theme):
        r = requests.post(
            f"{BASE_URL}/api/ai-designer/generate",
            headers=_h(token),
            json={
                "source_asset_id": source_asset_id,
                "item_name": "Smoke Test",
                "features": ["A", "B"],
                "price": "$9.99",
                "theme": theme,
                "auto_copy": False,
                "remove_background": False,
            },
            timeout=30,
        )
        assert r.status_code == 202, r.text[:300]
        jid = r.json()["job_id"]
        deadline = time.time() + 30
        while time.time() < deadline:
            d = requests.get(
                f"{BASE_URL}/api/ai-designer/job/{jid}",
                headers=_h(token), timeout=10,
            ).json()
            if d.get("status") in ("completed", "failed"):
                assert d["status"] == "completed", f"theme={theme} {d.get('error')}"
                return
            time.sleep(2)
        pytest.fail(f"Legacy theme {theme} did not complete in 30s")
