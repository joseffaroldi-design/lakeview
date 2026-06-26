"""Sprint 17A — Design Memory + Creative Director backend tests.

Covers:
- Auth on all endpoints (401 when unauth)
- Design Memory CRUD: 404 unknown, PUT upsert, GET round-trip, DELETE clear
- Schema validation: bad item_key → 400, empty payload → 400, extra fields ignored
- Creative Director: always 3 recs, ranks (Best/Good/Alternative), category inference
- Memory bias: saved theme should elevate that theme to Best Match
- Reusability: returns proper preview_color + pack metadata so the FE can render
"""
import os
import uuid
import pytest
import requests


def _read_base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for ln in f:
                if ln.startswith("REACT_APP_BACKEND_URL="):
                    return ln.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
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


# ---------------------------------------------------------------- auth
def test_design_memory_get_unauth():
    r = requests.get(f"{API}/design-memory/burgers::test-item", timeout=TIMEOUT)
    assert r.status_code in (401, 403)


def test_design_memory_put_unauth():
    r = requests.put(f"{API}/design-memory/burgers::test-item",
                     json={"theme": "burger_classic"}, timeout=TIMEOUT)
    assert r.status_code in (401, 403)


def test_creative_director_unauth():
    r = requests.post(f"{API}/creative-director/recommend",
                      json={"food_type": "burger"}, timeout=TIMEOUT)
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------- CRUD
def test_design_memory_404_unknown(auth):
    key = f"test::missing-{uuid.uuid4().hex[:8]}"
    r = requests.get(f"{API}/design-memory/{key}", headers=auth, timeout=TIMEOUT)
    assert r.status_code == 404


