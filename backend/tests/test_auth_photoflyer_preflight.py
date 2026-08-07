"""
Preflight tests: auth rate-limit sanity + Photo-to-Flyer dependent endpoints.
Uses LIVE preview backend URL (REACT_APP_BACKEND_URL). Password read from
/app/memory/test_credentials.md - never printed.
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://upload-stage-two.preview.emergentagent.com").rstrip("/")

def _load_admin_password():
    # Prefer environment. Fall back to reading /app/backend/.env directly
    # so tests run inside the container without extra setup. The plaintext
    # password is no longer stored in memory/test_credentials.md.
    pw = os.environ.get("ADMIN_PASSWORD", "")
    if pw:
        return pw
    try:
        with open("/app/backend/.env", "r") as f:
            for line in f:
                if line.startswith("ADMIN_PASSWORD="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    raise RuntimeError("ADMIN_PASSWORD not available (env or backend/.env)")

ADMIN_PASSWORD = _load_admin_password()


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def token(session):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed: HTTP {r.status_code} body={r.text[:300]}"
    data = r.json()
    tok = data.get("token") or data.get("access_token") or data.get("session_token")
    assert tok, f"No token in login response keys={list(data.keys())}"
    return tok


def test_login_success_returns_token(token):
    assert isinstance(token, str) and len(token) > 10


def test_login_wrong_password_returns_401_not_429(session):
    """Proves rate limiter is not currently tripped."""
    r = session.post(f"{BASE_URL}/api/auth/login", json={"password": "definitely-not-the-real-password-xyz"}, timeout=20)
    assert r.status_code == 401, f"Expected 401 got {r.status_code} body={r.text[:200]}"
    body = r.json()
    detail = (body.get("detail") or "").lower()
    assert "invalid" in detail, f"Unexpected detail: {detail}"


def test_auth_verify(session, token):
    r = session.get(f"{BASE_URL}/api/auth/verify", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200, f"verify failed: {r.status_code} {r.text[:200]}"


def test_ai_designer_themes(session, token):
    r = session.get(f"{BASE_URL}/api/ai-designer/themes", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    assert r.status_code == 200, f"themes failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    # Should return some list-like structure
    assert isinstance(data, (list, dict)), "themes response not list/dict"


def test_menu(session, token):
    r = session.get(f"{BASE_URL}/api/menu", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    assert r.status_code == 200, f"menu failed: {r.status_code} {r.text[:200]}"


def test_media_assets_images(session, token):
    r = session.get(f"{BASE_URL}/api/media/assets?kind=image", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    assert r.status_code == 200, f"media/assets failed: {r.status_code} {r.text[:200]}"
    # Save first asset id for downstream test
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("assets") or []
    pytest.first_asset_id = items[0].get("id") or items[0].get("_id") if items else None


def test_photo_flyer_analyze_existing(session, token):
    asset_id = getattr(pytest, "first_asset_id", None)
    if not asset_id:
        pytest.skip("No image assets available to test analyze-existing")
    r = session.post(
        f"{BASE_URL}/api/photo-flyer/analyze-existing",
        headers={"Authorization": f"Bearer {token}"},
        json={"asset_id": asset_id},
        timeout=60,
    )
    assert r.status_code == 200, f"analyze-existing failed: {r.status_code} body={r.text[:400]}"


def test_dashboard_route_reachable(session):
    # Frontend URL - use same base since preview serves both under same host
    r = session.get(f"{BASE_URL}/dashboard", timeout=20, allow_redirects=True)
    assert r.status_code == 200, f"/dashboard unreachable: {r.status_code}"
