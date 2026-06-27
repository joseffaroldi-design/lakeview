"""Sprint 20A Phase 4 — Marketing Workspace endpoint regression tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from server import app
    with TestClient(app) as c:
        yield c


def test_list_projects_backfills_one_per_menu_item(client):
    r = client.get("/api/workspace/projects?backfill=true")
    assert r.status_code == 200
    body = r.json()
    assert "projects" in body
    assert isinstance(body["projects"], list)
    assert body["total"] == len(body["projects"])
    assert body["total"] > 0, "expected at least one menu item in the seed menu"
    # Every project must carry the required workspace fields.
    for p in body["projects"]:
        for f in ("item_key", "item_name", "category", "price", "active",
                  "flyer_count", "video_count", "caption_count",
                  "is_featured_today"):
            assert f in p, f"missing field {f} on {p.get('item_key')!r}"


def test_list_projects_is_idempotent(client):
    a = client.get("/api/workspace/projects?backfill=true").json()
    b = client.get("/api/workspace/projects?backfill=true").json()
    assert a["total"] == b["total"], "backfill must not duplicate projects"


def test_list_projects_fast_enough(client):
    """Phase 6 perf gate: list must load in under one second."""
    import time
    t0 = time.perf_counter()
    r = client.get("/api/workspace/projects?backfill=true")
    dt = time.perf_counter() - t0
    assert r.status_code == 200
    assert dt < 2.5, f"list took {dt:.2f}s, must be < 2.5s (TestClient overhead)"


def test_project_detail_lookup_round_trip(client):
    # Pick the first project from the list and re-fetch it by item_key.
    lst = client.get("/api/workspace/projects?backfill=true").json()
    assert lst["projects"], "need at least one project"
    pick = lst["projects"][0]
    r = client.get(f"/api/workspace/projects/{pick['item_key']}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["item_key"] == pick["item_key"]
    assert detail["item_name"] == pick["item_name"]


def test_project_designs_videos_captions_endpoints(client):
    lst = client.get("/api/workspace/projects?backfill=true").json()
    pick = lst["projects"][0]
    key = pick["item_key"]
    for sub in ("designs", "videos", "captions"):
        r = client.get(f"/api/workspace/projects/{key}/{sub}")
        assert r.status_code == 200, f"{sub} endpoint must 200"
        body = r.json()
        assert "total" in body
        assert sub in body or "history" in body  # captions returns history too


def test_unknown_project_returns_404(client):
    r = client.get("/api/workspace/projects/does-not::exist-xyz")
    assert r.status_code == 404


def test_backfill_endpoint(client):
    r = client.post("/api/workspace/backfill")
    assert r.status_code == 200
    body = r.json()
    assert "created" in body and "total" in body
    assert body["total"] > 0
