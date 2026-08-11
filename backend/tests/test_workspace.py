"""Sprint 20A Phase 4 — Marketing Workspace endpoint regression tests.

Sprint 22 Phase 5: rewritten to call the live preview backend via `requests`
instead of FastAPI's TestClient. The TestClient flavour produced
`RuntimeError: Event loop is closed` whenever this file ran AFTER another
suite that consumed the global asyncio loop (e.g. test_ai_image_async). The
HTTP-based flavour has no shared event loop, runs in any order, and matches
the style of the rest of the integration tests in this folder.
"""
from __future__ import annotations
import os
import time
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://upload-stage-two.preview.emergentagent.com").rstrip("/")


def _get(path: str, **kw):
    return requests.get(f"{BASE_URL}{path}", timeout=30, **kw)


def _post(path: str, **kw):
    return requests.post(f"{BASE_URL}{path}", timeout=30, **kw)


def test_list_projects_backfills_one_per_menu_item():
    r = _get("/api/workspace/projects?backfill=true")
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    body = r.json()
    assert "projects" in body
    assert isinstance(body["projects"], list)
    assert body["total"] == len(body["projects"])
    assert body["total"] > 0, "expected at least one menu item in the seed menu"
    for p in body["projects"]:
        for f in ("item_key", "item_name", "category", "price", "active",
                  "flyer_count", "video_count", "caption_count",
                  "is_featured_today"):
            assert f in p, f"missing field {f} on {p.get('item_key')!r}"


def test_list_projects_is_idempotent():
    a = _get("/api/workspace/projects?backfill=true").json()
    b = _get("/api/workspace/projects?backfill=true").json()
    assert a["total"] == b["total"], "backfill must not duplicate projects"


def test_list_projects_fast_enough():
    """Phase 6 perf gate: list must load in under 2.5s over the network."""
    t0 = time.perf_counter()
    r = _get("/api/workspace/projects?backfill=true")
    dt = time.perf_counter() - t0
    assert r.status_code == 200
    assert dt < 2.5, f"list took {dt:.2f}s, must be < 2.5s"


def test_project_detail_lookup_round_trip():
    lst = _get("/api/workspace/projects?backfill=true").json()
    assert lst["projects"], "need at least one project"
    pick = lst["projects"][0]
    r = _get(f"/api/workspace/projects/{pick['item_key']}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["item_key"] == pick["item_key"]
    assert detail["item_name"] == pick["item_name"]


def test_project_designs_videos_captions_endpoints():
    lst = _get("/api/workspace/projects?backfill=true").json()
    pick = lst["projects"][0]
    key = pick["item_key"]
    for sub in ("designs", "videos", "captions"):
        r = _get(f"/api/workspace/projects/{key}/{sub}")
        assert r.status_code == 200, f"{sub} endpoint must 200"
        body = r.json()
        assert "total" in body
        assert sub in body or "history" in body


def test_unknown_project_returns_404():
    r = _get("/api/workspace/projects/does-not::exist-xyz")
    assert r.status_code == 404


def test_backfill_endpoint():
    # /api/workspace/backfill requires an authenticated admin session
    # (V1 blocker remediation). Follow the project's standard test-auth
    # pattern: log in with the env-provided ADMIN_PASSWORD, then call the
    # protected endpoint with the returned bearer token.
    login = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": os.environ["ADMIN_PASSWORD"]},
        timeout=15,
    )
    assert login.status_code == 200, f"login failed: {login.status_code} {login.text[:200]}"
    token = login.json()["token"]
    r = _post(
        "/api/workspace/backfill",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "created" in body and "total" in body
    assert body["total"] > 0
