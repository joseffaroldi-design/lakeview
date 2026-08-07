"""Sprint 22C — Homepage Layout Editor backend tests.

Covers:
- Public GET /api/homepage/layout (no auth, 9 sections, meta)
- PUT auth required (401 w/o token)
- PUT reorder + title/body override persistence
- PUT validation: duplicates, unknown keys, missing auto-append
- POST /api/homepage/layout/reset (admin)
- Seed defaults idempotency
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

EXPECTED_KEYS = {
    "hero", "todays_featured", "specials", "about", "menu",
    "email_signup", "loyalty", "catering", "contact",
}
CANONICAL_ORDER = [
    "hero", "todays_featured", "specials", "about", "menu",
    "email_signup", "loyalty", "catering", "contact",
]


# --------- shared session + token (module-scoped to respect rate limit) ---------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(autouse=True, scope="module")
def reset_layout_after(auth_headers):
    """Reset layout to defaults after all tests in this module run."""
    yield
    try:
        requests.post(f"{BASE_URL}/api/homepage/layout/reset", headers=auth_headers, timeout=15)
    except Exception:
        pass


# --------- GET (public) ---------
class TestGetLayout:
    def test_get_layout_public_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/homepage/layout", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == "main"
        assert isinstance(data["sections"], list)
        assert len(data["sections"]) == 9

    def test_get_layout_section_shape(self):
        r = requests.get(f"{BASE_URL}/api/homepage/layout", timeout=15)
        data = r.json()
        keys_in_resp = {s["key"] for s in data["sections"]}
        assert keys_in_resp == EXPECTED_KEYS
        for s in data["sections"]:
            for required in ("key", "label", "visible", "title", "body",
                             "supports_title", "supports_body", "note"):
                assert required in s, f"missing field {required} in section {s.get('key')}"


# --------- PUT auth ---------
class TestPutAuth:
    def test_put_layout_requires_auth(self):
        r = requests.put(
            f"{BASE_URL}/api/homepage/layout",
            json={"sections": [{"key": "hero", "visible": True}]},
            timeout=15,
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


# --------- PUT reorder + overrides ---------
class TestPutLayoutPersistence:
    def test_put_reorder_persists(self, auth_headers):
        # reverse the order
        new_order = list(reversed(CANONICAL_ORDER))
        payload = {"sections": [{"key": k, "visible": True} for k in new_order]}
        r = requests.put(f"{BASE_URL}/api/homepage/layout", json=payload, headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        resp_keys = [s["key"] for s in r.json()["sections"]]
        assert resp_keys == new_order

        # GET back
        g = requests.get(f"{BASE_URL}/api/homepage/layout", timeout=15)
        assert g.status_code == 200
        assert [s["key"] for s in g.json()["sections"]] == new_order

    def test_put_title_body_overrides_persist(self, auth_headers):
        payload = {"sections": []}
        for k in CANONICAL_ORDER:
            entry = {"key": k, "visible": True}
            if k == "about":
                entry["title"] = "  Our Family Story  "  # check .strip()
                entry["body"] = "Three generations of Faroldi cooking..."
            payload["sections"].append(entry)
        r = requests.put(f"{BASE_URL}/api/homepage/layout", json=payload, headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text

        g = requests.get(f"{BASE_URL}/api/homepage/layout", timeout=15)
        about = next(s for s in g.json()["sections"] if s["key"] == "about")
        assert about["title"] == "Our Family Story"  # stripped
        assert about["body"] == "Three generations of Faroldi cooking..."

    def test_put_visibility_persists(self, auth_headers):
        payload = {"sections": [
            {"key": k, "visible": (k != "specials")} for k in CANONICAL_ORDER
        ]}
        r = requests.put(f"{BASE_URL}/api/homepage/layout", json=payload, headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text

        g = requests.get(f"{BASE_URL}/api/homepage/layout", timeout=15)
        specials = next(s for s in g.json()["sections"] if s["key"] == "specials")
        assert specials["visible"] is False


# --------- PUT validation ---------
class TestPutValidation:
    def test_put_rejects_duplicate_keys(self, auth_headers):
        payload = {"sections": [
            {"key": "hero", "visible": True},
            {"key": "hero", "visible": True},
            {"key": "about", "visible": True},
        ]}
        r = requests.put(f"{BASE_URL}/api/homepage/layout", json=payload, headers=auth_headers, timeout=15)
        assert r.status_code == 400, r.text
        assert "Duplicate section keys" in r.json().get("detail", "")

    def test_put_rejects_unknown_keys(self, auth_headers):
        payload = {"sections": [
            {"key": "hero", "visible": True},
            {"key": "bogus_section_xyz", "visible": True},
        ]}
        r = requests.put(f"{BASE_URL}/api/homepage/layout", json=payload, headers=auth_headers, timeout=15)
        assert r.status_code == 400, r.text
        assert "Unknown section keys" in r.json().get("detail", "")

    def test_put_missing_sections_auto_appended(self, auth_headers):
        # submit only 5 of 9 known keys
        subset = ["hero", "about", "menu", "contact", "loyalty"]
        payload = {"sections": [{"key": k, "visible": True} for k in subset]}
        r = requests.put(f"{BASE_URL}/api/homepage/layout", json=payload, headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        sections = r.json()["sections"]
        assert len(sections) == 9
        resp_keys = [s["key"] for s in sections]
        # the submitted 5 should be at front in submitted order
        assert resp_keys[:5] == subset
        # the rest should be the missing 4, all visible=True
        missing = [k for k in CANONICAL_ORDER if k not in subset]
        assert set(resp_keys[5:]) == set(missing)
        for s in sections[5:]:
            assert s["visible"] is True


# --------- POST reset ---------
class TestReset:
    def test_reset_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/homepage/layout/reset", timeout=15)
        assert r.status_code == 401

    def test_reset_restores_canonical(self, auth_headers):
        # First scramble + add overrides
        payload = {"sections": [
            {"key": k, "visible": False, "title": f"X-{k}", "body": "y"}
            for k in reversed(CANONICAL_ORDER)
        ]}
        requests.put(f"{BASE_URL}/api/homepage/layout", json=payload, headers=auth_headers, timeout=15)

        r = requests.post(f"{BASE_URL}/api/homepage/layout/reset", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        sections = r.json()["sections"]
        assert [s["key"] for s in sections] == CANONICAL_ORDER
        for s in sections:
            assert s["visible"] is True
            assert s["title"] == ""
            assert s["body"] == ""

        # verify via GET
        g = requests.get(f"{BASE_URL}/api/homepage/layout", timeout=15)
        gsec = g.json()["sections"]
        assert [s["key"] for s in gsec] == CANONICAL_ORDER
        for s in gsec:
            assert s["visible"] is True
            assert s["title"] == ""
            assert s["body"] == ""


# --------- Regression: existing endpoints still functional ---------
class TestRegression:
    def test_content_endpoint_still_works(self):
        r = requests.get(f"{BASE_URL}/api/content", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "hero" in data and "about" in data and "contact" in data

    def test_menu_endpoint_still_works(self):
        r = requests.get(f"{BASE_URL}/api/menu", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) > 0
