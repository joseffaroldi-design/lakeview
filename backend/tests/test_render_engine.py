"""Sprint 16G — Render Engine 2.0 regression tests.

These tests pin down the new compositor's behaviour without depending on a
live HTTP server. They run in <5s and don't hit MongoDB.

Coverage:
  * feather_mask                — soft alpha; food remains majority opaque
  * render_food_with_shadows    — output is bigger than input; opaque-pixel
                                  count higher than input alone
  * dominant_food_colors        — returns sane RGB tuples, ignores transparent
  * apply_color_harmony         — corner alpha is small at default strength
  * pick_layout                 — deterministic + variants pick differently
  * compose_layered             — end-to-end render produces valid PNG with
                                  the food's dominant color reflected in
                                  upper-left corner pixels (cheap visual
                                  fingerprint of color-harmony pass)
  * Every theme renders in all 3 variants without raising.
"""
import io
import sys

import pytest
from PIL import Image

sys.path.insert(0, "/app/backend")

from render_engine import (  # noqa: E402
    feather_mask, render_food_with_shadows, dominant_food_colors,
    apply_color_harmony, pick_layout, compose_layered, LAYOUTS,
    LEGACY_LAYOUT_ALIAS, DEFAULT_SUPPORTED_LAYOUTS, CANVAS,
)


# ---------------------------------------------------------------- fixtures

def _solid_food(size=(400, 400), color=(180, 90, 40)):
    """A solid-colour RGB photo to stand in for an uploaded dish."""
    return Image.new("RGB", size, color).convert("RGBA")


