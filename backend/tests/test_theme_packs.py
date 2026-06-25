"""Sprint 16F — Theme Pack System regression.

Locks in:
  * theme_packs loader returns 22 themes across 6 packs with no warnings.
  * Duplicate IDs are detected (mocked).
  * /api/ai-designer/themes returns backward-compatible payload + new fields.
  * /api/ai-designer/themes returns `packs[]` grouped metadata.
  * Each new pack's themes complete a full generation end-to-end (1 per pack).
  * Validation drops malformed themes.
"""
import importlib
import os
import sys
import time
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def _fresh_ip() -> str:
    return f"198.51.100.{uuid.uuid4().int % 250 + 1}"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"password": ADMIN_PASSWORD},
        headers={"X-Forwarded-For": _fresh_ip()},
        timeout=10,
    )
    assert r.status_code == 200, r.text[:200]
    return r.json()["token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def source_asset_id(token):
    r = requests.get(
        f"{BASE_URL}/api/media/assets?kind=image&limit=1",
        headers=_h(token), timeout=15,
    )
    body = r.json()
    assets = body.get("assets", body) if isinstance(body, dict) else body
    assert assets, "Need at least one source image asset"
    return assets[0]["id"]


class TestThemePackLoader:
    def test_loader_assembles_expected_counts(self):
        from theme_packs import THEME_STYLES, PACKS, WARNINGS
        # 5 classic + 5 flyer + 12 new = 22
        assert len(THEME_STYLES) == 22, list(THEME_STYLES.keys())
        assert WARNINGS == [], WARNINGS
        pack_ids = {p["id"] for p in PACKS}
        assert pack_ids == {"classic", "flyer", "burger", "seafood",
                            "game_day", "seasonal"}, pack_ids

    def test_each_pack_carries_expected_theme_count(self):
        from theme_packs import PACKS
        by_id = {p["id"]: p for p in PACKS}
        assert len(by_id["classic"]["theme_ids"]) == 5
        assert len(by_id["flyer"]["theme_ids"]) == 5
        for pid in ("burger", "seafood", "game_day", "seasonal"):
            assert len(by_id[pid]["theme_ids"]) == 3, pid

    def test_theme_meta_is_attached_per_theme(self):
        from theme_packs import THEME_META
        for tid in ("luxury", "comic_pop", "burger_classic",
                    "seafood_coastal", "game_day_scoreboard", "mardi_gras"):
            assert tid in THEME_META, tid
            m = THEME_META[tid]
            assert m["pack"], (tid, m)
            assert m["pack_label"], (tid, m)
            assert m["best_use"], (tid, m)

    def test_no_duplicate_theme_ids_across_packs(self):
        from theme_packs import _PACK_MODULES
        seen = set()
        for mod in _PACK_MODULES:
            for tid in mod.THEMES:
                assert tid not in seen, f"duplicate {tid} in {mod.__name__}"
                seen.add(tid)

    def test_validator_rejects_missing_required_keys(self):
        from theme_packs import _validate_theme
        ok, why = _validate_theme("x", {"label": "x"})
        assert not ok
        assert "bg_color" in why or "missing" in why

    def test_validator_rejects_invalid_color(self):
        from theme_packs import _validate_theme
        spec = {
            "bg_color": (300, 0, 0),  # 300 > 255
            "title": {"font": "x", "color": (0, 0, 0)},
            "body":  {"font": "x", "color": (0, 0, 0)},
            "price": {},
            "branding_color": (0, 0, 0),
        }
        ok, why = _validate_theme("x", spec)
        assert not ok and "bg_color" in why

    def test_validator_accepts_valid_theme(self):
        from theme_packs import _validate_theme
        spec = {
            "bg_color": (10, 20, 30),
            "title": {"font": "x", "color": (0, 0, 0)},
            "body":  {"font": "x", "color": (0, 0, 0)},
            "price": {},
            "branding_color": (255, 255, 255),
        }
        ok, why = _validate_theme("x", spec)
        assert ok, why

    def test_router_re_exports_theme_styles(self):
        """The legacy test suite and frontend integrations import
        THEME_STYLES from routers.ai_designer. Must remain available."""
        from routers import ai_designer
        importlib.reload(ai_designer)  # ensure fresh
        assert "burger_classic" in ai_designer.THEME_STYLES
        assert "luxury" in ai_designer.THEME_STYLES
        assert len(ai_designer.THEME_STYLES) == 22


class TestThemesEndpoint:
    def test_themes_payload_shape(self, token):
        r = requests.get(
            f"{BASE_URL}/api/ai-designer/themes",
            headers=_h(token), timeout=10,
        )
        assert r.status_code == 200
        body = r.json()
        assert "themes" in body and "packs" in body
        assert body["variations_per_run"] == 3
        assert len(body["themes"]) == 22
        assert len(body["packs"]) == 6

    def test_backward_compatible_fields_present(self, token):
        """id, label, preview_color must still exist on every theme entry."""
        r = requests.get(
            f"{BASE_URL}/api/ai-designer/themes",
            headers=_h(token), timeout=10,
        )
        for t in r.json()["themes"]:
            assert "id" in t and "label" in t and "preview_color" in t
            assert t["preview_color"].startswith("#") and len(t["preview_color"]) == 7

    def test_new_metadata_fields_present(self, token):
        r = requests.get(
            f"{BASE_URL}/api/ai-designer/themes",
            headers=_h(token), timeout=10,
        )
        for t in r.json()["themes"]:
            for k in ("pack", "pack_label", "category", "best_use"):
                assert k in t, (t["id"], k)

    def test_all_22_themes_listed(self, token):
        r = requests.get(
            f"{BASE_URL}/api/ai-designer/themes",
            headers=_h(token), timeout=10,
        )
        ids = {t["id"] for t in r.json()["themes"]}
        expected = {
            # classic
            "luxury", "vintage", "modern", "social", "cajun",
            # flyer
            "comic_pop", "vintage_diner", "bold_purple_pop",
            "casual_teal", "distressed_orange",
            # burger
            "burger_classic", "burger_neon_diner", "burger_grill_smoke",
            # seafood
            "seafood_coastal", "seafood_lagoon", "seafood_dockside",
            # game day
            "game_day_scoreboard", "game_day_tailgate", "game_day_locker",
            # seasonal
            "mardi_gras", "summer_splash", "holiday_cheer",
        }
        assert ids == expected, ids - expected or expected - ids

    def test_packs_grouped_with_theme_ids(self, token):
        r = requests.get(
            f"{BASE_URL}/api/ai-designer/themes",
            headers=_h(token), timeout=10,
        )
        by_id = {p["id"]: p for p in r.json()["packs"]}
        assert "burger_classic" in by_id["burger"]["theme_ids"]
        assert "seafood_coastal" in by_id["seafood"]["theme_ids"]
        assert "game_day_scoreboard" in by_id["game_day"]["theme_ids"]
        assert "mardi_gras" in by_id["seasonal"]["theme_ids"]


class TestNewThemesRenderEndToEnd:
    """One representative theme per new pack must complete a full job."""

    @pytest.mark.parametrize("theme", [
        "burger_classic",
        "seafood_coastal",
        "game_day_scoreboard",
        "mardi_gras",
        # Plus one extra per pack to catch background_fn issues
        "burger_grill_smoke",
        "seafood_dockside",
        "game_day_tailgate",
        "holiday_cheer",
        # And the third variants of two packs
        "burger_neon_diner",
        "seafood_lagoon",
        "game_day_locker",
        "summer_splash",
    ])
    def test_new_theme_completes(self, token, source_asset_id, theme):
        r = requests.post(
            f"{BASE_URL}/api/ai-designer/generate",
            headers=_h(token),
            json={
                "source_asset_id": source_asset_id,
                "item_name": "Smoke Test",
                "features": ["A", "B"],
                "price": "$9.99",
                "theme": theme,
                "auto_copy": False,
                "remove_background": False,
            },
            timeout=30,
        )
        assert r.status_code == 202, r.text[:300]
        jid = r.json()["job_id"]
        deadline = time.time() + 45
        while time.time() < deadline:
            d = requests.get(
                f"{BASE_URL}/api/ai-designer/job/{jid}",
                headers=_h(token), timeout=10,
            ).json()
            if d.get("status") in ("completed", "failed"):
                assert d["status"] == "completed", (theme, d.get("error"))
                assert len(d["variations"]) == 3
                for v in d["variations"]:
                    assert v["status"] == "completed", (theme, v)
                return
            time.sleep(2)
        pytest.fail(f"theme {theme} did not complete in 45s")


class TestPilBackgroundDispatch:
    """Theme packs that ship a `background_fn` must be dispatched to it
    (i.e. legacy if/elif branches are bypassed)."""

    def test_background_fn_dispatched_for_new_themes(self):
        from routers.ai_designer import _pil_background, THEME_STYLES
        # Every new-pack theme must declare background_fn
        for tid in ("burger_classic", "seafood_coastal", "game_day_scoreboard",
                    "mardi_gras", "summer_splash", "holiday_cheer"):
            assert callable(THEME_STYLES[tid].get("background_fn")), tid
        # And produce valid PNG bytes
        b = _pil_background("burger_classic", 0)
        assert b.startswith(b"\x89PNG"), "not a PNG"

    def test_legacy_themes_have_no_background_fn(self):
        from routers.ai_designer import THEME_STYLES
        for tid in ("luxury", "vintage", "modern", "social", "cajun",
                    "comic_pop", "vintage_diner", "bold_purple_pop",
                    "casual_teal", "distressed_orange"):
            assert THEME_STYLES[tid].get("background_fn") is None, tid
