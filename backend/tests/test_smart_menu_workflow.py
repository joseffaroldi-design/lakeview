"""Sprint 17B — Smart Menu Workflow backend tests.

Covers:
- Creative Director now returns `style_traits {layout, typography, badge, overlay}`
  on every recommendation.
- `vision_choice` is whitelisted by Design Memory.
- /api/media/assets supports `theme`, `item_key`, `since` filters.
- Smart sort: favorites surface before non-favorites.
- POST /api/media/assets/{id}/used bumps last_used_at.
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests


def _read_base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                return ln.split("=", 1)[1].strip().rstrip("/")
    return ""


BASE_URL = _read_base_url()
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
API = f"{BASE_URL}/api"
TIMEOUT = 15


def _login():
    fresh_ip = f"198.51.100.{uuid.uuid4().int % 250 + 1}"
    r = requests.post(
        f"{API}/auth/login",
        json={"password": ADMIN_PASSWORD},
        headers={"X-Forwarded-For": fresh_ip},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def token():
    return _login()


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------- recs

def test_recommend_returns_style_traits(auth):
    r = requests.post(f"{API}/creative-director/recommend", headers=auth,
                      json={"item_key": "burgers::smash-burger"},
                      timeout=TIMEOUT)
    assert r.status_code == 200
    for rec in r.json()["recommendations"]:
        assert "style_traits" in rec, "missing style_traits"
        traits = rec["style_traits"]
        for k in ("layout", "typography", "badge", "overlay"):
            assert traits.get(k), f"missing trait {k} on {rec['id']}"


def test_recommend_traits_match_pack(auth):
    r = requests.post(f"{API}/creative-director/recommend", headers=auth,
                      json={"item_key": "burgers::smash-burger"},
                      timeout=TIMEOUT)
    assert r.status_code == 200
    burger_rec = next(x for x in r.json()["recommendations"] if x["pack"] == "burger")
    assert burger_rec["style_traits"]["layout"] == "Hero Left"
    assert burger_rec["style_traits"]["overlay"] == "Burger Smoke"


# ---------------------------------------------------------------- memory

def test_memory_accepts_vision_choice(auth):
    key = f"burgers::vision-{uuid.uuid4().hex[:6]}"
    r = requests.put(f"{API}/design-memory/{key}", headers=auth,
                     json={"theme": "burger_classic",
                           "vision_choice": "menu"}, timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json()["vision_choice"] == "menu"
    # Update choice
    r2 = requests.put(f"{API}/design-memory/{key}", headers=auth,
                      json={"vision_choice": "merge"}, timeout=TIMEOUT)
    assert r2.status_code == 200
    assert r2.json()["vision_choice"] == "merge"
    requests.delete(f"{API}/design-memory/{key}", headers=auth, timeout=TIMEOUT)


# ---------------------------------------------------------------- assets

def _upload_dummy_asset(auth, filename: str):
    """Upload a tiny in-memory PNG via /api/media/upload and return the asset row."""
    from io import BytesIO
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (32, 32), (200, 100, 100)).save(buf, format="PNG")
    files = {"file": (filename, buf.getvalue(), "image/png")}
    data = {"folder": "Custom"}
    r = requests.post(f"{API}/media/upload", headers=auth,
                      files=files, data=data, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    return r.json()


def test_assets_filter_by_theme_and_item_key_and_since(auth):
    # We can't easily create an ai_designer flyer in a test (full pipeline runs),
    # but the FILTER itself can be smoke-tested with a known absent theme/item.
    r = requests.get(f"{API}/media/assets", headers=auth,
                     params={"theme": "definitely-not-a-real-theme",
                             "item_key": "nope::nada"},
                     timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json()["assets"] == []

    # `since` filter — far future returns nothing.
    future = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    r2 = requests.get(f"{API}/media/assets", headers=auth,
                      params={"since": future}, timeout=TIMEOUT)
    assert r2.status_code == 200
    assert r2.json()["assets"] == []


def test_assets_smart_sort_favorites_first(auth):
    # Create two assets, favorite the second one. Smart sort must surface the
    # favorited one first regardless of upload order.
    a1 = _upload_dummy_asset(auth, "smart-sort-a.png")
    a2 = _upload_dummy_asset(auth, "smart-sort-b.png")

    # Favorite a2
    rp = requests.patch(f"{API}/media/assets/{a2['id']}", headers=auth,
                        json={"is_favorite": True}, timeout=TIMEOUT)
    assert rp.status_code == 200

    # Smart sort
    r = requests.get(f"{API}/media/assets", headers=auth, timeout=TIMEOUT)
    assert r.status_code == 200
    assets = r.json()["assets"]
    # a2 should appear before a1 (favorited first)
    ids = [a["id"] for a in assets]
    assert a2["id"] in ids and a1["id"] in ids
    assert ids.index(a2["id"]) < ids.index(a1["id"]), \
        f"favorite ({a2['id']}) did not surface above non-favorite ({a1['id']}) in smart sort"

    # cleanup
    requests.delete(f"{API}/media/assets/{a1['id']}", headers=auth, timeout=TIMEOUT)
    requests.delete(f"{API}/media/assets/{a2['id']}", headers=auth, timeout=TIMEOUT)


def test_assets_mark_used_bumps_last_used_at(auth):
    a = _upload_dummy_asset(auth, "mark-used.png")
    assert not a.get("last_used_at")
    r = requests.post(f"{API}/media/assets/{a['id']}/used",
                      headers=auth, timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # Re-fetch
    r2 = requests.get(f"{API}/media/assets", headers=auth, timeout=TIMEOUT)
    assets = r2.json()["assets"]
    found = next((x for x in assets if x["id"] == a["id"]), None)
    assert found is not None
    assert found.get("last_used_at"), "last_used_at not set after /used"
    # cleanup
    requests.delete(f"{API}/media/assets/{a['id']}", headers=auth, timeout=TIMEOUT)


def test_mark_used_404(auth):
    r = requests.post(f"{API}/media/assets/does-not-exist/used",
                      headers=auth, timeout=TIMEOUT)
    assert r.status_code == 404


# ---------------------------------------------------------------- recs + favorites

def test_recommend_favorite_bias(auth):
    """A favorited flyer for this item_key should bias recommendations
    toward that theme.

    Feb 2026 (Phase 2B) — the previously-favorited `burger_grill_smoke`
    theme is now retired (hidden from new selections). This test was
    updated to favorite `vintage_diner` instead — a visible burger-style
    theme — so the test's original intent (favorites influence ranks)
    keeps working post-retirement.
    """
    key = f"burgers::fav-{uuid.uuid4().hex[:6]}"
    a = _upload_dummy_asset(auth, "fav-flyer.png")
    rp = requests.patch(f"{API}/media/assets/{a['id']}", headers=auth,
                        json={
                            "is_favorite": True,
                            "tags": ["theme:burger_classic"],
                        }, timeout=TIMEOUT)
    assert rp.status_code == 200

    # burger_classic is visible + a burger-category theme. It should
    # appear in the top-3 and carry the "favorited" reason.
    r = requests.post(f"{API}/creative-director/recommend", headers=auth,
                      json={"item_key": key, "food_type": "smash burger"},
                      timeout=TIMEOUT)
    assert r.status_code == 200
    recs = r.json()["recommendations"]
    fav = next((x for x in recs if x["id"] == "burger_classic"), None)
    assert fav is not None, \
        f"burger_classic should be in top3, got {[x['id'] for x in recs]}"
    all_reasons = " ".join(fav.get("all_reasons", []))
    assert "favorited" in all_reasons.lower(), \
        f"favorite signal missing from reasons: {fav.get('all_reasons')}"

    # cleanup
    requests.delete(f"{API}/media/assets/{a['id']}", headers=auth, timeout=TIMEOUT)
