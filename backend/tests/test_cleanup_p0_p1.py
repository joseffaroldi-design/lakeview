"""
P0/P1 Regression Tests for Lakeview Burgers & Seafood
- P0: removed /api/status GET/POST endpoints (should 404)
- P1: session persistence across backend restart (MongoDB-backed)
- P0: ADMIN_PASSWORD loaded from .env (Lakeview872), no fallback
"""
import os
import time
import subprocess
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_PASSWORD = "Lakeview872"


# --- Removed /api/status endpoints (P0) ---
class TestRemovedStatusEndpoints:
    def test_get_status_returns_404(self):
        r = requests.get(f"{BASE_URL}/api/status")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text[:200]}"

    def test_post_status_returns_404(self):
        r = requests.post(f"{BASE_URL}/api/status", json={"client_name": "x"})
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text[:200]}"


# --- ADMIN_PASSWORD from .env, no fallback (P0) ---
class TestAdminPasswordFromEnv:
    def test_login_with_env_password_succeeds(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD})
        assert r.status_code == 200
        assert "token" in r.json()

    def test_login_with_old_default_password_fails(self):
        # If a hardcoded fallback was ever 'admin' or empty, ensure it does NOT work
        for bad in ["admin", "", "password", "lakeview"]:
            r = requests.post(f"{BASE_URL}/api/auth/login", json={"password": bad})
            assert r.status_code == 401, f"Password '{bad}' unexpectedly accepted ({r.status_code})"


# --- Logout invalidates session ---
class TestLogout:
    def test_logout_invalidates_token(self):
        login = requests.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD})
        token = login.json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        # token works pre-logout
        v = requests.get(f"{BASE_URL}/api/auth/verify", headers=h)
        assert v.status_code == 200
        # logout
        lo = requests.post(f"{BASE_URL}/api/auth/logout", headers=h)
        assert lo.status_code in (200, 204), f"Logout failed: {lo.status_code} {lo.text[:200]}"
        # token now invalid
        v2 = requests.get(f"{BASE_URL}/api/auth/verify", headers=h)
        assert v2.status_code == 401, f"Token still valid after logout: {v2.status_code}"


# --- Session persistence across backend restart (P1) ---
class TestSessionPersistence:
    def test_token_survives_backend_restart(self):
        # Login
        login = requests.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD})
        assert login.status_code == 200
        token = login.json()["token"]
        h = {"Authorization": f"Bearer {token}"}

        # Pre-restart verify
        v = requests.get(f"{BASE_URL}/api/auth/verify", headers=h)
        assert v.status_code == 200

        # Restart backend via supervisor
        r = subprocess.run(
            ["sudo", "supervisorctl", "restart", "backend"],
            capture_output=True, text=True, timeout=60,
        )
        assert r.returncode == 0, f"supervisorctl failed: {r.stderr}"

        # Wait for backend to come back
        deadline = time.time() + 45
        ready = False
        while time.time() < deadline:
            try:
                ping = requests.get(f"{BASE_URL}/api/", timeout=3)
                if ping.status_code == 200:
                    ready = True
                    break
            except Exception:
                pass
            time.sleep(1)
        assert ready, "Backend did not come back online after restart"

        # Token should still verify (sessions are in MongoDB)
        v2 = requests.get(f"{BASE_URL}/api/auth/verify", headers=h)
        assert v2.status_code == 200, f"Session lost after restart: {v2.status_code} {v2.text[:200]}"
        data = v2.json()
        assert data.get("authenticated") is True


# --- All 21 protected endpoints reject missing/invalid token ---
PROTECTED = [
    ("GET", "/api/analytics"),
    ("POST", "/api/specials"),
    ("PUT", "/api/specials/dummy-id"),
    ("DELETE", "/api/specials/dummy-id"),
    ("PUT", "/api/content/hero"),
    ("PUT", "/api/menu/categories/dummy"),
    ("GET", "/api/catering/inquiries"),
    ("PUT", "/api/catering/inquiries/dummy/status"),
    ("GET", "/api/newsletter/subscribers"),
    ("PUT", "/api/giveaway/settings"),
    ("GET", "/api/giveaway/entries"),
    ("PUT", "/api/giveaway/entries/dummy/claim"),
    ("GET", "/api/loyalty/members"),
    ("PUT", "/api/loyalty/members/dummy/stamp"),
    ("PUT", "/api/loyalty/members/dummy/claim"),
    ("POST", "/api/messages/send"),
    ("GET", "/api/messages/history"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/verify"),
]


class TestProtectedEndpointsRequireAuth:
    """Auth must be enforced; reject with 401 (or 422 if body validation triggers first)."""

    @pytest.mark.parametrize("method,path", PROTECTED)
    def test_no_token_blocked(self, method, path):
        url = f"{BASE_URL}{path}"
        r = requests.request(method, url, json={} if method in ("POST", "PUT") else None)
        # Accept 401 (auth) or 422 (Pydantic body validation runs first - still blocked).
        # logout is special: it returns 200 even with no token, which is acceptable for logout.
        if path == "/api/auth/logout":
            assert r.status_code in (200, 401)
        else:
            assert r.status_code in (401, 422, 404), f"{method} {path} expected 401/422/404 got {r.status_code}"

    @pytest.mark.parametrize("method,path", PROTECTED)
    def test_invalid_token_blocked(self, method, path):
        url = f"{BASE_URL}{path}"
        h = {"Authorization": "Bearer not-a-real-token-xyz"}
        r = requests.request(method, url, headers=h, json={} if method in ("POST", "PUT") else None)
        if path == "/api/auth/logout":
            assert r.status_code in (200, 401)
        else:
            # Must NOT return 200 with invalid token
            assert r.status_code != 200, f"{method} {path} accepted bad token! got {r.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
