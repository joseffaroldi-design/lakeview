"""AI Designer — themed marketing graphics via deterministic PIL composition.

Pipeline:
  1. Owner uploads a food photo + item name + bullet features + price + ONE theme.
  2. EVERY run produces EXACTLY 3 variations (A/B/C) using 3 different layouts.
  3. For each variation we:
       a) render a themed decorative background using PIL only (no AI).
       b) cut out the food using rembg (with rounded-rect fallback).
       c) crop to the food's bounding box and scale to ~55% of the canvas.
       d) composite the food on top of the PIL background — original pixels preserved.
       e) draw item name, feature bullets, price badge, restaurant branding via PIL.
  4. Final PNG is saved to media_assets as an "active" image.

The food image is NEVER sent through any AI model. Backgrounds are deterministic
PIL renders. Designs cost $0 per run; only the optional auto-copy step (one
structured LLM text call) consumes credits (~$0.001).

Routes:
  GET   /ai-designer/themes
  POST  /ai-designer/estimate
  POST  /ai-designer/generate (202)
  GET   /ai-designer/job/{id}
  GET   /ai-designer/jobs/recent
  POST  /ai-designer/jobs/{id}/pin
  GET   /ai-designer/templates
  POST  /ai-designer/jobs/{id}/save-template
  POST  /ai-designer/from-template/{tpl_id}?source_asset_id=…
  GET   /ai-designer/jobs/{id}/copy
  POST  /ai-designer/jobs/{id}/copy
"""
from __future__ import annotations

import io
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Cookie, Header, HTTPException
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel, ConfigDict, Field, constr

from auth import verify_session
import billing
import storage as objstore
from routers.media.shared import _now, _spawn_ai_image_task, db
# Tech Debt Sprint Step 2.1: Import from registries
from ai_designer.registries.layouts import PLATFORM_SIZES as _PLATFORM_SIZES_NEW, LAYOUTS as _LAYOUTS_NEW, get_canvas_size as _get_canvas_size_new
# Tech Debt Sprint Step 2.2: Import themes from registries
from ai_designer.registries.themes import (
    THEME_STYLES as _THEME_STYLES_NEW,
    THEME_META as _THEME_META_NEW,
    THEME_PACKS as _THEME_PACKS_NEW,
    THEME_WARNINGS as _THEME_WARNINGS_NEW,
    THEME_IDS as _THEME_IDS_NEW,
)
# Tech Debt Sprint Step 3: Import copy generation
from ai_designer.copy_generation import write_designer_copy as _write_designer_copy_new
# Tech Debt Sprint Step 4: Import pure helpers
from ai_designer.utils import (
    resolve_font_path as _resolve_font_path_new,
    load_font as _load_font_new,
    wrap_text as _wrap_text_new,
    map_food_to_theme as _map_food_to_theme_new,
    normalize_theme as _normalize_theme_new,
    fit_text_to_box as _fit_text_to_box_new,
)

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/ai-designer", tags=["ai-designer"])

CANVAS = 1024
VARIATION_LABELS = ["A", "B", "C", "D", "E"]  # Support up to 5 variants
RESTAURANT_BRANDING = os.environ.get("AI_DESIGNER_BRAND", "LAKEVIEW BURGERS & SEAFOOD")

# Platform-specific canvas sizes
# Tech Debt Sprint Step 2.1: Moved to ai_designer/registries/layouts.py
# Keeping old definitions commented for safety, will remove in final cleanup
# PLATFORM_SIZES = {
#     "instagram_post": (1024, 1024),
#     "instagram_story": (1080, 1920),
#     "tiktok": (1080, 1920),
#     "twitter": (1200, 675),
#     "facebook": (1200, 1200),
#     "email": (600, 600),
# }
# Use new import
PLATFORM_SIZES = _PLATFORM_SIZES_NEW

def _get_canvas_size(platform: str) -> Tuple[int, int]:
    """Return (width, height) for the given platform."""
    return _get_canvas_size_new(platform)

FONT_SERIF_BOLD   = "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"
FONT_SERIF        = "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"
FONT_SANS_BOLD    = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
FONT_SANS         = "/usr/share/fonts/truetype/freefont/FreeSans.ttf"

# Sprint 16A.1 — Display fonts for flyer-grade themes. Files live in
# /app/backend/fonts/ and are downloaded once at build time (SIL OFL / Apache).
# If a file is missing at runtime, `_resolve_font_path()` falls back to the
# matching FreeFont so the composer never crashes — themes just look closer
# to their legacy form on that machine.
_FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
FONT_BEBAS_NEUE       = str(_FONT_DIR / "BebasNeue-Regular.ttf")
FONT_BUNGEE           = str(_FONT_DIR / "Bungee-Regular.ttf")
FONT_PERMANENT_MARKER = str(_FONT_DIR / "PermanentMarker-Regular.ttf")

# Fallback chain: each display font maps to the closest FreeFont so the
# layout still looks deliberate when a display font is unavailable.
_FONT_FALLBACKS = {
    FONT_BEBAS_NEUE:       FONT_SANS_BOLD,
    FONT_BUNGEE:           FONT_SANS_BOLD,
    FONT_PERMANENT_MARKER: FONT_SERIF_BOLD,
}


def _resolve_font_path(path: str) -> str:
    """Return `path` if the font file exists; otherwise return the registered
    fallback. Tested at every theme resolution so a missing font file
    degrades gracefully instead of crashing.

    Tech Debt Sprint Step 4: now delegates to ai_designer.utils.resolve_font_path
    (kept as shim to preserve internal call sites until Step 5/6 land).
    """
    return _resolve_font_path_new(path)


# ---------------------------------------------------------------- Theme styles
# Sprint 16F — Themes now live in `/app/backend/theme_packs/` (one file per
# industry pack). The registry below dynamically loads + validates them at
# import time. `THEME_STYLES` keeps its original shape so the rest of this
# module + the existing test suite continue to work unchanged.
#
# To add a new theme: edit (or create) a `<name>_pack.py` under theme_packs/
# and add it to `theme_packs.__init__._PACK_MODULES`. No edits here required.

# Tech Debt Sprint Step 2.2: Themes now imported from registries
# Old import kept commented for safety:
# from theme_packs import THEME_STYLES, THEME_META, PACKS as THEME_PACKS, WARNINGS as _THEME_WARNINGS
# Use new registry imports:
THEME_STYLES = _THEME_STYLES_NEW
THEME_META = _THEME_META_NEW
THEME_PACKS = _THEME_PACKS_NEW
_THEME_WARNINGS = _THEME_WARNINGS_NEW

THEME_IDS = _THEME_IDS_NEW

if _THEME_WARNINGS:
    logger.warning("[ai-designer] theme pack warnings: %s", "; ".join(_THEME_WARNINGS))

# Three layout templates so each variation FEELS distinct beyond just the background.
# Tech Debt Sprint Step 2.1: Moved to ai_designer/registries/layouts.py
# LAYOUTS = ["centered", "asym_left", "stacked"]
LAYOUTS = _LAYOUTS_NEW


# ---------------------------------------------------------------- Schemas

class EstimateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    theme: constr(min_length=2, max_length=20) = "modern"


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_asset_id: constr(min_length=1, max_length=64)
    item_name: constr(min_length=1, max_length=120)
    features: List[constr(max_length=80)] = Field(default_factory=list)
    price: Optional[constr(max_length=40)] = None
    theme: constr(min_length=2, max_length=40) = "modern"
    auto_copy: bool = False
    # Sprint 15B.3: rembg/background removal is now OPT-IN. Default is False
    # so normal generation uses a rounded-rect fallback mask — eliminates the
    # ~5-15s synchronous rembg call per job that was wedging the single-worker
    # production pod. Users can enable it via the "Remove background" checkbox.
    remove_background: bool = False
    # Sprint 17B — Smart Menu Workflow: persist the menu-item slug on every
    # generated asset so the Library can filter by menu item and the
    # Creative Director can learn from favorited flyers per dish.
    item_key: Optional[constr(strip_whitespace=True, max_length=200)] = None
    # Priority 2 & 3 — Variant count and generation options
    variations: int = Field(default=3, ge=1, le=5)
    tone: Optional[constr(max_length=40)] = None
    marketing_goal: Optional[constr(max_length=60)] = None
    caption_length: Optional[constr(max_length=20)] = None
    platform: Optional[constr(max_length=40)] = None
    cta: Optional[constr(max_length=60)] = None
    include_price: bool = True
    include_description: bool = True
    # Priority 4.1 — Logo placement
    logo_url: Optional[constr(max_length=500)] = None
    logo_placement: Optional[constr(max_length=40)] = "none"
    logo_size: Optional[constr(max_length=20)] = "medium"
    # Priority 4.2 — Background customization was reverted to keep the Tech Debt
    # Sprint deploy-safe. The `background_type` field is intentionally removed
    # from this schema; `extra="ignore"` ensures any legacy callers still send-
    # ing it won't break. Re-introduce after Step 6 lands.


class SaveTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    variation_index: int = Field(ge=0, le=2)
    note: Optional[constr(max_length=200)] = None


# ---------------------------------------------------------------- Helpers

def _map_food_to_theme(food_type: str) -> str:
    """Phase 5: Restaurant Intelligence - Map detected food to recommended theme.

    Tech Debt Sprint Step 4: delegates to ai_designer.utils.map_food_to_theme.
    """
    return _map_food_to_theme_new(food_type)

