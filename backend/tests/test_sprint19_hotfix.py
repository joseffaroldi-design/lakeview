"""Sprint 19 hotfix — Composition quality regressions.

Locks in the global flyer-quality fixes:
  1. Food scale boosted via _scale_up_to_target — every layout makes the
     food at least ~70% of canvas (was ~50%).
  2. Every flyer has a filled badge background even if the badge style
     itself only draws an outline (distressed_stamp regression).
  3. Foreground overlays are composited at 45% opacity (max), so waves /
     smoke / confetti never dominate the hero.
"""
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from render_engine import (  # noqa: E402
    CANVAS,
    LAYOUTS,
    _scale_up_to_target,
)


def _make_food(w=480, h=720):
    """A tall portrait sandwich-ish RGBA."""
    img = Image.new("RGBA", (w, h), (210, 140, 80, 255))
    return img


def test_scale_up_actually_scales():
    src = Image.new("RGBA", (200, 300), (200, 200, 200, 255))
    out = _scale_up_to_target(src, max_w=1024, max_h=900, target_frac=0.9)
    # The larger dimension should now be close to 900 * 0.9 = 810
    assert max(out.size) >= 800, f"got {out.size}"


def test_scale_up_no_op_when_already_big():
    src = Image.new("RGBA", (900, 800), (200, 200, 200, 255))
    out = _scale_up_to_target(src, max_w=1024, max_h=900, target_frac=0.9)
    assert out.size == (900, 800)


@pytest.mark.parametrize("layout_name", list(LAYOUTS.keys()))
def test_every_layout_makes_food_at_least_60pct_of_smaller_axis(layout_name):
    food = _make_food()
    spec = LAYOUTS[layout_name](food)
    placed = spec["food"]
    # The food's larger dimension should be >= 60% of the canvas
    assert max(placed.size) >= int(CANVAS * 0.60), \
        f"{layout_name} food too small: {placed.size} (canvas={CANVAS})"


def test_every_layout_yields_valid_food_pos():
    food = _make_food()
    for name, fn in LAYOUTS.items():
        spec = fn(food)
        fx, fy = spec["food_pos"]
        # Food may bleed slightly off canvas but its centre must be on it.
        cx = fx + spec["food"].width // 2
        cy = fy + spec["food"].height // 2
        assert 0 <= cx <= CANVAS, f"{name} food centre off canvas: {cx}"
        assert 0 <= cy <= CANVAS, f"{name} food centre off canvas: {cy}"


def test_compose_once_emits_filled_badge_for_outline_only_style():
    """Even with badge_style='distressed_stamp' (outline-only), the
    composited canvas must have a non-transparent disc at the badge centre.
    """
    from render_engine import _compose_once

    bg = Image.new("RGB", (CANVAS, CANVAS), (40, 50, 70))
    food = Image.new("RGBA", (CANVAS // 2, CANVAS // 2), (200, 140, 80, 255))
    theme = {
        "label": "T", "bg_color": (40, 50, 70),
        "title": {"font": "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
                  "size": 90, "color": (245, 240, 230)},
        "bullets": {"font": "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                    "size": 22, "color": (245, 240, 230)},
        "branding_color": (200, 200, 200),
        "badge_bg": (220, 70, 50),
        "badge_fg": (255, 255, 255),
        "badge_ring": (255, 220, 100),
        "_badge_style": "distressed_stamp",
        "personality": {
            "tone": "elegant", "texture": 0.2, "type_weight": "regular",
            "saturation": 0.5, "badge_pool": ["distressed_stamp"],
            "allow_overlap": False, "title_oversize": 1.0,
            "backdrop_pool": ["none"],
        },
    }

    def draw_title(canvas, theme, name, x, y, w, align):
        return y + 100

    def draw_bullets(canvas, theme, feats, x, y, w):
        return None

    def draw_branding(canvas, theme):
        return None

    def draw_price_badge(canvas, theme, price, cx, cy, r):
        # Simulate distressed_stamp — only outline. The base filled disc
        # painted by _compose_once must still be visible underneath.
        from PIL import ImageDraw
        d = ImageDraw.Draw(canvas)
        d.rectangle((cx - r, cy - r, cx + r, cy + r),
                    outline=(255, 255, 255, 255), width=4)

    canvas, info, _ = _compose_once(
        bg_image=bg, food_rgba=food, theme=theme, theme_id="t1",
        variant_idx=0, draw_title=draw_title, draw_bullets=draw_bullets,
        draw_price_badge=draw_price_badge, draw_branding=draw_branding,
        item_name="Cuban", features=["ham", "pork"], price="$12.00",
    )
    # Sample the pixel exactly at the badge centre — must NOT be the bg colour.
    bx, by = info.badge_centre
    px = canvas.convert("RGB").getpixel((bx, by))
    bg_rgb = (40, 50, 70)
    # The filled badge disc should have replaced the background — check it's
    # appreciably different from the bg.
    diff = sum(abs(a - b) for a, b in zip(px, bg_rgb))
    assert diff > 50, \
        f"badge centre still shows bg pixel — fill missing. px={px}"


def test_overlay_alpha_capped_in_compose_once():
    """The overlay alpha multiplier should be applied — verify the overlay
    layer's max alpha can never exceed ~45% of the original."""
    from render_engine import _compose_once
    captured = {}

    def fake_overlay(canvas, draw, variant_idx):
        # Fill a 100x100 patch in opaque red. Compose_once must fade it.
        from PIL import ImageDraw
        d = ImageDraw.Draw(canvas)
        d.rectangle((40, 40, 140, 140), fill=(255, 0, 0, 255))
        captured["called"] = True

    bg = Image.new("RGB", (CANVAS, CANVAS), (40, 50, 70))
    food = Image.new("RGBA", (CANVAS // 2, CANVAS // 2), (200, 140, 80, 255))
    theme = {
        "label": "T", "bg_color": (40, 50, 70),
        "overlay_fn": fake_overlay,
        "title": {"font": "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
                  "size": 90, "color": (245, 240, 230)},
        "bullets": {"font": "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                    "size": 22, "color": (245, 240, 230)},
        "branding_color": (200, 200, 200),
        "badge_bg": (220, 70, 50),
        "badge_fg": (255, 255, 255),
        "badge_ring": (255, 220, 100),
        "personality": {
            "tone": "elegant", "texture": 0.2, "type_weight": "regular",
            "saturation": 0.5, "badge_pool": ["sticker"],
            "allow_overlap": False, "title_oversize": 1.0,
            "backdrop_pool": ["none"],
        },
    }

    def dt(c, t, n, x, y, w, a): return y + 100
    def db(c, t, f, x, y, w): return None
    def dpb(c, t, p, cx, cy, r): return None
    def dbd(c, t): return None

    canvas, _info, _ = _compose_once(
        bg_image=bg, food_rgba=food, theme=theme, theme_id="t1",
        variant_idx=0, draw_title=dt, draw_bullets=db,
        draw_price_badge=dpb, draw_branding=dbd,
        item_name="X", features=[], price="$5",
    )
    assert captured.get("called")
    # The overlay's red rectangle is fully opaque in fake_overlay; after the
    # fade the canvas at that pixel should be a BLEND, never the pure
    # background and never pure red. Sample (90, 90) which is well inside.
    px = canvas.convert("RGB").getpixel((90, 90))
    r, g, b = px
    # Pure red would be (255, 0, 0); fading to 45% blends towards the bg.
    # We just check the pixel is neither bg nor pure red.
    assert r > 80 and r < 240, f"overlay alpha not faded enough: px={px}"
