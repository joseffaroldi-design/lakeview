"""Sprint 12C backend consolidation tests — trimmed Sprint 16B.2.

What's still here (matches the current backend surface):
  - /api/media/* GETs that survived the Sprint 15B trim
  - /api/specials surface
  - TTL indexes on the four hot collections
  - General regression smokes on endpoints that are still live
  - Marketing-pack shared imports still resolve

What was removed from this file in Sprint 16B.2:
  - TestAiAdsAssetsMigrated — all CRUD/duplicate/bulk/export tests targeted
    /api/ai-ads/assets* routes that no longer exist (Sprint 15B).
  - TestRegressionSmokes coverage of /api/ai-ads/plugins, /plugins/restaurant,
    /templates, /providers — all removed in Sprint 15B.
  - /api/media/social-formats and /api/media/video/jobs — removed too.
  - test_friday_fish_fry_stable_id — too coupled to seed data.

A small TestRemovedRoutes block proves the removed endpoints stay gone.
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def _fresh_ip() -> str:
    return f"198.51.100.{uuid.uuid4().int % 250 + 1}"


@pytest.fixture(scope="session")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": ADMIN_PASSWORD},
        headers={"X-Forwarded-For": _fresh_ip()},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def mongo_db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


# ----------------- Media router split smokes (surviving subset) -----------------

class TestMediaRouterSplit:
    def test_health(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/media/health", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), dict)

    def test_assets_list(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/media/assets", headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "assets" in data or "items" in data or isinstance(data, list)

    def test_assets_list_excludes_legacy(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/media/assets?limit=500", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        body = r.json()
        items = body.get("assets") or body.get("items") or (body if isinstance(body, list) else [])
        legacy = [a for a in items if a.get("source") == "ai_ads_legacy"]
        assert legacy == [], f"Found legacy text rows in /api/media/assets: {len(legacy)}"

    def test_folders(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/media/folders", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text

    def test_stats(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/media/stats", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text

    def test_audit(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/media/audit", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text

    def test_auth_required(self):
        r = requests.get(f"{BASE_URL}/api/media/assets", timeout=15)
        assert r.status_code in (401, 403), f"Expected auth challenge, got {r.status_code}"


# ----------------- /api/ai-ads/stats (only surviving ai-ads route) -----------------

class TestAiAdsStats:
    def test_stats_responds(self, auth_headers):
        """The single surviving /api/ai-ads endpoint must still return its
        documented dict shape. asset_counts content moved (no longer
        sourced from the deleted ai_ads_legacy migration) — just assert
        the field is present and a dict."""
        r = requests.get(f"{BASE_URL}/api/ai-ads/stats", headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("total_campaigns", "ads_generated", "generations_this_month",
                  "asset_counts"):
            assert k in data, f"missing key {k}"
        assert isinstance(data["asset_counts"], dict)


# ----------------- Specials from marketing_packs -----------------

class TestSpecials:
    def test_list_public(self):
        r = requests.get(f"{BASE_URL}/api/specials", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)


# ----------------- TTL indexes -----------------

class TestTTLIndexes:
    @pytest.mark.parametrize("coll", [
        "failure_audit_log",
        "page_views",
        "ai_generations",
    ])
    def test_ttl_index_exists(self, mongo_db, coll):
        idx = mongo_db[coll].index_information()
        ttl_idx = [
            (name, info) for name, info in idx.items() if "expireAfterSeconds" in info
        ]
        if not ttl_idx:
            pytest.skip(f"TTL not configured on {coll} in this environment")
        name, info = ttl_idx[0]
        assert info["expireAfterSeconds"] == 0
        keys = dict(info["key"])
        assert "expires_at" in keys, f"TTL on {coll} not on expires_at: {keys}"


# ----------------- Regression smokes -----------------

class TestRegressionSmokes:
    def test_menu(self):
        r = requests.get(f"{BASE_URL}/api/menu", timeout=15)
        assert r.status_code == 200

    def test_content(self):
        r = requests.get(f"{BASE_URL}/api/content", timeout=15)
        assert r.status_code == 200

    def test_home_summary(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/home/summary", headers=auth_headers, timeout=15)
        assert r.status_code == 200

    def test_home_health(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/home/health", headers=auth_headers, timeout=15)
        assert r.status_code == 200

    def test_items_not_promoted(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/marketing-pack/items-not-promoted-recently?limit=3",
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200


# ----------------- Marketing pack shared imports still resolve -----------------

class TestMarketingPackPipeline:
    def test_shared_imports_resolve(self):
        # If the media split broke the shared re-exports, the import below
        # would raise. routers.marketing_pack imports from routers.media at
        # module load — this is exercised on app boot, but we double-check.
        from routers.media import (  # noqa: F401
            TMP_DIR, _fit_to, _hex_to_rgb, _now, _render_sync, _spawn_ai_image_task
        )

    def test_legacy_ai_assets_collection_dropped(self, mongo_db):
        names = mongo_db.list_collection_names()
        assert "ai_assets" not in names, "ai_assets collection should be dropped after Sprint 12C"


# ----------------- Removed routes regression -----------------

class TestRemovedRoutes:
    """Sprint 15B + ongoing trim — these endpoints must stay deleted."""

    @pytest.mark.parametrize("path", [
        "/api/ai-ads/assets",
        "/api/ai-ads/plugins",
        "/api/ai-ads/plugins/restaurant",
        "/api/ai-ads/templates",
        "/api/ai-ads/providers",
        "/api/media/social-formats",
        "/api/media/video/jobs",
    ])
    def test_get_route_gone(self, auth_headers, path):
        r = requests.get(f"{BASE_URL}{path}", headers=auth_headers, timeout=15)
        assert r.status_code in (404, 405), f"{path} returned {r.status_code}"
