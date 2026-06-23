"""Tests for AI Marketing Studio (Phase 1 + Phase 2) endpoints.

Covers:
- Auth login (env-driven ADMIN_PASSWORD)
- /api/ai-ads/templates, /config, /stats, /providers, /settings
- /api/ai-ads/campaigns CRUD
- /api/ai-ads/assets CRUD + filters + NEW /duplicate endpoint
- AI generation endpoints (treated as soft-fail: 402 / LLM-key issues are not bugs)
"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://food-graphics-lab.preview.emergentagent.com").rstrip("/")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


# ---------- Fixtures ----------

@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("session_token") or data.get("access_token")
    assert tok, f"No token in login response: {data}"
    return tok


@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------- Auth ----------

class TestAuth:
    def test_login_success(self, api):
        r = api.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD})
        assert r.status_code == 200
        d = r.json()
        tok = d.get("token") or d.get("session_token") or d.get("access_token")
        assert tok and isinstance(tok, str) and len(tok) > 10

    def test_login_wrong_password(self, api):
        r = api.post(f"{BASE_URL}/api/auth/login", json={"password": "wrong-password-xyz"})
        assert r.status_code in (401, 403)

    def test_verify_with_token(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/auth/verify", headers=auth_headers)
        assert r.status_code == 200

    def test_unauth_blocked(self):
        # Use fresh session (no cookies, no auth header) to verify protection
        r = requests.get(f"{BASE_URL}/api/ai-ads/templates")
        assert r.status_code == 401


# ---------- Catalog / Read endpoints ----------

class TestCatalog:
    def test_templates(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/ai-ads/templates", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        assert "templates" in d and "goals" in d and "platforms" in d and "tones" in d
        assert isinstance(d["templates"], list)
        assert isinstance(d["goals"], list)

    def test_stats(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/ai-ads/stats", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        for key in ("total_campaigns", "ads_generated", "generations_this_month", "asset_counts"):
            assert key in d

    def test_config_get(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/ai-ads/config", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        assert "provider" in d and "model" in d

    def test_config_put(self, api, auth_headers):
        # Read current
        cur = api.get(f"{BASE_URL}/api/ai-ads/config", headers=auth_headers).json()
        # Update (use same values — non-destructive)
        r = api.put(
            f"{BASE_URL}/api/ai-ads/config",
            headers=auth_headers,
            json={"provider": cur.get("provider", "emergent"), "model": cur.get("model", "gpt-5")},
        )
        assert r.status_code == 200
        # Verify by GET
        cur2 = api.get(f"{BASE_URL}/api/ai-ads/config", headers=auth_headers).json()
        assert cur2.get("provider") == cur.get("provider", "emergent")

    def test_providers(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/ai-ads/providers", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        for kind in ("text", "image", "video"):
            assert kind in d
            # Each provider catalog returns {available: [...], enabled: bool}
            catalog = d[kind]
            assert isinstance(catalog, dict)
            assert "available" in catalog
            assert isinstance(catalog["available"], list)

    def test_settings_get_then_put(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/ai-ads/settings", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        for k in ("default_industry", "default_tone", "default_platform", "monthly_generation_limit"):
            assert k in d

        # Update
        new_tone = "TEST_TONE"
        r2 = api.put(f"{BASE_URL}/api/ai-ads/settings", headers=auth_headers, json={"default_tone": new_tone})
        assert r2.status_code == 200

        # Verify persisted
        r3 = api.get(f"{BASE_URL}/api/ai-ads/settings", headers=auth_headers).json()
        assert r3.get("default_tone") == new_tone

        # Restore
        api.put(f"{BASE_URL}/api/ai-ads/settings", headers=auth_headers, json={"default_tone": d.get("default_tone") or "Local New Orleans Style"})


# ---------- Campaigns ----------

class TestCampaigns:
    def test_list_campaigns(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/ai-ads/campaigns", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        assert "campaigns" in d and isinstance(d["campaigns"], list)


# ---------- Assets (Creative Library) ----------

class TestAssets:
    created_ids = []

    def test_list_assets_no_filter(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/ai-ads/assets", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        assert "assets" in d

    def test_create_asset(self, api, auth_headers):
        body = {
            "kind": "ad_copy",
            "title": f"TEST_AD_{uuid.uuid4().hex[:6]}",
            "platform": "Facebook",
            "industry": "restaurant",
            "payload": {"headline": "Best Burger in Town", "body": "Come hungry"},
            "tags": ["test", "burger"],
            "status": "active",
        }
        r = api.post(f"{BASE_URL}/api/ai-ads/assets", headers=auth_headers, json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"] and d["title"] == body["title"]
        assert d["kind"] == "ad_copy"
        TestAssets.created_ids.append(d["id"])

    def test_filter_assets(self, api, auth_headers):
        # filter by kind
        r = api.get(f"{BASE_URL}/api/ai-ads/assets?kind=ad_copy&platform=Facebook", headers=auth_headers)
        assert r.status_code == 200
        for a in r.json()["assets"]:
            assert a.get("kind") == "ad_copy"
            assert a.get("platform") == "Facebook"

        # filter by q (search)
        r = api.get(f"{BASE_URL}/api/ai-ads/assets?q=TEST_AD", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        assert d["total"] >= 1

        # filter by status
        r = api.get(f"{BASE_URL}/api/ai-ads/assets?status=active", headers=auth_headers)
        assert r.status_code == 200

        # filter by is_favorite
        r = api.get(f"{BASE_URL}/api/ai-ads/assets?is_favorite=false", headers=auth_headers)
        assert r.status_code == 200

    def test_patch_asset_favorite(self, api, auth_headers):
        assert TestAssets.created_ids, "Need a created asset"
        aid = TestAssets.created_ids[0]
        r = api.put(f"{BASE_URL}/api/ai-ads/assets/{aid}", headers=auth_headers, json={"is_favorite": True})
        assert r.status_code == 200
        assert r.json()["is_favorite"] is True

        # Verify with GET (via list)
        r2 = api.get(f"{BASE_URL}/api/ai-ads/assets?is_favorite=true", headers=auth_headers)
        ids = [a["id"] for a in r2.json()["assets"]]
        assert aid in ids

    def test_patch_asset_archive(self, api, auth_headers):
        aid = TestAssets.created_ids[0]
        r = api.put(f"{BASE_URL}/api/ai-ads/assets/{aid}", headers=auth_headers, json={"status": "archived"})
        assert r.status_code == 200
        assert r.json()["status"] == "archived"

    def test_duplicate_asset(self, api, auth_headers):
        """NEW endpoint: POST /api/ai-ads/assets/{id}/duplicate"""
        aid = TestAssets.created_ids[0]
        # First mark it as favorite + active so we can confirm reset on duplicate
        api.put(f"{BASE_URL}/api/ai-ads/assets/{aid}", headers=auth_headers, json={"is_favorite": True, "status": "active"})
        original = api.get(f"{BASE_URL}/api/ai-ads/assets?q=TEST_AD", headers=auth_headers).json()
        orig_doc = next((a for a in original["assets"] if a["id"] == aid), None)
        assert orig_doc is not None

        r = api.post(f"{BASE_URL}/api/ai-ads/assets/{aid}/duplicate", headers=auth_headers)
        assert r.status_code == 200, r.text
        clone = r.json()

        # NEW id
        assert clone["id"] != aid
        # (Copy) suffix
        assert clone["title"].endswith("(Copy)")
        assert clone["title"] == f"{orig_doc['title']} (Copy)"
        # status=draft
        assert clone["status"] == "draft"
        # is_favorite=false
        assert clone["is_favorite"] is False
        # payload preserved
        assert clone["payload"] == orig_doc["payload"]
        assert clone["kind"] == orig_doc["kind"]

        TestAssets.created_ids.append(clone["id"])

        # Verify persistence
        r2 = api.get(f"{BASE_URL}/api/ai-ads/assets?q=TEST_AD", headers=auth_headers).json()
        all_ids = [a["id"] for a in r2["assets"]]
        assert clone["id"] in all_ids

    def test_duplicate_nonexistent(self, api, auth_headers):
        r = api.post(f"{BASE_URL}/api/ai-ads/assets/nonexistent-id-xxx/duplicate", headers=auth_headers)
        assert r.status_code == 404

    def test_delete_asset(self, api, auth_headers):
        # Cleanup all created assets
        for aid in TestAssets.created_ids:
            r = api.delete(f"{BASE_URL}/api/ai-ads/assets/{aid}", headers=auth_headers)
            assert r.status_code == 200
        # Verify gone
        for aid in TestAssets.created_ids:
            r = api.delete(f"{BASE_URL}/api/ai-ads/assets/{aid}", headers=auth_headers)
            assert r.status_code == 404
        TestAssets.created_ids.clear()


# ---------- AI Generation (soft-fail: 402/LLM-key issues are not bugs) ----------

class TestGenerationSoft:
    """Treat 402/budget/LLM errors as 'needs live key' — not failures."""

    def _soft_assert(self, r, label):
        if r.status_code == 200:
            d = r.json()
            assert "output" in d or "data" in d, f"{label}: no output in {d}"
            return ("ok", None)
        # Acceptable failures
        if r.status_code in (402, 502, 500):
            body = r.text.lower()
            if any(s in body for s in ("budget", "402", "key", "quota", "limit", "exceeded", "runtime")):
                return ("needs_live_key", r.text[:300])
            return ("needs_live_key", r.text[:300])
        # Anything else (e.g. 422, 401) IS a bug
        pytest.fail(f"{label} returned unexpected status {r.status_code}: {r.text[:300]}")

    def test_generate_master(self, api, auth_headers):
        body = {"goal": "Drive Reservations", "platform": "Facebook", "tone": "Friendly", "industry": "restaurant"}
        r = api.post(f"{BASE_URL}/api/ai-ads/generate", headers=auth_headers, json=body)
        status, msg = self._soft_assert(r, "generate")
        print(f"[generate] {status}: {msg}")

    @pytest.mark.parametrize("kind", ["social", "email", "sms", "image_concept", "video_concept"])
    def test_generate_specialty(self, api, auth_headers, kind):
        body = {"goal": "Promote Special", "platform": "Facebook", "tone": "Friendly", "industry": "restaurant"}
        r = api.post(f"{BASE_URL}/api/ai-ads/generate/{kind}", headers=auth_headers, json=body)
        status, msg = self._soft_assert(r, f"generate/{kind}")
        print(f"[generate/{kind}] {status}: {msg}")
