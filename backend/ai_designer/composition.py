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
    # Background painter primitives (Chunk 2 — keep `_xxx` names because
    # theme_packs/*.py import these directly from routers.ai_designer; the
    # router re-exports them under the same names.)
    "_halftone_dots",
    "_lightning_bolt",
    "_speed_lines",
    "_star",
    "_squiggle",
    "_sparks",
    "_distressed_grain",
    "_brush_stamp",
    "_radial_gradient",
    "_linear_gradient",
    "_corner_frame",
    "_corner_ornaments",
    "_diagonal_ribbon",
    "_marble_veins",
    "_checker_strip",
    "_corner_dots",
    "_olive_branch",
    "_confetti",
    "_wavy_ribbon",
]


# ---------------------------------------------------------------- Background painter primitives
# Tech Debt Sprint Step 6 / Chunk 2 — moved from routers/ai_designer.py.
# Kept the `_xxx` names because /app/backend/theme_packs/*.py imports them
# directly from `routers.ai_designer`. The router re-exports them under the
# same names so theme packs continue working without modification.
#
# All helpers reference `CANVAS` (the procedural-renderer reference size).
# This constant is duplicated here intentionally — it mirrors the value in
# routers/ai_designer.py and must stay in sync.

CANVAS = 1024


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
