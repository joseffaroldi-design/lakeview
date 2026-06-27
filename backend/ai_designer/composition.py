"""
Composition Primitives — Pure PIL Helpers

Lowest-risk extraction (Tech Debt Sprint Step 6, Chunk 1).
This module contains stateless drawing helpers used by the procedural
flyer composer. Nothing here touches the database, jobs, request/response,
storage, or themes — only PIL primitives.

What lives here:
  * Color helpers (_rgba)
  * PIL effect helpers (_rounded_rect_mask, _drop_shadow)
  * Ingredient-icon glyphs (_icon_burger ... _icon_lettuce)
  * Icon dispatch (_icon_for_feature, _draw_ingredient_icon)

What does NOT belong here (do not add without review):
  * Theme dict access
  * Job orchestration / DB writes
  * Quality scoring
  * Agency template / HTML renderer dispatch
  * _compose_design and its variant transforms
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter


# ---------------------------------------------------------------- Color helpers

def rgba(color) -> Tuple[int, int, int, int]:
    """Promote an `(r, g, b)` tuple to `(r, g, b, 255)`. Pass-through otherwise."""
    if isinstance(color, tuple) and len(color) == 3:
        return color + (255,)
    return color


# ---------------------------------------------------------------- PIL effects

def rounded_rect_mask(im: Image.Image, radius_pct: float = 0.08) -> Image.Image:
    """Apply a rounded-rect alpha mask to a photo. Preserves all original food pixels."""
    radius = int(min(im.width, im.height) * radius_pct)
    mask = Image.new("L", im.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=radius, fill=255)
    out = im.copy()
    out.putalpha(mask)
    return out


def drop_shadow(
    im: Image.Image,
    blur: int = 18,
    opacity: int = 110,
    offset: Tuple[int, int] = (0, 14),
) -> Image.Image:
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


def icon_for_feature(text: str) -> Optional[str]:
    """Return the icon kind that matches `text`, or None."""
    s = (text or "").lower()
    if not s:
        return None
    for kw, kind in ICON_KEYWORDS:
        if kw in s:
            return kind
    return None


def icon_burger(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # Top bun (rounded hump) + patty/cheese strip + bottom bun (flat-top hump)
    th = max(4, int(s * 0.42))
    bh = max(4, int(s * 0.32))
    d.pieslice((x, y, x + s, y + th * 2), 180, 360, fill=c)
    mid_y1 = y + th + 2
    mid_y2 = y + s - bh - 2
    if mid_y2 > mid_y1:
        d.rectangle((x + s // 14, mid_y1, x + s - s // 14, mid_y2), fill=c)
    d.pieslice((x, y + s - bh * 2, x + s, y + s), 0, 180, fill=c)


def icon_cheese(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # Wedge triangle pointing up-right
    pts = [(x, y + s - 2), (x + s - 2, y + s - 2), (x + s - 2, y + s // 5)]
    d.polygon(pts, fill=c)


def icon_onion(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # Concentric rings — top-down view of a sliced onion
    cx, cy = x + s // 2, y + s // 2
    w = max(2, s // 22)
    for r in (s // 2 - 1, int(s * 0.36), int(s * 0.22), max(3, s // 10)):
        if r > 0:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=c, width=w)


def icon_sauce(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
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


def icon_fries(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
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


def icon_shrimp(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
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


def icon_fish(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # Oval body + triangle tail on the right
    d.ellipse((x + s // 10, y + s // 4, x + s - s // 4, y + s * 3 // 4), fill=c)
    d.polygon(
        [(x + s - s // 4 - 2, y + s // 2),
         (x + s - 2, y + s // 5),
         (x + s - 2, y + s - s // 5)],
        fill=c,
    )


def icon_pickle(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
    # Vertical oval + 3 small bumps along one edge
    d.ellipse((x + s // 3, y + s // 8, x + s * 2 // 3, y + s - s // 8), fill=c)
    bump = max(3, s // 12)
    for fy in (y + s // 3, y + s // 2, y + s * 2 // 3):
        d.ellipse(
            (x + s * 2 // 3 - bump // 2, fy - bump // 2,
             x + s * 2 // 3 + bump, fy + bump),
            fill=c,
        )


def icon_drink(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
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


def icon_lettuce(d: ImageDraw.ImageDraw, x: int, y: int, s: int, c) -> None:
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
    "burger": icon_burger,
    "cheese": icon_cheese,
    "onion": icon_onion,
    "sauce": icon_sauce,
    "fries": icon_fries,
    "shrimp": icon_shrimp,
    "fish": icon_fish,
    "pickle": icon_pickle,
    "drink": icon_drink,
    "lettuce": icon_lettuce,
}


def draw_ingredient_icon(canvas: Image.Image, kind: str, x: int, y: int,
                         size: int, color) -> None:
    """Draw the ingredient glyph `kind` at (x, y) within a `size x size` box."""
    fn = _ICON_DRAWERS.get(kind)
    if not fn:
        return
    draw = ImageDraw.Draw(canvas, "RGBA")
    fn(draw, x, y, size, rgba(color))


__all__ = [
    "rgba",
    "rounded_rect_mask",
    "drop_shadow",
    "ICON_KEYWORDS",
    "icon_for_feature",
    "icon_burger",
    "icon_cheese",
    "icon_onion",
    "icon_sauce",
    "icon_fries",
    "icon_shrimp",
    "icon_fish",
    "icon_pickle",
    "icon_drink",
    "icon_lettuce",
    "draw_ingredient_icon",
]
