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
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Cookie, Header, HTTPException
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel, ConfigDict, Field, constr

from auth import verify_session
import billing
import storage as objstore
from routers.media.shared import _now, _spawn_ai_image_task, db

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/ai-designer", tags=["ai-designer"])

CANVAS = 1024
VARIATION_LABELS = ["A", "B", "C"]  # always exactly 3
RESTAURANT_BRANDING = os.environ.get("AI_DESIGNER_BRAND", "LAKEVIEW BURGERS & SEAFOOD")

FONT_SERIF_BOLD   = "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"
FONT_SERIF        = "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"
FONT_SANS_BOLD    = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
FONT_SANS         = "/usr/share/fonts/truetype/freefont/FreeSans.ttf"


# ---------------------------------------------------------------- Theme styles
# Each theme defines: human label, and PIL drawing constants (fonts, colors,
# badge styling). Variations come from 3 layout templates applied to the same
# theme, giving 3 visually distinct designs per run.

THEME_STYLES: Dict[str, Dict[str, Any]] = {
    "luxury": {
        "label": "Luxury Black & Gold",
        "bg_color": (16, 16, 16),
        "title": {"font": FONT_SERIF_BOLD, "color": (212, 175, 55), "size": 76},
        "body":  {"font": FONT_SANS, "color": (245, 235, 200), "size": 30, "marker": "•",
                  "marker_color": (212, 175, 55)},
        "price": {"bg": (212, 175, 55), "fg": (16, 16, 16), "ring": (255, 220, 120), "font": FONT_SERIF_BOLD},
        "branding_color": (180, 160, 110),
    },
    "vintage": {
        "label": "Vintage Diner",
        "bg_color": (240, 220, 195),
        "title": {"font": FONT_SERIF_BOLD, "color": (160, 30, 30), "size": 80},
        "body":  {"font": FONT_SANS_BOLD, "color": (50, 25, 15), "size": 28, "marker": "*",
                  "marker_color": (160, 30, 30)},
        "price": {"bg": (220, 50, 50), "fg": (255, 245, 220), "ring": (255, 245, 220), "font": FONT_SERIF_BOLD},
        "branding_color": (90, 50, 30),
    },
    "modern": {
        "label": "Modern Restaurant",
        "bg_color": (248, 245, 240),
        "title": {"font": FONT_SERIF_BOLD, "color": (24, 28, 48), "size": 72},
        "body":  {"font": FONT_SANS, "color": (60, 65, 80), "size": 28, "marker": "—",
                  "marker_color": (24, 28, 48)},
        "price": {"bg": (24, 28, 48), "fg": (255, 245, 215), "ring": (215, 195, 130), "font": FONT_SERIF_BOLD},
        "branding_color": (130, 130, 140),
    },
    "social": {
        "label": "Bright Social",
        "bg_color": (255, 200, 90),
        "title": {"font": FONT_SANS_BOLD, "color": (40, 25, 5), "size": 86},
        "body":  {"font": FONT_SANS_BOLD, "color": (40, 25, 5), "size": 30, "marker": ">",
                  "marker_color": (220, 60, 40)},
        "price": {"bg": (220, 50, 50), "fg": (255, 245, 220), "ring": (255, 200, 90), "font": FONT_SANS_BOLD},
        "branding_color": (110, 60, 30),
    },
    "cajun": {
        "label": "Cajun / Bayou",
        "bg_color": (60, 40, 20),
        "title": {"font": FONT_SERIF_BOLD, "color": (245, 210, 80), "size": 78},
        "body":  {"font": FONT_SANS_BOLD, "color": (245, 235, 210), "size": 28, "marker": "+",
                  "marker_color": (220, 100, 30)},
        "price": {"bg": (220, 130, 40), "fg": (30, 20, 10), "ring": (245, 210, 80), "font": FONT_SERIF_BOLD},
        "branding_color": (200, 170, 100),
    },
    # ---------------- Sprint 16A — Flyer-grade themes ----------------
    # Larger headline sizes (90-100px) + saturated palettes + chunky badges so
    # the output reads as a marketing flyer, not a polite menu card.
    "comic_pop": {
        "label": "Comic Pop",
        "bg_color": (12, 12, 16),
        "title": {"font": FONT_SANS_BOLD, "color": (255, 235, 70), "size": 100},
        "body":  {"font": FONT_SANS_BOLD, "color": (255, 255, 255), "size": 30, "marker": "▸",
                  "marker_color": (255, 235, 70)},
        "price": {"bg": (255, 235, 70), "fg": (12, 12, 16), "ring": (255, 255, 255), "font": FONT_SANS_BOLD},
        "branding_color": (255, 235, 70),
    },
    "vintage_diner": {
        "label": "Vintage Diner (Flyer)",
        "bg_color": (244, 232, 200),
        "title": {"font": FONT_SERIF_BOLD, "color": (35, 90, 50), "size": 92},
        "body":  {"font": FONT_SANS_BOLD, "color": (35, 60, 40), "size": 28, "marker": "★",
                  "marker_color": (180, 50, 40)},
        "price": {"bg": (180, 50, 40), "fg": (244, 232, 200), "ring": (35, 90, 50), "font": FONT_SERIF_BOLD},
        "branding_color": (90, 70, 40),
    },
    "bold_purple_pop": {
        "label": "Bold Purple Pop",
        "bg_color": (38, 18, 60),
        "title": {"font": FONT_SANS_BOLD, "color": (255, 240, 240), "size": 100},
        "body":  {"font": FONT_SANS_BOLD, "color": (255, 240, 240), "size": 30, "marker": "▸",
                  "marker_color": (255, 240, 100)},
        "price": {"bg": (255, 240, 100), "fg": (38, 18, 60), "ring": (240, 60, 140), "font": FONT_SANS_BOLD},
        "branding_color": (240, 200, 220),
    },
    "casual_teal": {
        "label": "Casual Teal",
        "bg_color": (170, 220, 215),
        "title": {"font": FONT_SERIF_BOLD, "color": (30, 70, 70), "size": 90},
        "body":  {"font": FONT_SANS_BOLD, "color": (30, 70, 70), "size": 28, "marker": "✓",
                  "marker_color": (220, 110, 60)},
        "price": {"bg": (250, 245, 230), "fg": (30, 70, 70), "ring": (220, 110, 60), "font": FONT_SERIF_BOLD},
        "branding_color": (50, 90, 90),
    },
    "distressed_orange": {
        "label": "Distressed Orange",
        "bg_color": (200, 80, 35),
        "title": {"font": FONT_SERIF_BOLD, "color": (252, 240, 215), "size": 96},
        "body":  {"font": FONT_SANS_BOLD, "color": (252, 240, 215), "size": 28, "marker": "■",
                  "marker_color": (252, 240, 215)},
        "price": {"bg": (40, 25, 20), "fg": (252, 240, 215), "ring": (252, 240, 215), "font": FONT_SERIF_BOLD},
        "branding_color": (252, 240, 215),
    },
}

