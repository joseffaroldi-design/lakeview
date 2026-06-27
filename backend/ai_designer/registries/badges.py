"""
Badge Registry

Badge style constants and selection logic.
Technical Debt Reduction Sprint Step 2.3
"""

# Sprint 18 — Badge style options
BADGE_STYLES = (
    "burst",
    "sticker", 
    "chalk_circle",
    "ribbon",
    "ticket",
    "distressed_stamp",
    "paint_splash",
    "hanging_tag"
)

# Expose for backward compatibility
__all__ = ["BADGE_STYLES"]
