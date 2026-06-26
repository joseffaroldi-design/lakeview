"""Sprint 20 Phase 0 — Agency template slot renderer.

Reads a Template manifest + background PNG and composites a finished flyer
by painting:
    1) background asset
    2) food photo into the `photo` slot (with feathering + drop shadow)
    3) title into the `title` slot (auto-fit, multi-line word wrap)
    4) features into the `features` slot (stacked_chips OR inline_pills)
    5) price badge into the `price` slot (filled disc + double ring)
    6) brand caption into the `brand` slot
    7) optional CTA into the `cta` slot
    8) any optional overlay assets

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
    at most `max_lines` wrapped lines. Returns (font, lines, line_h)."""
    size = base_size
    while size >= 22:
        f = _font(font_name, size)
        lines = _wrap_words(draw, text, f, max_w - letter_spacing * max(0, len(text) - 1))
        if len(lines) > max_lines:
            size -= 4
            continue
        # Measure tallest line
        h_total = 0
        for ln in lines:
            bb = draw.textbbox((0, 0), ln, font=f)
            h_total += (bb[3] - bb[1]) + 6  # 6 px line gap
        if h_total <= max_h:
            line_h = size + 8
            return f, lines, line_h
        size -= 4
    f = _font(font_name, 22)
    return f, [text[:32]], 30


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


def _draw_title(canvas: Image.Image, slot: Dict[str, Any], text: str) -> None:
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


def _draw_features(canvas: Image.Image, slot: Dict[str, Any], features: List[str]) -> None:
    if not features:
        return
    draw = ImageDraw.Draw(canvas, "RGBA")
    style = slot.get("style", "stacked_chips")
    font = _font(slot.get("font", "FONT_BEBAS_NEUE"), int(slot.get("size", 26)))
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
    draw = ImageDraw.Draw(canvas, "RGBA")
    cx = int(slot["cx"])
    cy = int(slot["cy"])
    r = int(slot["radius"])
    bg = _to_tuple(slot.get("bg"), (200, 30, 40))
    ring = _to_tuple(slot.get("ring"), (245, 235, 210))
    fg = _to_tuple(slot.get("fg"), (245, 235, 210))
    style = slot.get("style", "filled_disc_double_ring")
    # Outer ring
    if style.endswith("double_ring"):
        draw.ellipse((cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6),
                     outline=ring, width=4)
    # Filled disc
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=bg)
    # Inner ring accent
    draw.ellipse((cx - r + 10, cy - r + 10, cx + r - 10, cy + r - 10),
                 outline=ring, width=2)
    # Price text — auto fit so $XX.XX always sits inside the disc.
    text = price or ""
    size = int(slot.get("size", 56))
    f = _font(slot.get("font", "FONT_SERIF_BOLD"), size)
    bb = draw.textbbox((0, 0), text, font=f)
    while (bb[2] - bb[0]) > r * 1.5 and size > 22:
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
    f = _font(slot.get("font", "FONT_BEBAS_NEUE"), int(slot.get("size", 16)))
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
    f = _font(slot.get("font", "FONT_BEBAS_NEUE"), int(slot.get("size", 18)))
    color = _to_tuple(slot.get("color"), (245, 235, 210, 220))
    spacing = int(slot.get("letter_spacing", 4))
    _draw_text_with_spacing(draw, (int(slot["x"]), int(slot["y"])),
                            text, f, color, letter_spacing=spacing)


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

    if "title" in slots:
        _draw_title(canvas, slots["title"], item_name)
    if "features" in slots and features:
        _draw_features(canvas, slots["features"], list(features))
    if "price" in slots:
        _draw_badge(canvas, slots["price"], price)
    if "brand" in slots:
        _draw_brand(canvas, slots["brand"], brand)
    if "cta" in slots and cta:
        _draw_cta(canvas, slots["cta"], cta)
    return canvas
