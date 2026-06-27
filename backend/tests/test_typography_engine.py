"""Sprint 16I — Premium typography & badge engine regression."""
import hashlib
import sys

import pytest
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, "/app/backend")


class TestSplitTitleLines:
    def test_single_word_stays(self):
        from typography_engine import split_title_lines
        assert split_title_lines("Burger") == ["Burger"]

    def test_two_words_stack(self):
        from typography_engine import split_title_lines
        assert split_title_lines("Smash Burger") == ["Smash", "Burger"]

    def test_three_words_split_1_plus_2(self):
        from typography_engine import split_title_lines
        assert split_title_lines("Shrimp Po Boy") == ["Shrimp", "Po Boy"]

    def test_four_words_left_alone(self):
        from typography_engine import split_title_lines
        out = split_title_lines("Cheese Bacon Burger Deluxe")
        assert out == ["Cheese Bacon Burger Deluxe"]


class TestBadgeStyles:
    def test_pick_badge_style_returns_known(self):
        from typography_engine import pick_badge_style, BADGE_STYLES
        for theme in ("luxury", "burger_classic", "seafood_coastal"):
            for v in (0, 1, 2):
                assert pick_badge_style(theme, v) in BADGE_STYLES

    def test_pick_badge_style_deterministic(self):
        from typography_engine import pick_badge_style
        assert pick_badge_style("burger_classic", 1) == pick_badge_style("burger_classic", 1)

    def test_variants_pick_different_badges_for_at_least_one_theme(self):
        from typography_engine import pick_badge_style
        any_diff = False
        for theme in ("luxury", "burger_classic", "seafood_coastal",
                      "game_day_scoreboard", "mardi_gras"):
            styles = {pick_badge_style(theme, v) for v in (0, 1, 2)}
            if len(styles) > 1:
                any_diff = True
                break
        assert any_diff, "no theme has variant-diverse badges"

    def test_all_six_styles_render_without_raising(self):
        from typography_engine import draw_premium_badge, BADGE_STYLES
        import random as r
        font = ImageFont.load_default()
        for style in BADGE_STYLES:
            canvas = Image.new("RGBA", (300, 300), (40, 40, 40, 255))
            draw_premium_badge(
                canvas, cx=150, cy=150, radius=80,
                price_text="$14.50",
                bg=(252, 220, 60, 255), fg=(20, 20, 20),
                ring=(255, 255, 255, 255),
                font=font, style=style, rng=r.Random(0),
            )
            assert canvas.size == (300, 300)


class TestPillChips:
    def test_renders_and_returns_y_advance(self):
        from typography_engine import draw_pill_chips
        font = ImageFont.load_default()
        canvas = Image.new("RGBA", (800, 200), (0, 0, 0, 255))
        y_after = draw_pill_chips(
            canvas, ["Two patties", "American cheese", "Pickles"],
            x=20, y=40, max_w=760,
            bg=(255, 200, 60), fg=(20, 20, 20), font=font,
        )
        assert y_after > 40, "chips did not advance y"

    def test_empty_features_returns_y_unchanged(self):
        from typography_engine import draw_pill_chips
        font = ImageFont.load_default()
        canvas = Image.new("RGBA", (800, 200), (0, 0, 0, 255))
        y = draw_pill_chips(canvas, [], x=20, y=40, max_w=760,
                            bg=(255, 200, 60), fg=(20, 20, 20), font=font)
        assert y == 40


class TestEndToEnd:
    """End-to-end render smoke tests.

    Sprint 16H originally asserted "3 distinct PNGs per dish across
    centered/asym_left/stacked layouts". Sprint 18 (iterative
    compose_layered_with_score) and Sprint 20 (agency template + HTML
    renderer dispatch) shifted that contract: templated themes now emit
    a single canonical render and even the procedural path converges
    after the scorer picks the best layout. The contract guarded here
    is therefore "renders a valid PNG without crashing" — variant
    differentiation lives in `theme_packs.overlay_fn` (covered by
    test_overlays.py) and `agency_renderer` (covered by
    test_agency_templates.py).
    """

    @pytest.mark.parametrize("item,theme,photo", [
        ("Smash Burger",  "burger_classic",      "/app/memory/launch/assets/wings-source.jpg"),
        ("Café Fries",    "distressed_orange",   "/app/memory/launch/assets/cafe-fries-source.jpg"),
        ("Wings",         "game_day_scoreboard", "/app/memory/launch/assets/wings-source.jpg"),
    ])
    def test_dish_renders_valid_png(self, item, theme, photo):
        from routers.ai_designer import _compose_design, _pil_background, _prepare_food_cutout
        with open(photo, "rb") as f:
            food_bytes = f.read()
        food_rgba = _prepare_food_cutout(food_bytes, target_max=500, use_rembg=False)
        for v_idx, layout in enumerate(["centered", "asym_left", "stacked"]):
            bg = _pil_background(theme, v_idx)
            result = _compose_design(bg, food_rgba.copy(), item,
                                     ["Two patties", "American cheese", "Pickles"],
                                     "$14.50", theme, layout)
            out = result[0] if isinstance(result, tuple) else result
            assert out[:8] == b"\x89PNG\r\n\x1a\n"

    @pytest.mark.slow  # html_renderer (Playwright) — sandbox-incompatible
    @pytest.mark.parametrize("item,theme,photo", [
        ("Shrimp Po-Boy", "seafood_coastal",     "/app/memory/launch/assets/shrimp-poboy-source.jpg"),
        ("Oyster Plate",  "seafood_lagoon",      "/app/memory/launch/assets/oyster-plate-source.jpg"),
    ])
    def test_seafood_html_smoke(self, item, theme, photo):
        from routers.ai_designer import _compose_design, _pil_background, _prepare_food_cutout
        with open(photo, "rb") as f:
            food_bytes = f.read()
        food_rgba = _prepare_food_cutout(food_bytes, target_max=500, use_rembg=False)
        for v_idx, layout in enumerate(["centered", "asym_left", "stacked"]):
            bg = _pil_background(theme, v_idx)
            result = _compose_design(bg, food_rgba.copy(), item,
                                     ["Two patties", "American cheese", "Pickles"],
                                     "$14.50", theme, layout)
            out = result[0] if isinstance(result, tuple) else result
            assert out[:8] == b"\x89PNG\r\n\x1a\n"
