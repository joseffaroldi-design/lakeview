"""Sprint 15B.5 — Auth hardening regression tests.

Locks in:
  * Old password `Lakeview872` is no longer accepted.
  * `ADMIN_PASSWORD` is sourced from env (no hardcoded fallback).
  * `/api/auth/login` is rate-limited to 5 attempts / 15 minutes per IP.
  * Per-IP scoping: a locked IP does NOT lock out other IPs.
  * Authenticated endpoints accept a token issued by the new password.

Run with `REACT_APP_BACKEND_URL` and `ADMIN_PASSWORD` env set.
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

# A unique IP per test run so the slowapi window doesn't leak across runs.
def _fresh_ip() -> str:
    suffix = uuid.uuid4().int % 250 + 1
    return f"198.51.100.{suffix}"


class TestPasswordRotation:
    def test_old_password_lakeview872_rejected(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "Lakeview872"},
            headers={"X-Forwarded-For": _fresh_ip()},
            timeout=10,
        )
        assert r.status_code == 401, f"Old password unexpectedly accepted ({r.status_code})"

    def test_current_env_password_accepted(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": ADMIN_PASSWORD},
            headers={"X-Forwarded-For": _fresh_ip()},
            timeout=10,
        )
        assert r.status_code == 200, f"Env password rejected ({r.status_code})"
        assert "token" in r.json()

    def test_env_password_is_strong(self):
        # 24+ chars, mixed entropy. Guards against accidental rotation to a weak value.
        assert len(ADMIN_PASSWORD) >= 24, "ADMIN_PASSWORD must be at least 24 chars"


class TestLoginRateLimit:
    def test_five_wrong_then_lockout(self):
        ip = _fresh_ip()
        for i in range(5):
            r = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"password": "wrong"},
                headers={"X-Forwarded-For": ip},
                timeout=10,
            )
            assert r.status_code == 401, f"Attempt {i + 1} expected 401, got {r.status_code}"
        # 6th attempt should be rate-limited
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": "wrong"},
            headers={"X-Forwarded-For": ip},
            timeout=10,
        )
        assert r.status_code == 429, f"Expected 429 lockout, got {r.status_code}"

    def test_correct_password_also_counts_toward_limit(self):
        # Sprint 15B.5: slowapi window counts ALL attempts. After 5 attempts in 15 min,
        # even a correct password returns 429 — owner must wait for the window to clear.
        # This is the intended hardening: it prevents an attacker from probing 4 wrong
        # passwords then trying the real one on attempt 5.
        ip = _fresh_ip()
        for _ in range(5):
            requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"password": "wrong"},
                headers={"X-Forwarded-For": ip},
                timeout=10,
            )
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": ADMIN_PASSWORD},
            headers={"X-Forwarded-For": ip},
            timeout=10,
        )
        assert r.status_code == 429, f"Expected 429 after 5 prior attempts, got {r.status_code}"

    def test_lockout_is_per_ip(self):
        # Lock out one IP, then a fresh IP must still be able to authenticate.
        locked_ip = _fresh_ip()
        for _ in range(6):
            requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"password": "wrong"},
                headers={"X-Forwarded-For": locked_ip},
                timeout=10,
            )

        clean_ip = _fresh_ip()
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": ADMIN_PASSWORD},
            headers={"X-Forwarded-For": clean_ip},
            timeout=10,
        )
        assert r.status_code == 200, (
            f"Fresh IP unexpectedly affected by other IP's lockout ({r.status_code})"
        )
        assert "token" in r.json()


class TestAuthenticatedEndpoints:
    @pytest.fixture()
    def token(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": ADMIN_PASSWORD},
            headers={"X-Forwarded-For": _fresh_ip()},
            timeout=10,
        )
        assert r.status_code == 200
        return r.json()["token"]

    def test_verify_endpoint(self, token):
        r = requests.get(
            f"{BASE_URL}/api/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json().get("authenticated") is True

    def test_protected_endpoint_with_token(self, token):
        # /api/ai-designer/themes requires verify_session.
        r = requests.get(
            f"{BASE_URL}/api/ai-designer/themes",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        assert r.status_code == 200, f"Token rejected by protected endpoint ({r.status_code})"

    def test_protected_endpoint_without_token(self):
        r = requests.get(f"{BASE_URL}/api/ai-designer/themes", timeout=10)
        assert r.status_code == 401, f"Unauthenticated request unexpectedly succeeded ({r.status_code})"
