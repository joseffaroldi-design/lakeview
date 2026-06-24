"""
P0/P1 Regression Tests for Lakeview Burgers & Seafood
- P0: removed /api/status GET/POST endpoints (should 404)
- P1: session persistence across backend restart (MongoDB-backed)
- P0: ADMIN_PASSWORD loaded from .env (no hardcoded fallback)

Sprint 16B.3: PROTECTED list trimmed to current router surface (removed
specials write routes, giveaway routes, /api/menu/categories path). Added
TestRemovedRoutes regression to keep them gone.
"""
import os
import time
import subprocess
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def _fresh_ip() -> str:
    return f"203.0.113.{uuid.uuid4().int % 250 + 1}"


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
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": ADMIN_PASSWORD},
            headers={"X-Forwarded-For": _fresh_ip()},
        )
        assert r.status_code == 200
        assert "token" in r.json()

    def test_login_with_old_default_password_fails(self):
        # If a hardcoded fallback was ever 'admin' or empty, ensure it does NOT work.
        # Use a fresh X-Forwarded-For per attempt — the global login rate limit
        # (5 / 15 minutes per IP, Sprint 15B.5) would otherwise interfere.
        for bad in ["admin", "", "password", "lakeview"]:
            r = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"password": bad},
                headers={"X-Forwarded-For": _fresh_ip()},
            )
            assert r.status_code in (401, 422), f"Password '{bad}' unexpectedly accepted ({r.status_code})"


# --- Logout invalidates session ---
class TestLogout:
    def test_logout_invalidates_token(self):
        login = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": ADMIN_PASSWORD},
            headers={"X-Forwarded-For": _fresh_ip()},
        )
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
        login = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": ADMIN_PASSWORD},
            headers={"X-Forwarded-For": _fresh_ip()},
        )
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


# --- All currently-protected endpoints reject missing/invalid token ---
# Sprint 16B.3: trimmed the PROTECTED list to match the current router
# surface — removed entries for /api/specials write routes (read-only now),
# /api/giveaway/* (removed), and /api/menu/categories/{id} (wrong path —
# real route is /api/menu/{category_id}, already covered).
PROTECTED = [
    ("GET", "/api/analytics"),
    ("PUT", "/api/content/hero"),
    ("PUT", "/api/menu/dummy"),
    ("GET", "/api/catering/inquiries"),
    ("PUT", "/api/catering/inquiries/dummy/status"),
    ("GET", "/api/newsletter/subscribers"),
    ("GET", "/api/loyalty/members"),
    ("PUT", "/api/loyalty/members/dummy/stamp"),
    ("PUT", "/api/loyalty/members/dummy/claim"),
    ("POST", "/api/messages/send"),
    ("GET", "/api/messages/history"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/verify"),
]


# --- Sprint 15B removed-routes regression ---
# These used to be in PROTECTED — they're gone now, so auth-required tests
# don't apply. Replace with a sanity check that they actually 404/405.
REMOVED_ROUTES = [
    ("POST", "/api/specials"),
    ("PUT", "/api/specials/dummy-id"),
    ("DELETE", "/api/specials/dummy-id"),
    ("PUT", "/api/giveaway/settings"),
    ("GET", "/api/giveaway/entries"),
    ("PUT", "/api/giveaway/entries/dummy/claim"),
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


# --- Sprint 15B removed routes regression ---

class TestRemovedRoutes:
    """Specials write routes + giveaway endpoints were removed in Sprint 15B.
    They must stay gone — return 404 (no route) or 405 (method not allowed
    when only GET is registered on a path)."""

    @pytest.mark.parametrize("method,path", REMOVED_ROUTES)
    def test_removed_route_returns_404_or_405(self, method, path):
        url = f"{BASE_URL}{path}"
        r = requests.request(method, url, json={} if method in ("POST", "PUT") else None)
        assert r.status_code in (404, 405), (
            f"{method} {path} should be removed (Sprint 15B) — got {r.status_code}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
