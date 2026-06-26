"""Sprint 16G — Flyer Rendering Engine 2.0
================================================================================

Replaces the "photo-in-a-box + drop shadow" pipeline that shipped with
Sprint 13B. Every existing theme (and every future theme) inherits the
upgrade automatically — no theme-pack dict edits are required.

What this module owns
---------------------
  • `feather_mask`              — soft elliptical/rounded alpha mask, replaces
                                  the hard rounded-rect crop.
  • `render_food_with_shadows`  — layered ambient + contact shadow under
                                  the food. Replaces the single drop shadow.
  • `dominant_food_colors`      — pulls 1-3 representative colors from the
                                  uploaded photo (ignores shadows/highlights).
  • `apply_color_harmony`       — washes a portion of the canvas with the
                                  dominant food color at `harmony_strength`
                                  (default 0.25 → theme palette still wins).
  • `LAYOUTS` + `pick_layout`   — six composition variants. The legacy
                                  `centered / asym_left / stacked` strings
                                  still work and are mapped to the new
                                  layouts so old callers don't break.
  • `compose_with_layout`       — the single entry point the router calls.
                                  All the new behaviour lives behind it.

Design rules
------------
  1. Pure PIL. No new dependencies. No AI image generation.
  2. Backwards compatible. Themes that didn't opt in to `overlay_fn`,
     `harmony_strength` or `supported_layouts` get sensible defaults.
  3. Deterministic. Variants 0/1/2 always pick the same layout for a
     given theme id, so regenerating a flyer is reproducible.
  4. Cost: < 250 ms added per flyer at 1024 px.
"""
from __future__ import annotations

import hashlib
import io
import logging
import math
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageOps

logger = logging.getLogger("uvicorn.error")

CANVAS = 1024  # canonical canvas size; matches theme_packs._shared.CANVAS


# =============================================================================
# 1. SOFT MASKING — kill the rectangle
# =============================================================================

def feather_mask(im: Image.Image, radius_pct: float = 0.06,
                 feather_blur_pct: float = 0.025) -> Image.Image:
    """Apply a soft, blurred rounded-rect mask to an RGBA image.

    The mask is a rounded rectangle slightly inset from the photo edge, with
    a SMALL gaussian blur on the alpha so the boundary fades organically into
    transparency instead of clipping along a hard rectangle edge.

    Designed to keep ~92% of the food opaque and only soften the outer
    ~25 px on a 1024-px photo — the food stays photographic, only the rigid
    rectangular boundary is removed.

    `radius_pct` — corner radius as a % of the shortest side (0.0 → square,
                   0.5 → ellipse). Default 0.06.
    `feather_blur_pct` — softness of the edge fade (0.0 → hard, 0.10 → very
                         soft and the food becomes a blob). Default 0.025.
    """
    w, h = im.size
    if w == 0 or h == 0:
        return im
    inset = max(2, int(min(w, h) * feather_blur_pct * 0.9))
    radius = int(min(w, h) * radius_pct)

    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((inset, inset, w - inset, h - inset),
                        radius=radius, fill=255)
    blur_px = max(2, int(min(w, h) * feather_blur_pct))
    mask = mask.filter(ImageFilter.GaussianBlur(blur_px))

    # If the photo already has alpha (e.g. rembg cut-out), combine multiplicatively.
    if im.mode == "RGBA":
        existing = im.getchannel("A")
        combined = ImageChops_multiply(existing, mask)
        out = im.copy()
        out.putalpha(combined)
        return out
    out = im.convert("RGBA")
    out.putalpha(mask)
    return out


def ImageChops_multiply(a: Image.Image, b: Image.Image) -> Image.Image:
    """Tiny alias so we don't have to import ImageChops at top-level for one call."""
    from PIL import ImageChops
    return ImageChops.multiply(a, b)


# =============================================================================
# 2. LAYERED SHADOWS — ambient (the food sits in a space) + contact (anchored)
# =============================================================================

