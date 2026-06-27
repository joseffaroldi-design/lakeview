"""Burger pack — warm reds, yellows, browns; grill marks; bold price badges.

Each theme defines its own `background_fn(canvas, draw, variant_idx)` so
new themes can ship without touching the router's dispatch logic.
Primitives are lazy-imported from `routers.ai_designer` to avoid a
circular dependency at module load.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from ._shared import (
    CANVAS, FONT_BEBAS_NEUE, FONT_BUNGEE, FONT_PERMANENT_MARKER,
    FONT_SANS_BOLD,
)

PACK = {
    "id": "burger",
    "label": "Burger Joint",
    "category": "burger",
    "enabled": True,
    "description": "Diner-energy reds, grill-mark accents, hand-painted price badges.",
}


# ---------------------------------------------------------------- background renderers

def _bg_red_diner(canvas: Image.Image, draw: ImageDraw.ImageDraw, variant_idx: int) -> None:
    from routers.ai_designer import (
        _checker_strip, _star, _distressed_grain, _brush_stamp,
    )
    # Cream over deep red — classic diner energy
    canvas.paste(Image.new("RGB", canvas.size, (200, 30, 40)))
    _checker_strip(draw, (40, 25, 20), (252, 240, 215), y=0, h=44, square=44)
    _checker_strip(draw, (40, 25, 20), (252, 240, 215), y=CANVAS - 44, h=44, square=44)
    if variant_idx == 0:
        # Center cream panel
        draw.rounded_rectangle((90, 90, CANVAS - 90, CANVAS - 90), radius=20,
                               fill=(252, 240, 215), outline=(40, 25, 20, 230), width=5)
    elif variant_idx == 1:
        _brush_stamp(draw, (40, 25, 20, 230), x=80, y=80, w=CANVAS - 160, h=140)
        for cx, cy in [(150, CANVAS - 180), (CANVAS - 150, CANVAS - 180)]:
            _star(draw, (252, 220, 90, 240), cx=cx, cy=cy, r=26)
    else:
        _distressed_grain(canvas, (40, 25, 20, 30), density=1500)
        for cx, cy in [(160, 200), (CANVAS - 160, 200)]:
            _star(draw, (252, 220, 90, 240), cx=cx, cy=cy, r=24)


def _bg_neon_diner(canvas: Image.Image, draw: ImageDraw.ImageDraw, variant_idx: int) -> None:
    from routers.ai_designer import (
        _radial_gradient, _lightning_bolt, _halftone_dots, _star,
    )
    _radial_gradient(canvas, (28, 16, 10), (8, 4, 2), CANVAS // 2,
                     int(CANVAS * 0.5), int(CANVAS * 0.85))
    if variant_idx == 0:
        _lightning_bolt(draw, (255, 200, 60, 240), tip=(CANVAS - 80, 240), size=160)
        _halftone_dots(draw, (255, 60, 60, 200),
                       start_xy=(0, CANVAS - 400), end_xy=(400, CANVAS),
                       spacing=22, max_r=9)
    elif variant_idx == 1:
        # Neon glow border (concentric soft rounds)
        for inset, alpha in [(40, 70), (54, 110), (68, 160)]:
            draw.rounded_rectangle((inset, inset, CANVAS - inset, CANVAS - inset),
                                   radius=44, outline=(255, 60, 60, alpha), width=4)
        for cx, cy in [(140, 140), (CANVAS - 140, 140),
                       (140, CANVAS - 140), (CANVAS - 140, CANVAS - 140)]:
            _star(draw, (255, 200, 60, 240), cx=cx, cy=cy, r=18)
    else:
        # Diagonal yellow swoosh
        draw.polygon(
            [(0, CANVAS * 2 // 3), (CANVAS, CANVAS // 3),
             (CANVAS, CANVAS // 3 + 80), (0, CANVAS * 2 // 3 + 80)],
            fill=(255, 200, 60, 220),
        )
        _halftone_dots(draw, (255, 60, 60, 200),
                       start_xy=(CANVAS - 380, 0), end_xy=(CANVAS, 380),
                       spacing=22, max_r=9)


def _bg_grill_smoke(canvas: Image.Image, draw: ImageDraw.ImageDraw, variant_idx: int) -> None:
    from routers.ai_designer import (
        _radial_gradient, _distressed_grain, _brush_stamp, _olive_branch,
    )
    _radial_gradient(canvas, (70, 40, 20), (28, 14, 6), CANVAS // 2,
                     int(CANVAS * 0.55), int(CANVAS * 0.85))
    # Grill marks — diagonal char stripes top + bottom
    if variant_idx == 0:
        for i, y in enumerate(range(60, 220, 16)):
            draw.line((40 + i * 4, y, CANVAS - 40 - i * 4, y),
                      fill=(20, 12, 8, 200), width=4)
        for i, y in enumerate(range(CANVAS - 220, CANVAS - 60, 16)):
            draw.line((40 + i * 4, y, CANVAS - 40 - i * 4, y),
                      fill=(20, 12, 8, 200), width=4)
    elif variant_idx == 1:
        # Diagonal grill grid mid-canvas
        for x in range(-200, CANVAS + 200, 32):
            draw.line((x, 0, x + 400, CANVAS), fill=(20, 12, 8, 90), width=3)
        _brush_stamp(draw, (252, 220, 90, 230), x=60, y=CANVAS - 200,
                     w=CANVAS - 120, h=140)
    else:
        _distressed_grain(canvas, (252, 220, 90, 22), density=1800)
        # Wheat/herb sprigs in two corners
        _olive_branch(draw, (252, 220, 90, 200), x=80, y=CANVAS - 280, size=220)
        _olive_branch(draw, (252, 220, 90, 200), x=CANVAS - 280, y=120, size=200)


# ---------------------------------------------------------------- theme dicts

THEMES = {
    "burger_classic": {
        "label": "Burger Classic",
        "best_use": "Smash burgers, double stacks, Tuesday burger nights",
        "bg_color": (200, 30, 40),
        "title": {"font": FONT_BEBAS_NEUE, "color": (252, 220, 90), "size": 112,
                  "stroke_width": 4, "stroke_fill": (40, 25, 20),
                  "letter_spacing": 6, "shadow": (40, 25, 20, 200)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (40, 25, 20), "size": 34, "marker": "■",
                  "marker_color": (200, 30, 40), "letter_spacing": 3},
        "price": {"bg": (252, 220, 90), "fg": (40, 25, 20), "ring": (40, 25, 20), "font": FONT_BEBAS_NEUE},
        "branding_color": (40, 25, 20),
        "icons": True,
        "background_fn": _bg_red_diner,
    },
    "burger_neon_diner": {
        "label": "Neon Diner",
        "best_use": "Late-night burgers, pub combos, weekend specials",
        "bg_color": (18, 10, 6),
        "title": {"font": FONT_BUNGEE, "color": (255, 200, 60), "size": 108,
                  "stroke_width": 4, "stroke_fill": (18, 10, 6),
                  "letter_spacing": 4, "shadow": (255, 60, 60, 210)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (252, 240, 215), "size": 32, "marker": "▸",
                  "marker_color": (255, 200, 60), "letter_spacing": 2},
        "price": {"bg": (255, 60, 60), "fg": (252, 240, 215), "ring": (255, 200, 60), "font": FONT_BUNGEE},
        "branding_color": (255, 200, 60),
        "icons": True,
        "background_fn": _bg_neon_diner,
    },
    "burger_grill_smoke": {
        "label": "Grill & Smoke",
        "best_use": "Grilled burgers, BBQ smash, smokehouse menu",
        "bg_color": (48, 28, 16),
        "title": {"font": FONT_PERMANENT_MARKER, "color": (252, 220, 90), "size": 104,
                  "stroke_width": 3, "stroke_fill": (28, 14, 6),
                  "letter_spacing": 2, "shadow": (28, 14, 6, 220)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (252, 240, 215), "size": 32, "marker": "★",
                  "marker_color": (252, 220, 90), "letter_spacing": 2},
        "price": {"bg": (252, 220, 90), "fg": (28, 14, 6), "ring": (200, 60, 40), "font": FONT_PERMANENT_MARKER},
        "branding_color": (252, 220, 90),
        "icons": True,
        "background_fn": _bg_grill_smoke,
    },
}

# Sprint 16H — attach foreground overlay (smoke / grease splatter / seasoning).
from ._overlays import make_burger_overlay  # noqa: E402

for _tid in THEMES:
    THEMES[_tid]["overlay_fn"] = make_burger_overlay(_tid)

# Silence unused-import warnings — referenced via theme dicts.
_ = (FONT_BUNGEE, FONT_PERMANENT_MARKER, FONT_SANS_BOLD)
