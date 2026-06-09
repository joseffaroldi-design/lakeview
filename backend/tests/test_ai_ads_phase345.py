"""Phase 3 (restaurant plugin), Phase 4 (bulk + export), Phase 5 (analytics) tests."""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://lakeview-admin-dash.preview.emergentagent.com").rstrip("/")
ADMIN_PASSWORD = "Lakeview872"


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    d = r.json()
    tok = d.get("token") or d.get("session_token") or d.get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ----------- Phase 3: Restaurant plugin -----------

class TestPhase3Plugins:
    def test_list_plugins(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/ai-ads/plugins", headers=auth_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "plugins" in d and isinstance(d["plugins"], list)
        ids = [p.get("id") for p in d["plugins"]]
        assert "restaurant" in ids, f"restaurant plugin missing in {ids}"

    def test_get_restaurant_plugin(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/ai-ads/plugins/restaurant", headers=auth_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("id") == "restaurant"
        templates = d.get("templates") or []
        actions = d.get("actions") or []
        tmpl_ids = {t.get("id") for t in templates}
        act_ids = {a.get("id") for a in actions}
        expected_tmpls = {
            "daily_special", "seafood_special", "burger_special", "happy_hour",
            "catering_promotion", "event_promotion", "loyalty_campaign",
        }
        expected_actions = {
            "facebook_ad", "instagram_caption", "tiktok_caption",
            "google_business_post", "email_campaign", "sms_campaign",
            "flyer_copy", "image_prompt", "video_script_15",
        }
        assert expected_tmpls.issubset(tmpl_ids), f"missing templates: {expected_tmpls - tmpl_ids}"
        assert expected_actions.issubset(act_ids), f"missing actions: {expected_actions - act_ids}"
        assert len(templates) >= 7
        assert len(actions) >= 9

    def test_get_unknown_plugin(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/ai-ads/plugins/no_such_plugin", headers=auth_headers)
        assert r.status_code == 404

    def test_plugin_promote_two_actions(self, api, auth_headers):
        """Test promote endpoint with 2 fast actions. Allow LLM errors per-result (200 OK)."""
        body = {
            "context": {
                "item": {"name": "Cajun Shrimp Po-Boy", "price": "$14", "description": "Fried shrimp with remoulade"},
                "category": "Sandwiches",
            },
            "template_id": "seafood_special",
            "action_ids": ["sms_campaign", "flyer_copy"],  # short, cheap actions
            "save_to_library": True,
            "campaign_name": f"TEST_PROMOTE_{uuid.uuid4().hex[:6]}",
        }
        r = api.post(
            f"{BASE_URL}/api/ai-ads/plugins/restaurant/promote",
            headers=auth_headers,
            json=body,
            timeout=90,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:500]}"
        d = r.json()
        assert d.get("plugin_id") == "restaurant"
        results = d.get("results") or []
        assert len(results) == 2, f"expected 2 results, got {len(results)}"
        for res in results:
            assert "action_id" in res
            # Each result has either output or error (per spec)
            assert ("output" in res) or ("error" in res), f"result missing output/error: {res}"

        # If at least one result has output and save_to_library was true, asset must be in library
        saved_asset_ids = [r2.get("asset_id") for r2 in results if r2.get("asset_id")]
        for aid in saved_asset_ids:
            lr = api.get(f"{BASE_URL}/api/ai-ads/assets?q={body['campaign_name']}", headers=auth_headers)
            assert lr.status_code == 200
            ids = [a["id"] for a in lr.json()["assets"]]
            assert aid in ids, f"Saved asset {aid} not in library"
            # Cleanup
            api.delete(f"{BASE_URL}/api/ai-ads/assets/{aid}", headers=auth_headers)

    def test_plugin_promote_invalid_actions(self, api, auth_headers):
        body = {"context": {"item": {"name": "x"}}, "action_ids": ["not_a_real_action"]}
        r = api.post(f"{BASE_URL}/api/ai-ads/plugins/restaurant/promote", headers=auth_headers, json=body)
        assert r.status_code == 400


# ----------- Phase 4: Bulk + Export + new filters -----------

class TestPhase4Bulk:
    created_ids = []

    @pytest.fixture(autouse=True, scope="class")
    def _seed(self, request):
        # Create 3 test assets via direct API
        session = requests.Session()
        login = session.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD})
        tok = login.json().get("token") or login.json().get("session_token")
        headers = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
        ids = []
        for i in range(3):
            body = {
                "kind": "ad_copy",
                "title": f"TEST_BULK_{uuid.uuid4().hex[:6]}_{i}",
                "platform": "Facebook",
                "industry": "restaurant",
                "payload": {"headline": f"H{i}", "body": f"B{i}"},
                "tags": ["test", "bulk"],
                "status": "active",
            }
            r = session.post(f"{BASE_URL}/api/ai-ads/assets", headers=headers, json=body)
            assert r.status_code == 200, r.text
            ids.append(r.json()["id"])
        TestPhase4Bulk.created_ids = ids

        yield

        # Final cleanup
        for aid in ids:
            session.delete(f"{BASE_URL}/api/ai-ads/assets/{aid}", headers=headers)

    def test_bulk_favorite(self, api, auth_headers):
        ids = TestPhase4Bulk.created_ids
        r = api.post(f"{BASE_URL}/api/ai-ads/assets/bulk", headers=auth_headers,
                     json={"ids": ids, "action": "favorite"})
        assert r.status_code == 200
        assert r.json().get("updated") == len(ids)
        # Verify via GET
        for aid in ids:
            g = api.get(f"{BASE_URL}/api/ai-ads/assets?q=TEST_BULK", headers=auth_headers)
            assets = g.json()["assets"]
            doc = next((a for a in assets if a["id"] == aid), None)
            assert doc and doc.get("is_favorite") is True

    def test_bulk_archive(self, api, auth_headers):
        ids = TestPhase4Bulk.created_ids
        r = api.post(f"{BASE_URL}/api/ai-ads/assets/bulk", headers=auth_headers,
                     json={"ids": ids, "action": "archive"})
        assert r.status_code == 200
        assert r.json().get("updated") == len(ids)
        g = api.get(f"{BASE_URL}/api/ai-ads/assets?q=TEST_BULK&status=archived", headers=auth_headers)
        ar_ids = [a["id"] for a in g.json()["assets"]]
        for aid in ids:
            assert aid in ar_ids, f"{aid} not archived"

    def test_export_txt(self, api, auth_headers):
        r = api.post(f"{BASE_URL}/api/ai-ads/assets/export", headers=auth_headers,
                     json={"ids": TestPhase4Bulk.created_ids, "format": "txt"})
        assert r.status_code == 200
        d = r.json()
        assert d.get("format") == "txt"
        assert isinstance(d.get("data"), str)
        assert "TEST_BULK" in d["data"]

    def test_export_csv(self, api, auth_headers):
        r = api.post(f"{BASE_URL}/api/ai-ads/assets/export", headers=auth_headers,
                     json={"ids": TestPhase4Bulk.created_ids, "format": "csv"})
        assert r.status_code == 200
        d = r.json()
        assert d["format"] == "csv"
        assert "id,title,kind" in d["data"]

    def test_export_json(self, api, auth_headers):
        r = api.post(f"{BASE_URL}/api/ai-ads/assets/export", headers=auth_headers,
                     json={"ids": TestPhase4Bulk.created_ids, "format": "json"})
        assert r.status_code == 200
        d = r.json()
        assert d["format"] == "json"
        assert isinstance(d["data"], list)
        assert len(d["data"]) == len(TestPhase4Bulk.created_ids)
        # No mongo _id leakage
        for a in d["data"]:
            assert "_id" not in a

    def test_export_bad_format(self, api, auth_headers):
        r = api.post(f"{BASE_URL}/api/ai-ads/assets/export", headers=auth_headers,
                     json={"ids": TestPhase4Bulk.created_ids, "format": "yaml"})
        assert r.status_code == 400

    def test_export_empty_ids(self, api, auth_headers):
        r = api.post(f"{BASE_URL}/api/ai-ads/assets/export", headers=auth_headers,
                     json={"ids": [], "format": "txt"})
        assert r.status_code == 400

    def test_status_scheduled_allowed(self, api, auth_headers):
        aid = TestPhase4Bulk.created_ids[0]
        r = api.put(f"{BASE_URL}/api/ai-ads/assets/{aid}", headers=auth_headers,
                    json={"status": "scheduled"})
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "scheduled"
        # Verify by list filter
        g = api.get(f"{BASE_URL}/api/ai-ads/assets?status=scheduled", headers=auth_headers)
        assert aid in [a["id"] for a in g.json()["assets"]]

    def test_date_filters(self, api, auth_headers):
        # Use today as date_from to ensure our seeded assets show
        from datetime import datetime, timedelta, timezone as tz
        today = datetime.now(tz.utc).date().isoformat()
        tomorrow = (datetime.now(tz.utc) + timedelta(days=1)).date().isoformat()
        yesterday = (datetime.now(tz.utc) - timedelta(days=1)).date().isoformat()

        r = api.get(f"{BASE_URL}/api/ai-ads/assets?date_from={yesterday}&date_to={tomorrow}&q=TEST_BULK",
                    headers=auth_headers)
        assert r.status_code == 200
        ids = [a["id"] for a in r.json()["assets"]]
        for aid in TestPhase4Bulk.created_ids:
            assert aid in ids, f"date filter missed {aid}"

        # Future-only filter should return empty for our assets
        future = (datetime.now(tz.utc) + timedelta(days=10)).date().isoformat()
        farther = (datetime.now(tz.utc) + timedelta(days=20)).date().isoformat()
        r2 = api.get(f"{BASE_URL}/api/ai-ads/assets?date_from={future}&date_to={farther}&q=TEST_BULK",
                     headers=auth_headers)
        assert r2.status_code == 200
        ids2 = [a["id"] for a in r2.json()["assets"]]
        for aid in TestPhase4Bulk.created_ids:
            assert aid not in ids2

    def test_bulk_delete(self, api, auth_headers):
        ids = TestPhase4Bulk.created_ids
        r = api.post(f"{BASE_URL}/api/ai-ads/assets/bulk", headers=auth_headers,
                     json={"ids": ids, "action": "delete"})
        assert r.status_code == 200
        assert r.json().get("deleted") == len(ids)
        # Verify gone
        g = api.get(f"{BASE_URL}/api/ai-ads/assets?q=TEST_BULK", headers=auth_headers)
        remaining = [a["id"] for a in g.json()["assets"]]
        for aid in ids:
            assert aid not in remaining


