"""
Theme Registry

Single source of truth for all theme definitions.
Technical Debt Reduction Sprint Step 2.2

Re-exports from theme_packs package which contains:
- 22 themes across 6 packs
- Theme validation and loading
- Pack metadata
"""

# Import from the existing theme_packs structure
from .theme_packs import (
    THEME_STYLES,
    THEME_META,
    PACKS as THEME_PACKS,
    WARNINGS as THEME_WARNINGS,
)

# Derived data
THEME_IDS = list(THEME_STYLES.keys())

# Expose for backward compatibility
__all__ = [
    "THEME_STYLES",
    "THEME_META", 
    "THEME_PACKS",
    "THEME_WARNINGS",
    "THEME_IDS",
]
