"""Final Launch — carcass regression (Sprint 16B.3).

The original `test_final_launch.py` covered three groups of endpoints that
were all removed during Sprint 15B:
  • GET  /api/ai-ads/health
  • GET  /api/ai-ads/provider-setup/{provider}
  • POST /api/ai-ads/provider-connections/{provider}/connect|disconnect|test
  • GET  /api/ai-ads/provider-connections

Sprint 16B.3 collapses the file into:
  1. A regression block proving every one of those endpoints is gone.
  2. Replacement health coverage against the surviving `/api/home/health`
     and `/api/media/health` endpoints.
  3. Auth login still works (the implicit prerequisite the original file
     depended on).
"""
import os
import uuid

import pytest
import requests

API = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://food-graphics-lab.preview.emergentagent.com",
).rstrip("/") + "/api"

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def _fresh_ip() -> str:
    return f"198.51.100.{uuid.uuid4().int % 250 + 1}"


@pytest.fixture(scope="module")
def headers():
    r = requests.post(
        f"{API}/auth/login",
        json={"password": ADMIN_PASSWORD},
        headers={"X-Forwarded-For": _fresh_ip()},
        timeout=15,
    )
    assert r.status_code == 200, f"login: {r.status_code} {r.text[:200]}"
    return {"Authorization": f"Bearer {r.json()['token']}",
            "Content-Type": "application/json"}


# ---------- Surviving health surface ----------

class TestHealth:
    def test_home_health_ok(self, headers):
        """`/api/home/health` is the current dashboard health probe."""
        r = requests.get(f"{API}/home/health", headers=headers, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)

    def test_media_health_ok(self, headers):
        """`/api/media/health` is the storage/queue health probe."""
        r = requests.get(f"{API}/media/health", headers=headers, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body.get("storage", {}).get("reachable") is True


# ---------- Sprint 15B carcass regression ----------

REMOVED_GET = [
    "/api/ai-ads/health",
    "/api/ai-ads/provider-setup/facebook",
    "/api/ai-ads/provider-setup/instagram",
    "/api/ai-ads/provider-setup/google_business",
    "/api/ai-ads/provider-setup/mailchimp",
    "/api/ai-ads/provider-setup/email",
    "/api/ai-ads/provider-setup/sms",
    "/api/ai-ads/provider-setup/no_such_provider",
    "/api/ai-ads/provider-connections",
]

REMOVED_POST = [
    "/api/ai-ads/provider-connections/facebook/connect",
    "/api/ai-ads/provider-connections/facebook/disconnect",
    "/api/ai-ads/provider-connections/facebook/test",
    "/api/ai-ads/provider-connections/email/connect",
    "/api/ai-ads/provider-connections/email/disconnect",
    "/api/ai-ads/provider-connections/email/test",
]


class TestRemovedRoutes:
    @pytest.mark.parametrize("path", REMOVED_GET)
    def test_removed_get(self, headers, path):
        r = requests.get(f"{API.rsplit('/api', 1)[0]}{path}",
                         headers=headers, timeout=10)
        assert r.status_code in (404, 405), f"GET {path} returned {r.status_code}"

    @pytest.mark.parametrize("path", REMOVED_POST)
    def test_removed_post(self, headers, path):
        r = requests.post(f"{API.rsplit('/api', 1)[0]}{path}",
                          headers=headers, json={}, timeout=10)
        assert r.status_code in (404, 405), f"POST {path} returned {r.status_code}"
