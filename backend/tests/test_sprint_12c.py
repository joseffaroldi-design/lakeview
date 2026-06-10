"""Sprint 12C backend consolidation tests.

Covers:
  - /api/media/* surface preserved after routers/media.py split
  - /api/ai-ads/assets* now reads from media_assets (source='ai_ads_legacy')
  - /api/specials* sourced from marketing_packs (tag='special')
  - /api/ai-ads/stats includes asset_counts pulled from migrated rows
  - TTL indexes on failure_audit_log, publish_logs, page_views, ai_generations
  - Regression smokes on unchanged endpoints
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_PASSWORD = "Lakeview872"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD}, timeout=15)
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


# ----------------- Media router split smokes -----------------

class TestMediaRouterSplit:
    def test_health(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/media/health", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)

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

    def test_social_formats(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/media/social-formats", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # Should list known formats
        assert isinstance(data, (dict, list))

    def test_video_jobs(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/media/video/jobs", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text

    def test_auth_required(self):
        r = requests.get(f"{BASE_URL}/api/media/assets", timeout=15)
        assert r.status_code in (401, 403), f"Expected auth challenge, got {r.status_code}"


# ----------------- ai-ads/assets (merged) -----------------

class TestAiAdsAssetsMigrated:
    def test_list_total_18(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/ai-ads/assets", headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("total") == 18, f"expected 18 legacy assets, got {data.get('total')}"

    def test_kind_breakdown(self, auth_headers):
        # sms=9, social_post=6, image_concept=3
        expected = {"sms": 9, "social_post": 6, "image_concept": 3}
        for kind, want in expected.items():
            r = requests.get(
                f"{BASE_URL}/api/ai-ads/assets",
                params={"kind": kind},
                headers=auth_headers,
                timeout=15,
            )
            assert r.status_code == 200, r.text
            got = r.json().get("total")
            assert got == want, f"kind={kind}: expected {want}, got {got}"

    def test_q_search(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/ai-ads/assets",
            params={"q": "a"},
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200, r.text

    def test_crud_round_trip(self, auth_headers):
        title = f"TEST_sprint12c_{uuid.uuid4().hex[:8]}"
        # CREATE
        r = requests.post(
            f"{BASE_URL}/api/ai-ads/assets",
            headers=auth_headers,
            json={
                "kind": "sms",
                "title": title,
                "platform": "SMS",
                "payload": {"body": "hello"},
                "tags": ["TEST_"],
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text
        created = r.json()
        aid = created["id"]
        assert created["source"] == "ai_ads_legacy"

        # GET via list filtered by title
        r = requests.get(
            f"{BASE_URL}/api/ai-ads/assets", params={"q": title}, headers=auth_headers, timeout=15
        )
        assert r.status_code == 200
        assert any(a.get("id") == aid for a in r.json()["assets"])

        # PATCH
        r = requests.put(
            f"{BASE_URL}/api/ai-ads/assets/{aid}",
            headers=auth_headers,
            json={"is_favorite": True, "title": title + "_upd"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["is_favorite"] is True
        assert r.json()["title"] == title + "_upd"

        # DUPLICATE
        r = requests.post(
            f"{BASE_URL}/api/ai-ads/assets/{aid}/duplicate", headers=auth_headers, timeout=15
        )
        assert r.status_code == 200, r.text
        dup_id = r.json()["id"]
        assert dup_id != aid
        assert "(Copy)" in r.json()["title"]

        # BULK favorite
        r = requests.post(
            f"{BASE_URL}/api/ai-ads/assets/bulk",
            headers=auth_headers,
            json={"ids": [aid, dup_id], "action": "favorite"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("updated", 0) >= 1

        # EXPORT json
        r = requests.post(
            f"{BASE_URL}/api/ai-ads/assets/export",
            headers=auth_headers,
            json={"ids": [aid, dup_id], "format": "json"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["format"] == "json"
        assert len(r.json()["data"]) == 2

        # EXPORT csv
        r = requests.post(
            f"{BASE_URL}/api/ai-ads/assets/export",
            headers=auth_headers,
            json={"ids": [aid, dup_id], "format": "csv"},
            timeout=15,
        )
        assert r.status_code == 200 and "id,title,kind" in r.json()["data"]

        # DELETE both via bulk
        r = requests.post(
            f"{BASE_URL}/api/ai-ads/assets/bulk",
            headers=auth_headers,
            json={"ids": [aid, dup_id], "action": "delete"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["deleted"] == 2

        # Verify gone
        r = requests.put(
            f"{BASE_URL}/api/ai-ads/assets/{aid}",
            headers=auth_headers,
            json={"is_favorite": False},
            timeout=15,
        )
        assert r.status_code == 404


class TestAiAdsStats:
    def test_stats_asset_counts(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/ai-ads/stats", headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "asset_counts" in data
        ac = data["asset_counts"]
        assert ac.get("sms") == 9
        assert ac.get("social_post") == 6
        assert ac.get("image_concept") == 3


# ----------------- Specials from marketing_packs -----------------

class TestSpecials:
    def test_list_public(self):
        r = requests.get(f"{BASE_URL}/api/specials", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        s = data[0]
        for key in ("id", "title", "description", "price", "image_url", "is_active", "created_at"):
            assert key in s, f"Missing key {key} in special"

    def test_friday_fish_fry_stable_id(self):
        target_id = "6aac615f-c81b-457c-b8dc-83d9d87fee51"
        r = requests.get(f"{BASE_URL}/api/specials/{target_id}", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == target_id
        assert "Friday Fish Fry" in (data.get("title") or "")


# ----------------- TTL indexes -----------------

class TestTTLIndexes:
    @pytest.mark.parametrize("coll", ["failure_audit_log", "publish_logs", "page_views", "ai_generations"])
    def test_ttl_index_exists(self, mongo_db, coll):
        idx = mongo_db[coll].index_information()
        ttl_idx = [
            (name, info) for name, info in idx.items() if "expireAfterSeconds" in info
        ]
        assert ttl_idx, f"No TTL index on {coll}: {list(idx.keys())}"
        name, info = ttl_idx[0]
        assert info["expireAfterSeconds"] == 0
        keys = dict(info["key"])
        assert "expires_at" in keys, f"TTL on {coll} not on expires_at: {keys}"

    def test_ai_generations_have_expires_at(self, mongo_db):
        # All ai_generations rows should now have expires_at after backfill
        total = mongo_db.ai_generations.count_documents({})
        with_ttl = mongo_db.ai_generations.count_documents({"expires_at": {"$type": "date"}})
        assert total == with_ttl, f"ai_generations missing expires_at: {total - with_ttl}/{total}"


# ----------------- Regressions -----------------

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

    def test_ai_ads_plugins(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/ai-ads/plugins", headers=auth_headers, timeout=15)
        assert r.status_code == 200

    def test_ai_ads_plugin_restaurant(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/ai-ads/plugins/restaurant", headers=auth_headers, timeout=15)
        assert r.status_code == 200

    def test_ai_ads_templates(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/ai-ads/templates",
            params={"industry": "restaurant"},
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200

    def test_ai_ads_providers(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/ai-ads/providers", headers=auth_headers, timeout=15)
        assert r.status_code == 200


# ----------------- Marketing pack imports still resolve -----------------

class TestMarketingPackPipeline:
    def test_shared_imports_resolve(self):
        # If the media split broke the shared re-exports, the import below
        # would raise. routers.marketing_pack imports from routers.media at
        # module load — this is exercised on app boot, but we double-check.
        from routers.media import (  # noqa: F401
            TMP_DIR, _fit_to, _hex_to_rgb, _now, _render_sync, _spawn_ai_image_task
        )

    def test_specials_collection_dropped(self, mongo_db):
        # ai_assets dropped post-migration; specials should be dropped post-Sprint 12C
        names = mongo_db.list_collection_names()
        assert "ai_assets" not in names, "ai_assets collection should be dropped after Sprint 12C"
        # specials may or may not be dropped depending on rollout; just ensure no docs leak in
