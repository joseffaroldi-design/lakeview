"""
Shared Utilities

Helper functions used across AI Designer modules.
Technical Debt Reduction Sprint Step 4
"""

from typing import List
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
    return lines


def map_food_to_theme(food_type: str) -> str:
    """
    Restaurant Intelligence: Map detected food category to recommended theme.
    
    Priority 4.2 / Phase 5
    """
    if not food_type:
        return "modern"
    
    food_lower = food_type.lower()
    
    # Burger & Sandwich mapping
    if any(word in food_lower for word in ["burger", "sandwich", "po-boy", "poboy", "sub"]):
        return "burger_classic"
    # Seafood mapping  
    elif any(word in food_lower for word in ["seafood", "shrimp", "fish", "crab", "oyster", "lobster"]):
        return "cajun"
    # BBQ & Grilled mapping
    elif any(word in food_lower for word in ["bbq", "barbecue", "ribs", "brisket", "grilled", "smoked"]):
        return "bbq_smoke"
    # Pizza & Italian
    elif any(word in food_lower for word in ["pizza", "pasta", "italian"]):
        return "rustic"
    # Desserts
    elif any(word in food_lower for word in ["dessert", "cake", "pie", "ice cream", "sweet"]):
        return "vintage"
    # Drinks & Cocktails
    elif any(word in food_lower for word in ["cocktail", "beer", "wine", "drink", "coffee"]):
        return "neon"
    # Salads & Healthy
    elif any(word in food_lower for word in ["salad", "healthy", "vegetarian", "vegan"]):
        return "modern"
    # Chicken & Poultry
    elif any(word in food_lower for word in ["chicken", "wings", "poultry"]):
        return "game_day_wings"
    # Default fallback
    else:
        return "modern"


# Expose for backward compatibility
__all__ = [
    "resolve_font_path",
    "load_font", 
    "wrap_text",
    "map_food_to_theme",
    "FONT_SANS_BOLD",
]