def render_food_with_shadows(food_rgba: Image.Image,
                             ambient_blur: int = 26,
                             ambient_opacity: int = 130,
                             ambient_offset_y: int = 24,
                             contact_blur: int = 8,
                             contact_opacity: int = 150,
                             contact_offset_y: int = 8,
                             tint_rgb: Tuple[int, int, int] = (0, 0, 0)) -> Image.Image:
    """Return a padded RGBA layer with the food sitting on two shadow passes.

    * Ambient shadow — large, soft, offset down; gives volume in the scene.
    * Contact shadow — small, sharper, offset only a few pixels; anchors the
                       food onto the surface (no floating).
    * `tint_rgb` — shadow tint. Defaults to black. Themes with a colored mood
                   (e.g. warm orange BBQ) can pass `(60, 30, 10)` for a richer
                   feel.
    """
    pad = ambient_blur * 2 + 24
    layer = Image.new("RGBA", (food_rgba.width + pad * 2, food_rgba.height + pad * 2),
                      (0, 0, 0, 0))
    if food_rgba.mode != "RGBA":
        food_rgba = food_rgba.convert("RGBA")
    alpha = food_rgba.getchannel("A")

    # ---- Ambient pass ----
    amb_mask = Image.new("L", layer.size, 0)
    amb_mask.paste(alpha, (pad, pad + ambient_offset_y))
    amb_mask = amb_mask.filter(ImageFilter.GaussianBlur(ambient_blur))
    # Scale opacity by multiplying the mask channel
    if ambient_opacity != 255:
        amb_mask = amb_mask.point(lambda p, k=ambient_opacity: int(p * k / 255))
    amb_color = Image.new("RGBA", layer.size, tint_rgb + (255,))
    amb_color.putalpha(amb_mask)
    layer.alpha_composite(amb_color)

    # ---- Contact pass ----
    con_mask = Image.new("L", layer.size, 0)
    con_mask.paste(alpha, (pad, pad + contact_offset_y))
    con_mask = con_mask.filter(ImageFilter.GaussianBlur(contact_blur))
    if contact_opacity != 255:
        con_mask = con_mask.point(lambda p, k=contact_opacity: int(p * k / 255))
    con_color = Image.new("RGBA", layer.size, tint_rgb + (255,))
    con_color.putalpha(con_mask)
    layer.alpha_composite(con_color)

    # ---- Food on top ----
    layer.alpha_composite(food_rgba, (pad, pad))
    return layer


# =============================================================================
# 3. COLOR HARMONY — sample food, influence the canvas
# =============================================================================

def dominant_food_colors(food_rgba: Image.Image, n: int = 3) -> List[Tuple[int, int, int]]:
    """Return up to `n` representative colors from the food photo.

    Strategy: thumbnail to 64×64, run PIL quantize (median-cut), drop
    near-black + near-white buckets (those usually represent shadows /
    highlights / bg) and order the remaining by pixel count.
    """
    if food_rgba.width == 0 or food_rgba.height == 0:
        return []
    small = food_rgba.copy()
    small.thumbnail((64, 64), Image.LANCZOS)
    # Mask out transparent pixels by compositing onto neutral gray (so they
    # quantize into a single "ignore me" bucket we'll drop).
    if small.mode == "RGBA":
        bg = Image.new("RGB", small.size, (127, 127, 127))
        bg.paste(small, mask=small.getchannel("A"))
        rgb = bg
    else:
        rgb = small.convert("RGB")
    pal = rgb.quantize(colors=n + 4, method=Image.Quantize.MEDIANCUT)
    palette = pal.getpalette() or []
    counts = Counter(pal.getdata())
    picked: List[Tuple[int, int, int]] = []
    for idx, _ in counts.most_common(n + 4):
        if idx * 3 + 2 >= len(palette):
            continue
        r, g, b = palette[idx * 3], palette[idx * 3 + 1], palette[idx * 3 + 2]
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        if lum < 30 or lum > 235:
            continue
        # Reject near-neutral gray (probably the transparent-pixel placeholder).
        if abs(r - 127) < 8 and abs(g - 127) < 8 and abs(b - 127) < 8:
            continue
        picked.append((r, g, b))
        if len(picked) >= n:
            break
    return picked


