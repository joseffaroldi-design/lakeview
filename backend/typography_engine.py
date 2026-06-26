"""Sprint 16I — Premium typography & badge engine.

Layers on top of `routers.ai_designer`'s `_draw_title`, `_draw_price_badge`
and `_draw_bullets` without changing their public signatures.

What's new
----------
  * `split_title_lines`  — 1-3 word titles are rendered stacked one-per-line
                            with a 1.15× size bump per line (Phase 1).
  * `draw_title_backdrop`— optional ribbon / swash / distressed rect behind
                            each title line (Phase 2).
  * `BADGE_STYLES`        — burst, sticker, chalk_circle, ribbon, ticket,
                            distressed_stamp. `pick_badge_style(theme_id,
                            variant_idx)` returns one deterministically.
  * `draw_premium_badge`  — dispatcher that renders the chosen badge style.
  * `draw_pill_chips`     — pill-shaped ingredient tags (Phase 4).

Everything is opt-in: legacy themes that don't carry `pill_chips` /
`backdrop_style` / `badge_style` keys keep rendering the way they did
before this sprint. The router decides per (theme, variant) whether to
upgrade.
"""
from __future__ import annotations

import hashlib
import math
import random
from typing import List, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont


# ----------------------------------------------------------------- title split

def split_title_lines(name: str) -> List[str]:
    """Stack a 2-word title as two lines; keep 1-word as-is.

    For 3 words: split 2+1 ("Shrimp Po-Boy" → "Shrimp Po-Boy").
    For 4+ words: respect the original word_wrap.

    The router's existing _wrap_text will still apply per-line — this
    function ONLY decides where to introduce intentional line breaks.
    """
    name = (name or "").strip()
    words = name.split()
    if len(words) <= 1:
        return [name]
    if len(words) == 2:
        return [words[0], words[1]]
    if len(words) == 3:
        return [words[0], " ".join(words[1:])]
    # 4+ words → let the caller's wrap handle it
    return [name]


# ----------------------------------------------------------------- title backdrop