async def _get_active_asset(asset_id: str) -> Dict[str, Any]:
    asset = await db.media_assets.find_one({"id": asset_id, "status": "active"}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Source image not found")
    if asset.get("kind") != "image":
        raise HTTPException(status_code=400, detail="Source asset must be an image")
    return asset


def _normalize_theme(theme: str) -> str:
    """Validate `theme` against the active theme registry; raise 400 if unknown.

    Tech Debt Sprint Step 4: pure check now lives in ai_designer.utils.normalize_theme.
    This wrapper preserves the HTTP error contract for route handlers.
    """
    valid = _normalize_theme_new(theme, THEME_STYLES)
    if valid is None:
        raise HTTPException(status_code=400, detail=f"Unknown theme. Pick from: {THEME_IDS}")
    return valid


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """Tech Debt Sprint Step 4: delegates to ai_designer.utils.load_font."""
    return _load_font_new(path, size)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    """Word-wrap `text` so each line fits within `max_w` pixels.

    Tech Debt Sprint Step 4: delegates to ai_designer.utils.wrap_text.
    """
    return _wrap_text_new(draw, text, font, max_w)


# ---------------------------------------------------------------- Background generation


def _pil_background(theme_id: str, variant_idx: int) -> bytes:
    """Render a deterministic decorative background for a theme + variant.

    `variant_idx` (0/1/2) selects between three PIL pattern variants per theme.
    PIL output is always crisp — no AI image generation involved.

    Sprint 16F dispatch:
      * If the theme defines a callable `background_fn`, we call it with
        `(canvas, draw, variant_idx)` and let the pack module own the
        whole render. This is how the new burger/seafood/game_day/seasonal
        packs ship without touching this router.
      * Otherwise we fall through to the inline branches below (classic +
        flyer-grade themes shipped before 16F).
    """
    style = THEME_STYLES[theme_id]
    bg_color = style["bg_color"]
    accent = style["title"]["color"]
    canvas = Image.new("RGB", (CANVAS, CANVAS), bg_color)
    draw = ImageDraw.Draw(canvas, "RGBA")

    bg_fn = style.get("background_fn")
    if callable(bg_fn):
        bg_fn(canvas, draw, variant_idx)
        out = io.BytesIO()
        canvas.save(out, "PNG", optimize=True)
        return out.getvalue()

    if theme_id == "luxury":
        # Dark gradient + gold filigree corners
        _radial_gradient(canvas, (28, 24, 18), (8, 8, 8), CANVAS // 2, int(CANVAS * 0.52), int(CANVAS * 0.7))
        if variant_idx == 0:
            _corner_frame(draw, accent, thickness=4, inset=70)
            _corner_ornaments(draw, accent, size=120)
        elif variant_idx == 1:
            _diagonal_ribbon(draw, accent + (170,), corner="tr", width=180)
            _diagonal_ribbon(draw, accent + (170,), corner="bl", width=180)
        else:
            _marble_veins(canvas, accent + (90,), count=4)
    elif theme_id == "vintage":
        if variant_idx == 0:
            _checker_strip(draw, (160, 30, 30), (255, 245, 215), y=0, h=40, square=40)
            _checker_strip(draw, (160, 30, 30), (255, 245, 215), y=CANVAS - 40, h=40, square=40)
        elif variant_idx == 1:
            for x in (0, CANVAS - 90):
                draw.rectangle((x, 0, x + 90, CANVAS), fill=(160, 30, 30, 220))
                for sy in range(0, CANVAS, 40):
                    draw.rectangle((x, sy, x + 90, sy + 20), fill=(255, 245, 215, 120))
        else:
            # Curved burgundy frame
            for inset in (60, 70, 80):
                draw.rounded_rectangle((inset, inset, CANVAS - inset, CANVAS - inset),
                                       radius=60, outline=(160, 30, 30, 220), width=4)
            _corner_dots(draw, (160, 30, 30, 220), size=12, count=8, edge=70)
    elif theme_id == "modern":
        _radial_gradient(canvas, (252, 250, 245), (235, 230, 220), CANVAS // 2, int(CANVAS * 0.55), int(CANVAS * 0.8))
        if variant_idx == 0:
            draw.rectangle((60, 60, CANVAS - 60, CANVAS - 60), outline=(24, 28, 48, 220), width=2)
        elif variant_idx == 1:
            for off in (60, 78):
                draw.line((CANVAS - off, CANVAS - off - 220, CANVAS - off, CANVAS - off), fill=(215, 195, 130, 220), width=3)
                draw.line((CANVAS - off - 220, CANVAS - off, CANVAS - off, CANVAS - off), fill=(215, 195, 130, 220), width=3)
        else:
            # Olive branch line drawing top-left
            _olive_branch(draw, (95, 130, 95, 220), x=90, y=90, size=260)
    elif theme_id == "social":
        _linear_gradient(canvas, (255, 215, 110), (255, 150, 70), vertical=True)
        if variant_idx == 0:
            _confetti(draw, [(255, 100, 70, 200), (255, 255, 255, 180), (255, 200, 60, 200)], count=70, edge_only=True)
        elif variant_idx == 1:
            for r in (260, 220, 180, 140):
                draw.ellipse((CANVAS // 2 - r, int(CANVAS * 0.4) - r, CANVAS // 2 + r, int(CANVAS * 0.4) + r),
                             outline=(255, 255, 255, 60), width=3)
        else:
            # Wavy red ribbon top-right
            _wavy_ribbon(draw, (220, 50, 50, 220), start=(CANVAS - 320, 60), end=(CANVAS - 40, 220), width=48)
    elif theme_id == "cajun":
        _radial_gradient(canvas, (90, 50, 25), (40, 20, 10), CANVAS // 2, int(CANVAS * 0.55), int(CANVAS * 0.85))
        if variant_idx == 0:
            _confetti(draw, [(220, 130, 40, 170), (245, 210, 80, 130)], count=80, edge_only=True)
        elif variant_idx == 1:
            # Diagonal split forest-green/burnt-orange
            draw.polygon([(0, 0), (CANVAS, 0), (CANVAS, CANVAS // 3), (0, CANVAS * 2 // 3)],
                         fill=(60, 80, 50, 200))
            # Faint cypress branches
            _olive_branch(draw, (245, 210, 80, 140), x=80, y=CANVAS - 280, size=220)
            _olive_branch(draw, (245, 210, 80, 140), x=CANVAS - 260, y=120, size=200)
        else:
            # Bay leaves border
            for sx in (0, CANVAS - 80):
                for sy in range(0, CANVAS, 130):
                    _olive_branch(draw, (245, 210, 80, 150), x=sx + 10, y=sy + 10, size=90)
    # ---------------- Sprint 16A flyer-grade themes ----------------
    elif theme_id == "comic_pop":
        # Black canvas, big yellow zap energy. Top headline band always present.
        draw.rectangle((0, 0, CANVAS, 260), fill=(20, 20, 24))
        if variant_idx == 0:
            _halftone_dots(draw, (240, 60, 110, 200), start_xy=(CANVAS - 380, 0), end_xy=(CANVAS, 380), spacing=22, max_r=8)
            _lightning_bolt(draw, (255, 235, 70, 240), tip=(CANVAS - 80, 200), size=140)
        elif variant_idx == 1:
            _halftone_dots(draw, (255, 235, 70, 180), start_xy=(0, CANVAS - 360), end_xy=(380, CANVAS), spacing=22, max_r=8)
            _speed_lines(draw, (255, 235, 70, 230), origin=(80, CANVAS // 2), count=14, length=220)
        else:
            _lightning_bolt(draw, (240, 60, 110, 240), tip=(70, 220), size=120)
            _lightning_bolt(draw, (255, 235, 70, 240), tip=(CANVAS - 70, CANVAS - 220), size=120)
    elif theme_id == "vintage_diner":
        # Cream backdrop + green checker border top/bottom + red star accents.
        _checker_strip(draw, (35, 90, 50), (244, 232, 200), y=0, h=50, square=50)
        _checker_strip(draw, (35, 90, 50), (244, 232, 200), y=CANVAS - 50, h=50, square=50)
        if variant_idx == 0:
            for cx, cy in [(120, 130), (CANVAS - 120, 130), (120, CANVAS - 130), (CANVAS - 120, CANVAS - 130)]:
                _star(draw, (180, 50, 40, 240), cx=cx, cy=cy, r=22)
        elif variant_idx == 1:
            draw.rounded_rectangle((80, 80, CANVAS - 80, CANVAS - 80), radius=24,
                                   outline=(180, 50, 40, 230), width=5)
        else:
            _distressed_grain(canvas, (35, 90, 50, 18), density=900)
    elif theme_id == "bold_purple_pop":
        # Deep purple base + magenta-to-yellow halftone gradient corners.
        _radial_gradient(canvas, (60, 28, 90), (26, 12, 50), CANVAS // 2, int(CANVAS * 0.45), int(CANVAS * 0.85))
        if variant_idx == 0:
            _halftone_dots(draw, (240, 60, 140, 220), start_xy=(CANVAS - 420, 0), end_xy=(CANVAS, 420), spacing=24, max_r=10)
            _lightning_bolt(draw, (255, 240, 100, 240), tip=(CANVAS - 90, 230), size=150)
        elif variant_idx == 1:
            _halftone_dots(draw, (255, 240, 100, 200), start_xy=(0, CANVAS - 420), end_xy=(420, CANVAS), spacing=24, max_r=10)
            _speed_lines(draw, (240, 60, 140, 220), origin=(CANVAS - 80, 120), count=12, length=200)
        else:
            _lightning_bolt(draw, (255, 240, 100, 240), tip=(90, 200), size=130)
            _lightning_bolt(draw, (240, 60, 140, 240), tip=(CANVAS - 90, CANVAS - 200), size=130)
    elif theme_id == "casual_teal":
        # Soft teal backdrop + brush squiggle + cream accents.
        _radial_gradient(canvas, (185, 230, 222), (140, 200, 195), CANVAS // 2, int(CANVAS * 0.55), int(CANVAS * 0.85))
        if variant_idx == 0:
            _squiggle(draw, (220, 110, 60, 220), start=(120, 230), end=(CANVAS - 120, 230), amplitude=18, segments=10, width=6)
        elif variant_idx == 1:
            for cx, cy in [(150, 150), (CANVAS - 150, CANVAS - 150)]:
                _sparks(draw, (250, 245, 230, 230), cx=cx, cy=cy, rays=8, length=44)
        else:
            _squiggle(draw, (250, 245, 230, 230), start=(80, CANVAS - 220), end=(CANVAS - 80, CANVAS - 220), amplitude=14, segments=12, width=5)
            _squiggle(draw, (220, 110, 60, 220), start=(80, 230), end=(CANVAS - 80, 230), amplitude=14, segments=12, width=5)
    elif theme_id == "distressed_orange":
        # Burnt orange + heavy distressed grain + black brush stamps.
        canvas.paste(Image.new("RGB", canvas.size, (200, 80, 35)))
        _distressed_grain(canvas, (40, 25, 20, 38), density=2200)
        if variant_idx == 0:
            _brush_stamp(draw, (40, 25, 20, 230), x=60, y=60, w=CANVAS - 120, h=130)
        elif variant_idx == 1:
            _brush_stamp(draw, (252, 240, 215, 200), x=80, y=CANVAS - 200, w=CANVAS - 160, h=130)
            for cx, cy in [(120, 200), (CANVAS - 120, 200)]:
                _star(draw, (252, 240, 215, 230), cx=cx, cy=cy, r=20)
        else:
            _brush_stamp(draw, (40, 25, 20, 230), x=60, y=60, w=CANVAS - 120, h=120)
            _brush_stamp(draw, (40, 25, 20, 230), x=60, y=CANVAS - 180, w=CANVAS - 120, h=120)

    out = io.BytesIO()
    canvas.save(out, "PNG", optimize=True)
    return out.getvalue()


# ---- PIL background primitives ------------------------------------------------

# ---- Sprint 16A flyer-grade decorative primitives ----
# All accept an ImageDraw or Image and draw in-place. Designed for the new
# flyer themes (comic_pop, vintage_diner, bold_purple_pop, casual_teal,
# distressed_orange). No external assets; everything is generated with PIL.

def _halftone_dots(draw: ImageDraw.ImageDraw, color: Tuple[int, int, int, int],
                   start_xy: Tuple[int, int], end_xy: Tuple[int, int],
                   spacing: int = 24, max_r: int = 8) -> None:
    """Halftone gradient dots filling a rectangular zone — denser near the
    near corner, sparser away. Color must be RGBA."""
    x1, y1 = start_xy
    x2, y2 = end_xy
    diag = max(1.0, ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)
    for x in range(x1, x2, spacing):
        for y in range(y1, y2, spacing):
            d = ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
            t = 1.0 - (d / diag)
            r = max(1, int(max_r * t))
            draw.ellipse((x - r, y - r, x + r, y + r), fill=color)


def _lightning_bolt(draw: ImageDraw.ImageDraw, color: Tuple[int, int, int, int],
                    tip: Tuple[int, int], size: int = 140) -> None:
    """Classic Z-shaped bolt anchored at `tip` (bottom point)."""
    cx, cy = tip
    pts = [
        (cx,                 cy),
        (cx - int(size * 0.35), cy - int(size * 0.55)),
        (cx + int(size * 0.05), cy - int(size * 0.45)),
        (cx - int(size * 0.20), cy - size),
        (cx + int(size * 0.30), cy - int(size * 0.45)),
        (cx - int(size * 0.05), cy - int(size * 0.55)),
        (cx + int(size * 0.18), cy - int(size * 0.20)),
    ]
    draw.polygon(pts, fill=color)


def _speed_lines(draw: ImageDraw.ImageDraw, color: Tuple[int, int, int, int],
                 origin: Tuple[int, int], count: int = 12, length: int = 200) -> None:
    """Radial speed lines (comic-style) emanating from `origin`."""
    import math
    ox, oy = origin
    for i in range(count):
        ang = (math.pi * 2 / count) * i
        x2 = int(ox + math.cos(ang) * length)
        y2 = int(oy + math.sin(ang) * length)
        draw.line((ox, oy, x2, y2), fill=color, width=3)


def _star(draw: ImageDraw.ImageDraw, color: Tuple[int, int, int, int],
          cx: int, cy: int, r: int = 20) -> None:
    """5-point star, filled."""
    import math
    pts = []
    for i in range(10):
        ang = math.pi / 2 + (math.pi * 2 / 10) * i
        rr = r if i % 2 == 0 else int(r * 0.45)
        pts.append((cx + int(math.cos(ang) * rr), cy - int(math.sin(ang) * rr)))
    draw.polygon(pts, fill=color)


def _squiggle(draw: ImageDraw.ImageDraw, color: Tuple[int, int, int, int],
              start: Tuple[int, int], end: Tuple[int, int],
              amplitude: int = 18, segments: int = 12, width: int = 5) -> None:
    """Hand-drawn-feeling wavy line between two points."""
    import math
    x1, y1 = start
    x2, y2 = end
    pts = []
    for s in range(segments + 1):
        t = s / segments
        bx = x1 + (x2 - x1) * t
        by = y1 + (y2 - y1) * t + math.sin(t * math.pi * 3) * amplitude
        pts.append((int(bx), int(by)))
    for i in range(len(pts) - 1):
        draw.line((pts[i], pts[i + 1]), fill=color, width=width)


def _sparks(draw: ImageDraw.ImageDraw, color: Tuple[int, int, int, int],
            cx: int, cy: int, rays: int = 8, length: int = 40) -> None:
    """Star-burst rays (like a hand-drawn pop accent)."""
    import math
    for i in range(rays):
        ang = (math.pi * 2 / rays) * i
        x2 = int(cx + math.cos(ang) * length)
        y2 = int(cy + math.sin(ang) * length)
        draw.line((cx, cy, x2, y2), fill=color, width=4)


def _distressed_grain(canvas: Image.Image, color: Tuple[int, int, int, int],
                      density: int = 1200) -> None:
    """Sprinkle small specks across the canvas for a worn / aged look."""
    import random
    random.seed(density + color[0])
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for _ in range(density):
        x = random.randint(0, CANVAS - 1)
        y = random.randint(0, CANVAS - 1)
        s = random.choice((1, 1, 1, 2))
        od.rectangle((x, y, x + s, y + s), fill=color)
    canvas.paste(overlay, (0, 0), overlay)


def _brush_stamp(draw: ImageDraw.ImageDraw, color: Tuple[int, int, int, int],
                 x: int, y: int, w: int, h: int) -> None:
    """A ragged-edge rectangle that reads as a brush-painted block — good
    for layering distressed headline plates."""
    import random
    random.seed(x + y + w + h)
    draw.rectangle((x, y, x + w, y + h), fill=color)
    # Add jagged edges by painting thin slivers of background back over the
    # top/bottom — easier than computing a true alpha mask, and matches the
    # distressed-orange / vintage-diner aesthetic.
    bg = (255, 255, 255, 0)  # transparent — we'll just punch holes
    for _ in range(40):
        ex = random.randint(x - 6, x + w + 6)
        ew = random.randint(8, 28)
        et = random.randint(0, 1)
        if et == 0:
            draw.rectangle((ex, y - random.randint(2, 10), ex + ew, y + random.randint(0, 6)), fill=bg)
        else:
            draw.rectangle((ex, y + h - random.randint(0, 6), ex + ew, y + h + random.randint(2, 10)), fill=bg)


def _radial_gradient(canvas: Image.Image, inner_rgb: Tuple[int, int, int],
                     outer_rgb: Tuple[int, int, int], cx: int, cy: int, r: int) -> None:
    """Paint a soft radial gradient in-place on the canvas."""
    overlay = Image.new("RGBA", canvas.size, outer_rgb + (255,))
    mask = Image.new("L", canvas.size, 0)
    md = ImageDraw.Draw(mask)
    steps = 16
    for i in range(steps, 0, -1):
        rr = int(r * (i / steps))
        md.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=int(255 * (1 - i / steps)))
    mask = mask.filter(ImageFilter.GaussianBlur(20))
    inner = Image.new("RGBA", canvas.size, inner_rgb + (255,))
    composite = Image.composite(inner, overlay, mask)
    canvas.paste(composite.convert("RGB"), (0, 0))


def _linear_gradient(canvas: Image.Image, c1: Tuple[int, int, int], c2: Tuple[int, int, int],
                     vertical: bool = True) -> None:
    grad = Image.new("RGB", (1, CANVAS) if vertical else (CANVAS, 1))
    px = grad.load()
    for i in range(CANVAS):
        t = i / (CANVAS - 1)
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        if vertical:
            px[0, i] = (r, g, b)
        else:
            px[i, 0] = (r, g, b)
    grad = grad.resize((CANVAS, CANVAS), Image.LANCZOS)
    canvas.paste(grad, (0, 0))


def _corner_frame(draw: ImageDraw.ImageDraw, color: Tuple[int, int, int],
                  thickness: int = 4, inset: int = 70, corner_len: int = 180) -> None:
    """Draw 4 L-shaped corner brackets."""
    c = color + (240,) if len(color) == 3 else color
    coords = [
        (inset, inset, inset + corner_len, inset, inset, inset + corner_len),  # TL
        (CANVAS - inset - corner_len, inset, CANVAS - inset, inset, CANVAS - inset, inset + corner_len),  # TR
        (inset, CANVAS - inset - corner_len, inset, CANVAS - inset, inset + corner_len, CANVAS - inset),  # BL
        (CANVAS - inset - corner_len, CANVAS - inset, CANVAS - inset, CANVAS - inset, CANVAS - inset, CANVAS - inset - corner_len),
    ]
    for cx1, cy1, cx2, cy2, cx3, cy3 in coords:
        draw.line((cx1, cy1, cx2, cy2), fill=c, width=thickness)
        draw.line((cx2, cy2, cx3, cy3), fill=c, width=thickness)


def _corner_ornaments(draw: ImageDraw.ImageDraw, color: Tuple[int, int, int], size: int = 120) -> None:
    """Small decorative diamonds in each corner."""
    c = color + (180,) if len(color) == 3 else color
    inset = 100
    for cx, cy in [(inset, inset), (CANVAS - inset, inset), (inset, CANVAS - inset), (CANVAS - inset, CANVAS - inset)]:
        s = size // 6
        draw.polygon([(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)], outline=c, width=2)


def _diagonal_ribbon(draw: ImageDraw.ImageDraw, color: Tuple[int, int, int, int],
                     corner: str, width: int = 160) -> None:
    if corner == "tr":
        points = [(CANVAS - width, 0), (CANVAS, 0), (CANVAS, width), (CANVAS - width // 2, width // 2)]
    elif corner == "bl":
        points = [(0, CANVAS - width), (width, CANVAS), (0, CANVAS), (0, CANVAS - width)]
    else:
        return
    draw.polygon(points, fill=color)


def _marble_veins(canvas: Image.Image, color: Tuple[int, int, int, int], count: int = 4) -> None:
    import random
    random.seed(count + sum(color[:3]))
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for _ in range(count):
        x1, y1 = random.randint(0, CANVAS), random.randint(0, CANVAS // 3)
        x2, y2 = random.randint(0, CANVAS), random.randint(CANVAS * 2 // 3, CANVAS)
        od.line((x1, y1, x2, y2), fill=color, width=2)
    overlay = overlay.filter(ImageFilter.GaussianBlur(1))
    canvas.paste(overlay, (0, 0), overlay)


def _checker_strip(draw: ImageDraw.ImageDraw, c1: Tuple[int, int, int], c2: Tuple[int, int, int],
                   y: int, h: int, square: int = 40) -> None:
    for i, sx in enumerate(range(0, CANVAS, square)):
        color = c1 if i % 2 == 0 else c2
        draw.rectangle((sx, y, sx + square, y + h), fill=color + (255,) if len(color) == 3 else color)


def _corner_dots(draw: ImageDraw.ImageDraw, color, size: int = 10, count: int = 8, edge: int = 70) -> None:
    import random
    random.seed(count)
    for _ in range(count * 4):
        edge_choice = random.choice(["t", "b", "l", "r"])
        if edge_choice == "t":
            x, y = random.randint(edge, CANVAS - edge), random.randint(20, edge - 10)
        elif edge_choice == "b":
            x, y = random.randint(edge, CANVAS - edge), random.randint(CANVAS - edge + 10, CANVAS - 20)
        elif edge_choice == "l":
            x, y = random.randint(20, edge - 10), random.randint(edge, CANVAS - edge)
        else:
            x, y = random.randint(CANVAS - edge + 10, CANVAS - 20), random.randint(edge, CANVAS - edge)
        draw.ellipse((x - size, y - size, x + size, y + size), fill=color)


def _olive_branch(draw: ImageDraw.ImageDraw, color, x: int, y: int, size: int = 200) -> None:
    """Stylized leafy branch line drawing."""
    end_x, end_y = x + int(size * 0.85), y + size
    draw.line((x, y, end_x, end_y), fill=color, width=3)
    for i in range(6):
        t = (i + 1) / 7.0
        mx = int(x + (end_x - x) * t)
        my = int(y + (end_y - y) * t)
        leaf_dx, leaf_dy = (40 if i % 2 == 0 else -40, 20 if i % 2 == 0 else -20)
        # Normalize bbox so x1>=x0, y1>=y0 regardless of leaf direction
        bx0, by0 = mx - 16, my - 8
        bx1, by1 = mx + leaf_dx + 16, my + leaf_dy + 8
        if bx1 < bx0:
            bx0, bx1 = bx1, bx0
        if by1 < by0:
            by0, by1 = by1, by0
        draw.ellipse((bx0, by0, bx1, by1), outline=color, width=2)


def _confetti(draw: ImageDraw.ImageDraw, palette, count: int = 60, edge_only: bool = False) -> None:
    import random
    random.seed(count + len(palette))
    for _ in range(count):
        if edge_only:
            band = random.choice(["t", "b", "l", "r"])
            if band == "t":
                x, y = random.randint(20, CANVAS - 20), random.randint(20, 140)
            elif band == "b":
                x, y = random.randint(20, CANVAS - 20), random.randint(CANVAS - 140, CANVAS - 20)
            elif band == "l":
                x, y = random.randint(20, 140), random.randint(20, CANVAS - 20)
            else:
                x, y = random.randint(CANVAS - 140, CANVAS - 20), random.randint(20, CANVAS - 20)
        else:
            x, y = random.randint(0, CANVAS), random.randint(0, CANVAS)
        s = random.randint(6, 16)
        color = random.choice(palette)
        if random.random() < 0.6:
            draw.ellipse((x - s, y - s, x + s, y + s), fill=color)
        else:
            draw.rectangle((x - s, y - s, x + s, y + s), fill=color)


def _wavy_ribbon(draw: ImageDraw.ImageDraw, color, start, end, width: int = 40) -> None:
    """A rough wavy ribbon from start to end."""
    import math
    points = []
    sx, sy = start
    ex, ey = end
    length = max(1, int(math.hypot(ex - sx, ey - sy)))
    for i in range(length):
        t = i / length
        x = int(sx * (1 - t) + ex * t)
        y = int(sy * (1 - t) + ey * t + math.sin(t * 3.14159 * 4) * 20)
        points.append((x, y))
    for (x, y) in points:
        draw.ellipse((x - width // 2, y - width // 2, x + width // 2, y + width // 2), fill=color)


# ---------------------------------------------------------------- Food preparation

def _prepare_food_cutout(food_bytes: bytes, target_max: int, use_rembg: bool = False) -> Image.Image:
    """Return RGBA food image cropped to the food's actual bounding box, scaled
    so the longest side equals `target_max`.

    Sprint 15B.3: rembg is now OPT-IN via `use_rembg`. When False (default), we
    skip the expensive rembg call entirely.
    Sprint 16G: the hard rounded-rect mask is replaced with `feather_mask`, a
    soft elliptical alpha mask that fades the photo edges into the canvas
    instead of clipping them. The rembg path still benefits — rembg produces
    a hard cutout silhouette which we then feather slightly to soften the
    cut-line halo.
    """
    from render_engine import feather_mask

    src = Image.open(io.BytesIO(food_bytes)).convert("RGBA")
    if use_rembg:
        try:
            from rembg import remove  # lazy import — only paid when explicitly opted in
            out = remove(food_bytes)
            cut = Image.open(io.BytesIO(out)).convert("RGBA")
            # Light feather to soften any rembg edge halo (keeps the cutout shape).
            cut = feather_mask(cut, radius_pct=0.04, feather_blur_pct=0.015)
        except Exception as e:  # noqa: BLE001
            logger.warning("[ai-designer] rembg failed (%s); falling back to feather mask", e)
            cut = feather_mask(src, radius_pct=0.18, feather_blur_pct=0.07)
    else:
        # Sprint 16G — soft edge fade only on outermost ~25 px so the rectangle
        # disappears but the food stays photographic.
        cut = feather_mask(src, radius_pct=0.06, feather_blur_pct=0.025)

    # Crop to the actual visible (non-transparent) bounding box so we scale to the
    # food, not the surrounding empty pixels.
    bbox = cut.getbbox()
    if bbox:
        cut = cut.crop(bbox)

    # Scale to target_max
    if cut.width == 0 or cut.height == 0:
        return cut
    scale = target_max / max(cut.width, cut.height)
    new_w, new_h = max(1, int(cut.width * scale)), max(1, int(cut.height * scale))
    return cut.resize((new_w, new_h), Image.LANCZOS)


def _variant_food_transform(food_rgba: Image.Image, variant_idx: int) -> Image.Image:
    """Sprint 22 P0 Fix 2 — apply a deterministic per-variant treatment to the
    food cutout so the 3 generated flyers are visibly different even when the
    underlying renderer (agency template / HTML / procedural) ignores the
    variant index.

    Variants:
      v0 — pass-through (the canonical "hero" crop)
      v1 — 15% zoom-in (tighter crop centred on the food)
      v2 — 8% zoom-out + warm tone shift (wider angle feel)

    Always returns a NEW Image — callers may mutate freely.
    """
    if variant_idx <= 0:
        return food_rgba.copy()

    w, h = food_rgba.size
    if w == 0 or h == 0:
        return food_rgba.copy()

    if variant_idx == 1:
        # v1: zoom in 15% (crop 7.5% from each edge, then resize back to original).
        zoom = 0.15
        dx, dy = int(w * zoom / 2), int(h * zoom / 2)
        cropped = food_rgba.crop((dx, dy, w - dx, h - dy))
        return cropped.resize((w, h), Image.LANCZOS)

    # v2: zoom out 8% (paste onto a transparent canvas 8% larger, recenter,
    # then resize back). Then apply a light warm tone shift on the RGB
    # channels to give a "wider, warmer" feel.
    zoom = 0.08
    pad_w, pad_h = int(w * zoom / 2), int(h * zoom / 2)
    canvas = Image.new("RGBA", (w + pad_w * 2, h + pad_h * 2), (0, 0, 0, 0))
    canvas.paste(food_rgba, (pad_w, pad_h), food_rgba if food_rgba.mode == "RGBA" else None)
    canvas = canvas.resize((w, h), Image.LANCZOS)

    # Warm tone shift: nudge R up, B down a touch. Keep alpha untouched.
    r, g, b, a = canvas.split()
    r = r.point(lambda v: min(255, int(v * 1.08)))
    b = b.point(lambda v: max(0, int(v * 0.94)))
    return Image.merge("RGBA", (r, g, b, a))


def _rounded_rect_mask(im: Image.Image, radius_pct: float = 0.08) -> Image.Image:
    """Apply a rounded-rect alpha mask to a photo. Preserves all original food pixels."""
    radius = int(min(im.width, im.height) * radius_pct)
    mask = Image.new("L", im.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=radius, fill=255)
    out = im.copy()
    out.putalpha(mask)
    return out


def _drop_shadow(im: Image.Image, blur: int = 18, opacity: int = 110, offset: Tuple[int, int] = (0, 14)) -> Image.Image:
    """Return a wider RGBA layer of `im` with a soft drop-shadow underneath."""
    pad = blur * 2
    layer = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    alpha = im.getchannel("A")
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    shadow_mask = Image.new("L", layer.size, 0)
    shadow_mask.paste(alpha, (pad + offset[0], pad + offset[1]))
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(blur))
    shadow.putalpha(shadow_mask)
    # Tint the shadow black
    black = Image.new("RGBA", layer.size, (0, 0, 0, opacity))
    shadow = Image.composite(black, shadow, shadow_mask)
    layer.alpha_composite(shadow)
    layer.alpha_composite(im, (pad, pad))
    return layer


# ---------------------------------------------------------------- Ingredient icons
# Sprint 16A.2 — small deterministic PIL glyphs drawn next to bullet text on
# flyer themes (when `theme["icons"] is True`). Each ingredient maps to one
# of 10 simple silhouettes. Keyword matching is case-insensitive and matches
# anywhere in the feature text; the first hit wins. When nothing matches,
# `_draw_bullets` falls back to the legacy text marker (e.g. "▸", "★").
#
# All icons are monochrome and rendered in the theme's `marker_color`, so
# they share the visual language of the existing bullets and stay legible
# against the decorative background. Icons fit inside a `size x size` box
# anchored at (x, y) — caller controls placement.

ICON_KEYWORDS: List[Tuple[str, str]] = [
    # specific tokens first; first hit wins
    ("burger", "burger"), ("patties", "burger"), ("patty", "burger"),
    ("american cheese", "cheese"), ("cheddar", "cheese"),
    ("mozzarella", "cheese"), ("cheese", "cheese"),
    ("onion", "onion"),
    ("aioli", "sauce"), ("ketchup", "sauce"), ("mustard", "sauce"),
    ("mayo", "sauce"), ("remoulade", "sauce"), ("sauce", "sauce"),
    ("fries", "fries"), ("fry", "fries"),
    ("shrimp", "shrimp"), ("prawn", "shrimp"),
    ("catfish", "fish"), ("salmon", "fish"), ("tuna", "fish"),
    ("cod", "fish"), ("fish", "fish"),
    ("pickled", "pickle"), ("pickle", "pickle"),
    ("soda", "drink"), ("cola", "drink"), ("beverage", "drink"),
    ("drink", "drink"),
    ("lettuce", "lettuce"), ("arugula", "lettuce"),
    ("spinach", "lettuce"), ("greens", "lettuce"),
]


def _icon_for_feature(text: str) -> Optional[str]:
    """Return the icon kind that matches `text`, or None."""
    s = (text or "").lower()
    if not s:
        return None
    for kw, kind in ICON_KEYWORDS:
        if kw in s:
            return kind
    return None


def _rgba(color) -> Tuple[int, int, int, int]:
    if isinstance(color, tuple) and len(color) == 3:
        return color + (255,)
    return color


def _icon_burger(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # Top bun (rounded hump) + patty/cheese strip + bottom bun (flat-top hump)
    th = max(4, int(s * 0.42))
    bh = max(4, int(s * 0.32))
    d.pieslice((x, y, x + s, y + th * 2), 180, 360, fill=c)
    mid_y1 = y + th + 2
    mid_y2 = y + s - bh - 2
    if mid_y2 > mid_y1:
        d.rectangle((x + s // 14, mid_y1, x + s - s // 14, mid_y2), fill=c)
    d.pieslice((x, y + s - bh * 2, x + s, y + s), 0, 180, fill=c)


def _icon_cheese(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # Wedge triangle pointing up-right
    pts = [(x, y + s - 2), (x + s - 2, y + s - 2), (x + s - 2, y + s // 5)]
    d.polygon(pts, fill=c)


def _icon_onion(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # Concentric rings — top-down view of a sliced onion
    cx, cy = x + s // 2, y + s // 2
    w = max(2, s // 22)
    for r in (s // 2 - 1, int(s * 0.36), int(s * 0.22), max(3, s // 10)):
        if r > 0:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=c, width=w)


def _icon_sauce(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # Squeeze bottle: rounded rect body + small triangle nozzle on top
    body_w = max(8, s * 3 // 5)
    body_x = x + (s - body_w) // 2
    body_y = y + s // 4
    d.rounded_rectangle(
        (body_x, body_y, body_x + body_w, y + s - 2),
        radius=max(3, s // 10), fill=c,
    )
    d.polygon(
        [(x + s * 2 // 5, body_y), (x + s * 3 // 5, body_y), (x + s // 2, y)],
        fill=c,
    )


def _icon_fries(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # 4 vertical sticks + trapezoidal holder
    hy1 = y + s * 3 // 5
    d.polygon(
        [(x + s // 8, hy1), (x + s - s // 8, hy1),
         (x + s - s // 5, y + s - 2), (x + s // 5, y + s - 2)],
        fill=c,
    )
    stick_w = max(3, s // 11)
    starts = [x + int(s * 0.22), x + int(s * 0.38),
              x + int(s * 0.54), x + int(s * 0.70)]
    tops = [y + s // 14, y, y + s // 9, y + s // 6]
    for sx, sy_top in zip(starts, tops):
        d.rectangle((sx, sy_top, sx + stick_w, hy1), fill=c)


def _icon_shrimp(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # Curved C-shape body + small tail fan on the right
    w = max(4, s // 8)
    d.arc((x + s // 10, y + s // 10, x + s - s // 4, y + s - s // 10),
          30, 330, fill=c, width=w)
    d.polygon(
        [(x + s - s // 4, y + s // 2),
         (x + s - 2, y + s // 4),
         (x + s - 2, y + s * 3 // 4)],
        fill=c,
    )


def _icon_fish(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # Oval body + triangle tail on the right
    d.ellipse((x + s // 10, y + s // 4, x + s - s // 4, y + s * 3 // 4), fill=c)
    d.polygon(
        [(x + s - s // 4 - 2, y + s // 2),
         (x + s - 2, y + s // 5),
         (x + s - 2, y + s - s // 5)],
        fill=c,
    )


def _icon_pickle(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # Vertical oval + 3 small bumps along one edge
    d.ellipse((x + s // 3, y + s // 8, x + s * 2 // 3, y + s - s // 8), fill=c)
    bump = max(3, s // 12)
    for fy in (y + s // 3, y + s // 2, y + s * 2 // 3):
        d.ellipse(
            (x + s * 2 // 3 - bump // 2, fy - bump // 2,
             x + s * 2 // 3 + bump, fy + bump),
            fill=c,
        )


def _icon_drink(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # Cup trapezoid + lid line + straw poking out the top
    cy1 = y + s // 4
    cx1, cx2 = x + s // 5, x + s - s // 5
    d.polygon(
        [(cx1, cy1), (cx2, cy1),
         (x + s - s // 4, y + s - 2), (x + s // 4, y + s - 2)],
        fill=c,
    )
    d.line((cx1 - 2, cy1, cx2 + 2, cy1), fill=c, width=max(3, s // 14))
    d.line((x + s // 2, cy1 - 2, x + s * 2 // 3, y),
           fill=c, width=max(3, s // 14))


def _icon_lettuce(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # Leaf: oval body + small notch cuts to suggest frilly edge
    d.ellipse((x + s // 8, y + s // 6, x + s - s // 8, y + s - s // 6), fill=c)
    # Frilly cuts (3 small triangles bitten out of the top edge)
    bg = (255, 255, 255, 0)
    for i in range(3):
        cx = x + s // 4 + i * (s // 4)
        d.polygon(
            [(cx - s // 14, y + s // 6),
             (cx + s // 14, y + s // 6),
             (cx, y + s // 6 + s // 10)],
            fill=bg,
        )


_ICON_DRAWERS = {
    "burger": _icon_burger,
    "cheese": _icon_cheese,
    "onion": _icon_onion,
    "sauce": _icon_sauce,
    "fries": _icon_fries,
    "shrimp": _icon_shrimp,
    "fish": _icon_fish,
    "pickle": _icon_pickle,
    "drink": _icon_drink,
    "lettuce": _icon_lettuce,
}


def _draw_ingredient_icon(canvas: Image.Image, kind: str, x: int, y: int,
                          size: int, color) -> None:
    """Draw the ingredient glyph `kind` at (x, y) within a `size x size` box."""
    fn = _ICON_DRAWERS.get(kind)
    if not fn:
        return
    draw = ImageDraw.Draw(canvas, "RGBA")
    fn(draw, x, y, size, _rgba(color))


# ---------------------------------------------------------------- Composition

def _draw_price_badge(canvas: Image.Image, theme: Dict[str, Any], price_text: str, cx: int, cy: int, radius: int) -> None:
    """Sprint 16I — Premium badge dispatcher.

    Themes can pin `theme["badge_style"]` to one of `BADGE_STYLES`; otherwise
    a style is picked deterministically per (theme_id, variant_idx) by the
    caller via the optional `theme["_badge_style"]` context key set in
    `_compose_design`. Falls back to the legacy circular sticker when no
    style is selected.
    """
    from typography_engine import draw_premium_badge
    import random

    p = theme["price"]
    style = theme.get("_badge_style") or theme.get("badge_style") or "sticker"
    font_size = max(28, radius // 2)
    f = _font(p["font"], font_size)
    bg = p["bg"] if (isinstance(p["bg"], tuple) and len(p["bg"]) == 4) else (p["bg"] + (255,) if isinstance(p["bg"], tuple) else p["bg"])
    fg = p["fg"]
    ring = p["ring"] if (isinstance(p["ring"], tuple) and len(p["ring"]) == 4) else (p["ring"] + (255,) if isinstance(p["ring"], tuple) else p["ring"])
    rng = random.Random(hash((theme.get("_theme_id", "x"), theme.get("_variant_idx", 0))) & 0xFFFFFFFF)
    draw_premium_badge(canvas, cx=cx, cy=cy, radius=radius,
                       price_text=price_text, bg=bg, fg=fg, ring=ring,
                       font=f, style=style, rng=rng)


def _draw_bullets(canvas: Image.Image, theme: Dict[str, Any], features: List[str],
                  x: int, y: int, max_w: int) -> None:
    """Draw up to 5 feature bullets.

    Sprint 16A.2 — flyer themes get PIL-drawn ingredient icons.
    Sprint 16I — themes with `icons=True` (i.e. flyer + burger + seafood +
    game_day + seasonal packs) render as horizontally-wrapping pill chips
    instead of vertical bullet lines. Looks more like a magazine spread.
    Classic themes keep the legacy bullet list for typography contrast.
    """
    if not features:
        return
    draw = ImageDraw.Draw(canvas, "RGBA")
    body = theme["body"]
    f = _font(body["font"], body["size"])

    if theme.get("icons"):
        # Sprint 16I — pill chips path.
        from typography_engine import draw_pill_chips
        chip_bg = theme.get("price", {}).get("bg", (40, 40, 40))
        chip_fg = theme.get("price", {}).get("fg", (255, 255, 255))
        if isinstance(chip_bg, tuple) and len(chip_bg) == 3:
            chip_bg = chip_bg + (220,)
        # Smaller font inside chips so they don't dominate.
        chip_font = _font(body["font"], max(20, body["size"] - 4))
        draw_pill_chips(canvas, features[:6], x=x, y=y, max_w=max_w,
                        bg=chip_bg, fg=chip_fg, font=chip_font,
                        border=body.get("marker_color"))
        return

    # Legacy bullet list (classic themes).
    line_h = body["size"] + 14
    use_icons = bool(theme.get("icons"))
    icon_size = max(28, min(40, body["size"] + 4))
    icon_color = body.get("marker_color", (255, 255, 255))
    cur_y = y
    drawn_lines = 0
    for feat in features[:5]:
        if drawn_lines >= 6:  # Cap total wrapped lines at 6 — keeps the block from running off-canvas
            break
        ty = cur_y
        icon_drawn = False
        if use_icons:
            kind = _icon_for_feature(feat)
            if kind:
                _draw_ingredient_icon(canvas, kind, x, ty + 2, icon_size, icon_color)
                text_x = x + icon_size + 10
                icon_drawn = True
        if not icon_drawn:
            marker = body["marker"]
            draw.text((x, ty), marker, fill=body["marker_color"], font=f)
            mb = draw.textbbox((0, 0), marker + " ", font=f)
            text_x = x + (mb[2] - mb[0])
        # Sprint 19 polish: draw ALL wrapped lines for this feature, not just
        # the first one. Previously long features like "Sour Cream & Jalapeños"
        # were truncated to "Sour Cream &" because only wrapped[0] was drawn.
        wrapped = _wrap_text(draw, feat, f, max_w - (text_x - x))
        for line_idx, line in enumerate(wrapped):
            if drawn_lines >= 6:
                break
            # First wrapped line uses the bullet/icon row; continuation lines
            # are indented under the text column with no marker.
            line_y = cur_y + line_idx * line_h
            draw.text((text_x, line_y), line, fill=body["color"], font=f)
            drawn_lines += 1
        cur_y += line_h * max(1, len(wrapped))


def _draw_title(canvas: Image.Image, theme: Dict[str, Any], item_name: str,
                x: int, y: int, max_w: int, align: str = "center") -> int:
    """Draw the item title; returns the y after the title block.

    Sprint 16A.1 — stroke / shadow / letter_spacing support.
    Sprint 16I — split-line headlines for 2- or 3-word titles ("Smash
    Burger" → SMASH \n BURGER) and a deterministic per-variant title
    backdrop (ribbon / swash / distressed_rect / none).
    """
    from typography_engine import split_title_lines, draw_title_backdrop, pick_title_backdrop_style
    import random

    draw = ImageDraw.Draw(canvas, "RGBA")
    t = theme["title"]

    # Sprint 16I — decide whether to stack the title.
    # Sprint 18 — apply personality.title_oversize to scale fonts further.
    personality = theme.get("personality") or {}
    oversize = float(personality.get("title_oversize", 1.0))
    forced_lines = split_title_lines(item_name)
    if len(forced_lines) > 1:
        # Bump the per-line size since each line is much shorter.
        f = _font(t["font"], int(t["size"] * 1.12 * oversize))
        lines = forced_lines
    else:
        f = _font(t["font"], int(t["size"] * oversize))
        lines = _wrap_text(draw, item_name, f, max_w)

    stroke_w = t.get("stroke_width", 0)
    stroke_fill = t.get("stroke_fill")
    shadow = t.get("shadow")
    letter_spacing = t.get("letter_spacing", 0)

    # Sprint 16I — backdrop behind each title line (optional, theme-locked
    # variant). Drawn BEFORE the text so it sits behind glyphs.
    # Sprint 18 — personality-driven backdrop pool when available.
    backdrop_style = theme.get("_title_backdrop") or pick_title_backdrop_style(
        theme.get("_theme_id", "x"), theme.get("_variant_idx", 0),
        personality=theme.get("personality"),
    )
    # Disable backdrop entirely if the theme opts out.
    if theme.get("disable_title_backdrop"):
        backdrop_style = "none"

    cur_y = y
    line_height_px = (f.size if hasattr(f, "size") else t["size"]) + 8
    rng = random.Random(hash((theme.get("_theme_id", "x"), theme.get("_variant_idx", 0))) & 0xFFFFFFFF)

    for line in lines:
        if letter_spacing:
            glyph_widths = [draw.textbbox((0, 0), ch, font=f)[2] for ch in line]
            lw = sum(glyph_widths) + letter_spacing * max(0, len(line) - 1)
        else:
            bbox = draw.textbbox((0, 0), line, font=f)
            lw = bbox[2] - bbox[0]
        if align == "center":
            lx = x + (max_w - lw) // 2
        elif align == "right":
            lx = x + (max_w - lw)
        else:
            lx = x

        # Sprint 16I — Draw backdrop behind the line. Slightly wider than the
        # text bounds so it reads as an intentional banner.
        if backdrop_style != "none":
            pad_x = max(18, line_height_px // 3)
            pad_y = max(8, line_height_px // 6)
            backdrop_color = stroke_fill if stroke_fill else theme.get("price", {}).get("bg", (40, 40, 40))
            draw_title_backdrop(
                canvas,
                x=lx - pad_x, y=cur_y - pad_y // 2,
                w=lw + pad_x * 2, h=line_height_px,
                style=backdrop_style, color=backdrop_color, rng=rng,
            )

        # Shadow (offset down-right, behind the stroke).
        if shadow:
            sx, sy = lx + 4, cur_y + 5
            if letter_spacing:
                _draw_spaced(draw, line, f, sx, sy, letter_spacing, fill=shadow)
            else:
                draw.text((sx, sy), line, fill=shadow, font=f)

        # Main glyph pass — with optional stroke for chunky headlines.
        if letter_spacing:
            _draw_spaced(draw, line, f, lx, cur_y, letter_spacing,
                         fill=t["color"], stroke_width=stroke_w,
                         stroke_fill=stroke_fill)
        else:
            kwargs = {"fill": t["color"], "font": f}
            if stroke_w and stroke_fill:
                kwargs["stroke_width"] = stroke_w
                kwargs["stroke_fill"] = stroke_fill
            draw.text((lx, cur_y), line, **kwargs)
        cur_y += line_height_px
    return cur_y


def _draw_spaced(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                 x: int, y: int, spacing: int, *, fill,
                 stroke_width: int = 0, stroke_fill=None) -> None:
    """Render `text` glyph-by-glyph with `spacing` extra pixels between."""
    cx = x
    for ch in text:
        kwargs = {"fill": fill, "font": font}
        if stroke_width and stroke_fill:
            kwargs["stroke_width"] = stroke_width
            kwargs["stroke_fill"] = stroke_fill
        draw.text((cx, y), ch, **kwargs)
        cx += draw.textbbox((0, 0), ch, font=font)[2] + spacing


def _draw_branding(canvas: Image.Image, theme: Dict[str, Any]) -> None:
    """Footer-style restaurant branding line at the bottom of the canvas."""
    draw = ImageDraw.Draw(canvas, "RGBA")
    f = _font(FONT_SANS_BOLD, 20)
    text = RESTAURANT_BRANDING
    bbox = draw.textbbox((0, 0), text, font=f)
    tw = bbox[2] - bbox[0]
    draw.text(((CANVAS - tw) // 2, CANVAS - 40 - (bbox[3] - bbox[1])),
              text, fill=theme["branding_color"], font=f)


def _compose_design(bg_bytes: bytes, food_rgba: Image.Image,
                    item_name: str, features: List[str], price: Optional[str],
                    theme_id: str, layout: str,
                    variant_idx: int = 0,
                    cta: Optional[str] = None,
                    include_price: bool = True,
                    include_description: bool = True,
                    platform: str = "instagram_post",
                    tone: Optional[str] = None,
                    logo_url: Optional[str] = None,
                    logo_placement: Optional[str] = None,
                    logo_size: Optional[str] = None,
                    ) -> Tuple[bytes, Dict[str, Any]]:
    """Composite the final marketing graphic.

    Sprint 22 P0 Fix 2: `variant_idx` (0/1/2) is now propagated through every
    render path. The food cutout receives a deterministic per-variant
    transform (`_variant_food_transform`) BEFORE compositing so the 3
    generated flyers are visibly different — agency-template and HTML paths
    that ignore the underlying layout permutation still produce 3 distinct
    PNGs. See `_variant_food_transform` for the per-variant treatment.

    Sprint 20 Phase 0: dispatch FIRST to the new agency template slot
    renderer when a matching manifest exists. The procedural engine
    (Sprint 18 iterative compose_layered_with_score) is the fallback for
    any theme without a matching template, and for any agency render
    that raises.

    Sprint 18: procedural path runs the iterative compose_layered_with_score
    loop — renders an initial layout, evaluates it via quality_score, and
    if the score is below the agency-grade threshold (75) renders ONE
    alternative layout chosen by the weakest-metric hint. Returns the
    higher-scoring canvas PLUS a `score` dict that the caller persists on
    the asset.

    Sprint 20A (HTML/CSS pivot): for the `cajun` + `luxury` theme
    families, the new headless-browser HTML renderer is the priority
    path. Falls back through agency template → procedural on any error.
    """
    # Sprint 22 P0 Fix 2 — per-variant food treatment. Applied ONCE here so
    # every downstream renderer (HTML, agency template, procedural) inherits
    # the variation without needing path-specific logic. v0 returns a copy.
    food_rgba = _variant_food_transform(food_rgba, variant_idx)

    # ---- Sprint 20A: HTML/CSS rendering for Cajun + Luxury themes ----
    try:
        import html_renderer as _html
        if _html.is_supported(theme_id):
            # Save the food image to a temp file once so the headless
            # browser can inline it as a base64 data URL.
            import tempfile
            food_rgb = food_rgba.convert("RGB")
            with tempfile.NamedTemporaryFile(
                suffix=".jpg", delete=False, prefix="htmlflyer_food_"
            ) as tf:
                food_rgb.save(tf.name, "JPEG", quality=92)
                food_path = tf.name
            try:
                canvas_w, canvas_h = _get_canvas_size(platform)
                actual_cta = (cta or "").strip() or "Order Now · Mon-Sat 11-9"
                # Calculate render size (4× for retina/print quality)
                render_w = canvas_w * 2
                render_h = canvas_h * 2
                png_bytes = _html.render_flyer(
                    theme_id,
                    item_name=item_name or "",
                    features=features if include_description else [],
                    price=(price or "").strip() if include_price else "",
                    brand=RESTAURANT_BRANDING,
                    cta=actual_cta,
                    food_image_path=food_path,
                    output_width=canvas_w,
                    output_height=canvas_h,
                    render_width=render_w,
                    render_height=render_h,
                )
            finally:
                try:
                    os.unlink(food_path)
                except OSError:
                    pass
            score = {
                "total": 92.0,
                "label": "Excellent",
                "rank": "excellent",
                "render_path": "html_css",
                "template_id": f"html_{theme_id}",
                "template_label": f"HTML/CSS {theme_id.title()}",
                "metrics": {},
            }
            return png_bytes, score
    except Exception as e:  # noqa: BLE001
        import logging as _logging
        _logging.getLogger("uvicorn.error").warning(
            f"[ai_designer] HTML renderer failed for theme={theme_id!r}: {e!r} — falling back to agency/procedural"
        )

    # ---- Sprint 20 Phase 0: agency template fast path ----
    try:
        import agency_templates as _at
        from agency_renderer import compose_with_template

        # Pick by theme first (exact fallback_theme match wins); ignore
        # category since the theme already encodes it.
        tmpl = _at.pick_template_for(category=None, theme_hint=theme_id)
        # Priority 3 platform-sizing fix (Feb 2026): agency templates have a
        # FIXED `template.canvas` size (typically 1024×1024). If the caller
        # requested a different platform canvas, skip this path and fall
        # through to the procedural renderer which honors _get_canvas_size().
        # Without this skip, instagram_story / tiktok / twitter / fb / email
        # all silently rendered as 1024×1024.
        requested_canvas = _get_canvas_size(platform)
        if tmpl is not None and tmpl.canvas != requested_canvas:
            import logging as _logging
            _logging.getLogger("uvicorn.error").info(
                f"[ai_designer] platform={platform} canvas={requested_canvas} "
                f"!= template.canvas={tmpl.canvas} — skipping agency template "
                f"for theme={theme_id!r}, using procedural fallback."
            )
            tmpl = None
        if tmpl is not None:
            actual_features = features if include_description else []
            actual_price = (price or "").strip() if include_price else ""
            actual_cta = (cta or "").strip() or "LIMITED-TIME SPECIAL"
            agency_canvas = compose_with_template(
                tmpl,
                food_rgba=food_rgba,
                item_name=item_name or "",
                features=actual_features,
                price=actual_price,
                brand=RESTAURANT_BRANDING,
                cta=actual_cta,
            )
            out = io.BytesIO()
            agency_canvas.convert("RGB").save(out, "PNG", optimize=True)
            # Agency templates are pre-validated by a human designer — score
            # them at 88 (above the 80 retry threshold, "Very Good" label) so
            # the iterative procedural retry doesn't run.
            score = {
                "total": 88.0,
                "label": "Very Good",
                "rank": "very_good",
                "render_path": "agency_template",
                "template_id": tmpl.id,
                "template_label": tmpl.label,
                "metrics": {},
            }
            return out.getvalue(), score
    except Exception as e:  # noqa: BLE001
        # Any agency-renderer failure → silently fall through to procedural.
        import logging as _logging
        _logging.getLogger("uvicorn.error").warning(
            f"[ai_designer] agency template render failed for theme={theme_id!r}: {e!r} — falling back to procedural"
        )

    # ---- Procedural fallback (Sprint 18 iterative composer) ----
    from render_engine import compose_layered_with_score, LEGACY_LAYOUT_ALIAS

    # Get platform-specific canvas size
    canvas_w, canvas_h = _get_canvas_size(platform)
    
    theme = THEME_STYLES[theme_id]
    bg = Image.open(io.BytesIO(bg_bytes)).convert("RGB")
    # Resize background to match platform canvas
    if bg.size != (canvas_w, canvas_h):
        bg = bg.resize((canvas_w, canvas_h), Image.LANCZOS)

    legacy_to_variant = {"centered": 0, "asym_left": 1, "stacked": 2}
    # Sprint 22 P0 Fix 2 — prefer the explicit `variant_idx` if provided;
    # fall back to the legacy layout-name → variant_idx mapping so older
    # callers keep working.
    derived_variant = legacy_to_variant.get(layout, 0)
    variant_idx = variant_idx if variant_idx else derived_variant
    layout_override = None
    if layout in LEGACY_LAYOUT_ALIAS:
        layout_override = LEGACY_LAYOUT_ALIAS[layout]

    from typography_engine import pick_badge_style
    import random
    theme = dict(theme)
    theme["_theme_id"] = theme_id
    theme["_variant_idx"] = variant_idx
    
    # Phase 3: Diversity Engine - Add per-variant randomization
    variant_rng = random.Random(hash((theme_id, variant_idx)) & 0xFFFFFFFF)
    
    # Vary color intensity per variant (±10%)
    if "title" in theme and "color" in theme["title"]:
        title_color = theme["title"]["color"]
        if isinstance(title_color, (tuple, list)) and len(title_color) >= 3:
            intensity_factor = 1.0 + (variant_idx - 1) * 0.1  # v0: 0.9, v1: 1.0, v2: 1.1
            theme["title"]["color"] = tuple(
                min(255, max(0, int(c * intensity_factor))) for c in title_color[:3]
            ) + (title_color[3:] if len(title_color) > 3 else ())
    
    # Vary badge style per variant
    if not theme.get("badge_style"):
        # Sprint 18 — personality-aware badge pick.
        theme["_badge_style"] = pick_badge_style(
            theme_id, variant_idx, personality=theme.get("personality"))
    
    # Vary typography size slightly per variant (±5%)
    if "title" in theme and "size" in theme["title"]:
        base_size = theme["title"]["size"]
        size_variation = variant_rng.choice([-5, 0, 5])
        theme["title"]["size"] = max(40, base_size + size_variation)
    
    if "body" in theme and "size" in theme["body"]:
        base_body_size = theme["body"]["size"]
        body_variation = variant_rng.choice([-2, 0, 2])
        theme["body"]["size"] = max(16, base_body_size + body_variation)

    # Apply conditional rendering flags
    actual_price = price if include_price else None
    actual_features = features if include_description else []

    canvas, score = compose_layered_with_score(
        bg_image=bg,
        food_rgba=food_rgba,
        theme=theme,
        theme_id=theme_id,
        variant_idx=variant_idx,
        draw_title=_draw_title,
        draw_bullets=_draw_bullets,
        draw_price_badge=_draw_price_badge,
        draw_branding=_draw_branding,
        item_name=item_name,
        features=actual_features,
        price=actual_price,
        layout_override=layout_override,
        cta=cta,
        canvas_size=(canvas_w, canvas_h),
        # Sprint 19 hotfix — bump target so weak compositions actually retry.
        target_score=80.0,
        max_iterations=2,
    )
    out = io.BytesIO()
    canvas.convert("RGB").save(out, "PNG", optimize=True)
    png_bytes = out.getvalue()
    
    # Priority 4.1: Apply logo if requested
    if logo_url and logo_placement and logo_placement != "none":
        try:
            from logo_renderer import apply_logo_to_flyer
            from flyer_config import LogoPlacement, LogoSize
            
            # Load the generated image
            canvas_with_logo = Image.open(io.BytesIO(png_bytes))
            
            # Apply logo
            placement = LogoPlacement(logo_placement)
            size = LogoSize(logo_size or "medium")
            canvas_with_logo = apply_logo_to_flyer(canvas_with_logo, logo_url, placement, size)
            
            # Re-encode
            out_with_logo = io.BytesIO()
            canvas_with_logo.convert("RGB").save(out_with_logo, "PNG", optimize=True)
            png_bytes = out_with_logo.getvalue()
            logger.info(f"[ai-designer] Logo applied: {placement.value} @ {size.value}")
        except Exception as e:
            logger.error(f"[ai-designer] Logo application failed: {e}", exc_info=True)
            # Continue with original image without logo
    
    return png_bytes, score


# ---------------------------------------------------------------- LLM copy (unchanged from 13B)

# Tech Debt Sprint Step 3: Moved to ai_designer/copy_generation.py
# Old function kept commented for safety:
# async def _write_designer_copy(
#     item_name: str,
#     features: List[str],
#     price: Optional[str],
#     theme_label: str,
#     tone: Optional[str] = None,
#     marketing_goal: Optional[str] = None,
#     caption_length: Optional[str] = None,
# ) -> Dict[str, Any]:
#     ... [96 lines of copy generation logic]
#     return {...}
# Use new module:
_write_designer_copy = _write_designer_copy_new


# ---------------------------------------------------------------- Asset persistence

async def _save_design_asset(img_bytes: bytes, item_name: str, theme_id: str, variant: str,
                             item_key: Optional[str] = None,
                             source_asset_id: Optional[str] = None,
                             score_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    aid = str(uuid.uuid4())
    storage_path = objstore.make_path("ai_designs", aid, "png")
    objstore.put_bytes(storage_path, img_bytes, "image/png")
    with Image.open(io.BytesIO(img_bytes)) as im:
        w, h = im.size
    slug = item_name[:30].replace(" ", "-").lower().strip("-") or "design"
    doc = {
        "id": aid,
        "filename": f"design-{theme_id}-{slug}-{variant}-{aid[:6]}.png",
        "kind": "image", "mime": "image/png", "size_bytes": len(img_bytes),
        "width": w, "height": h, "duration_seconds": None,
        "folder": "AI Designer",
        "tags": ["ai-designer", f"theme:{theme_id}", f"variant:{variant}"],
        "storage_path": storage_path,
        "is_favorite": False, "status": "active",
        "source": "ai_designer",
        # Sprint 17B — top-level fields for Library filtering + Remix.
        "theme": theme_id,
        "item_name": item_name,
        "item_key": item_key,
        "source_asset_id": source_asset_id,
        # Sprint 18 — quality score persisted for future tuning + dev panel.
        "quality_score": (score_info or {}).get("score"),
        "quality_label": (score_info or {}).get("label"),
        "quality_metrics": (score_info or {}).get("metrics"),
        "quality_iterations": (score_info or {}).get("iteration"),
        "quality_layout": (score_info or {}).get("chosen_layout"),
        "uploaded_at": _now(), "updated_at": _now(),
    }
    await db.media_assets.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


# ---------------------------------------------------------------- Background worker

# Tech Debt Sprint Step 5: orchestration logic moved to
# `ai_designer/generation.py`. The router keeps the thin shim below so
# the existing spawn call (`_spawn_ai_image_task(_run_design_job(...))`)
# stays unchanged and composition/save helpers remain router-local.

from ai_designer.generation import run_design_job as _run_design_job_new


async def _run_design_job(job_id: str, body: GenerateRequest) -> None:
    """Thin shim — delegates to ai_designer.generation.run_design_job
    with router-local helpers injected."""
    await _run_design_job_new(
        job_id,
        body,
        db=db,
        now=_now,
        objstore=objstore,
        canvas_max=CANVAS,
        get_active_asset=_get_active_asset,
        prepare_food_cutout=_prepare_food_cutout,
        compose_design=_compose_design,
        save_design_asset=_save_design_asset,
        pil_background=_pil_background,
    )


# ---------------------------------------------------------------- Routes

@router.get("/themes")
async def list_themes(authorization: str = Header(None), session_token: str = Cookie(None)):
    """Sprint 16F — Flat theme list enriched with pack metadata.

    Response shape is backward compatible: `themes[*]` still carries
    `{id, label, preview_color}`. New fields (added, never removed):
        * pack       – pack id (e.g. "burger", "seafood")
        * pack_label – human pack name ("Burger Joint")
        * category   – pack category tag ("burger", "sports", …)
        * best_use   – per-theme tagline ("Smash burgers, Tuesday burger nights")

    `packs[]` is added as an optional grouped index for richer UIs.
    """
    await verify_session(authorization, session_token)
    themes_payload = []
    for tid, t in THEME_STYLES.items():
        m = THEME_META.get(tid, {})
        themes_payload.append({
            "id": tid,
            "label": t["label"],
            "preview_color": "#{:02x}{:02x}{:02x}".format(*t["bg_color"]),
            "pack": m.get("pack", ""),
            "pack_label": m.get("pack_label", ""),
            "category": m.get("category", ""),
            "best_use": m.get("best_use", ""),
        })
    return {
        "themes": themes_payload,
        "packs": [
            {
                "id": p["id"],
                "label": p["label"],
                "category": p["category"],
                "description": p["description"],
                "theme_ids": p["theme_ids"],
            }
            for p in THEME_PACKS
        ],
        "variations_per_run": 3,
    }


@router.post("/estimate")
async def estimate(
    body: EstimateRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Cost preview. AI Designer designs are free — only optional auto-copy uses credits."""
    await verify_session(authorization, session_token)
    _normalize_theme(body.theme)
    status = await billing.get_status(db)
    # Composition is PIL — zero LLM cost. Optional auto-copy is ~$0.001 (one text call).
    copy_cost = 0.001
    return {
        "theme": body.theme,
        "count": 3,
        "per_image_cost_usd": 0.0,
        "total_cost_usd": 0.0,
        "with_copy_cost_usd": round(copy_cost, 4),
        "current_balance_usd": status["current_balance_usd"],
        "would_exceed_balance": False,
        "tier": status["tier"],
    }


@router.post("/generate", status_code=202)
async def enqueue_generate(
    body: GenerateRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Enqueue an AI Designer run — always produces exactly 3 PIL-composed variations.
    Designs are free; only optional auto-copy (LLM text call) consumes credits."""
    await verify_session(authorization, session_token)
    _normalize_theme(body.theme)
    await _get_active_asset(body.source_asset_id)

    # Only auto-copy can cost anything — pre-flight it if enabled.
    if body.auto_copy:
        copy_cost = 0.005  # conservative ceiling
        can, status = await billing.check_can_afford(db, copy_cost, surface="ai_designer")
        if not can:
            raise HTTPException(status_code=402, detail={
                "code": "budget_exhausted", "status": 402, "retryable": False,
                "user_message": (
                    f"Not enough virtual balance for the marketing copy step. Need ~${copy_cost:.2f}, "
                    f"balance ${status['current_balance_usd']:.2f}. The 3 designs themselves are free — "
                    "uncheck 'Also write marketing copy' to run anyway."
                ),
                "technical": f"copy_required={copy_cost} balance={status['current_balance_usd']}",
            })

    job_id = str(uuid.uuid4())
    now = _now()
    await db.ai_design_jobs.insert_one({
        "id": job_id, "status": "pending",
        "source_asset_id": body.source_asset_id,
        "item_name": body.item_name, "features": body.features, "price": body.price,
        "themes": [body.theme], "theme": body.theme,
        "progress": 0, "variations": [],
        "estimated_cost_usd": 0.0,
        "created_at": now, "updated_at": now, "error": None,
    })
    _spawn_ai_image_task(_run_design_job(job_id, body))
    return {"job_id": job_id, "status": "pending", "estimated_cost_usd": 0.0}


@router.get("/job/{job_id}")
async def get_job(job_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    job = await db.ai_design_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/recent")
async def list_recent_jobs(
    limit: int = 5,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    limit = max(1, min(20, int(limit or 5)))
    projection = {
        "_id": 0, "id": 1, "item_name": 1, "themes": 1, "theme": 1, "variations": 1,
        "created_at": 1, "copy_pack": 1, "is_pinned": 1, "price": 1, "features": 1,
        "source_asset_id": 1,
    }
    pinned = await db.ai_design_jobs.find(
        {"status": "completed", "is_pinned": True}, projection,
    ).sort("created_at", -1).limit(3).to_list(length=3)
    pinned_ids = {p["id"] for p in pinned}
    remaining = max(0, limit - len(pinned))
    others_cur = db.ai_design_jobs.find(
        {"status": "completed", "id": {"$nin": list(pinned_ids)}}, projection,
    ).sort("created_at", -1).limit(remaining)
    others = await others_cur.to_list(length=remaining)

    def summarize(j: Dict[str, Any]) -> Dict[str, Any]:
        successes = [v for v in (j.get("variations") or []) if v.get("status") == "completed"]
        first = successes[0] if successes else None
        theme_id = j.get("theme") or (j.get("themes") or [""])[0]
        return {
            "id": j["id"],
            "item_name": j.get("item_name") or "Untitled",
            "primary_theme": theme_id,
            "primary_theme_label": THEME_STYLES.get(theme_id, {}).get("label", ""),
            "thumb_asset_id": first["asset_id"] if first else None,
            "variation_count": len(successes),
            "has_copy": bool(j.get("copy_pack")),
            "is_pinned": bool(j.get("is_pinned")),
            "price": j.get("price"),
            "features": j.get("features") or [],
            "created_at": j.get("created_at"),
        }

    return {"jobs": [summarize(j) for j in (pinned + others)]}


@router.post("/jobs/{job_id}/pin")
async def toggle_pin(job_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    job = await db.ai_design_jobs.find_one({"id": job_id}, {"_id": 0, "is_pinned": 1, "status": 1})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Only completed jobs can be pinned")
    will_pin = not bool(job.get("is_pinned"))
    if will_pin:
        pin_count = await db.ai_design_jobs.count_documents({"is_pinned": True, "status": "completed"})
        if pin_count >= 3:
            raise HTTPException(status_code=400, detail="Maximum 3 pinned designs. Unpin one first.")
    await db.ai_design_jobs.update_one({"id": job_id}, {"$set": {"is_pinned": will_pin, "updated_at": _now()}})
    return {"id": job_id, "is_pinned": will_pin}


@router.get("/templates")
async def list_templates(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    cur = db.ai_design_templates.find({}, {"_id": 0}).sort("created_at", -1).limit(20)
    items = await cur.to_list(length=20)
    return {"templates": items}


@router.post("/jobs/{job_id}/save-template")
async def save_template(
    job_id: str, body: SaveTemplateRequest,
    authorization: str = Header(None), session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    job = await db.ai_design_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    variations = job.get("variations") or []
    if body.variation_index >= len(variations):
        raise HTTPException(status_code=400, detail="variation_index out of range")
    v = variations[body.variation_index]
    if v.get("status") != "completed":
        raise HTTPException(status_code=400, detail="That variation didn't complete")

    theme_id = v.get("theme") or job.get("theme") or (job.get("themes") or [""])[0]
    tpl = {
        "id": str(uuid.uuid4()),
        "theme": theme_id,
        "theme_label": v.get("theme_label") or THEME_STYLES.get(theme_id, {}).get("label", theme_id),
        "item_name": job["item_name"],
        "features": job.get("features") or [],
        "price": job.get("price"),
        "source_job_id": job_id,
        "preview_asset_id": v["asset_id"],
        "note": body.note,
        "created_at": _now(), "last_used_at": _now(), "uses": 1,
    }
    await db.ai_design_templates.insert_one(tpl)
    return {k: val for k, val in tpl.items() if k != "_id"}


# Sprint 15B: POST /from-template/{template_id} removed — never called from frontend.


# ---------------------------------------------------------------- Copy pack endpoints

@router.get("/jobs/{job_id}/copy")
async def get_copy(job_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    job = await db.ai_design_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "has_copy": bool(job.get("copy_pack")),
        "copy_pack": job.get("copy_pack"),
        "copy_error": job.get("copy_error"),
    }


@router.post("/jobs/{job_id}/copy")
async def write_copy(job_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    job = await db.ai_design_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job hasn't completed yet")
    if job.get("copy_pack"):
        return {"copy_pack": job["copy_pack"], "regenerated": False}
    successes = [v for v in (job.get("variations") or []) if v.get("status") == "completed"]
    if not successes:
        raise HTTPException(status_code=400, detail="No completed designs to write copy for")
    theme_id = job.get("theme") or (job.get("themes") or [""])[0]
    label = THEME_STYLES.get(theme_id, {}).get("label", theme_id)
    try:
        copy_pack = await _write_designer_copy(job["item_name"], job.get("features") or [], job.get("price"), label)
    except Exception as e:  # noqa: BLE001
        from errors import classify_llm_error
        err = classify_llm_error(e, surface="ai_designer")
        await db.ai_design_jobs.update_one(
            {"id": job_id}, {"$set": {"copy_error": err.user_message or str(e)[:300], "updated_at": _now()}},
        )
        raise HTTPException(status_code=err.status or 500, detail=err.to_payload())
    await db.ai_design_jobs.update_one(
        {"id": job_id}, {"$set": {"copy_pack": copy_pack, "copy_error": None, "updated_at": _now()}},
    )
    return {"copy_pack": copy_pack, "regenerated": True}


async def cleanup_orphan_ai_design_jobs() -> None:
    orphan_err = {
        "code": "unknown", "status": 500, "retryable": True, "retry_action": "retry",
        "user_message": "This design run was interrupted by a server restart. Tap Try again.",
        "technical": "backend restarted with job in pending/processing state",
    }
    r = await db.ai_design_jobs.update_many(
        {"status": {"$in": ["pending", "processing"]}},
        {"$set": {"status": "failed", "error": orphan_err, "progress": 0, "updated_at": _now()}},
    )
    if r.modified_count > 0:
        logger.info("[ai-designer] Marked %d orphan job(s) as failed at startup", r.modified_count)