def apply_color_harmony(canvas: Image.Image, food_rgba: Image.Image,
                        strength: float = 0.25) -> Image.Image:
    """Subtly tint the canvas CORNERS with colors sampled from the food.

    Why corners only?  We can't safely paint a wash through the centre of
    the canvas — that's exactly where the food sits, and a mid-canvas wash
    causes the food's photographic detail to flatten against the background.
    Instead, two faint radial glows pull the food's dominant tones into
    diagonally opposite corners. The result reads as ambient lighting, not
    as a coloured overlay across the dish.

    `strength` is clamped to [0, 1]. The maximum corner alpha is ~45/255 at
    strength=1.0; at the recommended default of 0.25 it's ~12/255 — present
    but never overpowering.
    """
    if strength <= 0.0 or canvas.size != (CANVAS, CANVAS):
        return canvas
    colors = dominant_food_colors(food_rgba, n=2)
    if not colors:
        return canvas
    primary = colors[0]
    secondary = colors[1] if len(colors) > 1 else primary

    # Two opposite-corner glows — top-left + bottom-right (light + warmth)
    corner_alpha = int(min(1.0, strength) * 45)
    if corner_alpha < 4:
        return canvas
    glow = Image.new("L", (CANVAS, CANVAS), 0)
    gd = ImageDraw.Draw(glow)
    # Top-left blob — primary tint
    gd.ellipse((-300, -300, 380, 380), fill=corner_alpha)
    # Bottom-right blob — also primary so it stays cohesive
    gd.ellipse((CANVAS - 380, CANVAS - 380, CANVAS + 300, CANVAS + 300),
               fill=corner_alpha)
    glow = glow.filter(ImageFilter.GaussianBlur(180))
    layer_a = Image.new("RGBA", (CANVAS, CANVAS), primary + (255,))
    layer_a.putalpha(glow)
    canvas.alpha_composite(layer_a)

    # Cross-axis secondary glow — softer, narrower
    sec_alpha = int(min(1.0, strength) * 28)
    if sec_alpha >= 3 and secondary != primary:
        sg = Image.new("L", (CANVAS, CANVAS), 0)
        sgd = ImageDraw.Draw(sg)
        sgd.ellipse((CANVAS - 380, -300, CANVAS + 300, 380), fill=sec_alpha)
        sgd.ellipse((-300, CANVAS - 380, 380, CANVAS + 300), fill=sec_alpha)
        sg = sg.filter(ImageFilter.GaussianBlur(180))
        layer_b = Image.new("RGBA", (CANVAS, CANVAS), secondary + (255,))
        layer_b.putalpha(sg)
        canvas.alpha_composite(layer_b)
    return canvas


# =============================================================================
# 4. LIGHTING NUDGE — gently warm/cool the food to match the theme palette
# =============================================================================
# Cheap heuristic only (no LAB conversion): the food gets a faint tint pass
# using the theme's title accent color at ~10% opacity. Keeps the food
# recognisable while making it feel like it belongs in the design.

def warm_to_theme(food_rgba: Image.Image, accent_rgb: Tuple[int, int, int],
                  strength: float = 0.10) -> Image.Image:
    """Multiply-blend the food with `accent_rgb` at `strength`."""
    if strength <= 0:
        return food_rgba
    if food_rgba.mode != "RGBA":
        food_rgba = food_rgba.convert("RGBA")
    tint = Image.new("RGBA", food_rgba.size, accent_rgb + (int(255 * strength),))
    # Only apply where the food is opaque (so we don't tint stray transparent edges)
    alpha = food_rgba.getchannel("A")
    tint.putalpha(alpha)
    out = food_rgba.copy()
    out.alpha_composite(tint)
    return out


# =============================================================================
# 5. LAYOUTS — six composition variants
# =============================================================================
# Each layout is a (food_rect, title_rect, bullets_rect, badge_centre, badge_r,
# title_align, badge_size_factor) tuple. The router does the actual text+badge
# drawing — render_engine just decides geometry + food placement style.

LayoutSpec = Dict[str, Any]