# ----------- Phase 5: Extended Analytics -----------

class TestPhase5Analytics:
    def test_analytics_shape(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/ai-ads/analytics", headers=auth_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        # totals
        totals = d.get("totals", {})
        for k in ("total_campaigns", "total_generations", "generations_this_month",
                  "generations_last_30_days", "ads_generated", "emails_generated",
                  "sms_generated", "videos_generated", "images_generated"):
            assert k in totals, f"missing totals.{k}"
            assert isinstance(totals[k], int)
        # insights
        insights = d.get("insights", {})
        for k in ("most_used_platform", "most_used_campaign_type", "most_used_goal", "most_generated_items"):
            assert k in insights, f"missing insights.{k}"
        assert isinstance(insights["most_generated_items"], list)
        # charts
        charts = d.get("charts", {})
        for k in ("trend_30_days", "platform_usage", "campaign_type_breakdown"):
            assert k in charts, f"missing charts.{k}"
            assert isinstance(charts[k], list)


# ----------- Regression -----------

class TestRegression:
    def test_menu_public(self, api):
        r = api.get(f"{BASE_URL}/api/menu")
        assert r.status_code == 200
        d = r.json()
        # response shape - list of categories or wrapper
        cats = d if isinstance(d, list) else d.get("categories") or d.get("menu") or []
        assert isinstance(cats, list) and len(cats) > 0, f"no menu categories: {d}"

    def test_login_still_works(self, api):
        r = api.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD})
        assert r.status_code == 200
