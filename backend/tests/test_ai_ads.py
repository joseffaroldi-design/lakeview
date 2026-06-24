"""Tests for the surviving AI Ads surface.

Sprint 15B removed 9 of 10 legacy routes (templates, /generate, assets CRUD,
config, providers, settings, campaigns). Only `/api/ai-ads/stats` remains —
it backs the Home tab KPI tiles. Anything beyond that should NOT exist.
"""
import os

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://food-graphics-lab.preview.emergentagent.com",
).rstrip("/")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


# ---------- Fixtures ----------

@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("session_token") or data.get("access_token")
    assert tok, f"No token in login response: {data}"
    return tok


@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------- Auth ----------

class TestAuth:
    def test_login_success(self, api):
        r = api.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD})
        assert r.status_code == 200
        d = r.json()
        tok = d.get("token") or d.get("session_token") or d.get("access_token")
        assert tok and isinstance(tok, str) and len(tok) > 10

    def test_verify_with_token(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/auth/verify", headers=auth_headers)
        assert r.status_code == 200

    def test_unauth_blocked(self):
        # /stats is the one surviving ai-ads route; it must still require auth.
        r = requests.get(f"{BASE_URL}/api/ai-ads/stats")
        assert r.status_code == 401


# ---------- The only surviving ai-ads route ----------

class TestStats:
    def test_stats_shape(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/ai-ads/stats", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        for key in (
            "total_campaigns",
            "ads_generated",
            "generations_this_month",
            "most_used_platform",
            "most_used_goal",
            "asset_counts",
            "platforms_breakdown",
            "goals_breakdown",
        ):
            assert key in d, f"missing key: {key}"
        # Counters are ints
        for k in ("total_campaigns", "ads_generated", "generations_this_month"):
            assert isinstance(d[k], int), (k, d[k])
        # Maps are dicts
        for k in ("asset_counts", "platforms_breakdown", "goals_breakdown"):
            assert isinstance(d[k], dict), (k, d[k])


# ---------- Sprint 15B carcass removal regression ----------

class TestRemovedRoutes:
    """Verify the 9 removed routes do NOT come back as live endpoints.

    Each removed path should return 404 (not 200/422/500). They were never
    used from the frontend; any reappearance would be dead code resurfacing.
    """

    @pytest.mark.parametrize("path,method", [
        ("/api/ai-ads/templates", "GET"),
        ("/api/ai-ads/config", "GET"),
        ("/api/ai-ads/providers", "GET"),
        ("/api/ai-ads/settings", "GET"),
        ("/api/ai-ads/campaigns", "GET"),
        ("/api/ai-ads/assets", "GET"),
        ("/api/ai-ads/generate", "POST"),
        ("/api/ai-ads/generate/social", "POST"),
        ("/api/ai-ads/assets/anything/duplicate", "POST"),
    ])
    def test_removed_route_is_gone(self, api, auth_headers, path, method):
        if method == "GET":
            r = api.get(f"{BASE_URL}{path}", headers=auth_headers)
        else:
            r = api.post(f"{BASE_URL}{path}", headers=auth_headers, json={})
        assert r.status_code in (404, 405), (
            f"{method} {path} unexpectedly returned {r.status_code} "
            f"(should be 404/405 after Sprint 15B removal)"
        )
