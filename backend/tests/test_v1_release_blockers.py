"""V1 release-blocker remediation — regression tests for the four
previously-unauthenticated write routes that were tightened during
Sprint V1 blocker fixes.

Each protected route must:
  1. Reject anonymous callers (no admin token) with HTTP 401.
  2. Reach the existing handler behavior when called with a valid
     admin session token (we do not assert on downstream 2xx/4xx —
     only that we are past the auth wall, i.e. NOT 401).

The tests hit the live preview URL because the auth stack relies on
the FastAPI lifespan, MongoDB, bcrypt, and slowapi being wired
through supervisor.
"""
import os
import pytest
import requests

BASE = os.environ.get("PYTEST_BACKEND_URL", "https://upload-stage-two.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

PROTECTED_ROUTES = [
    ("POST", "/workspace/backfill", {}),
    ("POST", "/workspace/projects/does-not-exist/hero", {"asset_id": "any-id"}),
    ("POST", "/html-template/preview", {"theme": "cajun", "item_name": "Test"}),
    ("POST", "/html-template/bulk-render", {"theme": "cajun", "limit": 1}),
]


@pytest.fixture(scope="module")
def admin_token():
    pw = os.environ.get("ADMIN_PASSWORD", "")
    if not pw:
        # Read from backend/.env for local runs
        try:
            for line in open("/app/backend/.env"):
                if line.startswith("ADMIN_PASSWORD="):
                    pw = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        except Exception:
            pass
    if not pw:
        pytest.skip("ADMIN_PASSWORD not available for auth")
    r = requests.post(f"{API}/auth/login", json={"password": pw}, timeout=15)
    r.raise_for_status()
    return r.json().get("token")


@pytest.mark.parametrize("method,path,payload", PROTECTED_ROUTES)
def test_anonymous_rejected(method, path, payload):
    """Unauthenticated write must not reach the handler."""
    r = requests.request(method, f"{API}{path}", json=payload, timeout=15)
    assert r.status_code == 401, (
        f"{method} {path} expected 401 anon, got {r.status_code}: {r.text[:200]}"
    )


@pytest.mark.parametrize("method,path,payload", PROTECTED_ROUTES)
def test_authenticated_reaches_handler(method, path, payload, admin_token):
    """Authorized admin call must pass auth. Downstream behavior
    (200/400/404/etc.) is orthogonal to this test — the only assertion
    is that the auth wall is not the one blocking the call."""
    r = requests.request(
        method,
        f"{API}{path}",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    assert r.status_code != 401, (
        f"{method} {path} still 401 with a valid token: {r.text[:200]}"
    )


def test_flyer_share_endpoints_removed():
    """Drift endpoints from cfc0eea must no longer exist."""
    r = requests.post(
        f"{API}/analytics/flyer-share",
        json={"item_key": "x", "platform": "webshare"},
        timeout=10,
    )
    assert r.status_code == 404, f"POST /analytics/flyer-share should be 404, got {r.status_code}"
    r = requests.get(f"{API}/analytics/flyer-shares", timeout=10)
    assert r.status_code == 404, f"GET /analytics/flyer-shares should be 404, got {r.status_code}"
