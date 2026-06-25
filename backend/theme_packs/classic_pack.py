"""Classic pack — the original 5 PIL themes shipped before Sprint 16A.

These themes use legacy decorative backgrounds (corner frames, ribbons,
checker strips, olive branches, etc.) rendered inline by the router's
`_pil_background()` dispatch. No `background_fn` here — `ai_designer.py`
recognises these IDs and falls through to its built-in branches.

Data layout matches the original THEME_STYLES dict so the router's
composition pipeline (title, bullets, price badge) keeps working
unchanged.
"""
from __future__ import annotations

from ._shared import (
    FONT_SANS, FONT_SANS_BOLD, FONT_SERIF_BOLD,
)

PACK = {
    "id": "classic",
    "label": "Classic Restaurant",
    "category": "general",
    "enabled": True,
    "description": "The original five PIL themes — works for any restaurant style.",
}

THEMES = {
    "luxury": {
        "label": "Luxury Black & Gold",
        "best_use": "Steakhouse, upscale dining, holiday tasting menus",
        "bg_color": (16, 16, 16),
        "title": {"font": FONT_SERIF_BOLD, "color": (212, 175, 55), "size": 76},
        "body":  {"font": FONT_SANS, "color": (245, 235, 200), "size": 30, "marker": "•",
                  "marker_color": (212, 175, 55)},
        "price": {"bg": (212, 175, 55), "fg": (16, 16, 16), "ring": (255, 220, 120), "font": FONT_SERIF_BOLD},
        "branding_color": (180, 160, 110),
    },
    "vintage": {
        "label": "Vintage Diner",
        "best_use": "Diners, breakfast specials, retro burger nights",
        "bg_color": (240, 220, 195),
        "title": {"font": FONT_SERIF_BOLD, "color": (160, 30, 30), "size": 80},
        "body":  {"font": FONT_SANS_BOLD, "color": (50, 25, 15), "size": 28, "marker": "*",
                  "marker_color": (160, 30, 30)},
        "price": {"bg": (220, 50, 50), "fg": (255, 245, 220), "ring": (255, 245, 220), "font": FONT_SERIF_BOLD},
        "branding_color": (90, 50, 30),
    },
    "modern": {
        "label": "Modern Restaurant",
        "best_use": "Cafes, bistros, weekly chef's specials",
        "bg_color": (248, 245, 240),
        "title": {"font": FONT_SERIF_BOLD, "color": (24, 28, 48), "size": 72},
        "body":  {"font": FONT_SANS, "color": (60, 65, 80), "size": 28, "marker": "—",
                  "marker_color": (24, 28, 48)},
        "price": {"bg": (24, 28, 48), "fg": (255, 245, 215), "ring": (215, 195, 130), "font": FONT_SERIF_BOLD},
        "branding_color": (130, 130, 140),
    },
    "social": {
        "label": "Bright Social",
        "best_use": "Instagram promos, happy hour, brunch posts",
        "bg_color": (255, 200, 90),
        "title": {"font": FONT_SANS_BOLD, "color": (40, 25, 5), "size": 86},
        "body":  {"font": FONT_SANS_BOLD, "color": (40, 25, 5), "size": 30, "marker": ">",
                  "marker_color": (220, 60, 40)},
        "price": {"bg": (220, 50, 50), "fg": (255, 245, 220), "ring": (255, 200, 90), "font": FONT_SANS_BOLD},
        "branding_color": (110, 60, 30),
    },
    "cajun": {
        "label": "Cajun / Bayou",
        "best_use": "Po-boys, gumbo, jambalaya, NOLA specials",
        "bg_color": (60, 40, 20),
        "title": {"font": FONT_SERIF_BOLD, "color": (245, 210, 80), "size": 78},
        "body":  {"font": FONT_SANS_BOLD, "color": (245, 235, 210), "size": 28, "marker": "+",
                  "marker_color": (220, 100, 30)},
        "price": {"bg": (220, 130, 40), "fg": (30, 20, 10), "ring": (245, 210, 80), "font": FONT_SERIF_BOLD},
        "branding_color": (200, 170, 100),
    },
}
