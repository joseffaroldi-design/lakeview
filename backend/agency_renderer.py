"""Sprint 20 Phase 0 + Phase 0.5 — Agency template slot renderer.

Reads a Template manifest + background PNG and composites a finished flyer
by painting:
    1) background asset
    2) food photo into the `photo` slot (with feathering + drop shadow)
    3) title into the `title` slot (auto-fit, multi-line word wrap,
       proportional line-height, no truncation)
    4) features into the `features` slot (stacked_chips OR inline_pills,
       24px floor)
    5) premium filled price badge with soft shadow (no thin outer ring)
    6) optional `logo` wordmark (top-center / top-left / footer band)
    7) brand caption into the `brand` slot
    8) optional CTA into the `cta` slot
    9) any optional overlay assets

Phase 0.5 additions:
    * `_draw_logo` — configurable position, scale, opacity, monochrome,
      footer-band mode. Falls back to a PIL text-mark wordmark when no
      logo PNG is supplied.
    * `_MIN_FONT_PX` — minimum font floor (24px) enforced at draw time
      so designers can't accidentally ship illegible secondary text.
    * `_draw_badge` — soft drop shadow, premium filled disc only,
      optional inner accent ring only.

Public surface:
    compose_with_template(template, *, food_rgba, item_name, features,
                          price, brand, cta) -> PIL.Image
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Sequence

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from agency_templates import Template

log = logging.getLogger("uvicorn.error")

# Font resolution mirrors typography_engine — we resolve symbolic names to
# concrete filesystem paths at render time.
_FONT_DIR = "/usr/share/fonts/truetype/liberation"
_APP_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_FONT_LOOKUP = {
    "FONT_SERIF_BOLD": os.path.join(_FONT_DIR, "LiberationSerif-Bold.ttf"),
    "FONT_SERIF":      os.path.join(_FONT_DIR, "LiberationSerif-Regular.ttf"),
    "FONT_SANS_BOLD":  os.path.join(_FONT_DIR, "LiberationSans-Bold.ttf"),
    "FONT_SANS":       os.path.join(_FONT_DIR, "LiberationSans-Regular.ttf"),
    "FONT_BEBAS_NEUE": os.path.join(_APP_FONT_DIR, "BebasNeue-Regular.ttf"),
    "FONT_BUNGEE":     os.path.join(_APP_FONT_DIR, "Bungee-Regular.ttf"),
}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = _FONT_LOOKUP.get(name) or _FONT_LOOKUP["FONT_SERIF_BOLD"]
    if not os.path.exists(path):
        # Fallback to first available DejaVu
        for cand in _FONT_LOOKUP.values():
            if os.path.exists(cand):
                path = cand
                break
    return ImageFont.truetype(path, size)


# --- Phase 0.5: minimum legible font size floor (24 px). Slots whose
#     declared size dips below this are silently bumped up at draw time
#     to guarantee thumbnail readability without breaking older manifests.
_MIN_FONT_PX = 24


def _floor_size(declared: int, *, secondary: bool = False) -> int:
    """Enforce the 24px minimum for body/secondary text. Title sizes are
    auto-fit downward by `_fit_title` and aren't subject to this floor
    (we let large titles shrink to 28px before truncation kicks in)."""
    if not secondary:
        return max(int(declared), 28)
    return max(int(declared), _MIN_FONT_PX)


def _to_tuple(c: Any, default: tuple = (255, 255, 255)) -> tuple:
    if isinstance(c, list) and len(c) in (3, 4):
        return tuple(c)
    return default


def _fit_cover(food: Image.Image, w: int, h: int) -> Image.Image:
    """Scale the food image to COVER the slot (overflow cropped centered)."""
    fw, fh = food.size
    scale = max(w / fw, h / fh)
    nw, nh = int(fw * scale), int(fh * scale)
    out = food.resize((nw, nh), Image.LANCZOS)
    x = (nw - w) // 2
    y = (nh - h) // 2
    return out.crop((x, y, x + w, y + h))


def _feather_mask(w: int, h: int, feather: int) -> Image.Image:
    """Round-rect alpha mask, blurred so the photo edges fade into bg."""
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    margin = max(0, feather // 2)
    d.rounded_rectangle((margin, margin, w - margin, h - margin),
                        radius=feather, fill=255)
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=max(8, feather // 2)))
    return mask


def _paste_photo(canvas: Image.Image, food: Image.Image, slot: Dict[str, Any]) -> None:
    x, y, w, h = slot["x"], slot["y"], slot["w"], slot["h"]
    feather = int(slot.get("feather", 32))
    food_rgb = food.convert("RGB") if food.mode != "RGB" else food
    fitted = _fit_cover(food_rgb, w, h)
    mask = _feather_mask(w, h, feather)
    # Drop shadow first (under the photo).
    if slot.get("shadow"):
        sx, sy = slot.get("shadow_offset", [0, 18])
        sblur = int(slot.get("shadow_blur", 28))
        shadow = Image.new("RGBA", (w + sblur * 2, h + sblur * 2), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle(
            (sblur, sblur, sblur + w, sblur + h),
            radius=feather, fill=(0, 0, 0, 180),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=sblur))
        canvas.paste(shadow, (x - sblur + sx, y - sblur + sy), shadow)
    canvas.paste(fitted, (x, y), mask)


def _wrap_words(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    """Greedy word wrap, never returns empty."""
    words = (text or "").split()
    if not words:
        return [""]
    lines: List[str] = []
    cur = words[0]
    for w in words[1:]:
        probe = cur + " " + w
        bb = draw.textbbox((0, 0), probe, font=font)
        if (bb[2] - bb[0]) <= max_w:
            cur = probe
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _fit_title(draw: ImageDraw.ImageDraw, text: str, font_name: str,
               max_w: int, max_h: int, base_size: int, max_lines: int,
               letter_spacing: int = 0) -> tuple:
    """Find the largest font size where `text` fits in `(max_w, max_h)` with
    at most `max_lines` wrapped lines. Phase 0.5: proportional line gap,
    smarter long-title balancing, and never returns a truncated title.

    Returns (font, lines, line_h).
    """
    size = base_size
    # Soft floor for titles — never go below 32px even when the text is
    # very long. We expand `max_lines` first, then `max_h`, before letting
    # the title shrink below this floor.
    soft_floor = 32
    while size >= soft_floor:
        f = _font(font_name, size)
        lines = _wrap_words(draw, text, f, max_w - letter_spacing * max(0, len(text) - 1))
        # Proportional line gap = ~22% of the font size (tight modern feel).
        gap = max(6, int(size * 0.22))
        h_total = 0
        for ln in lines:
            bb = draw.textbbox((0, 0), ln, font=f)
            h_total += (bb[3] - bb[1]) + gap
        if len(lines) <= max_lines and h_total <= max_h:
            line_h = size + gap
            return f, lines, line_h
        size -= 4
    # We hit the soft floor. Allow more lines instead of truncating — bump
    # max_lines until the text fits vertically OR we'd need >5 lines.
    f = _font(font_name, soft_floor)
    gap = max(6, int(soft_floor * 0.22))
    expanded_max = max_lines
    while expanded_max < 5:
        expanded_max += 1
        lines = _wrap_words(draw, text, f, max_w - letter_spacing * max(0, len(text) - 1))
        if len(lines) <= expanded_max:
            line_h = soft_floor + gap
            return f, lines, line_h
    # Last-resort: just return whatever wrap we have. Caller's slot may
    # bleed past the original `max_h` — that's a manifest-design issue and
    # never returning a truncated label is the bigger win.
    lines = _wrap_words(draw, text, f, max_w)
    line_h = soft_floor + gap
    return f, lines, line_h


def _draw_text_with_spacing(draw: ImageDraw.ImageDraw, xy: tuple, text: str,
                            font: ImageFont.FreeTypeFont, fill: tuple,
                            stroke_width: int = 0, stroke_fill=None,
                            letter_spacing: int = 0) -> None:
    if letter_spacing <= 0:
        draw.text(xy, text, font=font, fill=fill,
                  stroke_width=stroke_width, stroke_fill=stroke_fill)
        return
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill,
                  stroke_width=stroke_width, stroke_fill=stroke_fill)
        bb = draw.textbbox((0, 0), ch, font=font)
        x += (bb[2] - bb[0]) + letter_spacing


def _draw_title(canvas: Image.Image, slot: Dict[str, Any], text: str) -> int:
    """Returns the rendered title block height in pixels so the Quality
    Score engine can correctly evaluate typography_hierarchy."""
    draw = ImageDraw.Draw(canvas, "RGBA")
    label = text or ""
    if slot.get("uppercase"):
        label = label.upper()
    font, lines, line_h = _fit_title(
        draw, label,
        font_name=slot.get("font", "FONT_SERIF_BOLD"),
        max_w=slot["w"],
        max_h=slot["h"],
        base_size=int(slot.get("size", 96)),
        max_lines=int(slot.get("max_lines", 2)),
        letter_spacing=int(slot.get("letter_spacing", 0)),
    )
    color = _to_tuple(slot.get("color"), (255, 255, 255))
    stroke_w = int(slot.get("stroke_width", 0))
    stroke_fill = _to_tuple(slot.get("stroke_fill"), (0, 0, 0)) if stroke_w else None
    align = slot.get("align", "left")
    spacing = int(slot.get("letter_spacing", 0))
    x = slot["x"]
    y = slot["y"]
    for ln in lines:
        bb = draw.textbbox((0, 0), ln, font=font)
        line_w = (bb[2] - bb[0]) + spacing * max(0, len(ln) - 1)
        if align == "center":
            ln_x = x + (slot["w"] - line_w) // 2
        elif align == "right":
            ln_x = x + slot["w"] - line_w
        else:
            ln_x = x
        _draw_text_with_spacing(draw, (ln_x, y), ln, font, color,
                                stroke_width=stroke_w, stroke_fill=stroke_fill,
                                letter_spacing=spacing)
        y += line_h
    # Return rendered block height in pixels
    return line_h * max(1, len(lines))


def _draw_features(canvas: Image.Image, slot: Dict[str, Any], features: List[str]) -> None:
    if not features:
        return
    draw = ImageDraw.Draw(canvas, "RGBA")
    style = slot.get("style", "stacked_chips")
    font = _font(slot.get("font", "FONT_BEBAS_NEUE"),
                 _floor_size(slot.get("size", 26), secondary=True))
    bg = _to_tuple(slot.get("bg"), (200, 30, 40, 230))
    fg = _to_tuple(slot.get("fg"), (245, 235, 210))
    padding = int(slot.get("padding", 14))
    radius = int(slot.get("border_radius", 12))
    uppercase = bool(slot.get("uppercase"))
    letter_spacing = int(slot.get("letter_spacing", 0))
    max_items = int(slot.get("max_items", 4))
    items = [(f or "").strip() for f in features[:max_items] if (f or "").strip()]
    if uppercase:
        items = [f.upper() for f in items]

    if style == "stacked_chips":
        line_h = int(slot.get("line_h", 60))
        x0 = slot["x"]
        y = slot["y"]
        for txt in items:
            # Single-line truncate / fit chip width
            bb = draw.textbbox((0, 0), txt, font=font)
            tw = (bb[2] - bb[0]) + letter_spacing * max(0, len(txt) - 1)
            th = bb[3] - bb[1]
            chip_w = min(slot["w"], tw + padding * 2)
            chip_h = max(line_h - 8, th + padding)
            draw.rounded_rectangle(
                (x0, y, x0 + chip_w, y + chip_h),
                radius=radius, fill=bg,
            )
            ty = y + (chip_h - th) // 2 - 4
            _draw_text_with_spacing(draw, (x0 + padding, ty), txt, font, fg,
                                    letter_spacing=letter_spacing)
            y += line_h
    elif style == "inline_pills":
        x0 = slot["x"]; y0 = slot["y"]
        cur_x = x0; cur_y = y0
        line_h = int(slot.get("size", 24)) + padding * 2 + 8
        for txt in items:
            bb = draw.textbbox((0, 0), txt, font=font)
            tw = (bb[2] - bb[0]) + letter_spacing * max(0, len(txt) - 1)
            th = bb[3] - bb[1]
            chip_w = tw + padding * 2
            chip_h = th + padding
            if cur_x + chip_w > x0 + slot["w"]:
                cur_x = x0
                cur_y += line_h
                if cur_y + chip_h > y0 + slot["h"]:
                    return  # bail — would overflow safe zone
            draw.rounded_rectangle(
                (cur_x, cur_y, cur_x + chip_w, cur_y + chip_h),
                radius=radius, fill=bg,
            )
            ty = cur_y + (chip_h - th) // 2 - 4
            _draw_text_with_spacing(draw, (cur_x + padding, ty), txt, font, fg,
                                    letter_spacing=letter_spacing)
            cur_x += chip_w + 12


def _draw_badge(canvas: Image.Image, slot: Dict[str, Any], price: str) -> None:
    """Phase 0.5: premium filled badge with a soft drop shadow. The thin
    outer ring is dropped (felt 'dated'). An inner accent ring is kept
    only when the manifest explicitly opts in (`inner_ring: true`)."""
    cx = int(slot["cx"])
    cy = int(slot["cy"])
    r = int(slot["radius"])
    bg = _to_tuple(slot.get("bg"), (200, 30, 40))
    ring = _to_tuple(slot.get("ring"), (245, 235, 210))
    fg = _to_tuple(slot.get("fg"), (245, 235, 210))
    style = slot.get("style", "filled_premium")
    want_shadow = slot.get("shadow", True)
    want_inner_ring = bool(slot.get("inner_ring", False) or style.endswith("inner_ring"))

    # Soft drop shadow under the disc — paste onto canvas in its own layer
    # so the blur doesn't bleed onto pre-painted artwork.
    if want_shadow:
        sblur = int(slot.get("shadow_blur", 18))
        soff_x, soff_y = slot.get("shadow_offset", [0, 10])
        sw = sh = (r + sblur) * 2 + 8
        shadow = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        scx = sw // 2; scy = sh // 2
        sd.ellipse((scx - r, scy - r, scx + r, scy + r), fill=(0, 0, 0, 140))
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=sblur))
        canvas.paste(shadow, (cx - sw // 2 + soff_x, cy - sh // 2 + soff_y), shadow)

    draw = ImageDraw.Draw(canvas, "RGBA")
    # Filled disc — the premium hero shape
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=bg)
    # Optional inner accent ring (off by default — felt floaty in audit)
    if want_inner_ring:
        draw.ellipse((cx - r + 10, cy - r + 10, cx + r - 10, cy + r - 10),
                     outline=ring, width=2)

    # Price text — auto fit so $XX.XX always sits inside the disc.
    text = price or ""
    size = int(slot.get("size", 56))
    f = _font(slot.get("font", "FONT_SERIF_BOLD"), size)
    bb = draw.textbbox((0, 0), text, font=f)
    while (bb[2] - bb[0]) > r * 1.5 and size > _MIN_FONT_PX:
        size -= 4
        f = _font(slot.get("font", "FONT_SERIF_BOLD"), size)
        bb = draw.textbbox((0, 0), text, font=f)
    tx = cx - (bb[2] - bb[0]) // 2
    ty = cy - (bb[3] - bb[1]) // 2 - 4
    draw.text((tx, ty), text, font=f, fill=fg)


def _draw_brand(canvas: Image.Image, slot: Dict[str, Any], brand: str) -> None:
    if not brand:
        return
    draw = ImageDraw.Draw(canvas, "RGBA")
    text = brand.upper() if slot.get("uppercase") else brand
    f = _font(slot.get("font", "FONT_BEBAS_NEUE"),
              _floor_size(slot.get("size", 24), secondary=True))
    color = _to_tuple(slot.get("color"), (245, 235, 210, 200))
    spacing = int(slot.get("letter_spacing", 4))
    bb = draw.textbbox((0, 0), text, font=f)
    tw = (bb[2] - bb[0]) + spacing * max(0, len(text) - 1)
    if slot.get("anchor") == "center":
        x = int(slot["cx"]) - tw // 2
    else:
        x = int(slot.get("x", 60))
    y = int(slot["y"])
    _draw_text_with_spacing(draw, (x, y), text, f, color, letter_spacing=spacing)


def _draw_cta(canvas: Image.Image, slot: Dict[str, Any], cta: str) -> None:
    if not cta:
        return
    draw = ImageDraw.Draw(canvas, "RGBA")
    text = cta.upper() if slot.get("uppercase") else cta
    f = _font(slot.get("font", "FONT_BEBAS_NEUE"),
              _floor_size(slot.get("size", 24), secondary=True))
    color = _to_tuple(slot.get("color"), (245, 235, 210, 220))
    spacing = int(slot.get("letter_spacing", 4))
    _draw_text_with_spacing(draw, (int(slot["x"]), int(slot["y"])),
                            text, f, color, letter_spacing=spacing)


# --------------------------------------------------------------- logo slot

def _resolve_logo_anchor(anchor: str, canvas_w: int, canvas_h: int,
                        block_w: int, block_h: int, margin: int) -> tuple:
    """Map a logo `anchor` string to an (x, y) origin inside the canvas."""
    if anchor == "top-center":
        return ((canvas_w - block_w) // 2, margin)
    if anchor == "top-left":
        return (margin, margin)
    if anchor == "top-right":
        return (canvas_w - block_w - margin, margin)
    if anchor == "footer-center":
        return ((canvas_w - block_w) // 2, canvas_h - block_h - margin)
    if anchor == "footer-left":
        return (margin, canvas_h - block_h - margin)
    if anchor == "footer-right":
        return (canvas_w - block_w - margin, canvas_h - block_h - margin)
    # Default: top-center.
    return ((canvas_w - block_w) // 2, margin)


def _apply_opacity(color: tuple, opacity: int) -> tuple:
    """Clamp opacity (0-255) onto a colour tuple."""
    if opacity >= 255:
        return color if len(color) == 4 else (*color, 255)
    r, g, b = color[:3]
    a = max(0, min(255, opacity))
    return (r, g, b, a)


def _mono(color: tuple, monochrome: bool, dark_bg: bool) -> tuple:
    """If `monochrome` is set, snap colour to white-or-black depending on
    inferred background. Otherwise return colour unchanged."""
    if not monochrome:
        return color
    if dark_bg:
        return (248, 245, 240, color[3] if len(color) == 4 else 255)
    return (16, 16, 16, color[3] if len(color) == 4 else 255)


def _sample_bg_luma(canvas: Image.Image, x: int, y: int, w: int, h: int) -> float:
    """Average luminance of the region the logo will paint over — used to
    drive automatic safe-zone contrast and monochrome polarity."""
    cw, ch = canvas.size
    x0 = max(0, min(cw - 1, x))
    y0 = max(0, min(ch - 1, y))
    x1 = max(0, min(cw, x + w))
    y1 = max(0, min(ch, y + h))
    if x1 <= x0 or y1 <= y0:
        return 128.0
    region = canvas.crop((x0, y0, x1, y1)).convert("RGB").resize((16, 16))
    import numpy as np
    arr = np.asarray(region, dtype=np.uint8)
    if arr.size == 0:
        return 128.0
    luma = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    return float(luma.mean())


def _draw_logo(canvas: Image.Image, slot: Dict[str, Any],
               brand: str = "LAKEVIEW") -> None:
    """Render the brand wordmark + optional tagline as the prominent
    identity element. Supports:
        - anchor: top-center | top-left | top-right | footer-* 
        - opacity, monochrome, footer_mode, scale
        - automatic safe-zone luma detection → monochrome polarity swap
        - automatic spacing from title/CTA via the `margin` field
    The mark renders as a clean PIL text-mark when no logo PNG is
    supplied — the same dimensions a designer's PNG would occupy when
    they later drop one in.
    """
    if not slot:
        return
    anchor = slot.get("anchor", "top-center")
    margin = int(slot.get("margin", 36))
    scale = float(slot.get("scale", 1.0))
    opacity = int(slot.get("opacity", 235))
    monochrome = bool(slot.get("monochrome", False))
    footer_mode = bool(slot.get("footer_mode", False))

    primary = slot.get("text") or brand.split()[0] if brand else "LAKEVIEW"
    primary = primary.upper() if slot.get("uppercase", True) else primary
    tagline = slot.get("tagline") or "BURGERS · SEAFOOD"
    tagline = tagline.upper() if slot.get("uppercase", True) else tagline

    primary_size = max(_MIN_FONT_PX, int(slot.get("size", 38) * scale))
    tagline_size = max(_MIN_FONT_PX, int(slot.get("tagline_size", 18) * scale))
    primary_font = _font(slot.get("font", "FONT_SERIF_BOLD"), primary_size)
    tagline_font = _font(slot.get("tagline_font", "FONT_BEBAS_NEUE"), tagline_size)
    primary_ls = int(slot.get("letter_spacing", 6))
    tagline_ls = int(slot.get("tagline_letter_spacing", 6))

    show_rule = bool(slot.get("show_rule", True))
    rule_w = int(slot.get("rule_width", 80))
    rule_thickness = max(1, int(slot.get("rule_thickness", 2)))

    # Measure block dimensions
    measure = ImageDraw.Draw(canvas, "RGBA")
    pb = measure.textbbox((0, 0), primary, font=primary_font)
    pw = (pb[2] - pb[0]) + primary_ls * max(0, len(primary) - 1)
    ph = pb[3] - pb[1]
    tb = measure.textbbox((0, 0), tagline, font=tagline_font)
    tw = (tb[2] - tb[0]) + tagline_ls * max(0, len(tagline) - 1) if tagline else 0
    th = (tb[3] - tb[1]) if tagline else 0
    rule_gap = 8 if show_rule and tagline else 0
    block_w = max(pw, tw, rule_w if show_rule else 0)
    block_h = ph + (rule_gap + rule_thickness + 4 + th if tagline else 0)

    canvas_w, canvas_h = canvas.size
    x, y = _resolve_logo_anchor(anchor, canvas_w, canvas_h, block_w, block_h, margin)

    # Footer mode: paint a full-width translucent footer band first so the
    # mark stays legible no matter how busy the background gets.
    if footer_mode:
        band_h = block_h + margin
        band = Image.new("RGBA", (canvas_w, band_h),
                         _to_tuple(slot.get("footer_band_color"), (12, 12, 16, 180)))
        canvas.paste(band, (0, canvas_h - band_h), band)
        # Recompute y in footer band coordinates
        x, y = _resolve_logo_anchor("footer-center" if "center" in anchor else anchor,
                                    canvas_w, canvas_h, block_w, block_h, margin // 2)

    # Auto monochrome polarity from bg luma
    luma = _sample_bg_luma(canvas, x, y, block_w, block_h)
    dark_bg = luma < 128

    base_color = _to_tuple(slot.get("color"), (245, 235, 210))
    color = _apply_opacity(_mono(base_color, monochrome, dark_bg), opacity)
    tagline_color = _apply_opacity(
        _mono(_to_tuple(slot.get("tagline_color"), color), monochrome, dark_bg),
        max(opacity - 30, 160),
    )

    draw = ImageDraw.Draw(canvas, "RGBA")
    # Primary mark — centered within the resolved block
    px_origin = x + (block_w - pw) // 2 if anchor.endswith("-center") else x
    _draw_text_with_spacing(draw, (px_origin, y), primary,
                            primary_font, color, letter_spacing=primary_ls)
    cy = y + ph + rule_gap
    if show_rule and tagline:
        rule_x = x + (block_w - rule_w) // 2
        draw.rectangle((rule_x, cy, rule_x + rule_w, cy + rule_thickness),
                       fill=color)
        cy += rule_thickness + 4
    if tagline:
        tx = x + (block_w - tw) // 2 if anchor.endswith("-center") else x
        _draw_text_with_spacing(draw, (tx, cy), tagline,
                                tagline_font, tagline_color,
                                letter_spacing=tagline_ls)


def compose_with_template(
    template: Template,
    *,
    food_rgba: Image.Image,
    item_name: str,
    features: Sequence[str],
    price: str,
    brand: str = "LAKEVIEW BURGERS & SEAFOOD",
    cta: str = "",
) -> Image.Image:
    """Composite a finished flyer using `template`.

    Caller is responsible for falling back to the procedural engine if this
    raises. We only raise on catastrophic asset/manifest errors — for any
    drawable issue we degrade gracefully so the flyer always ships.
    """
    canvas = Image.open(template.background_path).convert("RGB")
    if canvas.size != template.canvas:
        canvas = canvas.resize(template.canvas, Image.LANCZOS)

    slots = template.slots
    # Order matters: photo + shadow first, then text on top.
    if "photo" in slots:
        _paste_photo(canvas, food_rgba, slots["photo"])

    # Any "above_food" overlay assets
    for ov in template.overlay_paths:
        try:
            ol = Image.open(ov).convert("RGBA").resize(template.canvas, Image.LANCZOS)
            canvas.paste(ol, (0, 0), ol)
        except Exception as e:  # noqa: BLE001
            log.warning(f"[agency_renderer] overlay {ov} failed: {e}")

    last_title_h: int = 0
    if "title" in slots:
        last_title_h = _draw_title(canvas, slots["title"], item_name) or 0
    if "features" in slots and features:
        _draw_features(canvas, slots["features"], list(features))
    if "price" in slots:
        _draw_badge(canvas, slots["price"], price)
    if "logo" in slots:
        _draw_logo(canvas, slots["logo"], brand)
    if "brand" in slots:
        _draw_brand(canvas, slots["brand"], brand)
    if "cta" in slots and cta:
        _draw_cta(canvas, slots["cta"], cta)
    # Expose the rendered title block height as an Image attribute so the
    # caller (validation / scoring) can pass it to quality_score for an
    # accurate typography_hierarchy reading.
    try:
        canvas.title_pixel_height = last_title_h  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    return canvas
