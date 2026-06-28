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


# Tech Debt Sprint Step 6 / Chunk 7: theme background dispatcher moved to
# `ai_designer.composition`. Re-exported here under the same `_pil_background`
# name because tests (`test_theme_packs`, `test_variant_uniqueness`,
# `test_render_engine`, `test_overlays`, `test_typography_engine`) import it
# directly from `routers.ai_designer`. Keeping the re-export preserves their
# import path with zero churn.
from ai_designer.composition import _pil_background


# ---- PIL background primitives ------------------------------------------------
# Tech Debt Sprint Step 6 / Chunk 2 — all 19 decorative drawing helpers moved
# to `ai_designer.composition`. We re-export them here under the same `_xxx`
# names because `/app/backend/theme_packs/*.py` imports them directly from
# `routers.ai_designer`. Keeping the public import surface identical is the
# whole point of the re-export.

from ai_designer.composition import (
    _halftone_dots,
    _lightning_bolt,
    _speed_lines,
    _star,
    _squiggle,
    _sparks,
    _distressed_grain,
    _brush_stamp,
    _radial_gradient,
    _linear_gradient,
    _corner_frame,
    _corner_ornaments,
    _diagonal_ribbon,
    _marble_veins,
    _checker_strip,
    _corner_dots,
    _olive_branch,
    _confetti,
    _wavy_ribbon,
)


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
    """Tech Debt Sprint Step 6 / Chunk 3: delegates to
    ai_designer.composition._variant_food_transform.
    """
    from ai_designer.composition import _variant_food_transform as _impl
    return _impl(food_rgba, variant_idx)


def _rounded_rect_mask(im: Image.Image, radius_pct: float = 0.08) -> Image.Image:
    """Tech Debt Sprint Step 6: delegates to ai_designer.composition.rounded_rect_mask."""
    from ai_designer.composition import rounded_rect_mask as _impl
    return _impl(im, radius_pct)


def _drop_shadow(im: Image.Image, blur: int = 18, opacity: int = 110, offset: Tuple[int, int] = (0, 14)) -> Image.Image:
    """Tech Debt Sprint Step 6: delegates to ai_designer.composition.drop_shadow."""
    from ai_designer.composition import drop_shadow as _impl
    return _impl(im, blur, opacity, offset)


# ---------------------------------------------------------------- Ingredient icons
# Sprint 16A.2 — small deterministic PIL glyphs drawn next to bullet text on
# flyer themes. Implementation now lives in `ai_designer.composition`; the
# router only re-exports the icon dispatch surface used by `_draw_bullets`.

# Tech Debt Sprint Step 6: imports replace ~145 lines of inlined helpers.
from ai_designer.composition import (
    ICON_KEYWORDS,
    icon_for_feature as _icon_for_feature,
    rgba as _rgba,
    icon_burger as _icon_burger,
    icon_cheese as _icon_cheese,
    icon_onion as _icon_onion,
    icon_sauce as _icon_sauce,
    icon_fries as _icon_fries,
    icon_shrimp as _icon_shrimp,
    icon_fish as _icon_fish,
    icon_pickle as _icon_pickle,
    icon_drink as _icon_drink,
    icon_lettuce as _icon_lettuce,
    draw_ingredient_icon as _draw_ingredient_icon,
    _ICON_DRAWERS,  # re-exported for backward compatibility with tests that import it
)


# ---------------------------------------------------------------- Composition

def _draw_price_badge(canvas: Image.Image, theme: Dict[str, Any], price_text: str, cx: int, cy: int, radius: int) -> None:
    """Tech Debt Sprint Step 6 / Chunk 5: delegates to
    ai_designer.composition._draw_price_badge. Signature unchanged so
    `typography_engine`-aware callers continue to work without modification.
    """
    from ai_designer.composition import _draw_price_badge as _impl
    _impl(canvas, theme, price_text, cx, cy, radius)


def _draw_bullets(canvas: Image.Image, theme: Dict[str, Any], features: List[str],
                  x: int, y: int, max_w: int) -> None:
    """Tech Debt Sprint Step 6 / Chunk 6: delegates to
    ai_designer.composition._draw_bullets. Signature unchanged.
    """
    from ai_designer.composition import _draw_bullets as _impl
    _impl(canvas, theme, features, x, y, max_w)


def _draw_title(canvas: Image.Image, theme: Dict[str, Any], item_name: str,
                x: int, y: int, max_w: int, align: str = "center") -> int:
    """Tech Debt Sprint Step 6 / Chunk 8: delegates to
    ai_designer.composition._draw_title. Signature and return value unchanged.
    """
    from ai_designer.composition import _draw_title as _impl
    return _impl(canvas, theme, item_name, x, y, max_w, align)


def _draw_spaced(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                 x: int, y: int, spacing: int, *, fill,
                 stroke_width: int = 0, stroke_fill=None) -> None:
    """Tech Debt Sprint Step 6 / Chunk 3: delegates to
    ai_designer.composition._draw_spaced.
    """
    from ai_designer.composition import _draw_spaced as _impl
    _impl(draw, text, font, x, y, spacing,
          fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)


def _draw_branding(canvas: Image.Image, theme: Dict[str, Any]) -> None:
    """Tech Debt Sprint Step 6 / Chunk 4: delegates to
    ai_designer.composition._draw_branding with router-local constants
    (`FONT_SANS_BOLD`, `RESTAURANT_BRANDING`, `CANVAS`) injected. Preserves
    the original signature so call sites in `_compose_design` and elsewhere
    remain untouched.
    """
    from ai_designer.composition import _draw_branding as _impl
    _impl(canvas, theme, branding_text=RESTAURANT_BRANDING,
          font_path=FONT_SANS_BOLD, canvas_size=CANVAS)


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
    """Tech Debt Sprint Step 6 / Chunk 9: delegates to
    ai_designer.renderer.compose_design. Signature/return value unchanged.
    The router injects `RESTAURANT_BRANDING` so the renderer stays free of
    env access at call time.
    """
    from ai_designer.renderer import compose_design
    return compose_design(
        bg_bytes, food_rgba, item_name, features, price, theme_id, layout,
        variant_idx=variant_idx, cta=cta,
        include_price=include_price, include_description=include_description,
        platform=platform, tone=tone,
        logo_url=logo_url, logo_placement=logo_placement, logo_size=logo_size,
        branding_text=RESTAURANT_BRANDING,
    )


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
