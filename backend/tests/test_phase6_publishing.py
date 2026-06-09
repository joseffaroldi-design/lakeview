"""Phase 6 — Schedule & Publish System tests."""
import asyncio
import os
import time
import uuid

import pytest
import requests

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
if not API.endswith("/api"):
    API = API.rstrip("/") + "/api"

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Lakeview872")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"password": ADMIN_PASSWORD}, timeout=20)
    r.raise_for_status()
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def asset_id(headers):
    """Create an in-DB asset directly via assets endpoint so we don't need an LLM."""
    payload = {
        "kind": "social_post",
        "title": f"PHASE6_TEST_{uuid.uuid4().hex[:8]}",
        "platform": "Facebook",
        "industry": "restaurant",
        "payload": {"caption": "Test caption for phase 6 publish tests."},
        "tags": ["phase6", "test"],
        "is_favorite": False,
        "status": "draft",
    }
    r = requests.post(f"{API}/ai-ads/assets", json=payload, headers=headers, timeout=10)
    r.raise_for_status()
    aid = r.json()["id"]
    yield aid
    requests.delete(f"{API}/ai-ads/assets/{aid}", headers=headers, timeout=10)


def test_providers_catalog(headers):
    r = requests.get(f"{API}/ai-ads/publish-providers", headers=headers, timeout=10)
    assert r.status_code == 200
    data = r.json()
    ids = [p["id"] for p in data["providers"]]
    for required in ("facebook", "instagram", "google_business", "mailchimp", "email", "sms"):
        assert required in ids, f"Missing required provider {required}"
    # Future-ready providers exist + flagged coming_soon
    for cs in ("tiktok", "linkedin", "x", "youtube"):
        assert cs in ids
    for p in data["providers"]:
        if p["id"] in ("tiktok", "linkedin", "x", "youtube"):
            assert p.get("coming_soon") is True


def test_publish_stats(headers):
    r = requests.get(f"{API}/ai-ads/publish-stats", headers=headers, timeout=10)
    assert r.status_code == 200
    body = r.json()
    for k in ("total_scheduled", "by_status", "success_rate_pct", "avg_publishes_per_day_30d", "platforms"):
        assert k in body


def test_schedule_cancel(asset_id, headers):
    future_iso = "2099-01-01T12:00:00+00:00"
    r = requests.post(
        f"{API}/ai-ads/schedule",
        json={"asset_id": asset_id, "provider": "facebook", "scheduled_at": future_iso},
        headers=headers, timeout=10,
    )
    assert r.status_code == 200, r.text
    sp = r.json()
    assert sp["status"] == "scheduled"
    sp_id = sp["id"]

    r2 = requests.post(f"{API}/ai-ads/cancel/{sp_id}", headers=headers, timeout=10)
    assert r2.status_code == 200
    assert r2.json()["status"] == "cancelled"


