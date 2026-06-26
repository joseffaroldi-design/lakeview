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
    The "safe default" — works for every kind of dish."""
    safe = 60
    title_band_h = 200
    bottom_band_h = 230
    food_max_w = CANVAS - 2 * safe
    food_max_h = CANVAS - title_band_h - bottom_band_h - 40
    food = _fit(food_rgba, food_max_w, food_max_h)
    fx = (CANVAS - food.width) // 2
    fy = title_band_h + 20 + (food_max_h - food.height) // 2
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
    """Food fills 75% of the canvas, bleeding off the right edge. Title and
    price overlay the left third. Editorial / poster feel."""
    safe = 50
    food_max_w = int(CANVAS * 0.85)
    food_max_h = int(CANVAS * 0.85)
    food = _fit(food_rgba, food_max_w, food_max_h)
    fx = CANVAS - food.width + int(food.width * 0.06)   # bleed off the right
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
    safe = 50
    food_max_w = int(CANVAS * 0.55)
    food_max_h = int(CANVAS * 0.78)
    food = _fit(food_rgba, food_max_w, food_max_h)
    fx = safe - 20
    fy = (CANVAS - food.height) // 2
    text_x = int(CANVAS * 0.55)
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
    safe = 50
    food_max_w = int(CANVAS * 0.55)
    food_max_h = int(CANVAS * 0.78)
    food = _fit(food_rgba, food_max_w, food_max_h)
    fx = CANVAS - food.width - safe + 20
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
    safe = 60
    food_max_w = int(CANVAS * 0.50)
    food_max_h = int(CANVAS * 0.50)
    food = _fit(food_rgba, food_max_w, food_max_h)
    fx = (CANVAS - food.width) // 2
    fy = int(CANVAS * 0.18) + (int(CANVAS * 0.52) - food.height) // 2
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
    """The Sprint 16G compositor.

    Builds the final flyer one z-layer at a time:

        bg (RGB) → soft-vignette band (legibility) → color-harmony wash →
        food (with feathered mask + layered shadows) → overlay_fn (foreground
        particles) → bullets/title/badge → branding.

    `draw_title`, `draw_bullets`, `draw_price_badge`, `draw_branding` are
    callbacks supplied by `routers.ai_designer` — this module never imports
    the router (no circular dependency).
    """
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

    # Tint shadow with theme accent if the theme has a dark mood; default black.
    accent = theme.get("title", {}).get("color")
    shadow_tint = (0, 0, 0)
    if isinstance(accent, (tuple, list)) and len(accent) >= 3 and theme.get("bg_color"):
        bg = theme["bg_color"]
        bg_lum = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
        if bg_lum < 80:  # dark themes → very slightly warm shadow looks better
            shadow_tint = (24, 12, 4)

    food_with_shadow = render_food_with_shadows(spec["food"], tint_rgb=shadow_tint)
    fx, fy = spec["food_pos"]
    # Re-centre by the shadow's padding so the food still sits at the chosen point.
    pad_x = (food_with_shadow.width - spec["food"].width) // 2
    pad_y = (food_with_shadow.height - spec["food"].height) // 2
    canvas.alpha_composite(food_with_shadow, (fx - pad_x, fy - pad_y))

    # ---- Foreground overlay (per-theme particles / texture / light rays) ----
    overlay_fn = theme.get("overlay_fn")
    if callable(overlay_fn):
        try:
            fg = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            fg_draw = ImageDraw.Draw(fg, "RGBA")
            overlay_fn(fg, fg_draw, variant_idx)
            canvas = Image.alpha_composite(canvas, fg)
        except Exception as e:  # noqa: BLE001
            logger.warning("[render_engine] overlay_fn failed for %s: %s", theme_id, e)

    # ---- Text + badge ---- (rect: x, y, w, h)
    tx, ty, tw, _th = spec["title_rect"]
    title_end_y = draw_title(canvas, theme, item_name, tx, ty, tw, spec["title_align"])
    bx, by, bw, _bh = spec["bullets_rect"]
    # If the layout placed bullets near the title and the title overflowed, push down.
    if by < title_end_y + 8 and spec["title_align"] == "center":
        by = title_end_y + 8
    draw_bullets(canvas, theme, features, bx, by, bw)

    cx, cy = spec["badge_centre"]
    draw_price_badge(canvas, theme,
                     (price or "").strip() or "—",
                     cx, cy, spec["badge_radius"])

    # ---- Branding ----
    draw_branding(canvas, theme)
    return canvas


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
]

# Suppress unused-import warning when ImageOps is imported but only sometimes used.
_ = ImageOps
