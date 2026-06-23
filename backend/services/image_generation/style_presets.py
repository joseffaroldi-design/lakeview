"""Sprint 15B.8 — 10 named style presets for restaurant marketing imagery.

A preset is a prompt scaffold that wraps the owner's raw prompt with
photography direction, lighting, composition and brand tone. Presets are
shared across providers — the same scaffolded prompt goes to Flux or
OpenAI without modification.

Each preset has:
  * `key`        — stable id stored on the job row
  * `label`      — UI text
  * `scaffold`   — f-string consuming `{prompt}` placeholder
  * `negative`   — common quality guard (used by Flux only; OpenAI ignores)
"""
from __future__ import annotations

from typing import List, Dict


_QUALITY_NEGATIVE = (
    "blurry, low quality, watermark, text artifacts, distorted, "
    "bad anatomy, oversaturated, plastic-looking, AI fingers, deformed hands"
)


STYLE_PRESETS: List[Dict[str, str]] = [
    {
        "key": "restaurant_food_photography",
        "label": "Restaurant Food Photography",
        "scaffold": (
            "Editorial restaurant food photography of {prompt}. "
            "Shot on a 50mm lens, shallow depth of field, soft window light from "
            "the left, rustic wooden table, natural shadows, vibrant but realistic "
            "colors, garnish details visible, professional menu-shoot quality."
        ),
        "negative": _QUALITY_NEGATIVE,
    },
    {
        "key": "smash_burger_advertising",
        "label": "Smash Burger Advertising",
        "scaffold": (
            "Bold advertising photograph of {prompt} — a juicy smash burger with "
            "melted American cheese cascading over a charred patty, crisp lettuce, "
            "ripe tomato, sesame brioche bun, dramatic side lighting, glossy melted "
            "cheese highlights, steam rising, beer-bar background out of focus."
        ),
        "negative": _QUALITY_NEGATIVE,
    },
    {
        "key": "seafood_marketing",
        "label": "Seafood Marketing",
        "scaffold": (
            "High-end seafood marketing shot of {prompt}. Fresh-from-the-Gulf look, "
            "ice and lemon wedges, butter glaze on shellfish, cool blue undertones, "
            "wooden dock or weathered slate plate, herb garnish, water droplets, "
            "coastal natural light."
        ),
        "negative": _QUALITY_NEGATIVE,
    },
    {
        "key": "catering_promotion",
        "label": "Catering Promotion",
        "scaffold": (
            "Catering promotional photograph of {prompt}. Abundant family-style "
            "spread, multiple platters arranged on a long table, warm golden-hour "
            "lighting, guests slightly out of focus in background, celebratory "
            "atmosphere, generous portions, hand-lettered chalkboard sign blurred "
            "in background."
        ),
        "negative": _QUALITY_NEGATIVE,
    },
    {
        "key": "new_orleans_local",
        "label": "New Orleans Local Business",
        "scaffold": (
            "New Orleans neighborhood-restaurant atmosphere featuring {prompt}. "
            "French Quarter wrought-iron and gas-lantern lighting, jazz-club warm "
            "amber tones, vintage tile flooring, Creole color palette of mustard, "
            "deep red and forest green, lived-in character, locally beloved feel."
        ),
        "negative": _QUALITY_NEGATIVE,
    },
    {
        "key": "mardi_gras_advertising",
        "label": "Mardi Gras Advertising",
        "scaffold": (
            "Mardi Gras themed advertising of {prompt}. Purple, gold and green "
            "color story, masks, beads and confetti as supporting elements, "
            "festive bokeh lights, celebratory but tasteful — not gaudy, premium "
            "carnival energy, late-evening street-party lighting."
        ),
        "negative": _QUALITY_NEGATIVE,
    },
    {
        "key": "luxury_restaurant",
        "label": "Luxury Restaurant",
        "scaffold": (
            "Luxury fine-dining presentation of {prompt}. Black slate or pristine "
            "white china, minimalist plating, single-source dramatic top light, "
            "deep shadows, microgreens and sauce streaks, Michelin-guide tasting-"
            "menu aesthetic, expensive ingredient cues."
        ),
        "negative": _QUALITY_NEGATIVE,
    },
    {
        "key": "social_media_ad",
        "label": "Social Media Ad",
        "scaffold": (
            "Scroll-stopping social media ad creative featuring {prompt}. Bold "
            "vibrant colors, high contrast, centered hero composition with room "
            "for overlay copy at top and bottom, thumb-stopping in a feed, "
            "Instagram-friendly saturation, modern brand-ad aesthetic."
        ),
        "negative": _QUALITY_NEGATIVE,
    },
    {
        "key": "flyer_design",
        "label": "Flyer Design",
        "scaffold": (
            "Marketing flyer hero image of {prompt}. Clean composition with "
            "negative space for headline copy, single focal subject, even soft "
            "lighting, print-ready resolution feel, slight vignetting, brand-"
            "ready isolation, no on-image text or words."
        ),
        "negative": _QUALITY_NEGATIVE + ", on-image text, lettering, typography",
    },
    {
        "key": "poster_design",
        "label": "Poster Design",
        "scaffold": (
            "Bold poster-style composition of {prompt}. Strong vertical or square "
            "framing, dramatic top-down light, single subject filling 70% of the "
            "frame, contrast-heavy, gallery-print feel, suitable for large-format "
            "printing, no text on image."
        ),
        "negative": _QUALITY_NEGATIVE + ", on-image text, lettering, typography",
    },
]


_PRESET_BY_KEY = {p["key"]: p for p in STYLE_PRESETS}


def build_prompt(style_key: str, raw_prompt: str) -> tuple[str, str]:
    """Return `(scaffolded_prompt, negative_prompt)` for the given preset.

    Falls back to the raw prompt with no scaffold if the style key is
    unknown — the router validates inputs but providers must not crash
    on a typo'd key.
    """
    preset = _PRESET_BY_KEY.get(style_key)
    if not preset:
        return raw_prompt, _QUALITY_NEGATIVE
    scaffolded = preset["scaffold"].format(prompt=raw_prompt.strip())
    return scaffolded, preset.get("negative", _QUALITY_NEGATIVE)


def preset_keys() -> List[str]:
    return [p["key"] for p in STYLE_PRESETS]