def test_reschedule(asset_id, headers):
    r = requests.post(
        f"{API}/ai-ads/schedule",
        json={"asset_id": asset_id, "provider": "instagram", "scheduled_at": "2099-01-01T12:00:00+00:00"},
        headers=headers, timeout=10,
    )
    sp_id = r.json()["id"]
    r2 = requests.post(
        f"{API}/ai-ads/reschedule/{sp_id}",
        json={"scheduled_at": "2099-02-02T15:00:00+00:00"},
        headers=headers, timeout=10,
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "scheduled"
    assert body["scheduled_at"].startswith("2099-02-02")
    # cleanup
    requests.post(f"{API}/ai-ads/cancel/{sp_id}", headers=headers, timeout=10)


def test_publish_now_simulated(asset_id, headers):
    # NEW CONTRACT (iter 13+): real providers — without a connection, publish must FAIL with actionable error
    r = requests.post(
        f"{API}/ai-ads/publish",
        json={"asset_id": asset_id, "provider": "facebook"},
        headers=headers, timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "failed", body
    err = (body.get("error_message") or "").lower()
    assert "connection" in err or "credential" in err, body


def test_bundle_schedule(asset_id, headers):
    r = requests.post(
        f"{API}/ai-ads/bundle-schedule",
        json={
            "asset_ids": [asset_id, asset_id],  # same asset twice — bundle creates two SPs
            "default_provider": "email",
            "default_scheduled_at": "2099-03-01T10:00:00+00:00",
            "stagger_minutes": 30,
        },
        headers=headers, timeout=10,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["scheduled"]) == 2
    # Stagger applied
    t0 = data["scheduled"][0]["scheduled_at"]
    t1 = data["scheduled"][1]["scheduled_at"]
    assert t0 != t1
    # cleanup
    for sp in data["scheduled"]:
        requests.post(f"{API}/ai-ads/cancel/{sp['id']}", headers=headers, timeout=10)


def test_calendar_endpoint(headers):
    r = requests.get(
        f"{API}/ai-ads/calendar",
        params={"start": "2099-01-01T00:00:00+00:00", "end": "2099-12-31T23:59:59+00:00"},
        headers=headers, timeout=10,
    )
    assert r.status_code == 200
    assert "events" in r.json()


def test_queue_endpoint(headers):
    r = requests.get(f"{API}/ai-ads/publish-queue", headers=headers, timeout=10)
    assert r.status_code == 200
    cols = r.json().get("columns") or {}
    for k in ("queued", "publishing", "published", "failed"):
        assert k in cols


def test_logs_endpoint(headers):
    r = requests.get(f"{API}/ai-ads/publish-logs", headers=headers, timeout=10)
    assert r.status_code == 200
    assert "logs" in r.json()


def test_provider_connect_disconnect(headers):
    # Connect
    r = requests.post(
        f"{API}/ai-ads/provider-connections/facebook/connect",
        json={"credentials": {"page_id": "TEST_PAGE", "access_token": "TEST_TOKEN"}, "display_name": "Test FB"},
        headers=headers, timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    # Secrets must NOT come back in plain
    assert body["credentials"]["page_id"] == "***"
    assert body["status"] == "connected"

    # List
    r2 = requests.get(f"{API}/ai-ads/provider-connections", headers=headers, timeout=10)
    assert r2.status_code == 200
    conns = r2.json()["connections"]
    assert any(c["provider"] == "facebook" for c in conns)

    # Disconnect
    r3 = requests.post(f"{API}/ai-ads/provider-connections/facebook/disconnect", headers=headers, timeout=10)
    assert r3.status_code == 200
    assert r3.json()["deleted"] >= 1


def test_automation_crud(headers):
    rule = {
        "name": f"TEST_RULE_{uuid.uuid4().hex[:6]}",
        "frequency": "weekly",
        "day_of_week": 4,
        "hour": 9,
        "template_id": "seafood_special",
    }
    r = requests.post(f"{API}/ai-ads/automations", json=rule, headers=headers, timeout=10)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]

    # List
    r2 = requests.get(f"{API}/ai-ads/automations", headers=headers, timeout=10)
    assert r2.status_code == 200
    assert any(x["id"] == rid for x in r2.json()["rules"])

    # Update
    rule["hour"] = 14
    r3 = requests.put(f"{API}/ai-ads/automations/{rid}", json=rule, headers=headers, timeout=10)
    assert r3.status_code == 200
    assert r3.json()["hour"] == 14

    # Delete
    r4 = requests.delete(f"{API}/ai-ads/automations/{rid}", headers=headers, timeout=10)
    assert r4.status_code == 200


def test_smart_recommendations(headers):
    r = requests.get(f"{API}/ai-ads/smart-recommendations", headers=headers, timeout=10)
    assert r.status_code == 200
    body = r.json()
    for k in ("best_platform", "best_hour_utc", "best_content_type", "best_day", "evidence"):
        assert k in body


def test_scheduler_runs_due_post(asset_id, headers):
    """End-to-end: schedule for now, manually tick the scheduler, expect published."""
    now_iso = "2025-01-01T00:00:00+00:00"  # in the past
    r = requests.post(
        f"{API}/ai-ads/schedule",
        json={"asset_id": asset_id, "provider": "sms", "scheduled_at": now_iso},
        headers=headers, timeout=10,
    )
    sp_id = r.json()["id"]

    # Manually tick the scheduler
    r2 = requests.post(f"{API}/ai-ads/run-due-now", headers=headers, timeout=20)
    assert r2.status_code == 200
    executed = r2.json()["results"]
    ids = [e["id"] for e in executed]
    assert sp_id in ids

    # Re-fetch — NEW CONTRACT: scheduler runs the post, but without provider connection it must be 'failed'
    cal = requests.get(f"{API}/ai-ads/calendar", headers=headers, timeout=10).json()["events"]
    matching = [e for e in cal if e["id"] == sp_id]
    assert matching
    assert matching[0]["status"] == "failed"
    assert matching[0].get("error_message")
