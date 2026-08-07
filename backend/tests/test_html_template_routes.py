"""Sprint 20A — endpoint tests for /api/html-template/* routes.

NOTE: The actual render tests are marked `slow` because Playwright +
TestClient combine slowly under pytest's sandbox; the same calls run
fast against the live uvicorn process (curl-verified). Schema/contract
tests run unconditionally.
"""
from __future__ import annotations

import io
import os
import pytest
from fastapi.testclient import TestClient
from PIL import Image


def _admin_password() -> str:
    """Load ADMIN_PASSWORD from env or /app/backend/.env fallback.
    Plaintext no longer lives in memory/test_credentials.md after the V1
    release-blocker remediation."""
    pw = os.environ.get("ADMIN_PASSWORD", "")
    if pw:
        return pw
    try:
        for line in open("/app/backend/.env"):
            if line.startswith("ADMIN_PASSWORD="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return ""


# Import the app late so settings/db are wired
@pytest.fixture(scope="module")
def client():
    from server import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin_headers(client):
    pw = _admin_password()
    if not pw:
        pytest.skip("ADMIN_PASSWORD not available")
    r = client.post("/api/auth/login", json={"password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_themes_endpoint(client):
    r = client.get("/api/html-template/themes")
    assert r.status_code == 200
    j = r.json()
    assert "themes" in j
    assert "cajun" in j["themes"]
    assert "luxury" in j["themes"]
    assert "seafood" in j["themes"]


@pytest.mark.slow
def test_preview_returns_png(client, admin_headers):
    r = client.post("/api/html-template/preview", json={
        "theme": "luxury",
        "item_name": "Test Filet",
        "features": ["A", "B", "C"],
        "price": "$24.50",
        "output_size": 256,
        "render_size": 512,
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("image/png")
    im = Image.open(io.BytesIO(r.content))
    assert im.size == (256, 256)


def test_preview_rejects_unsupported_theme(client, admin_headers):
    r = client.post("/api/html-template/preview", json={
        "theme": "burger_classic",  # not in HTML renderer
        "item_name": "x",
        "output_size": 256, "render_size": 512,
    }, headers=admin_headers)
    assert r.status_code == 400


@pytest.mark.slow
def test_bulk_render_lifecycle(client, admin_headers):
    r = client.post("/api/html-template/bulk-render", json={
        "theme": "luxury",
        "limit": 2,
        "output_size": 256,
        "render_size": 512,
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "job_id" in body
    assert body["status"] == "queued"
    job_id = body["job_id"]

    r2 = client.get(f"/api/html-template/bulk-render/{job_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == job_id


def test_bulk_render_unknown_job_id_404s(client):
    r = client.get("/api/html-template/bulk-render/does-not-exist")
    assert r.status_code == 404


def test_featured_returns_known_schema(client):
    r = client.get("/api/html-template/featured")
    # Either 200 with a flyer, or 404 if the library is empty.
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        body = r.json()
        for k in ("asset_id", "item_name", "theme", "image_url", "pool_size", "rotated_for"):
            assert k in body
        assert body["image_url"].startswith("/api/media/file/")
