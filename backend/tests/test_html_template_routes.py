"""Sprint 20A — endpoint tests for /api/html-template/* routes."""
from __future__ import annotations

import io
import os
import pytest
from fastapi.testclient import TestClient
from PIL import Image

# Import the app late so settings/db are wired
@pytest.fixture(scope="module")
def client():
    from server import app
    with TestClient(app) as c:
        yield c


def test_themes_endpoint(client):
    r = client.get("/api/html-template/themes")
    assert r.status_code == 200
    j = r.json()
    assert "themes" in j
    assert "cajun" in j["themes"]
    assert "luxury" in j["themes"]
    assert "seafood" in j["themes"]


def test_preview_returns_png(client):
    r = client.post("/api/html-template/preview", json={
        "theme": "luxury",
        "item_name": "Test Filet",
        "features": ["A", "B", "C"],
        "price": "$24.50",
        "output_size": 256,
        "render_size": 512,
    })
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("image/png")
    im = Image.open(io.BytesIO(r.content))
    assert im.size == (256, 256)


def test_preview_rejects_unsupported_theme(client):
    r = client.post("/api/html-template/preview", json={
        "theme": "burger_classic",  # not in HTML renderer
        "item_name": "x",
        "output_size": 256, "render_size": 512,
    })
    assert r.status_code == 400


def test_bulk_render_lifecycle(client):
    # Kick off a tiny job; should accept the request and return a job_id.
    r = client.post("/api/html-template/bulk-render", json={
        "theme": "luxury",
        "limit": 2,
        "output_size": 256,
        "render_size": 512,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "job_id" in body
    assert body["status"] == "queued"
    job_id = body["job_id"]

    # Status endpoint should return 200 immediately (job created in db).
    r2 = client.get(f"/api/html-template/bulk-render/{job_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == job_id


def test_bulk_render_unknown_job_id_404s(client):
    r = client.get("/api/html-template/bulk-render/does-not-exist")
    assert r.status_code == 404
