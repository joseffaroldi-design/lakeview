"""Seasonal pack — Mardi Gras, Summer Seafood Splash, Holiday Cheer."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from ._shared import (
    CANVAS, FONT_BEBAS_NEUE, FONT_BUNGEE, FONT_PERMANENT_MARKER,
    FONT_SERIF_BOLD,
)

PACK = {
    "id": "seasonal",
    "label": "Seasonal & Holiday",
    "category": "seasonal",
    "enabled": True,
    "description": "Calendar-aware palettes — Mardi Gras, summer splash, holiday cheer.",
}


# ---------------------------------------------------------------- background renderers

def _bead_string(draw: ImageDraw.ImageDraw, palette, start, end,
                 spacing: int = 26, r: int = 10) -> None:
    sx, sy = start
    ex, ey = end
    length = max(1.0, math.hypot(ex - sx, ey - sy))
    steps = int(length / spacing)
    for i in range(steps + 1):
        t = i / max(1, steps)
        x = int(sx + (ex - sx) * t)
        y = int(sy + (ey - sy) * t)
        color = palette[i % len(palette)]
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)


def _palm_frond(draw: ImageDraw.ImageDraw, color, x: int, y: int, size: int = 200) -> None:
    end_x, end_y = x + int(size * 0.1), y + size
    draw.line((x, y, end_x, end_y), fill=color, width=4)
    for i in range(8):
        t = (i + 1) / 9.0
        mx = int(x + (end_x - x) * t)
        my = int(y + (end_y - y) * t)
        leaf_len = int(size * (0.35 - 0.025 * i))
        draw.line((mx, my, mx - leaf_len, my - leaf_len // 2), fill=color, width=3)
        draw.line((mx, my, mx + leaf_len, my - leaf_len // 2), fill=color, width=3)


def _snowflake(draw: ImageDraw.ImageDraw, color, cx: int, cy: int, size: int = 30) -> None:
    for i in range(6):
        ang = math.pi / 3 * i
        x2 = int(cx + math.cos(ang) * size)
        y2 = int(cy + math.sin(ang) * size)
        draw.line((cx, cy, x2, y2), fill=color, width=3)
        # small arms
        bx = int(cx + math.cos(ang) * size * 0.55)
        by = int(cy + math.sin(ang) * size * 0.55)
        side = math.pi / 4
        for s in (-1, 1):
            ax = int(bx + math.cos(ang + s * side) * size * 0.25)
            ay = int(by + math.sin(ang + s * side) * size * 0.25)
            draw.line((bx, by, ax, ay), fill=color, width=2)


def _bg_mardi_gras(canvas: Image.Image, draw: ImageDraw.ImageDraw, variant_idx: int) -> None:
    from routers.ai_designer import _radial_gradient, _star
    _radial_gradient(canvas, (90, 30, 130), (35, 10, 60), CANVAS // 2,
                     int(CANVAS * 0.55), int(CANVAS * 0.9))
    palette = [(252, 220, 60, 240), (60, 160, 80, 240), (180, 60, 220, 240),
               (252, 240, 210, 240)]
    if variant_idx == 0:
        # Two bead strings draping across the top
        _bead_string(draw, palette, (0, 120), (CANVAS, 220))
        _bead_string(draw, palette, (0, 200), (CANVAS, 320))
        for cx, cy in [(140, CANVAS - 160), (CANVAS - 140, CANVAS - 160)]:
            _star(draw, (252, 220, 60, 240), cx=cx, cy=cy, r=30)
    elif variant_idx == 1:
        # Fleur-de-lis substitute: 3 stars in a row
        for cx in (CANVAS // 4, CANVAS // 2, CANVAS * 3 // 4):
            _star(draw, (252, 220, 60, 240), cx=cx, cy=160, r=34)
        _bead_string(draw, palette, (0, CANVAS - 220), (CANVAS, CANVAS - 120))
    else:
        # Diagonal bead drapes corner-to-corner
        _bead_string(draw, palette, (0, 80), (CANVAS // 2, 320), spacing=24, r=10)
        _bead_string(draw, palette, (CANVAS, 80), (CANVAS // 2, 320), spacing=24, r=10)
        _bead_string(draw, palette, (0, CANVAS - 80), (CANVAS // 2, CANVAS - 320),
                     spacing=24, r=10)
        _bead_string(draw, palette, (CANVAS, CANVAS - 80), (CANVAS // 2, CANVAS - 320),
                     spacing=24, r=10)


def _bg_summer_splash(canvas: Image.Image, draw: ImageDraw.ImageDraw, variant_idx: int) -> None:
    from routers.ai_designer import _radial_gradient, _star, _wavy_ribbon
    _radial_gradient(canvas, (140, 220, 230), (60, 170, 200), CANVAS // 2,
                     int(CANVAS * 0.55), int(CANVAS * 0.9))
    # sun-yellow top accent
    draw.rectangle((0, 0, CANVAS, 80), fill=(252, 220, 80))
    draw.rectangle((0, CANVAS - 80, CANVAS, CANVAS), fill=(252, 220, 80))
    if variant_idx == 0:
        _palm_frond(draw, (40, 100, 60, 230), x=80, y=120, size=320)
        _palm_frond(draw, (40, 100, 60, 230), x=CANVAS - 100, y=120, size=320)
        _wavy_ribbon(draw, (252, 240, 210, 220),
                     start=(80, CANVAS // 2 + 280), end=(CANVAS - 80, CANVAS // 2 + 280),
                     width=24)
    elif variant_idx == 1:
        for cx, cy in [(150, 200), (CANVAS - 150, 200),
                       (150, CANVAS - 200), (CANVAS - 150, CANVAS - 200)]:
            _star(draw, (252, 220, 80, 240), cx=cx, cy=cy, r=26)
        _wavy_ribbon(draw, (252, 240, 210, 220),
                     start=(60, 240), end=(CANVAS - 60, 240), width=22)
        _wavy_ribbon(draw, (252, 240, 210, 220),
                     start=(60, CANVAS - 240), end=(CANVAS - 60, CANVAS - 240), width=22)
    else:
        _palm_frond(draw, (40, 100, 60, 230), x=60, y=CANVAS - 380, size=360)
        _palm_frond(draw, (40, 100, 60, 230), x=CANVAS - 120, y=CANVAS - 380, size=360)
        # Sun rays from top-center
        for i in range(-3, 4):
            ang = math.radians(90 + i * 14)
            x2 = int(CANVAS // 2 + math.cos(ang) * 360)
            y2 = int(140 - math.sin(ang) * 360)
            draw.line((CANVAS // 2, 140, x2, y2),
                      fill=(252, 220, 80, 200), width=4)


def _bg_holiday_cheer(canvas: Image.Image, draw: ImageDraw.ImageDraw, variant_idx: int) -> None:
    from routers.ai_designer import _radial_gradient
    _radial_gradient(canvas, (40, 80, 60), (12, 30, 22), CANVAS // 2,
                     int(CANVAS * 0.55), int(CANVAS * 0.95))
    # red top + bottom bands
    draw.rectangle((0, 0, CANVAS, 100), fill=(170, 30, 40))
    draw.rectangle((0, CANVAS - 100, CANVAS, CANVAS), fill=(170, 30, 40))
    # gold pinstripe between bands and the green
    for y in (100, CANVAS - 100):
        draw.line((0, y + 4, CANVAS, y + 4), fill=(252, 200, 60, 240), width=3)
    if variant_idx == 0:
        # Falling snowflakes
        for cx, cy in [(160, 220), (300, 380), (CANVAS - 280, 280),
                       (CANVAS - 140, 460), (200, CANVAS - 280),
                       (CANVAS - 200, CANVAS - 360), (CANVAS // 2 + 60, 540)]:
            _snowflake(draw, (252, 240, 210, 230), cx=cx, cy=cy, size=34)
    elif variant_idx == 1:
        # Gold garland swag along top + bottom
        steps = 14
        for i in range(steps):
            t = i / (steps - 1)
            x = int(t * CANVAS)
            y_top = int(140 + math.sin(t * math.pi) * 40)
            y_bot = int(CANVAS - 140 - math.sin(t * math.pi) * 40)
            draw.ellipse((x - 10, y_top - 10, x + 10, y_top + 10),
                         fill=(252, 200, 60, 240))
            draw.ellipse((x - 10, y_bot - 10, x + 10, y_bot + 10),
                         fill=(252, 200, 60, 240))
    else:
        # Mix: snowflakes in corners + holly-style red dot clusters
        for cx, cy in [(160, 220), (CANVAS - 160, 220),
                       (160, CANVAS - 220), (CANVAS - 160, CANVAS - 220)]:
            _snowflake(draw, (252, 240, 210, 230), cx=cx, cy=cy, size=38)
        for cx, cy in [(CANVAS // 2 - 20, 200), (CANVAS // 2 + 20, 200),
                       (CANVAS // 2, 230)]:
            draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10),
                         fill=(220, 40, 50, 240))


# ---------------------------------------------------------------- theme dicts

THEMES = {
    "mardi_gras": {
        "label": "Mardi Gras",
        "best_use": "Mardi Gras week, king cake, Fat Tuesday menus",
        "bg_color": (60, 20, 90),
        "title": {"font": FONT_BUNGEE, "color": (252, 220, 60), "size": 110,
                  "stroke_width": 4, "stroke_fill": (35, 10, 60),
                  "letter_spacing": 4, "shadow": (60, 160, 80, 220)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (252, 240, 210), "size": 32, "marker": "★",
                  "marker_color": (252, 220, 60), "letter_spacing": 2},
        "price": {"bg": (252, 220, 60), "fg": (35, 10, 60), "ring": (60, 160, 80), "font": FONT_BUNGEE},
        "branding_color": (252, 220, 60),
        "icons": True,
        "background_fn": _bg_mardi_gras,
    },
    "summer_splash": {
        "label": "Summer Splash",
        "best_use": "Boil season, summer seafood, patio specials",
        "bg_color": (90, 190, 215),
        "title": {"font": FONT_PERMANENT_MARKER, "color": (12, 50, 70), "size": 106,
                  "stroke_width": 3, "stroke_fill": (252, 240, 210),
                  "letter_spacing": 3, "shadow": (252, 220, 80, 220)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (12, 50, 70), "size": 32, "marker": "☼",
                  "marker_color": (220, 110, 40), "letter_spacing": 2},
        "price": {"bg": (252, 220, 80), "fg": (12, 50, 70), "ring": (252, 240, 210), "font": FONT_PERMANENT_MARKER},
        "branding_color": (12, 50, 70),
        "icons": True,
        "background_fn": _bg_summer_splash,
    },
    "holiday_cheer": {
        "label": "Holiday Cheer",
        "best_use": "Thanksgiving, Christmas, NYE — holiday menus",
        "bg_color": (30, 70, 50),
        "title": {"font": FONT_SERIF_BOLD, "color": (252, 220, 60), "size": 102,
                  "stroke_width": 3, "stroke_fill": (12, 30, 22),
                  "letter_spacing": 3, "shadow": (170, 30, 40, 220)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (252, 240, 210), "size": 32, "marker": "❄",
                  "marker_color": (252, 220, 60), "letter_spacing": 2},
        "price": {"bg": (170, 30, 40), "fg": (252, 240, 210), "ring": (252, 220, 60), "font": FONT_SERIF_BOLD},
        "branding_color": (252, 220, 60),
        "icons": True,
        "background_fn": _bg_holiday_cheer,
    },
}

# Sprint 16H — attach per-theme foreground overlay (glitter / sun rays / snow).
from ._overlays import make_seasonal_overlay  # noqa: E402

for _tid in THEMES:
    THEMES[_tid]["overlay_fn"] = make_seasonal_overlay(_tid)
