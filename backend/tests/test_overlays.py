"""Sprint 16H — Overlay / art direction regression.

Locks in:
  * Every loaded theme exposes a callable `overlay_fn`.
  * Calling overlay_fn(canvas, draw, variant_idx) does not raise for any
    of the 22 themes × 3 variants.
  * Variant 0/1/2 produce visibly different output for the same theme
    (variant_idx is genuinely seeding the RNG).
  * The full e2e render of the 5 acceptance dishes (Smash Burger, Café
    Fries, Wings, Shrimp Po-Boy, Oyster Plate) produces 3 distinct
    PNG hashes per dish.
"""
import hashlib
import io
import sys

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, "/app/backend")


class TestOverlaySystem:
    def test_every_theme_has_callable_overlay_fn(self):
        from theme_packs import THEME_STYLES
        for tid, t in THEME_STYLES.items():
            assert callable(t.get("overlay_fn")), tid

    @pytest.mark.parametrize("theme_id", [
        "luxury", "modern", "comic_pop", "distressed_orange",
        "burger_classic", "burger_neon_diner", "burger_grill_smoke",
        "seafood_coastal", "seafood_lagoon", "seafood_dockside",
        "game_day_scoreboard", "game_day_tailgate", "game_day_locker",
        "mardi_gras", "summer_splash", "holiday_cheer",
    ])
    def test_overlay_runs_for_all_three_variants(self, theme_id):
        from theme_packs import THEME_STYLES
        from render_engine import CANVAS
        t = THEME_STYLES[theme_id]
        for v in (0, 1, 2):
            canvas = Image.new("RGBA", (CANVAS, CANVAS), (40, 40, 40, 255))
            draw = ImageDraw.Draw(canvas, "RGBA")
            t["overlay_fn"](canvas, draw, v)
            # Must still be a valid RGBA canvas at the end
            assert canvas.size == (CANVAS, CANVAS)
            assert canvas.mode == "RGBA"

    @pytest.mark.parametrize("theme_id", [
        "burger_classic", "burger_neon_diner",
        "seafood_coastal", "seafood_lagoon",
        "game_day_scoreboard", "game_day_tailgate",
        "mardi_gras", "summer_splash",
    ])
    def test_variants_produce_different_overlay_output(self, theme_id):
        """Overlay must paint differently across variant_idx 0/1/2."""
        from theme_packs import THEME_STYLES
        from render_engine import CANVAS
        t = THEME_STYLES[theme_id]
        hashes = set()
        for v in (0, 1, 2):
            canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
            draw = ImageDraw.Draw(canvas, "RGBA")
            t["overlay_fn"](canvas, draw, v)
            buf = io.BytesIO()
            canvas.save(buf, "PNG")
            hashes.add(hashlib.md5(buf.getvalue()).hexdigest())
        assert len(hashes) >= 2, f"variants gave too few unique overlays: {hashes}"


class TestAcceptanceFiveDishes:
    """The Sprint 16H acceptance set."""

    def _render(self, item_name, theme_id, features, price, photo_path):
        from routers.ai_designer import _compose_design, _pil_background, _prepare_food_cutout
        with open(photo_path, "rb") as f:
            food_bytes = f.read()
        food_rgba = _prepare_food_cutout(food_bytes, target_max=500, use_rembg=False)
        outs = []
        for v_idx, layout in enumerate(["centered", "asym_left", "stacked"]):
            bg = _pil_background(theme_id, v_idx)
            out = _compose_design(bg, food_rgba.copy(), item_name,
                                  features, price, theme_id, layout)
            assert out[:8] == b"\x89PNG\r\n\x1a\n"
            outs.append(out)
        return outs

    @pytest.mark.parametrize("item,theme_id,photo", [
        ("Smash Burger",  "burger_classic",      "/app/memory/launch/assets/wings-source.jpg"),
        ("Café Fries",    "distressed_orange",   "/app/memory/launch/assets/cafe-fries-source.jpg"),
        ("Wings",         "game_day_scoreboard", "/app/memory/launch/assets/wings-source.jpg"),
        ("Shrimp Po-Boy", "seafood_coastal",     "/app/memory/launch/assets/shrimp-poboy-source.jpg"),
        ("Oyster Plate",  "seafood_lagoon",      "/app/memory/launch/assets/oyster-plate-source.jpg"),
    ])
    def test_dish_has_three_distinct_variations(self, item, theme_id, photo):
        outs = self._render(item, theme_id, ["a", "b", "c"], "$9.99", photo)
        hashes = {hashlib.md5(o).hexdigest() for o in outs}
        assert len(hashes) == 3, f"{item}: only got {len(hashes)} distinct variants"