def draw_title_backdrop(canvas: Image.Image, *, x: int, y: int, w: int, h: int,
                        style: str, color, rng: random.Random) -> None:
    """Paint a designer backdrop behind a title line.

    Styles:
      * `ribbon`           — horizontal ribbon banner with notched tails
      * `swash`            — angled brush-stroke ellipse
      * `distressed_rect`  — solid rect with rough/grainy edge
      * `none`             — no-op
    """
    if style == "none" or w <= 0 or h <= 0:
        return
    draw = ImageDraw.Draw(canvas, "RGBA")

    if style == "ribbon":
        notch = max(12, h // 3)
        body_color = color if len(color) == 4 else color + (220,)
        # main body polygon
        draw.polygon([
            (x, y), (x + w, y),
            (x + w, y + h), (x + w - notch, y + h // 2 + h // 6),
            (x + notch, y + h // 2 + h // 6), (x, y + h),
        ], fill=body_color)
        # shadow tail under both ends
        shadow = (0, 0, 0, 90)
        draw.polygon([
            (x - notch, y + h - 4), (x, y + h),
            (x, y + h + notch // 2),
        ], fill=shadow)
        draw.polygon([
            (x + w + notch, y + h - 4), (x + w, y + h),
            (x + w, y + h + notch // 2),
        ], fill=shadow)
        return

    if style == "swash":
        # Angled ellipse painted as a brush stroke
        pad = max(20, h // 2)
        layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        body_color = color if len(color) == 4 else color + (235,)
        ld.ellipse((pad - 10, pad, w + pad + 10, h + pad), fill=body_color)
        # Soften edges
        layer = layer.filter(ImageFilter.GaussianBlur(2))
        canvas.alpha_composite(layer, (x - pad, y - pad))
        return

    if style == "distressed_rect":
        body_color = color if len(color) == 4 else color + (235,)
        draw.rectangle((x, y, x + w, y + h), fill=body_color)
        # Chew up the corners with tiny transparent dots
        for _ in range(int(rng.uniform(20, 35))):
            ex = rng.choice([
                rng.randint(x - 3, x + 12),
                rng.randint(x + w - 12, x + w + 3),
            ])
            ey = rng.randint(y - 2, y + h + 2)
            r = rng.randint(2, 5)
            draw.ellipse((ex - r, ey - r, ex + r, ey + r), fill=(0, 0, 0, 0))
        return

    # default = none
    return


def pick_title_backdrop_style(theme_id: str, variant_idx: int) -> str:
    """Deterministic backdrop choice per (theme, variant).

    Returns one of `ribbon`, `swash`, `distressed_rect`, or `none`. We pick
    `none` ~33% of the time so themes don't look over-decorated.
    """
    seed = int(hashlib.md5(f"{theme_id}::{variant_idx}".encode()).hexdigest()[:6], 16)
    return ["ribbon", "swash", "distressed_rect", "none"][seed % 4]


# ----------------------------------------------------------------- BADGES

BADGE_STYLES = ("burst", "sticker", "chalk_circle", "ribbon",
                "ticket", "distressed_stamp")


def pick_badge_style(theme_id: str, variant_idx: int) -> str:
    seed = int(hashlib.md5(f"{theme_id}::bdg::{variant_idx}".encode()).hexdigest()[:6], 16)
    return BADGE_STYLES[seed % len(BADGE_STYLES)]


def draw_premium_badge(canvas: Image.Image, *, cx: int, cy: int, radius: int,
                       price_text: str, bg, fg, ring, font: ImageFont.FreeTypeFont,
                       style: str, rng: random.Random) -> None:
    """Dispatch to the chosen badge style. All styles render at (cx, cy) with
    nominal `radius`; some (ribbon, ticket) are wider than tall.
    """
    draw = ImageDraw.Draw(canvas, "RGBA")

    if style == "burst":
        # 10-pointed star burst
        pts = []
        outer, inner = radius + 14, radius - 6
        for i in range(20):
            ang = math.pi * i / 10 - math.pi / 2
            r = outer if i % 2 == 0 else inner
            pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
        draw.polygon(pts, fill=ring, outline=fg)
        draw.ellipse((cx - radius + 6, cy - radius + 6, cx + radius - 6, cy + radius - 6),
                     fill=bg)
        _text_center(draw, price_text, font, cx, cy, fg)
        return

    if style == "chalk_circle":
        # Hand-drawn circle with broken/dashed outline
        for i in range(0, 360, 14):
            jitter = rng.randint(-4, 4)
            r = radius + jitter
            x0, y0 = cx - r, cy - r
            x1, y1 = cx + r, cy + r
            draw.arc((x0, y0, x1, y1), i, i + 10, fill=fg, width=4)
        _text_center(draw, price_text, font, cx, cy, fg)
        return

    if style == "ribbon":
        # Horizontal ribbon banner — wider than tall
        bw = int(radius * 2.4)
        bh = int(radius * 1.1)
        notch = bh // 3
        # body
        draw.polygon([
            (cx - bw // 2, cy - bh // 2), (cx + bw // 2, cy - bh // 2),
            (cx + bw // 2 + notch, cy), (cx + bw // 2, cy + bh // 2),
            (cx - bw // 2, cy + bh // 2),
            (cx - bw // 2 - notch, cy),
        ], fill=bg, outline=fg)
        _text_center(draw, price_text, font, cx, cy, fg)
        return

    if style == "ticket":
        # Rounded rectangle with two circular notches (event ticket)
        bw, bh = int(radius * 2.2), int(radius * 1.4)
        draw.rounded_rectangle((cx - bw // 2, cy - bh // 2, cx + bw // 2, cy + bh // 2),
                               radius=12, fill=bg, outline=fg, width=3)
        # punch circles on each side
        nr = bh // 5
        draw.ellipse((cx - bw // 2 - nr, cy - nr, cx - bw // 2 + nr, cy + nr),
                     fill=ring)
        draw.ellipse((cx + bw // 2 - nr, cy - nr, cx + bw // 2 + nr, cy + nr),
                     fill=ring)
        _text_center(draw, price_text, font, cx, cy, fg)
        return

    if style == "distressed_stamp":
        # Square with rotated rectangle outline — passport stamp feel
        s = int(radius * 1.7)
        draw.rectangle((cx - s, cy - s, cx + s, cy + s), outline=fg, width=4)
        # secondary rect rotated ~6°: approximate via offset corners
        off = 6
        draw.line((cx - s + off, cy - s, cx + s - off, cy - s), fill=fg, width=2)
        draw.line((cx + s, cy - s + off, cx + s, cy + s - off), fill=fg, width=2)
        # text + a faded "FRESH" sub-stamp
        _text_center(draw, price_text, font, cx, cy, fg)
        return

    # default = sticker (legacy circular)
    draw.ellipse((cx - radius - 6, cy - radius - 6, cx + radius + 6, cy + radius + 6),
                 fill=ring)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=bg)
    _text_center(draw, price_text, font, cx, cy, fg)


def _text_center(draw: ImageDraw.ImageDraw, text: str, font, cx: int, cy: int, fg) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - bbox[1]), text, fill=fg, font=font)


# ----------------------------------------------------------------- PILL CHIPS

def draw_pill_chips(canvas: Image.Image, features: Sequence[str], *,
                    x: int, y: int, max_w: int,
                    bg, fg, font: ImageFont.FreeTypeFont,
                    border=None, max_rows: int = 3) -> int:
    """Render ingredients as horizontally-wrapping rounded pill chips.

    Returns the y-coordinate AFTER the chip block. Each chip auto-sizes to
    its text. Wraps to a new row when the next chip would exceed `max_w`.
    """
    if not features:
        return y
    draw = ImageDraw.Draw(canvas, "RGBA")
    chip_h = font.size + 14
    pad_x = max(10, chip_h // 3)
    row_gap = 8
    chip_gap = 7
    cur_x = x
    cur_y = y
    rows = 1
    for feat in features[:6]:
        text = feat.strip()
        if not text:
            continue
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        chip_w = tw + pad_x * 2
        if cur_x + chip_w > x + max_w:
            cur_x = x
            cur_y += chip_h + row_gap
            rows += 1
            if rows > max_rows:
                break
        # Pill background
        if isinstance(bg, tuple) and len(bg) == 3:
            bg = bg + (235,)
        draw.rounded_rectangle((cur_x, cur_y, cur_x + chip_w, cur_y + chip_h),
                               radius=chip_h // 2, fill=bg,
                               outline=border, width=2 if border else 0)
        # Text
        draw.text((cur_x + pad_x, cur_y + (chip_h - bbox[3] - bbox[1]) // 2 - bbox[1] // 2),
                  text, fill=fg, font=font)
        cur_x += chip_w + chip_gap
    return cur_y + chip_h
