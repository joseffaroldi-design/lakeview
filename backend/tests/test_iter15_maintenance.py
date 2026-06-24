"""Iter-15 carcass regression.

Sprint 15B removed nearly every endpoint this test file originally covered
(/api/ai-ads/health, /assets, /calendar, /publish-queue, /analytics,
/plugins/*, /provider-connections/*). This file used to assert latency
SLOs and behaviour on those endpoints — now they're gone, so the only
useful coverage is:

  1. The removed routes STAY removed (regression so they don't come back).
  2. Auth login still works and is the correct status-shape (was iter-15's
     unrelated regression assertion).

If you find yourself adding a real test here, prefer creating a focused
file under the relevant surface (e.g. test_media_orphans.py, test_ai_ads.py
already cover what little remains of the ai-ads namespace).
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://food-graphics-lab.preview.emergentagent.com",
).rstrip("/")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def _fresh_ip() -> str:
    """Return a unique synthetic IP to dodge the 5-per-15-min login limit
    when this file runs alongside other auth-touching test files."""
    return f"198.51.100.{uuid.uuid4().int % 250 + 1}"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": ADMIN_PASSWORD},
        headers={"X-Forwarded-For": _fresh_ip()},
        timeout=15,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# Routes removed in Sprint 15B (and the now-deleted /provider-connections
# surface from iter-15 itself). Each must return 404 or 405 — never 200.
REMOVED_GET = [
    "/api/ai-ads/health",
    "/api/ai-ads/assets",
    "/api/ai-ads/assets?limit=20",
    "/api/ai-ads/calendar",
    "/api/ai-ads/publish-queue",
    "/api/ai-ads/analytics",
    "/api/ai-ads/plugins",
    "/api/ai-ads/plugins/restaurant",
    "/api/ai-ads/templates",
    "/api/ai-ads/providers",
    "/api/ai-ads/provider-connections",
]

REMOVED_POST = [
    "/api/ai-ads/provider-connections/test-all",
    "/api/ai-ads/provider-connections/email/connect",
    "/api/ai-ads/provider-connections/email/disconnect",
    "/api/ai-ads/generate",
]


@pytest.mark.parametrize("path", REMOVED_GET)
def test_removed_get_route_returns_404(headers, path):
    r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=15)
    assert r.status_code in (404, 405), (
        f"GET {path} should be removed (Sprint 15B) — got {r.status_code}"
    )


@pytest.mark.parametrize("path", REMOVED_POST)
def test_removed_post_route_returns_404(headers, path):
    r = requests.post(f"{BASE_URL}{path}", headers=headers, json={}, timeout=15)
    assert r.status_code in (404, 405), (
        f"POST {path} should be removed (Sprint 15B) — got {r.status_code}"
    )


# ---- Auth survival (was iter-15's unrelated regression) ----

def test_login_returns_token_on_success():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": ADMIN_PASSWORD},
        headers={"X-Forwarded-For": _fresh_ip()},
        timeout=10,
    )
    assert r.status_code == 200
    assert "token" in r.json()


def test_login_401_on_bad_password():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": "wrong"},
        headers={"X-Forwarded-For": _fresh_ip()},
        timeout=10,
    )
    assert r.status_code == 401