THEME_IDS = list(THEME_STYLES.keys())

# Three layout templates so each variation FEELS distinct beyond just the background.
LAYOUTS = ["centered", "asym_left", "stacked"]


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
    theme: constr(min_length=2, max_length=20) = "modern"
    auto_copy: bool = False
    # Sprint 15B.3: rembg/background removal is now OPT-IN. Default is False
    # so normal generation uses a rounded-rect fallback mask — eliminates the
    # ~5-15s synchronous rembg call per job that was wedging the single-worker
    # production pod. Users can enable it via the "Remove background" checkbox.
    remove_background: bool = False


class SaveTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    variation_index: int = Field(ge=0, le=2)
    note: Optional[constr(max_length=200)] = None


# ---------------------------------------------------------------- Helpers

async def _get_active_asset(asset_id: str) -> Dict[str, Any]:
    asset = await db.media_assets.find_one({"id": asset_id, "status": "active"}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Source image not found")
    if asset.get("kind") != "image":
        raise HTTPException(status_code=400, detail="Source asset must be an image")
    return asset


def _normalize_theme(theme: str) -> str:
    if theme not in THEME_STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown theme. Pick from: {THEME_IDS}")
    return theme


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size=size)
    except Exception:
        return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    """Word-wrap `text` so each line fits within `max_w` pixels."""
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


# ---------------------------------------------------------------- Background generation


