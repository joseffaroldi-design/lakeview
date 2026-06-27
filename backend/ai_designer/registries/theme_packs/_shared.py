"""Sprint 16F — Shared constants and font paths for theme packs.

Centralized here so pack modules don't need to import from
`routers.ai_designer` at module load time (which would cause a circular
import: ai_designer imports theme_packs at startup).

The same constants are imported by `routers.ai_designer` itself, so a
single edit here (e.g. swapping a font) propagates everywhere.
"""
from __future__ import annotations

from pathlib import Path

CANVAS = 1024

FONT_SERIF_BOLD = "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"
FONT_SERIF      = "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"
FONT_SANS_BOLD  = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
FONT_SANS       = "/usr/share/fonts/truetype/freefont/FreeSans.ttf"

# Display fonts (Sprint 16A.1) — falls back to FreeFont if missing.
_FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
FONT_BEBAS_NEUE       = str(_FONT_DIR / "BebasNeue-Regular.ttf")
FONT_BUNGEE           = str(_FONT_DIR / "Bungee-Regular.ttf")
FONT_PERMANENT_MARKER = str(_FONT_DIR / "PermanentMarker-Regular.ttf")