def test_design_memory_put_get_delete_roundtrip(auth):
    key = f"burgers::cafe-fries-{uuid.uuid4().hex[:6]}"
    # PUT (insert)
    r = requests.put(
        f"{API}/design-memory/{key}",
        headers=auth,
        json={
            "theme": "burger_neon_diner",
            "layout": "split",
            "overlay": "smoke",
            "badge": "ribbon",
            "typography": "bold",
            "crop": "center",
            "harmony": "warm",
            "favorite_flyer_id": "asset_abc",
            # Should be silently dropped by the whitelist:
            "captions": "this is generated copy — never store me",
            "video_id": "vid_xyz",
        },
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["theme"] == "burger_neon_diner"
    assert body["crop"] == "center"
    assert body["use_count"] == 1
    assert "captions" not in body, "Whitelist failed — copy leaked into design memory"
    assert "video_id" not in body, "Whitelist failed — video leaked into design memory"

    # GET round-trip
    r2 = requests.get(f"{API}/design-memory/{key}", headers=auth, timeout=TIMEOUT)
    assert r2.status_code == 200
    assert r2.json()["theme"] == "burger_neon_diner"

    # PUT again — use_count increments
    r3 = requests.put(f"{API}/design-memory/{key}",
                      headers=auth, json={"theme": "burger_classic"}, timeout=TIMEOUT)
    assert r3.status_code == 200
    assert r3.json()["use_count"] == 2
    assert r3.json()["theme"] == "burger_classic"
    # Earlier fields preserved by upsert
    assert r3.json()["crop"] == "center"

    # DELETE
    r4 = requests.delete(f"{API}/design-memory/{key}", headers=auth, timeout=TIMEOUT)
    assert r4.status_code == 200
    assert r4.json()["ok"] is True

    # GET 404 again
    r5 = requests.get(f"{API}/design-memory/{key}", headers=auth, timeout=TIMEOUT)
    assert r5.status_code == 404


def test_design_memory_invalid_key(auth):
    r = requests.put(f"{API}/design-memory/Not_A_Valid_Key!",
                     headers=auth, json={"theme": "burger_classic"}, timeout=TIMEOUT)
    assert r.status_code == 400


def test_design_memory_empty_payload(auth):
    r = requests.put(f"{API}/design-memory/burgers::any",
                     headers=auth, json={}, timeout=TIMEOUT)
    assert r.status_code == 400


# ---------------------------------------------------------------- recommender
def test_recommend_always_three(auth):
    r = requests.post(f"{API}/creative-director/recommend", headers=auth,
                      json={"food_type": "smash burger"}, timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert len(body["recommendations"]) == 3
    ranks = [x["rank"] for x in body["recommendations"]]
    assert ranks == ["Best Match", "Good Match", "Alternative"]
    stars = [x["stars"] for x in body["recommendations"]]
    assert stars == [5, 4, 3]


def test_recommend_payload_shape(auth):
    r = requests.post(f"{API}/creative-director/recommend", headers=auth,
                      json={"food_type": "shrimp po-boy"}, timeout=TIMEOUT)
    assert r.status_code == 200
    rec0 = r.json()["recommendations"][0]
    for k in ("id", "label", "pack", "pack_label", "category",
              "best_use", "preview_color", "score", "rank", "stars", "reason"):
        assert k in rec0, f"missing key {k} in recommendation"
    assert rec0["preview_color"].startswith("#")


def test_recommend_category_burger(auth):
    r = requests.post(f"{API}/creative-director/recommend", headers=auth,
                      json={"item_key": "burgers::smash-burger",
                            "food_type": "smash burger"}, timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body["context"]["category"] == "burger"
    # Best Match must be from the burger pack
    assert body["recommendations"][0]["pack"] == "burger"


def test_recommend_category_seafood(auth):
    r = requests.post(f"{API}/creative-director/recommend", headers=auth,
                      json={"item_key": "po-boys::shrimp-po-boy",
                            "food_type": "shrimp po-boy",
                            "features": ["fried", "cajun"]}, timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body["context"]["category"] == "seafood"
    assert body["recommendations"][0]["pack"] == "seafood"


def test_recommend_category_sports_wings(auth):
    r = requests.post(f"{API}/creative-director/recommend", headers=auth,
                      json={"item_key": "apps::saints-wings",
                            "food_type": "buffalo wings"}, timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json()["context"]["category"] == "sports"


def test_recommend_memory_bias_elevates_saved_theme(auth):
    """Save a memory theme that is NOT the natural #1 and confirm it
    moves to the Best Match slot."""
    key = f"burgers::memory-{uuid.uuid4().hex[:6]}"
    # First, get the natural ranking with no memory.
    r0 = requests.post(f"{API}/creative-director/recommend", headers=auth,
                       json={"item_key": key, "food_type": "smash burger"},
                       timeout=TIMEOUT)
    assert r0.status_code == 200
    natural = [x["id"] for x in r0.json()["recommendations"]]
    # Pick the #2 theme — saving it should bump it to #1.
    target = natural[1]

    # Save memory
    rp = requests.put(f"{API}/design-memory/{key}", headers=auth,
                      json={"theme": target}, timeout=TIMEOUT)
    assert rp.status_code == 200

    # Re-recommend
    r1 = requests.post(f"{API}/creative-director/recommend", headers=auth,
                       json={"item_key": key, "food_type": "smash burger"},
                       timeout=TIMEOUT)
    assert r1.status_code == 200
    body = r1.json()
    assert body["context"]["has_memory"] is True
    assert body["context"]["memory_theme"] == target
    assert body["recommendations"][0]["id"] == target
    assert "saved style" in body["recommendations"][0]["reason"].lower()

    # cleanup
    requests.delete(f"{API}/design-memory/{key}", headers=auth, timeout=TIMEOUT)


def test_recommend_memory_wins_across_categories(auth):
    """Sprint 17A spec: when the owner explicitly saves a style, it MUST
    win even if the menu item belongs to a different category. This
    protects against +50 category bonus drowning out memory bias.
    """
    key = f"apps::xcat-{uuid.uuid4().hex[:6]}"  # 'apps' → sports category
    # Save a burger theme as memory for this sports-category item.
    rp = requests.put(f"{API}/design-memory/{key}", headers=auth,
                      json={"theme": "burger_neon_diner"}, timeout=TIMEOUT)
    assert rp.status_code == 200

    r1 = requests.post(f"{API}/creative-director/recommend", headers=auth,
                       json={"item_key": key, "food_type": "buffalo wings"},
                       timeout=TIMEOUT)
    assert r1.status_code == 200
    body = r1.json()
    # Even though the item is sports-category, the saved burger theme wins.
    assert body["recommendations"][0]["id"] == "burger_neon_diner", \
        f"cross-category memory failed; top3={[r['id'] for r in body['recommendations']]}"
    assert body["recommendations"][0]["rank"] == "Best Match"

    requests.delete(f"{API}/design-memory/{key}", headers=auth, timeout=TIMEOUT)


def test_recommend_general_fallback(auth):
    """No item_key + ambiguous food → category=general, general/poster themes preferred."""
    r = requests.post(f"{API}/creative-director/recommend", headers=auth,
                      json={"food_type": "chef's special"}, timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body["context"]["category"] == "general"
    # At least one of the top-3 should be from general or poster pack
    packs = {x["pack"] for x in body["recommendations"]}
    assert packs & {"classic", "flyer"}, f"expected general/poster themes, got {packs}"
