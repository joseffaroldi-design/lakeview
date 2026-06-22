"""Iteration 15 — Post-Launch Optimization Maintenance Tests.

Covers the 7 maintenance items shipped in option (b):
  (1) MongoDB indexes — hot endpoint latency
  (2) Plugin catalog pre-warm — restaurant plugin fast
  (3) NEW POST /api/ai-ads/provider-connections/test-all
  (6) Plugin catalog cached on startup
  (REGRESSION) Health endpoint still ok=true
"""

import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://food-graphics-lab.preview.emergentagent.com").rstrip("/")
ADMIN_PASSWORD = "Lakeview872"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ---- (1) MongoDB indexes: hot endpoints should respond fast ----
@pytest.mark.parametrize("path", [
    "/api/ai-ads/health",
    "/api/ai-ads/assets?limit=20",
    "/api/ai-ads/calendar",
    "/api/ai-ads/publish-queue",
    "/api/ai-ads/analytics",
])
def test_hot_endpoint_latency(headers, path):
    t0 = time.perf_counter()
    r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=15)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"
    # Indexes ensure these are well under 1.5s end-to-end through ingress
    assert elapsed_ms < 1500, f"{path} took {elapsed_ms:.0f}ms (expected <1500ms)"


# ---- Health endpoint contract ----
def test_health_ok(headers):
    r = requests.get(f"{BASE_URL}/api/ai-ads/health", headers=headers, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert "checks" in data
    assert data["checks"]["database"]["ok"] is True


# ---- (6) Plugin catalog pre-warm: restaurant plugin should be fast ----
def test_restaurant_plugin_fast(headers):
    t0 = time.perf_counter()
    r = requests.get(f"{BASE_URL}/api/ai-ads/plugins/restaurant", headers=headers, timeout=10)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    data = r.json()
    assert data.get("id") == "restaurant"
    # Cached in-process — should be well under 1500ms end-to-end through ingress
    assert elapsed_ms < 1500, f"restaurant plugin took {elapsed_ms:.0f}ms"


# ---- (3) NEW: POST /provider-connections/test-all ----
def test_test_all_with_no_connections(headers):
    """Clean state — disconnect any existing connections then call test-all → 0/0/0."""
    # Best-effort: enumerate and disconnect any leftover test connections (idempotent)
    r0 = requests.get(f"{BASE_URL}/api/ai-ads/provider-connections", headers=headers, timeout=10)
    if r0.status_code == 200:
        for conn in r0.json().get("connections", []):
            requests.post(
                f"{BASE_URL}/api/ai-ads/provider-connections/{conn['provider']}/disconnect",
                headers=headers, timeout=10,
            )

    r = requests.post(f"{BASE_URL}/api/ai-ads/provider-connections/test-all", headers=headers, timeout=15)
    assert r.status_code == 200, f"test-all -> {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert "results" in data and "summary" in data
    assert data["results"] == []
    assert data["summary"] == {"connected": 0, "passed": 0, "failed": 0}


def test_test_all_with_one_connection_parallel(headers):
    """Connect one provider with a bogus key, run test-all, expect 1/0/1 and last_test_at populated."""
    # Connect email/SendGrid with a deliberately invalid key
    connect_payload = {
        "credentials": {"api_key": "SG.INVALID_PROBE_ITER15", "from_email": "noreply@example.com"},
    }
    rc = requests.post(
        f"{BASE_URL}/api/ai-ads/provider-connections/email/connect",
        headers=headers, json=connect_payload, timeout=15,
    )
    assert rc.status_code in (200, 201), f"connect failed: {rc.status_code} {rc.text[:200]}"

    try:
        t0 = time.perf_counter()
        r = requests.post(f"{BASE_URL}/api/ai-ads/provider-connections/test-all", headers=headers, timeout=30)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["results"], list) and len(data["results"]) == 1
        result = data["results"][0]
        assert result["provider"] == "email"
        # Bogus SendGrid key → expect ok=False with real upstream error surfaced
        assert result["ok"] is False
        assert "message" in result
        assert data["summary"]["connected"] == 1
        assert data["summary"]["failed"] == 1
        assert data["summary"]["passed"] == 0

        # Verify last_test_at was recorded on the connection
        rg = requests.get(f"{BASE_URL}/api/ai-ads/provider-connections", headers=headers, timeout=10)
        assert rg.status_code == 200
        conn = next((c for c in rg.json()["connections"] if c["provider"] == "email"), None)
        assert conn is not None
        assert conn.get("last_test_at") is not None
        assert conn.get("last_test_ok") is False

        # Parallel probe should not be slow — round-trip <10s even with real SendGrid call
        assert elapsed_ms < 10000, f"test-all took {elapsed_ms:.0f}ms"
    finally:
        # Cleanup
        requests.post(
            f"{BASE_URL}/api/ai-ads/provider-connections/email/disconnect",
            headers=headers, timeout=10,
        )


# ---- (REGRESSION) auth still works ----
def test_login_endpoint_exempt_from_401_interceptor_response_shape():
    """Login itself must return token on success (frontend interceptor exempts /auth/login)."""
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD}, timeout=10)
    assert r.status_code == 200
    assert "token" in r.json()


def test_login_401_on_bad_password():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"password": "wrong"}, timeout=10)
    assert r.status_code == 401
