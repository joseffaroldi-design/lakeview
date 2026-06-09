"""Final Launch — production hardening tests.

Covers: provider setup-guide endpoint, test-connection endpoint, /health.
"""
import os
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
    return {"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"}


def test_health(headers):
    r = requests.get(f"{API}/ai-ads/health", headers=headers, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "ok" in body
    assert "checks" in body
    for required in ("database", "llm_key", "scheduler", "providers"):
        assert required in body["checks"]
    assert body["checks"]["database"]["ok"] is True
    assert "total" in body["checks"]["providers"]
    assert body["checks"]["providers"]["total"] == 6


@pytest.mark.parametrize("provider", ["facebook", "instagram", "google_business", "mailchimp", "email", "sms"])
def test_setup_guides(provider, headers):
    r = requests.get(f"{API}/ai-ads/provider-setup/{provider}", headers=headers, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["title"]
    assert isinstance(body["steps"], list) and len(body["steps"]) >= 3
    assert body["docs_url"].startswith("http")


def test_setup_guide_unknown_404(headers):
    r = requests.get(f"{API}/ai-ads/provider-setup/no_such_provider", headers=headers, timeout=10)
    assert r.status_code == 404


def test_test_connection_requires_saved_connection(headers):
    requests.post(f"{API}/ai-ads/provider-connections/facebook/disconnect", headers=headers, timeout=10)
    r = requests.post(f"{API}/ai-ads/provider-connections/facebook/test", headers=headers, timeout=15)
    assert r.status_code == 404


def test_test_connection_real_facebook_call(headers):
    """Confirms test endpoint actually contacts Graph API."""
    requests.post(
        f"{API}/ai-ads/provider-connections/facebook/connect",
        json={"credentials": {"page_id": "1", "access_token": "INVALID"}},
        headers=headers, timeout=10,
    )
    try:
        r = requests.post(f"{API}/ai-ads/provider-connections/facebook/test", headers=headers, timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        # Real graph.facebook.com response
        assert "Facebook returned" in body["message"] or "OAuth" in body["message"]
        assert body["latency_ms"] >= 0
    finally:
        requests.post(f"{API}/ai-ads/provider-connections/facebook/disconnect", headers=headers, timeout=10)


def test_test_connection_records_last_test(headers):
    requests.post(
        f"{API}/ai-ads/provider-connections/email/connect",
        json={"credentials": {"api_key": "SG.INVALID"}},
        headers=headers, timeout=10,
    )
    try:
        requests.post(f"{API}/ai-ads/provider-connections/email/test", headers=headers, timeout=20)
        r = requests.get(f"{API}/ai-ads/provider-connections", headers=headers, timeout=10)
        conns = r.json()["connections"]
        email_conn = next((c for c in conns if c["provider"] == "email"), None)
        assert email_conn is not None
        assert "last_test_at" in email_conn
        assert "last_test_ok" in email_conn
        assert email_conn["last_test_ok"] is False
    finally:
        requests.post(f"{API}/ai-ads/provider-connections/email/disconnect", headers=headers, timeout=10)
