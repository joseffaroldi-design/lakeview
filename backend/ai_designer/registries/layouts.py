"""
Layout Registry

Platform sizes and layout definitions.
Extracted from ai_designer.py - Technical Debt Reduction Sprint Step 2.1
"""

from typing import Tuple

# Platform-specific canvas sizes (Priority 2 & 3)
#
# Feb 2026 fix — "Facebook Post" was previously mapped to a 1200×1200
# square, but Meta's Feed/Link-share standard is 1200×630 landscape. We
# now expose both explicitly:
#   - `facebook_feed`  → 1200×1200 (square in-feed image)
#   - `facebook_post`  → 1200×630  (landscape link-share, standard "post")
# The legacy `facebook` key stays pointed at the square so old saved jobs
# keep their historical dimensions.
PLATFORM_SIZES = {
    "instagram_post":   (1024, 1024),
    "instagram_story":  (1080, 1920),
    "tiktok":           (1080, 1920),
    "twitter":          (1200, 675),
    "facebook":         (1200, 1200),  # legacy alias — square feed
    "facebook_feed":    (1200, 1200),  # square in-feed image
    "facebook_post":    (1200, 630),   # landscape link-share (standard FB post)
    "facebook_landscape": (1200, 630), # alias for facebook_post
    "email":            (600, 600),
}

# Layout options for composition
LAYOUTS = ["centered", "asym_left", "stacked"]


def get_canvas_size(platform: str) -> Tuple[int, int]:
    """Return (width, height) for the given platform."""
    return PLATFORM_SIZES.get(platform, (1024, 1024))


# Expose for backward compatibility
__all__ = ["PLATFORM_SIZES", "LAYOUTS", "get_canvas_size"]
