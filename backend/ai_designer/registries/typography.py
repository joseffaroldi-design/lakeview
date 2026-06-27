"""
Typography Registry

Font families, sizes, and text rendering configurations.
Technical Debt Reduction Sprint Step 2.3
"""

# Title backdrop styles (Sprint 16I+18)
TITLE_BACKDROP_STYLES = [
    "ribbon",
    "swash", 
    "distressed_rect",
    "brush",
    "torn_paper",
    "paint_stroke",
    "none"
]

# Default font paths (used by various renderers)
DEFAULT_FONTS = {
    "sans": "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "serif": "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
}

# Typography constants
TITLE_SIZE_MULTIPLIER = 1.15  # For stacked title lines
MIN_TITLE_SIZE = 40
MAX_TITLE_SIZE = 120

BODY_TEXT_SIZE = 24
BADGE_TEXT_SIZE_RATIO = 0.8  # Relative to badge radius

# Text wrapping
MAX_LINE_WIDTH_RATIO = 0.85  # Of canvas width

# Expose for backward compatibility
__all__ = [
    "TITLE_BACKDROP_STYLES",
    "DEFAULT_FONTS",
    "TITLE_SIZE_MULTIPLIER",
    "MIN_TITLE_SIZE",
    "MAX_TITLE_SIZE",
    "BODY_TEXT_SIZE",
    "BADGE_TEXT_SIZE_RATIO",
    "MAX_LINE_WIDTH_RATIO",
]
