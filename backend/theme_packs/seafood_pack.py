"""Seafood pack — Gulf/coastal blues, whites, cream sand, nautical accents."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from ._shared import (
    CANVAS, FONT_BEBAS_NEUE, FONT_PERMANENT_MARKER, FONT_SERIF_BOLD,
)

PACK = {
    "id": "seafood",
    "label": "Gulf Seafood",
    "category": "seafood",
    "enabled": True,
    "description": "Coastal palettes — navy, deep teal, sand, white — with wave + rope accents.",
}


# ---------------------------------------------------------------- background renderers

def _wave_line(draw: ImageDraw.ImageDraw, color, y: int, amp: int, period: int,
               width: int = 4) -> None:
    pts = []
    for x in range(0, CANVAS + 4, 6):
        pts.append((x, int(y + math.sin(x / period * math.pi * 2) * amp)))
    for i in range(len(pts) - 1):
        draw.line((pts[i], pts[i + 1]), fill=color, width=width)


def _rope_border(draw: ImageDraw.ImageDraw, color, inset: int = 60) -> None:
    """Twisted rope feel: chain of small ellipses along each edge."""
    step = 22
    r = 9
    # top + bottom
    for x in range(inset, CANVAS - inset + 1, step):
        draw.ellipse((x - r, inset - r, x + r, inset + r), outline=color, width=3)
        draw.ellipse((x - r, CANVAS - inset - r, x + r, CANVAS - inset + r),
                     outline=color, width=3)
    # left + right
    for y in range(inset + step, CANVAS - inset, step):
        draw.ellipse((inset - r, y - r, inset + r, y + r), outline=color, width=3)
        draw.ellipse((CANVAS - inset - r, y - r, CANVAS - inset + r, y + r),
                     outline=color, width=3)


def _anchor(draw: ImageDraw.ImageDraw, color, cx: int, cy: int, size: int) -> None:
    w = max(3, size // 14)
    # top ring
    draw.ellipse((cx - size // 6, cy - size // 2, cx + size // 6, cy - size // 4),
                 outline=color, width=w)
    # shaft
    draw.line((cx, cy - size // 4, cx, cy + size // 3), fill=color, width=w)
    # crossbar
    draw.line((cx - size // 4, cy - size // 8, cx + size // 4, cy - size // 8),
              fill=color, width=w)
    # bottom arc
    draw.arc((cx - size // 2, cy - size // 6, cx + size // 2, cy + size // 2),
             20, 160, fill=color, width=w)
    # bottom points
    draw.line((cx - size // 2 + 6, cy + size // 4, cx - size // 3, cy + size // 2),
              fill=color, width=w)
    draw.line((cx + size // 2 - 6, cy + size // 4, cx + size // 3, cy + size // 2),
              fill=color, width=w)


def _bg_coastal(canvas: Image.Image, draw: ImageDraw.ImageDraw, variant_idx: int) -> None:
    from routers.ai_designer import _radial_gradient
    _radial_gradient(canvas, (220, 235, 240), (180, 210, 220), CANVAS // 2,
                     int(CANVAS * 0.55), int(CANVAS * 0.85))
    # navy top band
    draw.rectangle((0, 0, CANVAS, 180), fill=(20, 45, 90))
    draw.rectangle((0, CANVAS - 180, CANVAS, CANVAS), fill=(20, 45, 90))
    if variant_idx == 0:
        _rope_border(draw, (245, 235, 210, 230), inset=60)
        _anchor(draw, (245, 235, 210, 230), cx=120, cy=CANVAS // 2, size=120)
        _anchor(draw, (245, 235, 210, 230), cx=CANVAS - 120, cy=CANVAS // 2, size=120)
    elif variant_idx == 1:
        _wave_line(draw, (245, 235, 210, 200), y=200, amp=10, period=120, width=4)
        _wave_line(draw, (245, 235, 210, 200), y=CANVAS - 200, amp=10, period=120, width=4)
    else:
        _wave_line(draw, (10, 80, 130, 220), y=210, amp=12, period=140, width=5)
        _wave_line(draw, (10, 80, 130, 220), y=CANVAS - 210, amp=12, period=140, width=5)
        _anchor(draw, (245, 235, 210, 230), cx=CANVAS // 2, cy=CANVAS - 90, size=80)


def _bg_lagoon(canvas: Image.Image, draw: ImageDraw.ImageDraw, variant_idx: int) -> None:
    from routers.ai_designer import _radial_gradient, _star
    _radial_gradient(canvas, (170, 215, 215), (90, 160, 175), CANVAS // 2,
                     int(CANVAS * 0.55), int(CANVAS * 0.85))
    # cream rounded panel
    if variant_idx == 0:
        draw.rounded_rectangle((90, 90, CANVAS - 90, CANVAS - 90), radius=28,
                               outline=(252, 240, 210, 240), width=5)
        for y in (CANVAS // 4, CANVAS * 3 // 4):
            _wave_line(draw, (252, 240, 210, 230), y=y, amp=8, period=100, width=4)
    elif variant_idx == 1:
        _anchor(draw, (10, 60, 80, 230), cx=140, cy=160, size=110)
        _anchor(draw, (10, 60, 80, 230), cx=CANVAS - 140, cy=CANVAS - 160, size=110)
        _rope_border(draw, (252, 240, 210, 200), inset=70)
    else:
        # 5 small starfish
        for cx, cy in [(120, 200), (CANVAS - 120, 200),
                       (120, CANVAS - 200), (CANVAS - 120, CANVAS - 200),
                       (CANVAS // 2, 150)]:
            _star(draw, (252, 220, 120, 240), cx=cx, cy=cy, r=28)
        _wave_line(draw, (252, 240, 210, 200), y=CANVAS // 2 + 220,
                   amp=14, period=130, width=5)


def _bg_dockside(canvas: Image.Image, draw: ImageDraw.ImageDraw, variant_idx: int) -> None:
    from routers.ai_designer import _radial_gradient, _distressed_grain
    _radial_gradient(canvas, (60, 95, 120), (16, 36, 60), CANVAS // 2,
                     int(CANVAS * 0.55), int(CANVAS * 0.9))
    _distressed_grain(canvas, (252, 240, 210, 18), density=1600)
    # vertical "planks" pattern
    if variant_idx == 0:
        for x in range(0, CANVAS, 90):
            draw.line((x, 0, x, CANVAS), fill=(252, 240, 210, 40), width=2)
        _wave_line(draw, (252, 240, 210, 220), y=240, amp=14, period=130, width=5)
        _wave_line(draw, (252, 240, 210, 220), y=CANVAS - 240, amp=14, period=130, width=5)
    elif variant_idx == 1:
        _rope_border(draw, (252, 240, 210, 200), inset=70)
        _anchor(draw, (252, 240, 210, 220), cx=CANVAS // 2, cy=CANVAS // 2, size=180)
    else:
        # Lighthouse beam — pale wedge
        draw.polygon(
            [(120, 100), (CANVAS - 120, 100), (CANVAS // 2, CANVAS // 2)],
            fill=(252, 240, 210, 38),
        )
        _wave_line(draw, (252, 240, 210, 200), y=CANVAS - 200,
                   amp=16, period=140, width=5)


# ---------------------------------------------------------------- theme dicts

THEMES = {
    "seafood_coastal": {
        "label": "Coastal Navy",
        "best_use": "Po-boys, shrimp baskets, oyster nights",
        "bg_color": (200, 220, 230),
        "title": {"font": FONT_SERIF_BOLD, "color": (245, 235, 210), "size": 96,
                  "stroke_width": 3, "stroke_fill": (12, 30, 60),
                  "letter_spacing": 4, "shadow": (12, 30, 60, 200)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (12, 30, 60), "size": 32, "marker": "✦",
                  "marker_color": (12, 30, 60), "letter_spacing": 2},
        "price": {"bg": (12, 30, 60), "fg": (245, 235, 210), "ring": (200, 60, 50), "font": FONT_SERIF_BOLD},
        "branding_color": (12, 30, 60),
        "icons": True,
        "background_fn": _bg_coastal,
    },
    "seafood_lagoon": {
        "label": "Lagoon Cream",
        "best_use": "Crab cakes, ceviche, summer seafood menu",
        "bg_color": (170, 215, 215),
        "title": {"font": FONT_PERMANENT_MARKER, "color": (10, 60, 80), "size": 100,
                  "stroke_width": 2, "stroke_fill": (252, 240, 210),
                  "letter_spacing": 2, "shadow": (10, 60, 80, 90)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (10, 60, 80), "size": 32, "marker": "✓",
                  "marker_color": (220, 120, 60), "letter_spacing": 2},
        "price": {"bg": (252, 220, 120), "fg": (10, 60, 80), "ring": (10, 60, 80), "font": FONT_PERMANENT_MARKER},
        "branding_color": (10, 60, 80),
        "icons": True,
        "background_fn": _bg_lagoon,
    },
    "seafood_dockside": {
        "label": "Dockside Weathered",
        "best_use": "Catch-of-the-day, fish fry, dock-to-table",
        "bg_color": (40, 70, 95),
        "title": {"font": FONT_BEBAS_NEUE, "color": (252, 240, 210), "size": 108,
                  "stroke_width": 3, "stroke_fill": (16, 36, 60),
                  "letter_spacing": 5, "shadow": (16, 36, 60, 220)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (252, 240, 210), "size": 32, "marker": "▸",
                  "marker_color": (252, 220, 120), "letter_spacing": 2},
        "price": {"bg": (252, 220, 120), "fg": (16, 36, 60), "ring": (252, 240, 210), "font": FONT_BEBAS_NEUE},
        "branding_color": (252, 240, 210),
        "icons": True,
        "background_fn": _bg_dockside,
    },
}