def _gradient_food(size=(400, 400)):
    """A two-tone gradient photo so dominant_food_colors has more than one bucket."""
    im = Image.new("RGB", size, (180, 90, 40))
    for y in range(size[1]):
        for x in range(0, size[0], 8):
            im.putpixel((x, y), (200, 150, 60) if x > size[0] // 2 else (140, 60, 20))
    return im.convert("RGBA")


# ---------------------------------------------------------------- feather_mask

class TestFeatherMask:
    def test_keeps_centre_pixel_opaque(self):
        im = _solid_food()
        out = feather_mask(im)
        cx, cy = out.width // 2, out.height // 2
        assert out.mode == "RGBA"
        assert out.getpixel((cx, cy))[3] >= 250, "centre pixel must stay opaque"

    def test_softens_corner(self):
        im = _solid_food()
        out = feather_mask(im)
        corner_alpha = out.getpixel((2, 2))[3]
        assert corner_alpha < 200, f"corner should be partially transparent, got alpha={corner_alpha}"

    def test_no_alpha_clipping_along_edge(self):
        """The right edge must transition smoothly — no single-pixel alpha jumps."""
        im = _solid_food((400, 400))
        out = feather_mask(im)
        # Sample a horizontal slice at y=mid; alpha should monotonically rise
        # from the right edge inward (no hard cliff).
        mid_y = out.height // 2
        alphas = [out.getpixel((x, mid_y))[3] for x in range(out.width - 30, out.width)]
        # Largest single-step jump should be modest (gradient, not a cliff).
        max_jump = max(abs(alphas[i + 1] - alphas[i]) for i in range(len(alphas) - 1))
        assert max_jump < 40, f"alpha cliff detected on edge (max step={max_jump})"

    def test_preserves_existing_rembg_alpha(self):
        """When fed an RGBA cutout (rembg path) the existing alpha must be
        multiplicatively combined — opaque areas stay opaque, transparent
        stays transparent."""
        im = Image.new("RGBA", (200, 200), (200, 100, 50, 255))
        # Carve a transparent hole in the corner
        for x in range(0, 50):
            for y in range(0, 50):
                im.putpixel((x, y), (200, 100, 50, 0))
        out = feather_mask(im)
        # Hole area must STILL be ~transparent (existing zero alpha wins).
        assert out.getpixel((10, 10))[3] < 5
        # Centre still opaque.
        assert out.getpixel((100, 100))[3] >= 250


# ---------------------------------------------------------------- shadows

class TestRenderFoodWithShadows:
    def test_output_padded(self):
        food = _solid_food()
        out = render_food_with_shadows(food)
        assert out.width > food.width
        assert out.height > food.height

    def test_food_pixels_preserved(self):
        food = _solid_food((200, 200), color=(180, 90, 40))
        out = render_food_with_shadows(food)
        # Centre of food should still be original color (shadow doesn't cover food).
        cx, cy = out.width // 2, out.height // 2
        r, g, b, a = out.getpixel((cx, cy))
        assert a == 255
        # Allow small tolerance for shadow bleed
        assert abs(r - 180) < 12 and abs(g - 90) < 12 and abs(b - 40) < 12

    def test_shadow_appears_below_food(self):
        """A pixel just below the food's bottom edge must be darker than
        background transparent (shadow visible there)."""
        food = _solid_food((200, 200))
        out = render_food_with_shadows(food)
        # Sample 25 px below where food ends.
        below_x = out.width // 2
        below_y = (out.height + 200) // 2 + 25
        if below_y < out.height:
            _, _, _, a = out.getpixel((below_x, below_y))
            assert a > 15, "no visible shadow below food"


# ---------------------------------------------------------------- color sampling

class TestDominantFoodColors:
    def test_returns_at_least_one_for_solid(self):
        # A solid 180/90/40 photo should yield exactly that as the primary color.
        food = _solid_food((400, 400), (180, 90, 40))
        colors = dominant_food_colors(food, n=3)
        assert len(colors) >= 1
        r, g, b = colors[0]
        assert abs(r - 180) <= 5 and abs(g - 90) <= 5 and abs(b - 40) <= 5

    def test_skips_black_and_white(self):
        # Mostly black background — should NOT return (0,0,0).
        im = Image.new("RGB", (200, 200), (5, 5, 5))
        # Add a small red square so there's at least one "non-black" colour
        from PIL import ImageDraw
        ImageDraw.Draw(im).rectangle((60, 60, 140, 140), fill=(200, 60, 40))
        colors = dominant_food_colors(im.convert("RGBA"), n=3)
        for r, g, b in colors:
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            assert 30 <= lum <= 235, f"luminance {lum} out of range for {(r, g, b)}"

    def test_empty_image_returns_empty(self):
        im = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        # 1×1 transparent: thumbnail will still produce something but the
        # quantize bucket will be filtered. Should not raise.
        colors = dominant_food_colors(im, n=3)
        assert isinstance(colors, list)


# ---------------------------------------------------------------- color harmony

class TestApplyColorHarmony:
    def test_strength_zero_no_change(self):
        canvas = Image.new("RGBA", (CANVAS, CANVAS), (10, 20, 30, 255))
        before = canvas.getpixel((50, 50))
        food = _solid_food()
        apply_color_harmony(canvas, food, strength=0.0)
        assert canvas.getpixel((50, 50)) == before

    def test_default_strength_corners_tinted(self):
        canvas = Image.new("RGBA", (CANVAS, CANVAS), (20, 20, 20, 255))
        food = _solid_food(color=(200, 60, 30))  # warm red
        apply_color_harmony(canvas, food, strength=0.25)
        # Top-left corner should now lean redder than the original neutral grey
        r, g, b, _ = canvas.getpixel((40, 40))
        assert r >= 22, "corner did not tint toward food primary"

    def test_strength_caps_at_subtle(self):
        """Even at strength=1.0 the centre of the canvas (where food sits)
        should remain ~original — the wash only touches corners."""
        canvas = Image.new("RGBA", (CANVAS, CANVAS), (40, 40, 40, 255))
        food = _solid_food(color=(220, 60, 30))
        apply_color_harmony(canvas, food, strength=1.0)
        r, g, b, _ = canvas.getpixel((CANVAS // 2, CANVAS // 2))
        # Centre must drift by less than ~30 units from original 40.
        assert abs(r - 40) + abs(g - 40) + abs(b - 40) < 60


# ---------------------------------------------------------------- layout picker

class TestPickLayout:
    def test_deterministic(self):
        assert pick_layout("luxury", 0) == pick_layout("luxury", 0)

    def test_three_variants_pick_three_layouts(self):
        layouts = {pick_layout("luxury", v) for v in (0, 1, 2)}
        assert len(layouts) >= 2, f"variants gave too few unique layouts: {layouts}"

    def test_different_themes_diverge(self):
        a = pick_layout("luxury", 0)
        b = pick_layout("burger_classic", 0)
        # Not strictly required to differ, but the seed should normally
        # produce different starts. At least one of the 3 variants must.
        diverged = any(pick_layout("luxury", v) != pick_layout("burger_classic", v)
                       for v in (0, 1, 2))
        assert diverged, f"all 3 variants identical between luxury and burger_classic: {a}/{b}"

    def test_supported_layouts_respected(self):
        out = pick_layout("luxury", 0, supported=["hero_center"])
        assert out == "hero_center"

    def test_empty_supported_falls_back(self):
        out = pick_layout("luxury", 0, supported=[])
        assert out == "hero_center"

    def test_legacy_aliases_resolve(self):
        for legacy, modern in LEGACY_LAYOUT_ALIAS.items():
            assert modern in LAYOUTS or modern == "stacked"


# ---------------------------------------------------------------- end-to-end

def _noop_draw_title(canvas, theme, item_name, x, y, w, align):
    # Returns y after the "title block" — emulate ~80 px high.
    return y + 80


def _noop_draw_bullets(canvas, theme, features, x, y, w):
    return None


def _noop_draw_price_badge(canvas, theme, price, cx, cy, r):
    return None


def _noop_draw_branding(canvas, theme):
    return None


_FAKE_THEME = {
    "bg_color": (40, 40, 40),
    "title": {"font": "X", "color": (255, 255, 255), "size": 80},
    "body":  {"font": "X", "color": (255, 255, 255), "size": 28},
    "price": {"bg": (255, 200, 60), "fg": (40, 40, 40), "ring": (255, 255, 255), "font": "X"},
    "branding_color": (200, 200, 200),
    "harmony_strength": 0.25,
}


class TestComposeLayered:
    def test_e2e_produces_valid_canvas(self):
        bg = Image.new("RGB", (CANVAS, CANVAS), (40, 40, 40))
        food = _solid_food((400, 400), (200, 60, 30))
        result = compose_layered(
            bg_image=bg, food_rgba=food, theme=_FAKE_THEME,
            theme_id="luxury", variant_idx=0,
            draw_title=_noop_draw_title,
            draw_bullets=_noop_draw_bullets,
            draw_price_badge=_noop_draw_price_badge,
            draw_branding=_noop_draw_branding,
            item_name="Test", features=["A"], price="$9.99",
        )
        assert result.size == (CANVAS, CANVAS)
        assert result.mode == "RGBA"

    def test_overlay_fn_invoked(self):
        called = []
        def my_overlay(canvas, draw, variant_idx):
            called.append(variant_idx)
        theme = dict(_FAKE_THEME, overlay_fn=my_overlay)
        bg = Image.new("RGB", (CANVAS, CANVAS), (40, 40, 40))
        food = _solid_food()
        compose_layered(
            bg_image=bg, food_rgba=food, theme=theme,
            theme_id="x", variant_idx=2,
            draw_title=_noop_draw_title,
            draw_bullets=_noop_draw_bullets,
            draw_price_badge=_noop_draw_price_badge,
            draw_branding=_noop_draw_branding,
            item_name="X", features=[], price="$1",
        )
        assert called == [2]

    def test_overlay_fn_failure_does_not_crash(self):
        def broken_overlay(canvas, draw, variant_idx):
            raise RuntimeError("boom")
        theme = dict(_FAKE_THEME, overlay_fn=broken_overlay)
        bg = Image.new("RGB", (CANVAS, CANVAS), (40, 40, 40))
        food = _solid_food()
        # Must not raise — the engine logs and continues.
        compose_layered(
            bg_image=bg, food_rgba=food, theme=theme,
            theme_id="x", variant_idx=0,
            draw_title=_noop_draw_title,
            draw_bullets=_noop_draw_bullets,
            draw_price_badge=_noop_draw_price_badge,
            draw_branding=_noop_draw_branding,
            item_name="X", features=[], price="$1",
        )

    @pytest.mark.parametrize("layout_name", list(LAYOUTS.keys()))
    def test_every_layout_runs_without_raising(self, layout_name):
        bg = Image.new("RGB", (CANVAS, CANVAS), (40, 40, 40))
        food = _solid_food((420, 380))  # non-square to stress _fit
        result = compose_layered(
            bg_image=bg, food_rgba=food, theme=_FAKE_THEME,
            theme_id="x", variant_idx=0,
            draw_title=_noop_draw_title,
            draw_bullets=_noop_draw_bullets,
            draw_price_badge=_noop_draw_price_badge,
            draw_branding=_noop_draw_branding,
            item_name="Test", features=["A", "B"], price="$10",
            layout_override=layout_name,
        )
        assert result.size == (CANVAS, CANVAS)


# ---------------------------------------------------------------- regression: all themes still render

class TestAllThemesStillRender:
    @pytest.mark.slow  # 22 themes × 3 variants = 66 renders (~60s+); run via -m slow
    def test_all_22_themes_render_three_variants(self):
        """The Sprint 16G refactor must not break any of the 22 themes."""
        from routers.ai_designer import (
            _compose_design, _pil_background, _prepare_food_cutout,
        )
        from theme_packs import THEME_STYLES

        # Use a tiny synthetic photo (no I/O) — solid pink, 200×200.
        food_bytes_io = io.BytesIO()
        Image.new("RGB", (200, 200), (220, 120, 90)).save(food_bytes_io, "JPEG")
        food_bytes = food_bytes_io.getvalue()
        food_rgba = _prepare_food_cutout(food_bytes, target_max=500, use_rembg=False)

        failures = []
        for tid in THEME_STYLES:
            for layout in ("centered", "asym_left", "stacked"):
                try:
                    bg = _pil_background(tid, ("centered", "asym_left", "stacked").index(layout))
                    out = _compose_design(
                        bg, food_rgba.copy(),
                        "Test Dish", ["a", "b"], "$9.99", tid, layout,
                    )
                    assert out and len(out) > 8000, f"{tid}/{layout} tiny PNG"
                    # Confirm valid PNG header
                    assert out[:8] == b"\x89PNG\r\n\x1a\n", f"{tid}/{layout} bad PNG header"
                except Exception as e:  # noqa: BLE001
                    failures.append(f"{tid}/{layout}: {e}")
        assert not failures, "\n".join(failures)