def _scale_up_to_target(food: Image.Image, max_w: int, max_h: int,
                        target_frac: float = 0.92) -> Image.Image:
    """Sprint 19 hotfix — boost the food image to actually fill its slot.

    `_fit` shrinks until the food fits within (max_w, max_h) preserving
    aspect, which often leaves 30-50% of the slot empty for portrait
    dishes. This function then scales the result UP so the LARGER of
    width/height equals `target_frac * min(max_w, max_h)`. The food
    becomes the hero per spec (60-75% canvas prominence).
    """
    if food.width == 0 or food.height == 0:
        return food
    target = int(min(max_w, max_h) * target_frac)
    cur = max(food.width, food.height)
    if cur >= target:
        return food
    scale = target / cur
    nw = min(max_w, int(food.width * scale))
    nh = min(max_h, int(food.height * scale))
    return food.resize((nw, nh), Image.LANCZOS)


def _fit(food: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """Scale `food` so it fits inside (max_w, max_h) while preserving aspect."""
    if food.width == 0 or food.height == 0:
        return food
    scale = min(max_w / food.width, max_h / food.height)
    new_w = max(1, int(food.width * scale))
    new_h = max(1, int(food.height * scale))
    return food.resize((new_w, new_h), Image.LANCZOS)


def layout_hero_center(food_rgba: Image.Image,
                       title_size_hint: int = 110) -> LayoutSpec:
    """Title top, food big in the middle, bullets + price band at the bottom.
    The "safe default" — works for every kind of dish.

    Sprint 19 hotfix: bumped food caps so the dish actually dominates
    (target 60–75% of canvas, was ~55%).
    """
    safe = 40
    title_band_h = 180
    bottom_band_h = 200
    food_max_w = CANVAS - 2 * safe
    food_max_h = CANVAS - title_band_h - bottom_band_h
    food = _fit(food_rgba, food_max_w, food_max_h)
    # Sprint 19: scale up 1.35× so a tall portrait dish actually fills the slot.
    food = _scale_up_to_target(food, food_max_w, food_max_h, target_frac=0.92)
    fx = (CANVAS - food.width) // 2
    fy = title_band_h + 10 + (food_max_h - food.height) // 2
    return {
        "food": food,
        "food_pos": (fx, fy),
        "title_rect": (safe, safe, CANVAS - 2 * safe, title_band_h),
        "title_align": "center",
        "bullets_rect": (safe, CANVAS - bottom_band_h + 10, CANVAS - 2 * safe - 220, bottom_band_h - 20),
        "badge_centre": (CANVAS - 130, CANVAS - 130),
        "badge_radius": 100,
    }


def layout_full_bleed(food_rgba: Image.Image,
                      title_size_hint: int = 110) -> LayoutSpec:
    """Food fills 90%+ of the canvas, bleeding off the right edge. Title and
    price overlay the left third. Editorial / poster feel."""
    safe = 50
    food_max_w = int(CANVAS * 0.98)
    food_max_h = int(CANVAS * 0.98)
    food = _fit(food_rgba, food_max_w, food_max_h)
    food = _scale_up_to_target(food, food_max_w, food_max_h, target_frac=0.95)
    fx = CANVAS - food.width + int(food.width * 0.08)   # bleed off the right
    fy = (CANVAS - food.height) // 2
    return {
        "food": food,
        "food_pos": (fx, fy),
        "title_rect": (safe, safe + 30, int(CANVAS * 0.50), 280),
        "title_align": "left",
        "bullets_rect": (safe, int(CANVAS * 0.52), int(CANVAS * 0.45), 240),
        "badge_centre": (safe + 110, CANVAS - 150),
        "badge_radius": 105,
    }


def layout_left_focus(food_rgba: Image.Image,
                      title_size_hint: int = 100) -> LayoutSpec:
    """Food large on the left, text column on the right."""
    safe = 40
    food_max_w = int(CANVAS * 0.70)   # was 0.55
    food_max_h = int(CANVAS * 0.90)   # was 0.78
    food = _fit(food_rgba, food_max_w, food_max_h)
    food = _scale_up_to_target(food, food_max_w, food_max_h, target_frac=0.92)
    fx = safe - 30
    fy = (CANVAS - food.height) // 2
    text_x = int(CANVAS * 0.62)
    text_w = CANVAS - text_x - safe
    return {
        "food": food,
        "food_pos": (fx, fy),
        "title_rect": (text_x, safe + 30, text_w, 260),
        "title_align": "left",
        "bullets_rect": (text_x, safe + 320, text_w, 280),
        "badge_centre": (CANVAS - 130, CANVAS - 150),
        "badge_radius": 95,
    }


def layout_right_focus(food_rgba: Image.Image,
                       title_size_hint: int = 100) -> LayoutSpec:
    """Mirror of left_focus — food right, text column left."""
    safe = 40
    food_max_w = int(CANVAS * 0.70)
    food_max_h = int(CANVAS * 0.90)
    food = _fit(food_rgba, food_max_w, food_max_h)
    food = _scale_up_to_target(food, food_max_w, food_max_h, target_frac=0.92)
    fx = CANVAS - food.width - safe + 30
    fy = (CANVAS - food.height) // 2
    return {
        "food": food,
        "food_pos": (fx, fy),
        "title_rect": (safe, safe + 30, int(CANVAS * 0.40), 260),
        "title_align": "left",
        "bullets_rect": (safe, safe + 320, int(CANVAS * 0.42), 280),
        "badge_centre": (safe + 110, CANVAS - 150),
        "badge_radius": 95,
    }


def layout_bottom_hero(food_rgba: Image.Image,
                       title_size_hint: int = 120) -> LayoutSpec:
    """Title BIG at the top, food spans the bottom 60% slightly off-canvas."""
    safe = 50
    title_band_h = int(CANVAS * 0.38)
    food_max_w = int(CANVAS * 0.92)
    food_max_h = int(CANVAS * 0.65)
    food = _fit(food_rgba, food_max_w, food_max_h)
    fx = (CANVAS - food.width) // 2
    # Push 5% below the canvas so it bleeds at the bottom
    fy = CANVAS - food.height + int(food.height * 0.05)
    return {
        "food": food,
        "food_pos": (fx, fy),
        "title_rect": (safe, safe, CANVAS - 2 * safe, title_band_h - 80),
        "title_align": "center",
        # Bullets squeezed in the narrow strip between title and food
        "bullets_rect": (safe, title_band_h - 30, int(CANVAS * 0.55), 110),
        "badge_centre": (CANVAS - 140, title_band_h + 10),
        "badge_radius": 95,
    }


def layout_stacked(food_rgba: Image.Image,
                   title_size_hint: int = 110) -> LayoutSpec:
    """Title large at the top, food upper-center, bullets+price band bottom."""
    safe = 50
    food_max_w = int(CANVAS * 0.78)
    food_max_h = int(CANVAS * 0.68)
    food = _fit(food_rgba, food_max_w, food_max_h)
    food = _scale_up_to_target(food, food_max_w, food_max_h, target_frac=0.92)
    fx = (CANVAS - food.width) // 2
    fy = int(CANVAS * 0.18) + (food_max_h - food.height) // 2
    return {
        "food": food,
        "food_pos": (fx, fy),
        "title_rect": (safe, safe - 10, CANVAS - 2 * safe, 190),
        "title_align": "center",
        "bullets_rect": (safe, CANVAS - 230, int(CANVAS * 0.55), 200),
        "badge_centre": (CANVAS - 150, CANVAS - 150),
        "badge_radius": 100,
    }


LAYOUTS: Dict[str, Callable[..., LayoutSpec]] = {
    "hero_center":  layout_hero_center,
    "full_bleed":   layout_full_bleed,
    "left_focus":   layout_left_focus,
    "right_focus":  layout_right_focus,
    "bottom_hero":  layout_bottom_hero,
    "stacked":      layout_stacked,
}

# Legacy aliases — old code paths still pass these strings.
LEGACY_LAYOUT_ALIAS = {
    "centered":   "hero_center",
    "asym_left":  "left_focus",
    "asym_right": "right_focus",
    "stacked":    "stacked",
}

DEFAULT_SUPPORTED_LAYOUTS: Tuple[str, ...] = (
    "hero_center", "left_focus", "bottom_hero", "right_focus", "full_bleed", "stacked",
)


def pick_layout(theme_id: str, variant_idx: int,
                supported: Optional[Sequence[str]] = None) -> str:
    """Deterministically choose one of the supported layouts for this
    (theme, variant) pair. Three variants of the same theme always pick
    three DIFFERENT layouts when at least 3 are supported.

    `supported=None`  → use the default pool (all 6 layouts).
    `supported=[]`    → caller explicitly disabled the picker → return the
                        safest layout (hero_center) instead.
    """
    if supported is None:
        pool = list(DEFAULT_SUPPORTED_LAYOUTS)
    elif len(supported) == 0:
        return "hero_center"
    else:
        pool = list(supported)
    if not pool:
        return "hero_center"
    # Stable seed from the theme id so different themes pick different start indexes
    seed = int(hashlib.md5(theme_id.encode("utf-8")).hexdigest()[:6], 16)
    return pool[(seed + variant_idx) % len(pool)]


# =============================================================================
# 6. THE NEW PIPELINE — one entry point the router calls
# =============================================================================

def compose_layered(
    *,
    bg_image: Image.Image,
    food_rgba: Image.Image,
    theme: Dict[str, Any],
    theme_id: str,
    variant_idx: int,
    draw_title: Callable[[Image.Image, Dict[str, Any], int, int, int, int, str], int],
    draw_bullets: Callable[[Image.Image, Dict[str, Any], int, int, int], None],
    draw_price_badge: Callable[[Image.Image, Dict[str, Any], str, int, int, int], None],
    draw_branding: Callable[[Image.Image, Dict[str, Any]], None],
    item_name: str,
    features: List[str],
    price: Optional[str],
    layout_override: Optional[str] = None,
) -> Image.Image:
    """Sprint 16G compositor — single render path. Preserved for callers
    that only need the canvas.
    """
    canvas, _info, _title_h = _compose_once(
        bg_image=bg_image, food_rgba=food_rgba,
        theme=theme, theme_id=theme_id, variant_idx=variant_idx,
        draw_title=draw_title, draw_bullets=draw_bullets,
        draw_price_badge=draw_price_badge, draw_branding=draw_branding,
        item_name=item_name, features=features, price=price,
        layout_override=layout_override,
    )
    return canvas


def compose_layered_with_score(
    *,
    bg_image: Image.Image,
    food_rgba: Image.Image,
    theme: Dict[str, Any],
    theme_id: str,
    variant_idx: int,
    draw_title: Callable[[Image.Image, Dict[str, Any], int, int, int, int, str], int],
    draw_bullets: Callable[[Image.Image, Dict[str, Any], int, int, int], None],
    draw_price_badge: Callable[[Image.Image, Dict[str, Any], str, int, int, int], None],
    draw_branding: Callable[[Image.Image, Dict[str, Any]], None],
    item_name: str,
    features: List[str],
    price: Optional[str],
    layout_override: Optional[str] = None,
    target_score: float = 75.0,
    max_iterations: int = 2,
) -> Tuple[Image.Image, Dict[str, Any]]:
    """Sprint 18 — iterative compose. Renders an initial candidate,
    scores it, and if the score is below `target_score` renders ONE
    alternative layout (chosen by mapping the weakest metric → layout
    hint). Returns the higher-scoring canvas + the score breakdown.

    Budget: at most `max_iterations` total renders (default 2), so the
    extra cost over compose_layered is one full render (~250ms) + two
    scorings (~60ms) → still under the 500ms/flyer ceiling.
    """
    from quality_score import (
        CompositionInfo,
        WEAKEST_TO_HINT,
        score_composition,
    )

    supported = theme.get("supported_layouts")
    supported_set = set(supported or DEFAULT_SUPPORTED_LAYOUTS)
    tried: List[str] = []
    best_canvas: Optional[Image.Image] = None
    best_score: Optional[Dict[str, Any]] = None
    best_layout: Optional[str] = None

    current_override = layout_override
    for it in range(max(1, max_iterations)):
        canvas, info, title_h = _compose_once(
            bg_image=bg_image, food_rgba=food_rgba,
            theme=theme, theme_id=theme_id, variant_idx=variant_idx,
            draw_title=draw_title, draw_bullets=draw_bullets,
            draw_price_badge=draw_price_badge, draw_branding=draw_branding,
            item_name=item_name, features=features, price=price,
            layout_override=current_override,
        )
        sc = score_composition(canvas, info, title_pixel_height=title_h)
        sc["iteration"] = it + 1
        sc["layout"] = info.layout_name
        tried.append(info.layout_name)
        if best_score is None or sc["score"] > best_score["score"]:
            best_canvas, best_score, best_layout = canvas, sc, info.layout_name
        if sc["score"] >= target_score:
            break
        # Pick the next layout candidate based on the weakest metric.
        hint = WEAKEST_TO_HINT.get(sc["weakest"])
        # Skip if the hint is unsupported by the theme or already tried.
        if not hint or hint not in supported_set or hint in tried:
            # Fallback: rotate to the next layout in the supported pool.
            pool = [x for x in (supported or DEFAULT_SUPPORTED_LAYOUTS) if x not in tried]
            if not pool:
                break
            hint = pool[0]
        current_override = hint

    assert best_canvas is not None and best_score is not None
    best_score["candidates_tried"] = tried
    best_score["chosen_layout"] = best_layout
    return best_canvas, best_score


def _compose_once(
    *,
    bg_image: Image.Image,
    food_rgba: Image.Image,
    theme: Dict[str, Any],
    theme_id: str,
    variant_idx: int,
    draw_title: Callable[[Image.Image, Dict[str, Any], int, int, int, int, str], int],
    draw_bullets: Callable[[Image.Image, Dict[str, Any], int, int, int], None],
    draw_price_badge: Callable[[Image.Image, Dict[str, Any], str, int, int, int], None],
    draw_branding: Callable[[Image.Image, Dict[str, Any]], None],
    item_name: str,
    features: List[str],
    price: Optional[str],
    layout_override: Optional[str] = None,
):
    """The Sprint 16G compositor (single render). Returns
    (canvas, CompositionInfo, title_pixel_height).
    """
    from quality_score import CompositionInfo

    canvas = bg_image.convert("RGBA")

    # ---- Title-legibility bands (top/bottom) — unchanged from 13B ----
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, CANVAS, 140), fill=(0, 0, 0, 60))
    od.rectangle((0, CANVAS - 140, CANVAS, CANVAS), fill=(0, 0, 0, 50))
    canvas = Image.alpha_composite(canvas, overlay)

    # ---- COLOR HARMONY — food's primary tone tinted onto the canvas band ----
    harmony_strength = float(theme.get("harmony_strength", 0.25))
    if harmony_strength > 0:
        apply_color_harmony(canvas, food_rgba, strength=harmony_strength)

    # ---- Choose layout & render food with new shadows ----
    layout_name = layout_override or pick_layout(
        theme_id, variant_idx,
        supported=theme.get("supported_layouts"),
    )
    layout_name = LEGACY_LAYOUT_ALIAS.get(layout_name, layout_name)
    if layout_name not in LAYOUTS:
        layout_name = "hero_center"
    spec = LAYOUTS[layout_name](food_rgba)

    accent = theme.get("title", {}).get("color")
    shadow_tint = (0, 0, 0)
    if isinstance(accent, (tuple, list)) and len(accent) >= 3 and theme.get("bg_color"):
        bg = theme["bg_color"]
        bg_lum = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
        if bg_lum < 80:
            shadow_tint = (24, 12, 4)

    food_with_shadow = render_food_with_shadows(spec["food"], tint_rgb=shadow_tint)
    fx, fy = spec["food_pos"]
    pad_x = (food_with_shadow.width - spec["food"].width) // 2
    pad_y = (food_with_shadow.height - spec["food"].height) // 2
    canvas.alpha_composite(food_with_shadow, (fx - pad_x, fy - pad_y))

    # ---- Foreground overlay (per-theme particles / texture / light rays) ----
    # Sprint 19 hotfix: overlays should SUPPORT the food, not compete with
    # it. Composite the overlay layer at 45% opacity (was 100%) so waves /
    # smoke / confetti recede behind the hero.
    overlay_fn = theme.get("overlay_fn")
    if callable(overlay_fn):
        try:
            fg = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            fg_draw = ImageDraw.Draw(fg, "RGBA")
            overlay_fn(fg, fg_draw, variant_idx)
            # Knock overlay alpha down to 45% so it never fights the food.
            alpha = fg.getchannel("A")
            faded = alpha.point(lambda v: int(v * 0.45))
            fg.putalpha(faded)
            canvas = Image.alpha_composite(canvas, fg)
        except Exception as e:  # noqa: BLE001
            logger.warning("[render_engine] overlay_fn failed for %s: %s", theme_id, e)

    # ---- Text + badge ----
    tx, ty, tw, _th = spec["title_rect"]
    title_end_y = draw_title(canvas, theme, item_name, tx, ty, tw, spec["title_align"])
    bx, by, bw, _bh = spec["bullets_rect"]
    if by < title_end_y + 8 and spec["title_align"] == "center":
        by = title_end_y + 8
    draw_bullets(canvas, theme, features, bx, by, bw)

    # Sprint 19 hotfix — GUARANTEE the badge has a filled background.
    # Some legacy badge styles (e.g. distressed_stamp) only drew an outline
    # which read as "broken / dashed circle". Draw a filled disc UNDER every
    # badge so even outline-only styles always look intentional.
    cx, cy = spec["badge_centre"]
    badge_radius = spec["badge_radius"]
    badge_bg = theme.get("badge_bg") or theme.get("branding_color") or (220, 70, 50)
    badge_ring = theme.get("badge_ring") or (255, 220, 100)
    badge_pad_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(badge_pad_layer)
    # Subtle outer ring for premium feel
    bdraw.ellipse(
        (cx - badge_radius - 8, cy - badge_radius - 8,
         cx + badge_radius + 8, cy + badge_radius + 8),
        fill=tuple(list(badge_ring)[:3]) + (255,),
    )
    bdraw.ellipse(
        (cx - badge_radius, cy - badge_radius,
         cx + badge_radius, cy + badge_radius),
        fill=tuple(list(badge_bg)[:3]) + (255,),
    )
    canvas = Image.alpha_composite(canvas, badge_pad_layer)

    draw_price_badge(canvas, theme,
                     (price or "").strip() or "—",
                     cx, cy, badge_radius)

    # ---- Branding ----
    draw_branding(canvas, theme)

    # ---- Pack composition info for scoring ----
    food_bbox = (fx, fy, fx + spec["food"].width, fy + spec["food"].height)
    title_bbox = (tx, ty, tx + tw, max(ty + 60, title_end_y))
    title_pixel_height = max(40, title_end_y - ty)
    bullets_bbox = (bx, by, bx + bw, by + spec["bullets_rect"][3])
    info = CompositionInfo(
        canvas_size=CANVAS,
        food_bbox=food_bbox,
        title_bbox=title_bbox,
        badge_centre=(cx, cy),
        badge_radius=spec["badge_radius"],
        bullets_bbox=bullets_bbox,
        has_overlay=bool(overlay_fn),
    )
    # Stash chosen layout name on the info object so the iterative wrapper
    # can record what was tried. (CompositionInfo is a dataclass — set
    # via attribute write.)
    info.layout_name = layout_name  # type: ignore[attr-defined]
    return canvas, info, title_pixel_height


__all__ = [
    "CANVAS",
    "feather_mask",
    "render_food_with_shadows",
    "dominant_food_colors",
    "apply_color_harmony",
    "warm_to_theme",
    "LAYOUTS",
    "LEGACY_LAYOUT_ALIAS",
    "DEFAULT_SUPPORTED_LAYOUTS",
    "pick_layout",
    "compose_layered",
    "compose_layered_with_score",
]

# Suppress unused-import warning when ImageOps is imported but only sometimes used.
_ = ImageOps
