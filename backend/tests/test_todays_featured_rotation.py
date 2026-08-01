"""Phase 2G regression — Today's Featured rotation must not collapse to 1.

The prior default `window_days=14` silently degraded rotation to a single
flyer once the bulk-render pool aged out of the window. The fix is to
default to "no age restriction" (`window_days=0`) so the deterministic
daily rotation covers every active `html_bulk` asset.

These tests hit the live backend over HTTP (not ASGI in-process) to avoid
motor client / event-loop leakage that occurs when the full pytest suite
shares a single process. Uses requests, matching the pattern used by
test_smart_menu_workflow.py and other integration tests in this repo.
"""
import os
from datetime import datetime, timedelta, timezone

import requests
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

API = os.environ.get("PYTEST_BACKEND_URL", "http://localhost:8001/api")
TIMEOUT = 15


def _sync(coro):
    """Run a Mongo cleanup coroutine with a fresh loop each call."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _seed_assets(rows):
    async def _insert():
        c = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            db = c[os.environ["DB_NAME"]]
            await db.media_assets.insert_many(rows)
        finally:
            c.close()
    _sync(_insert())


def _cleanup(ids):
    async def _delete():
        c = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            db = c[os.environ["DB_NAME"]]
            await db.media_assets.delete_many({"id": {"$in": ids}})
        finally:
            c.close()
    _sync(_delete())


def test_featured_default_window_does_not_collapse_pool_to_one():
    """With the fixed default, an aged-out pool (all assets > 14 days old)
    must still rotate across >1 asset."""
    old_iso = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    ids = [f"phase2g-test-asset-{i}" for i in range(3)]
    seeds = [
        {"id": ids[i], "source": "html_bulk", "status": "active",
         "kind": "image", "filename": f"phase2g_{i}.png",
         "storage_path": f"lakeview/phase2g_{i}.png",
         "item_name": f"Phase2G Test Dish {i}", "theme": "luxury",
         "uploaded_at": old_iso, "width": 1200, "height": 630}
        for i in range(3)
    ]
    _seed_assets(seeds)
    try:
        r = requests.get(f"{API}/html-template/featured", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["pool_size"] >= 3, (
            f"Expected pool_size >= 3 after seeding 3 aged assets, "
            f"got {body['pool_size']}. Rotation is still collapsed."
        )
    finally:
        _cleanup(ids)


def test_featured_explicit_window_still_honoured():
    """?window_days=14 must exclude aged assets while keeping the fresh one."""
    fresh_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    old_iso = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    fresh = {"id": "phase2g-fresh", "source": "html_bulk",
             "status": "active", "kind": "image", "filename": "fresh.png",
             "storage_path": "lakeview/fresh.png",
             "item_name": "Fresh Dish", "theme": "luxury",
             "uploaded_at": fresh_iso, "width": 1200, "height": 630}
    old = {"id": "phase2g-old", "source": "html_bulk", "status": "active",
           "kind": "image", "filename": "old.png",
           "storage_path": "lakeview/old.png",
           "item_name": "Old Dish", "theme": "cajun",
           "uploaded_at": old_iso, "width": 1200, "height": 630}
    _seed_assets([fresh, old])
    try:
        r = requests.get(f"{API}/html-template/featured?window_days=14",
                         timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["pool_size"] >= 1
        # The 60-day-old seed must NOT be selectable in the 14-day window.
        assert body["asset_id"] != "phase2g-old"
    finally:
        _cleanup(["phase2g-fresh", "phase2g-old"])
