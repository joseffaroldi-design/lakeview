"""
Shared Utilities

Helper functions used across AI Designer modules.
Technical Debt Reduction Sprint Step 4
"""

from typing import List, Optional, Iterable, Tuple
from pathlib import Path
from PIL import ImageDraw, ImageFont


# Font paths
FONT_SANS_BOLD = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"

# Font fallbacks mapping
_FONT_FALLBACKS = {
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf": FONT_SANS_BOLD,
}


def resolve_font_path(path: str) -> str:
    """
    Return `path` if the font file exists; otherwise return the registered
    fallback. Tested at every theme resolution so a missing font file
    degrades gracefully instead of crashing.
    """
    if Path(path).exists():
        return path
    fallback = _FONT_FALLBACKS.get(path, FONT_SANS_BOLD)
    return fallback if Path(fallback).exists() else FONT_SANS_BOLD


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """
    Load a TrueType font with fallback to default.
    """
    try:
        return ImageFont.truetype(resolve_font_path(path), size=size)
    except Exception:
        return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    """
    Word-wrap `text` so each line fits within `max_w` pixels.
    """
    words = (text or "").split()
    lines: List[str] = []
    cur: List[str] = []
    for w in words:
        trial = (" ".join(cur + [w])).strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if (bbox[2] - bbox[0]) <= max_w or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines or [""]


def map_food_to_theme(food_type: str) -> str:
    """
    Restaurant Intelligence: Map detected food category to recommended theme.
    
    Priority 4.2 / Phase 5
    """
    if not food_type:
        return "comic_pop"
    
    food_lower = food_type.lower()
    
    # Burger & Sandwich mapping
    if any(word in food_lower for word in ["burger", "sandwich", "po-boy", "poboy", "sub"]):
        return "burger_classic"
    # Seafood mapping  
    elif any(word in food_lower for word in ["seafood", "shrimp", "fish", "crab", "oyster", "lobster"]):
        return "cajun"
    # BBQ & Grilled mapping
    elif any(word in food_lower for word in ["bbq", "barbecue", "ribs", "brisket", "grilled", "smoked"]):
        return "burger_grill_smoke"
    # Pizza & Italian
    elif any(word in food_lower for word in ["pizza", "pasta", "italian"]):
        return "vintage_diner"
    # Desserts
    elif any(word in food_lower for word in ["dessert", "cake", "pie", "ice cream", "sweet"]):
        return "vintage_diner"
    # Drinks & Cocktails
    elif any(word in food_lower for word in ["cocktail", "beer", "wine", "drink", "coffee"]):
        return "burger_neon_diner"
    # Salads & Healthy
    elif any(word in food_lower for word in ["salad", "healthy", "vegetarian", "vegan"]):
        return "modern"
    # Chicken & Poultry
    elif any(word in food_lower for word in ["chicken", "wings", "poultry"]):
        return "game_day_tailgate"
    # Default fallback
    else:
        return "comic_pop"


def normalize_theme(theme: str, valid_themes: Iterable[str]) -> Optional[str]:
    """
    Validate `theme` against `valid_themes` (list/set/dict of valid IDs).

    Returns the theme string if valid, otherwise None.

    Pure helper: caller is responsible for raising HTTPException with the
    appropriate context. Keeps utils.py framework-agnostic.
    """
    if not theme:
        return None
    if theme in valid_themes:
        return theme
    return None


def fit_text_to_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    max_w: int,
    max_h: int,
    max_size: int = 96,
    min_size: int = 16,
    line_spacing: float = 1.15,
) -> Tuple[ImageFont.FreeTypeFont, List[str], int]:
    """
    Auto-shrink the font for `text` so wrapped lines fit within
    a `max_w` x `max_h` bounding box.

    Returns: (font, lines, total_height_px)

    Tries sizes from `max_size` down to `min_size`; returns the largest
    size whose wrapped layout fits. Falls back to `min_size` if none fit.
    """
    if not text:
        font = load_font(font_path, max_size)
        return font, [""], 0

    size = max_size
    last_result: Optional[Tuple[ImageFont.FreeTypeFont, List[str], int]] = None

    while size >= min_size:
        font = load_font(font_path, size)
        lines = wrap_text(draw, text, font, max_w)
        # Measure total height
        line_h = 0
        for ln in lines:
            bbox = draw.textbbox((0, 0), ln or " ", font=font)
            line_h = max(line_h, bbox[3] - bbox[1])
        total_h = int(line_h * line_spacing * len(lines))
        if total_h <= max_h:
            return font, lines, total_h
        last_result = (font, lines, total_h)
        size -= 2

    # Nothing fit perfectly — return smallest attempt
    if last_result is not None:
        return last_result
    font = load_font(font_path, min_size)
    return font, [text], 0


# Expose for backward compatibility
__all__ = [
    "resolve_font_path",
    "load_font",
    "wrap_text",
    "map_food_to_theme",
    "normalize_theme",
    "fit_text_to_box",
    "FONT_SANS_BOLD",
]