def _pil_background(theme_id: str, variant_idx: int) -> bytes:
    """Render a deterministic decorative background for a theme + variant.

    `variant_idx` (0/1/2) selects between three PIL pattern variants per theme.
    PIL output is always crisp — no AI image generation involved.
    """
    style = THEME_STYLES[theme_id]
    bg_color = style["bg_color"]
    accent = style["title"]["color"]
    canvas = Image.new("RGB", (CANVAS, CANVAS), bg_color)
    draw = ImageDraw.Draw(canvas, "RGBA")

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
    skip the expensive rembg call entirely and apply a rounded-rect alpha mask.
    This keeps generation fast and unblocks the single-worker production pod.
    """
    src = Image.open(io.BytesIO(food_bytes)).convert("RGBA")
    if use_rembg:
        try:
            from rembg import remove  # lazy import — only paid when explicitly opted in
            out = remove(food_bytes)
            cut = Image.open(io.BytesIO(out)).convert("RGBA")
        except Exception as e:  # noqa: BLE001
            logger.warning("[ai-designer] rembg failed (%s); falling back to rounded-rect mask", e)
            cut = _rounded_rect_mask(src, radius_pct=0.08)
    else:
        cut = _rounded_rect_mask(src, radius_pct=0.08)

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


# ---------------------------------------------------------------- Composition

def _draw_price_badge(canvas: Image.Image, theme: Dict[str, Any], price_text: str, cx: int, cy: int, radius: int) -> None:
    """Draw a circular price badge centered at (cx, cy)."""
    draw = ImageDraw.Draw(canvas, "RGBA")
    p = theme["price"]
    # Outer ring
    draw.ellipse((cx - radius - 6, cy - radius - 6, cx + radius + 6, cy + radius + 6),
                 fill=p["ring"] + (255,) if isinstance(p["ring"], tuple) and len(p["ring"]) == 3 else p["ring"])
    # Inner badge
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=p["bg"])
    # Price text
    font_size = max(28, radius // 2)
    f = _font(p["font"], font_size)
    bbox = draw.textbbox((0, 0), price_text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - bbox[1]), price_text, fill=p["fg"], font=f)


def _draw_bullets(canvas: Image.Image, theme: Dict[str, Any], features: List[str],
                  x: int, y: int, max_w: int) -> None:
    """Draw up to 5 feature bullets stacked vertically."""
    if not features:
        return
    draw = ImageDraw.Draw(canvas, "RGBA")
    body = theme["body"]
    f = _font(body["font"], body["size"])
    line_h = body["size"] + 14
    for i, feat in enumerate(features[:5]):
        ty = y + i * line_h
        marker = body["marker"]
        # marker in marker_color
        draw.text((x, ty), marker, fill=body["marker_color"], font=f)
        mb = draw.textbbox((0, 0), marker + " ", font=f)
        text_x = x + (mb[2] - mb[0])
        # truncate single line if too wide
        wrapped = _wrap_text(draw, feat, f, max_w - (text_x - x))
        draw.text((text_x, ty), wrapped[0], fill=body["color"], font=f)


def _draw_title(canvas: Image.Image, theme: Dict[str, Any], item_name: str,
                x: int, y: int, max_w: int, align: str = "center") -> int:
    """Draw the item title; returns the y after the title block."""
    draw = ImageDraw.Draw(canvas, "RGBA")
    t = theme["title"]
    f = _font(t["font"], t["size"])
    lines = _wrap_text(draw, item_name, f, max_w)
    cur_y = y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=f)
        lw = bbox[2] - bbox[0]
        if align == "center":
            lx = x + (max_w - lw) // 2
        elif align == "right":
            lx = x + (max_w - lw)
        else:
            lx = x
        draw.text((lx, cur_y), line, fill=t["color"], font=f)
        cur_y += t["size"] + 8
    return cur_y


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
                    theme_id: str, layout: str) -> bytes:
    """Composite the final marketing graphic. PIL is the source of truth — never AI."""
    theme = THEME_STYLES[theme_id]
    # Background
    bg = Image.open(io.BytesIO(bg_bytes)).convert("RGB")
    if bg.size != (CANVAS, CANVAS):
        bg = bg.resize((CANVAS, CANVAS), Image.LANCZOS)
    canvas = bg.convert("RGBA")

    # Subtle vignette overlay to make title/branding more readable
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, CANVAS, 140), fill=(0, 0, 0, 60))   # top band for title legibility
    od.rectangle((0, CANVAS - 140, CANVAS, CANVAS), fill=(0, 0, 0, 50))  # bottom band
    canvas = Image.alpha_composite(canvas, overlay)

    # Layout-specific placement
    safe_pad = 60
    if layout == "centered":
        # Title centered top, food center, bullets right column, price bottom-right
        title_y_end = _draw_title(canvas, theme, item_name, safe_pad, safe_pad, CANVAS - 2 * safe_pad, "center")
        # Food
        food_max = int(CANVAS * 0.55)
        food = food_rgba
        # Fit food into a square of food_max
        scale = food_max / max(food.width, food.height)
        food_r = food.resize((max(1, int(food.width * scale)), max(1, int(food.height * scale))), Image.LANCZOS)
        food_shadowed = _drop_shadow(food_r)
        fx = (CANVAS - food_shadowed.width) // 2
        fy = title_y_end + 20
        canvas.alpha_composite(food_shadowed, (fx, fy))
        # Bullets bottom-left band
        _draw_bullets(canvas, theme, features, safe_pad, CANVAS - 240, CANVAS - 2 * safe_pad - 220)
        # Price badge bottom-right
        _draw_price_badge(canvas, theme, (price or "").strip() or "—",
                          CANVAS - 130, CANVAS - 200, 90)

    elif layout == "asym_left":
        # Food big on the left, text column on the right
        food_max = int(CANVAS * 0.52)
        food = food_rgba
        scale = food_max / max(food.width, food.height)
        food_r = food.resize((max(1, int(food.width * scale)), max(1, int(food.height * scale))), Image.LANCZOS)
        food_shadowed = _drop_shadow(food_r)
        fx = safe_pad - 30
        fy = (CANVAS - food_shadowed.height) // 2
        canvas.alpha_composite(food_shadowed, (fx, fy))
        # Title top-right
        text_x = int(CANVAS * 0.55)
        text_w = CANVAS - text_x - safe_pad
        title_y_end = _draw_title(canvas, theme, item_name, text_x, safe_pad + 20, text_w, "left")
        _draw_bullets(canvas, theme, features, text_x, title_y_end + 20, text_w)
        _draw_price_badge(canvas, theme, (price or "").strip() or "—",
                          CANVAS - 130, CANVAS - 180, 80)

    else:  # "stacked"
        # Title large at top, food in upper-center, bullets+price band at bottom
        title_y_end = _draw_title(canvas, theme, item_name, safe_pad, safe_pad - 10, CANVAS - 2 * safe_pad, "center")
        food_max = int(CANVAS * 0.50)
        food = food_rgba
        scale = food_max / max(food.width, food.height)
        food_r = food.resize((max(1, int(food.width * scale)), max(1, int(food.height * scale))), Image.LANCZOS)
        food_shadowed = _drop_shadow(food_r)
        fx = (CANVAS - food_shadowed.width) // 2
        fy = title_y_end + 10
        canvas.alpha_composite(food_shadowed, (fx, fy))
        # Bullets left bottom
        _draw_bullets(canvas, theme, features, safe_pad, CANVAS - 230, int(CANVAS * 0.55))
        # Price right bottom
        _draw_price_badge(canvas, theme, (price or "").strip() or "—",
                          CANVAS - 150, CANVAS - 180, 95)

    # Footer branding
    _draw_branding(canvas, theme)

    out = io.BytesIO()
    canvas.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()


# ---------------------------------------------------------------- LLM copy (unchanged from 13B)

async def _write_designer_copy(item_name: str, features: List[str], price: Optional[str], theme_label: str) -> Dict[str, Any]:
    from ai_engine.client import generate_structured

    feat_text = "\n".join(f"- {f}" for f in features) if features else "(none)"
    price_str = (price or "").strip() or "(omit)"
    sys_prompt = (
        "You are a New Orleans restaurant marketing copywriter for Lakeview "
        "Burgers & Seafood. Write warm, mouth-watering, locally flavored copy. "
        "Output ONLY a valid JSON object — no markdown."
    )
    usr_prompt = (
        f"Item: {item_name}\n"
        f"Features:\n{feat_text}\n"
        f"Price: {price_str}\n"
        f"Visual theme: {theme_label}\n\n"
        "Generate a complete marketing pack:\n"
        " - fb_post: 60-100 words, Facebook-style conversational, 1 emoji max, ends with CTA on its own line.\n"
        " - ig_post: 30-50 words, punchy Instagram-native, 2-3 emojis, ends with a hook question or CTA.\n"
        " - gbp: 80-180 words for Google Business Profile, leads with the offer, ends with next step.\n"
        " - sms: under 140 chars, includes item + price, ends with CTA.\n"
        " - email_subject: 4-7 words, attention-grabbing.\n"
        " - email_body: 60-120 words, friendly, plain text only.\n"
        " - hashtags: 8-12 relevant hashtags as strings (no '#' prefix)."
    )
    schema = (
        '{"fb_post":"string","ig_post":"string","gbp":"string","sms":"string",'
        '"email_subject":"string","email_body":"string","hashtags":["string"]}'
    )
    wrapped = await generate_structured(db, system_prompt=sys_prompt, user_prompt=usr_prompt, schema_hint=schema)
    out = wrapped.get("data") or {}
    return {
        "fb_post": (out.get("fb_post") or "").strip()[:2000],
        "ig_post": (out.get("ig_post") or "").strip()[:2000],
        "gbp": (out.get("gbp") or "").strip()[:1500],
        "sms": (out.get("sms") or "").strip()[:160],
        "email": {
            "subject": (out.get("email_subject") or "").strip()[:120],
            "body": (out.get("email_body") or "").strip()[:2000],
        },
        "hashtags": [h.lstrip("#").strip() for h in (out.get("hashtags") or [])][:15],
        "generated_at": _now(),
    }


# ---------------------------------------------------------------- Asset persistence

async def _save_design_asset(img_bytes: bytes, item_name: str, theme_id: str, variant: str) -> Dict[str, Any]:
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
        "uploaded_at": _now(), "updated_at": _now(),
    }
    await db.media_assets.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


# ---------------------------------------------------------------- Background worker

async def _run_design_job(job_id: str, body: GenerateRequest) -> None:
    async def update(**fields: Any) -> None:
        fields["updated_at"] = _now()
        await db.ai_design_jobs.update_one({"id": job_id}, {"$set": fields})

    async def fail(user_msg: str, technical: str = "", code: str = "generation_failed") -> None:
        await update(status="failed", progress=0, error={
            "code": code, "status": 500, "retryable": True, "retry_action": "retry",
            "user_message": user_msg, "technical": technical,
        })

    # Load source food photo
    try:
        asset = await _get_active_asset(body.source_asset_id)
        food_bytes, _ = objstore.get_bytes(asset["storage_path"])
    except HTTPException as e:
        await fail(e.detail if isinstance(e.detail, str) else "Source asset not found")
        return
    except Exception as e:  # noqa: BLE001
        await fail("Couldn't load your source photo from storage. Try again.", str(e))
        return

    # Pre-process food cutout ONCE — same cutout used in all 3 variations.
    # Sprint 15B.3: only run rembg if the user explicitly opted in.
    try:
        food_rgba = _prepare_food_cutout(
            food_bytes,
            target_max=int(CANVAS * 0.65),
            use_rembg=bool(getattr(body, "remove_background", False)),
        )
    except Exception as e:  # noqa: BLE001
        await fail("Couldn't read your source photo. Try a different image.", str(e))
        return

    await update(status="processing", progress=5)

    variations: List[Dict[str, Any]] = []
    total = 3
    for idx, variant in enumerate(VARIATION_LABELS):
        layout = LAYOUTS[idx]
        try:
            bg_bytes = _pil_background(body.theme, idx)
            graphic_bytes = _compose_design(bg_bytes, food_rgba,
                                            body.item_name, body.features, body.price,
                                            body.theme, layout)
        except Exception as e:  # noqa: BLE001
            variations.append({"theme": body.theme, "variant": variant, "layout": layout,
                               "status": "failed", "error": "Composition failed",
                               "error_code": "compose_error"})
            logger.exception("[ai-designer] job=%s variant=%s composition failed: %s",
                             job_id, variant, e)
            await update(progress=int(100 * (idx + 1) / total), variations=variations)
            continue

        saved = await _save_design_asset(graphic_bytes, body.item_name, body.theme, variant)
        variations.append({
            "theme": body.theme,
            "theme_label": THEME_STYLES[body.theme]["label"],
            "variant": variant,
            "layout": layout,
            "status": "completed",
            "asset_id": saved["id"],
            "asset": saved,
            "cost_usd": 0.0,
        })
        await update(progress=int(100 * (idx + 1) / total), variations=variations)

    successes = [v for v in variations if v.get("status") == "completed"]
    if not successes:
        await update(status="failed", error={
            "code": "all_variations_failed", "status": 500, "retryable": True,
            "retry_action": "retry",
            "user_message": "All 3 variations failed. Try again or pick a different theme.",
            "technical": "all variations failed",
        })
        return

    await update(status="completed", progress=100, variations=variations)
    logger.info("[ai-designer] job=%s completed %d/%d variations", job_id, len(successes), total)

    if body.auto_copy:
        try:
            label = THEME_STYLES[body.theme]["label"]
            copy_pack = await _write_designer_copy(body.item_name, body.features, body.price, label)
            await db.ai_design_jobs.update_one(
                {"id": job_id}, {"$set": {"copy_pack": copy_pack, "updated_at": _now()}},
            )
            logger.info("[ai-designer] job=%s auto-copy completed", job_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("[ai-designer] job=%s auto-copy failed: %s", job_id, e)
            await db.ai_design_jobs.update_one(
                {"id": job_id}, {"$set": {"copy_error": str(e)[:300], "updated_at": _now()}},
            )


# ---------------------------------------------------------------- Routes

@router.get("/themes")
async def list_themes(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    return {
        "themes": [
            {
                "id": tid,
                "label": t["label"],
                "preview_color": "#{:02x}{:02x}{:02x}".format(*t["bg_color"]),
            }
            for tid, t in THEME_STYLES.items()
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
