"""Today's Pick graphics — extracted from `routers/todays_pick.py` in
Item 4 (Feb 2026) of the V1.0 Follow-up sprint.

Pure PIL composition: no database, no HTTP, no environment reads except
the branding string. Exactly the same bytes as the pre-split code —
verified by `tests/test_todays_pick_graphics_snapshot.py` (22 tests
including SHA-256 byte-hash snapshots for every layout × input pair).
"""
from __future__ import annotations

import io
import os
import random
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------- Constants

CANVAS = 1024
VARIATION_LABELS = ["A", "B", "C"]
RESTAURANT_BRANDING = os.environ.get("AI_DESIGNER_BRAND", "LAKEVIEW BURGERS & SEAFOOD")

FONT_SERIF_BOLD = "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"
FONT_SERIF      = "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"
FONT_SANS_BOLD  = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
FONT_SANS       = "/usr/share/fonts/truetype/freefont/FreeSans.ttf"

# Modern theme (clean, professional)
THEME: Dict[str, Any] = {
    "label": "Modern Restaurant",
    "bg_color": (248, 245, 240),
    "title": {"font": FONT_SERIF_BOLD, "color": (24, 28, 48), "size": 72},
    "body":  {"font": FONT_SANS, "color": (60, 65, 80), "size": 28, "marker": "—", "marker_color": (24, 28, 48)},
    "price": {"bg": (24, 28, 48), "fg": (255, 245, 215), "ring": (215, 195, 130), "font": FONT_SERIF_BOLD},
    "branding_color": (130, 130, 140),
}

LAYOUTS: List[str] = ["centered", "asym_left", "stacked"]


# ---------------------------------------------------------------- PIL helpers

def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    """Word-wrap text to fit max width."""
    words = text.split()
    lines, current = [], []
    for w in words:
        test = " ".join(current + [w])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_w:
            current.append(w)
        else:
            if current:
                lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))
    return lines if lines else [text]


def _generate_simple_background(theme: Dict[str, Any]) -> bytes:
    """Generate a simple gradient background."""
    img = Image.new("RGB", (CANVAS, CANVAS), theme["bg_color"])
    draw = ImageDraw.Draw(img)

    # Add subtle texture
    base_color = theme["bg_color"]
    for _ in range(80):
        x, y = random.randint(0, CANVAS), random.randint(0, CANVAS)
        s = random.randint(8, 20)
        # Slightly darker/lighter variations
        variation = random.randint(-15, 15)
        color = tuple(max(0, min(255, c + variation)) for c in base_color)
        draw.ellipse((x - s, y - s, x + s, y + s), fill=color)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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


def _draw_price_badge(canvas: Image.Image, theme: Dict[str, Any], price_text: str, cx: int, cy: int, radius: int) -> None:
    """Draw a circular price badge centered at (cx, cy)."""
    draw = ImageDraw.Draw(canvas, "RGBA")
    p = theme["price"]
    # Outer ring
    draw.ellipse((cx - radius - 6, cy - radius - 6, cx + radius + 6, cy + radius + 6), fill=p["ring"])
    # Inner badge
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=p["bg"])
    # Price text
    font_size = max(28, radius // 2)
    f = _font(p["font"], font_size)
    bbox = draw.textbbox((0, 0), price_text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - bbox[1]), price_text, fill=p["fg"], font=f)


def _draw_branding(canvas: Image.Image, theme: Dict[str, Any]) -> None:
    """Footer-style restaurant branding line at the bottom of the canvas."""
    draw = ImageDraw.Draw(canvas, "RGBA")
    f = _font(FONT_SANS_BOLD, 20)
    text = RESTAURANT_BRANDING
    bbox = draw.textbbox((0, 0), text, font=f)
    tw = bbox[2] - bbox[0]
    draw.text(((CANVAS - tw) // 2, CANVAS - 40 - (bbox[3] - bbox[1])), text, fill=theme["branding_color"], font=f)


def _compose_simple_design(item_name: str, price: Optional[str], layout: str, theme: Dict[str, Any]) -> bytes:
    """Compose a simple marketing graphic without food photo (text-only design)."""
    # Background
    bg_bytes = _generate_simple_background(theme)
    bg = Image.open(io.BytesIO(bg_bytes)).convert("RGB")
    canvas = bg.convert("RGBA")

    # Subtle vignette overlay
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, CANVAS, 140), fill=(0, 0, 0, 60))
    od.rectangle((0, CANVAS - 140, CANVAS, CANVAS), fill=(0, 0, 0, 50))
    canvas = Image.alpha_composite(canvas, overlay)

    safe_pad = 60

    if layout == "centered":
        # Title centered, price badge bottom-right
        _draw_title(canvas, theme, item_name, safe_pad, CANVAS // 2 - 100, CANVAS - 2 * safe_pad, "center")
        if price:
            _draw_price_badge(canvas, theme, f"${price}", CANVAS - 120, CANVAS - 120, 65)
    elif layout == "asym_left":
        # Title left-aligned, price badge top-right
        _draw_title(canvas, theme, item_name, safe_pad, safe_pad + 80, CANVAS - 2 * safe_pad, "left")
        if price:
            _draw_price_badge(canvas, theme, f"${price}", CANVAS - 120, 120, 65)
    else:  # stacked
        # Title top-center, price badge bottom-center
        _draw_title(canvas, theme, item_name, safe_pad, safe_pad, CANVAS - 2 * safe_pad, "center")
        if price:
            _draw_price_badge(canvas, theme, f"${price}", CANVAS // 2, CANVAS - 120, 75)

    _draw_branding(canvas, theme)

    # Convert to RGB and save
    final = canvas.convert("RGB")
    buf = io.BytesIO()
    final.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()


__all__ = [
    "CANVAS",
    "VARIATION_LABELS",
    "RESTAURANT_BRANDING",
    "FONT_SERIF_BOLD",
    "FONT_SERIF",
    "FONT_SANS_BOLD",
    "FONT_SANS",
    "THEME",
    "LAYOUTS",
    "_font",
    "_wrap_text",
    "_generate_simple_background",
    "_draw_title",
    "_draw_price_badge",
    "_draw_branding",
    "_compose_simple_design",
]
