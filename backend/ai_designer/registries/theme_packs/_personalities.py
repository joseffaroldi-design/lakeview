"""Sprint 18 — Theme Personalities

Per-pack design language that drives every render. Picked up automatically
by render_engine / typography_engine via the loader in `theme_packs.__init__`.
We attach these onto every theme's metadata at load time so the rendering
pipeline can read `theme["personality"]` without importing this module.

Personality dict shape
----------------------
    {
        "tone":            "aggressive" | "fresh" | "energetic" | "festive" | "elegant" | "promotional",
        "texture":         0.0 .. 1.0,   # how distressed / textured the backdrops feel
        "type_weight":     "heavy" | "bold" | "regular",
        "saturation":      0.0 .. 1.0,   # color saturation bias
        "badge_pool":      ["burst", "ribbon", "paint_splash", "sticker", "hanging_tag", "chalk_circle", "ticket", "distressed_stamp"],
        "allow_overlap":   bool,         # whether title may overlap food
        "title_oversize":  0.9 .. 1.4,   # multiplier on default title size
        "backdrop_pool":   ["brush", "torn_paper", "paint_stroke", "ribbon", "swash", "distressed_rect", "none"],
    }
"""
from __future__ import annotations

from typing import Dict, Any

# All 8 badge styles (Sprint 16I + Sprint 18 additions).
_ALL_BADGES = [
    "burst", "ribbon", "paint_splash", "sticker",
    "hanging_tag", "chalk_circle", "ticket", "distressed_stamp",
]
# All 7 backdrop styles (Sprint 16I + Sprint 18 additions).
_ALL_BACKDROPS = [
    "brush", "torn_paper", "paint_stroke",
    "ribbon", "swash", "distressed_rect", "none",
]


PERSONALITIES: Dict[str, Dict[str, Any]] = {
    "burger": {
        "tone": "aggressive",
        "texture": 0.75,
        "type_weight": "heavy",
        "saturation": 0.85,
        "badge_pool": ["paint_splash", "distressed_stamp", "burst", "sticker"],
        "allow_overlap": True,
        "title_oversize": 1.20,
        "backdrop_pool": ["paint_stroke", "torn_paper", "distressed_rect", "brush"],
    },
    "seafood": {
        "tone": "fresh",
        "texture": 0.35,
        "type_weight": "bold",
        "saturation": 0.70,
        "badge_pool": ["ribbon", "hanging_tag", "sticker", "chalk_circle"],
        "allow_overlap": False,
        "title_oversize": 1.05,
        "backdrop_pool": ["ribbon", "brush", "swash", "none"],
    },
    "sports": {
        "tone": "energetic",
        "texture": 0.55,
        "type_weight": "heavy",
        "saturation": 0.95,
        "badge_pool": ["burst", "ticket", "sticker", "paint_splash"],
        "allow_overlap": True,
        "title_oversize": 1.25,
        "backdrop_pool": ["distressed_rect", "paint_stroke", "torn_paper", "swash"],
    },
    "seasonal": {
        "tone": "festive",
        "texture": 0.50,
        "type_weight": "bold",
        "saturation": 0.80,
        "badge_pool": ["ribbon", "burst", "sticker", "hanging_tag"],
        "allow_overlap": False,
        "title_oversize": 1.10,
        "backdrop_pool": ["brush", "ribbon", "swash", "torn_paper"],
    },
    "general": {
        "tone": "elegant",
        "texture": 0.20,
        "type_weight": "regular",
        "saturation": 0.55,
        "badge_pool": ["sticker", "chalk_circle", "ribbon", "ticket"],
        "allow_overlap": False,
        "title_oversize": 1.00,
        "backdrop_pool": ["ribbon", "swash", "none", "brush"],
    },
    "poster": {
        "tone": "promotional",
        "texture": 0.40,
        "type_weight": "bold",
        "saturation": 0.75,
        "badge_pool": ["ticket", "sticker", "burst", "ribbon"],
        "allow_overlap": True,
        "title_oversize": 1.15,
        "backdrop_pool": ["torn_paper", "ribbon", "swash", "distressed_rect"],
    },
}


def personality_for(pack_category: str) -> Dict[str, Any]:
    """Return the personality dict for the given pack category. Falls
    back to 'general' for unknown packs (legacy themes)."""
    return PERSONALITIES.get(pack_category, PERSONALITIES["general"])
