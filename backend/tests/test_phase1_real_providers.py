"""Phase 1 — Real provider tests.

These confirm:
  • No simulation: publishing without a connection returns status='failed'
    with an actionable error_message (not a fake success).
  • With invalid credentials, the request reaches the real platform API and
    the platform's own error is surfaced (e.g. Facebook 'Invalid OAuth').
"""
import os
import uuid

import pytest
import requests

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
if not API.endswith("/api"):
    API = API.rstrip("/") + "/api"

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Lakeview872")


@pytest.fixture(scope="module")
def headers():
    r = requests.post(f"{API}/auth/login", json={"password": ADMIN_PASSWORD}, timeout=10)
    r.raise_for_status()
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def asset_id(headers):
    payload = {
        "kind": "social_post",
        "title": f"REAL_PROVIDER_TEST_{uuid.uuid4().hex[:8]}",
        "platform": "Facebook",
        "industry": "restaurant",
        "payload": {"caption": "Crawfish étouffée tonight at Lakeview. Closed at 11pm."},
        "tags": ["test"],
        "status": "draft",
    }
    r = requests.post(f"{API}/ai-ads/assets", json=payload, headers=headers, timeout=10)
    r.raise_for_status()
    aid = r.json()["id"]
    yield aid
    requests.delete(f"{API}/ai-ads/assets/{aid}", headers=headers, timeout=10)


def _ensure_disconnected(provider, headers):
    requests.post(f"{API}/ai-ads/provider-connections/{provider}/disconnect", headers=headers, timeout=10)


@pytest.mark.parametrize("provider", ["facebook", "instagram", "google_business", "mailchimp", "email", "sms"])
def test_publish_without_connection_fails_clearly(provider, asset_id, headers):
    _ensure_disconnected(provider, headers)
    r = requests.post(
        f"{API}/ai-ads/publish",
        json={"asset_id": asset_id, "provider": provider},
        headers=headers, timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "failed", f"Expected failed for unconnected {provider}, got {body['status']}"
    assert body["error_message"], "No error message"
    assert "connection" in body["error_message"].lower() or "credential" in body["error_message"].lower()
    assert body["external_id"] is None


def test_facebook_invalid_token_returns_real_error(asset_id, headers):
    requests.post(
        f"{API}/ai-ads/provider-connections/facebook/connect",
        json={"credentials": {"page_id": "1234567890", "access_token": "INVALID_TOKEN"}},
        headers=headers, timeout=10,
    )
    try:
        r = requests.post(
            f"{API}/ai-ads/publish",
            json={"asset_id": asset_id, "provider": "facebook"},
            headers=headers, timeout=30,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "failed"
        # The platform's own error must come through — proves real HTTP hit
        assert "Facebook API error" in body["error_message"]
    finally:
        _ensure_disconnected("facebook", headers)


def test_instagram_requires_image_url(asset_id, headers):
    requests.post(
        f"{API}/ai-ads/provider-connections/instagram/connect",
        json={"credentials": {"ig_user_id": "test", "access_token": "test"}},
        headers=headers, timeout=10,
    )
    try:
        r = requests.post(
            f"{API}/ai-ads/publish",
            json={"asset_id": asset_id, "provider": "instagram"},
            headers=headers, timeout=15,
        )
        body = r.json()
        # No image_url on the test asset payload → clear error
        assert body["status"] == "failed"
        assert "image_url" in body["error_message"]
    finally:
        _ensure_disconnected("instagram", headers)


def test_sendgrid_invalid_key_returns_real_error(asset_id, headers):
    requests.post(
        f"{API}/ai-ads/provider-connections/email/connect",
        json={"credentials": {
            "api_key": "SG.INVALID_KEY_TEST",
            "from_email": "test@example.com",
            "from_name": "Test",
            "recipients": "owner@example.com",
        }},
        headers=headers, timeout=10,
    )
    try:
        # Promote the test asset to email kind for this run
        requests.put(f"{API}/ai-ads/assets/{asset_id}", json={"kind": "email"}, headers=headers, timeout=10)
        r = requests.post(
            f"{API}/ai-ads/publish",
            json={"asset_id": asset_id, "provider": "email"},
            headers=headers, timeout=30,
        )
        body = r.json()
        assert body["status"] == "failed"
        assert "SendGrid" in body["error_message"]
    finally:
        _ensure_disconnected("email", headers)
