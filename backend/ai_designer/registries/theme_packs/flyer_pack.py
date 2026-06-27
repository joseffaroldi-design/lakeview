"""Flyer-grade pack — bold poster typography + chunky badges (Sprint 16A).

Larger headline sizes (90-110px) + saturated palettes + ingredient-icon
bullets. Background renders are still handled by inline branches in
`routers.ai_designer._pil_background()` so we keep this pack as pure
data.
"""
from __future__ import annotations

from ._shared import (
    FONT_BEBAS_NEUE, FONT_BUNGEE, FONT_PERMANENT_MARKER,
)

PACK = {
    "id": "flyer",
    "label": "Flyer-Grade Poster",
    "category": "poster",
    "enabled": True,
    "description": "Display fonts, saturated palettes, ingredient icons.",
}

THEMES = {
    "comic_pop": {
        "label": "Comic Pop",
        "best_use": "Limited drops, kids' menus, social reels",
        "bg_color": (12, 12, 16),
        "title": {"font": FONT_BUNGEE, "color": (255, 235, 70), "size": 112,
                  "stroke_width": 4, "stroke_fill": (12, 12, 16),
                  "letter_spacing": 4, "shadow": (0, 0, 0, 180)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (255, 255, 255), "size": 34, "marker": "▸",
                  "marker_color": (255, 235, 70), "letter_spacing": 2},
        "price": {"bg": (255, 235, 70), "fg": (12, 12, 16), "ring": (255, 255, 255), "font": FONT_BUNGEE},
        "branding_color": (255, 235, 70),
        "icons": True,
    },
    "vintage_diner": {
        "label": "Vintage Diner (Flyer)",
        "best_use": "Burger nights, milkshakes, retro promos",
        "bg_color": (244, 232, 200),
        "title": {"font": FONT_BEBAS_NEUE, "color": (35, 90, 50), "size": 108,
                  "stroke_width": 3, "stroke_fill": (244, 232, 200),
                  "letter_spacing": 6, "shadow": (35, 90, 50, 60)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (35, 60, 40), "size": 32, "marker": "★",
                  "marker_color": (180, 50, 40), "letter_spacing": 3},
        "price": {"bg": (180, 50, 40), "fg": (244, 232, 200), "ring": (35, 90, 50), "font": FONT_BEBAS_NEUE},
        "branding_color": (90, 70, 40),
        "icons": True,
    },
    "bold_purple_pop": {
        "label": "Bold Purple Pop",
        "best_use": "Late-night menu, cocktails, neon promos",
        "bg_color": (38, 18, 60),
        "title": {"font": FONT_BUNGEE, "color": (255, 240, 240), "size": 112,
                  "stroke_width": 4, "stroke_fill": (38, 18, 60),
                  "letter_spacing": 4, "shadow": (240, 60, 140, 200)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (255, 240, 240), "size": 34, "marker": "▸",
                  "marker_color": (255, 240, 100), "letter_spacing": 2},
        "price": {"bg": (255, 240, 100), "fg": (38, 18, 60), "ring": (240, 60, 140), "font": FONT_BUNGEE},
        "branding_color": (240, 200, 220),
        "icons": True,
    },
    "casual_teal": {
        "label": "Casual Teal",
        "best_use": "Brunch, fresh bowls, healthy lunch specials",
        "bg_color": (170, 220, 215),
        "title": {"font": FONT_PERMANENT_MARKER, "color": (30, 70, 70), "size": 104,
                  "stroke_width": 2, "stroke_fill": (250, 245, 230),
                  "letter_spacing": 2, "shadow": (220, 110, 60, 100)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (30, 70, 70), "size": 32, "marker": "✓",
                  "marker_color": (220, 110, 60), "letter_spacing": 2},
        "price": {"bg": (250, 245, 230), "fg": (30, 70, 70), "ring": (220, 110, 60), "font": FONT_PERMANENT_MARKER},
        "branding_color": (50, 90, 90),
        "icons": True,
    },
    "distressed_orange": {
        "label": "Distressed Orange",
        "best_use": "BBQ, smokehouse, grill nights",
        "bg_color": (200, 80, 35),
        "title": {"font": FONT_PERMANENT_MARKER, "color": (252, 240, 215), "size": 110,
                  "stroke_width": 3, "stroke_fill": (40, 25, 20),
                  "letter_spacing": 2, "shadow": (40, 25, 20, 200)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (252, 240, 215), "size": 32, "marker": "■",
                  "marker_color": (252, 240, 215), "letter_spacing": 3},
        "price": {"bg": (40, 25, 20), "fg": (252, 240, 215), "ring": (252, 240, 215), "font": FONT_PERMANENT_MARKER},
        "branding_color": (252, 240, 215),
        "icons": True,
    },
}

# Sprint 16H — attach per-theme foreground overlay (halftone, splatter, confetti).
from ._overlays import make_flyer_overlay  # noqa: E402

for _tid in THEMES:
    THEMES[_tid]["overlay_fn"] = make_flyer_overlay(_tid)
