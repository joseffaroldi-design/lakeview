"""
Layout Registry

Platform sizes and layout definitions.
Extracted from ai_designer.py - Technical Debt Reduction Sprint Step 2.1
"""

from typing import Tuple

# Platform-specific canvas sizes (Priority 2 & 3)
PLATFORM_SIZES = {
    "instagram_post": (1024, 1024),
    "instagram_story": (1080, 1920),
    "tiktok": (1080, 1920),
    "twitter": (1200, 675),
    "facebook": (1200, 1200),
    "email": (600, 600),
}

# Layout options for composition
LAYOUTS = ["centered", "asym_left", "stacked"]


def get_canvas_size(platform: str) -> Tuple[int, int]:
    """Return (width, height) for the given platform."""
    return PLATFORM_SIZES.get(platform, (1024, 1024))


# Expose for backward compatibility
__all__ = ["PLATFORM_SIZES", "LAYOUTS", "get_canvas_size"]
