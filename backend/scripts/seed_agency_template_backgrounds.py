"""PIL v2 placeholder backgrounds — light upgrade pass.

Replaces the v1 simple-gradient placeholders with more design-y procedural
art per the Sprint 20 Phase 0 interim brief. Realistic target: 7-7.5/10
on AI vision. The real path to 8-9/10 is still replacing these with
hand-designed Canva/Figma PNGs dropped into the same folder.

Techniques used:
  * Perlin-ish multi-octave noise for organic paper grain
  * Vertical+radial gradient blends for depth
  * Halftone dot patterns (kept SUBTLE so they don't read as confetti)
  * Foil-effect diagonal gradient stripes for luxury accents
  * Checker borders (classic diner)
  * Jersey/scoreboard stripes (game day)
  * Coastal wave bands (seafood)
  * Subtle inner vignette on EVERY template

Run from /app/backend:
    python scripts/seed_agency_template_backgrounds.py
"""
from __future__ import annotations

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFilter, ImageChops

BACKGROUNDS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "agency_templates", "backgrounds",
)
os.makedirs(BACKGROUNDS_DIR, exist_ok=True)

W = H = 1024


# ---------------------- low-level texture helpers ----------------------

def _vertical_gradient(im: Image.Image, c1, c2) -> None:
    px = im.load()
    h = im.size[1]
    for y in range(h):
        t = y / max(1, h - 1)
        col = (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        )
        for x in range(im.size[0]):
            px[x, y] = col


def _radial_gradient(im: Image.Image, c_center, c_edge, falloff=0.95) -> None:
    px = im.load()
    w, h = im.size
    cx, cy = w // 2, h // 2
    max_r = ((w // 2) ** 2 + (h // 2) ** 2) ** 0.5
    for y in range(h):
        for x in range(w):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            t = min(1.0, (d / max_r) / falloff)
            px[x, y] = (
                int(c_center[0] + (c_edge[0] - c_center[0]) * t),
                int(c_center[1] + (c_edge[1] - c_center[1]) * t),
                int(c_center[2] + (c_edge[2] - c_center[2]) * t),
            )


def _diagonal_gradient(im: Image.Image, c1, c2, angle_deg=45.0) -> None:
    """Smooth diagonal gradient — for foil/sheen effects."""
    px = im.load()
    w, h = im.size
    rad = math.radians(angle_deg)
    dx, dy = math.cos(rad), math.sin(rad)
    proj_max = dx * w + dy * h
    for y in range(h):
        for x in range(w):
            t = (dx * x + dy * y) / max(1.0, proj_max)
            t = max(0.0, min(1.0, t))
            px[x, y] = (
                int(c1[0] + (c2[0] - c1[0]) * t),
                int(c1[1] + (c2[1] - c1[1]) * t),
                int(c1[2] + (c2[2] - c1[2]) * t),
            )


def _grain(im: Image.Image, strength=5, seed=1) -> None:
    rng = random.Random(seed)
    px = im.load()
    w, h = im.size
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            n = rng.randint(-strength, strength)
            px[x, y] = (
                max(0, min(255, r + n)),
                max(0, min(255, g + n)),
                max(0, min(255, b + n)),
            )


def _paper_texture(seed=42) -> Image.Image:
    """Multi-octave noise → blurred paper grain. Output is an L-mode mask
    you composite over a gradient base for analog texture."""
    rng = random.Random(seed)
    base = Image.new("L", (W // 4, H // 4))
    px = base.load()
    for y in range(base.size[1]):
        for x in range(base.size[0]):
            px[x, y] = rng.randint(110, 160)
    base = base.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(2))
    # Second octave
    base2 = Image.new("L", (W // 16, H // 16))
    px2 = base2.load()
    for y in range(base2.size[1]):
        for x in range(base2.size[0]):
            px2[x, y] = rng.randint(80, 175)
    base2 = base2.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(5))
    return ImageChops.add(base, base2, scale=2.0).filter(ImageFilter.GaussianBlur(1))


def _inner_vignette(im: Image.Image, strength=0.55) -> None:
    """Soft darken at the corners — universal "designed" feel."""
    vig = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(vig)
    d.ellipse((-200, -200, W + 200, H + 200), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(180))
    overlay = Image.new("RGB", (W, H), (0, 0, 0))
    im.paste(overlay, (0, 0), ImageChops.invert(vig).point(lambda v: int(v * strength)))


def _halftone_dots(im: Image.Image, color, alpha=70, spacing=22, max_r=4, seed=7) -> None:
    """Subtle halftone — fades from bottom to top so it doesn't dominate."""
    rng = random.Random(seed)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for y in range(spacing // 2, H, spacing):
        # Fade out near the title (top) and brand (bottom).
        v = 1.0 - abs((y - H / 2) / (H / 2)) ** 2  # peaks at center
        fade = max(0.0, min(1.0, v * 0.85))
        for x in range(spacing // 2, W, spacing):
            if rng.random() > 0.55:
                continue
            r = rng.uniform(1, max_r)
            a = int(alpha * fade)
            if a < 8:
                continue
            d.ellipse((x - r, y - r, x + r, y + r), fill=color + (a,))
    im.alpha_composite(layer) if im.mode == "RGBA" else \
        im.paste(layer, (0, 0), layer)


def _checker_border(im: Image.Image, c1, c2, square=24, band=24) -> None:
    """Classic-diner red-white border bands top + bottom."""
    d = ImageDraw.Draw(im)
    for x in range(0, W, square):
        color = c1 if (x // square) % 2 == 0 else c2
        d.rectangle((x, 0, x + square, band), fill=color)
        d.rectangle((x, H - band, x + square, H), fill=color)


def _jersey_stripes(im: Image.Image, color, alpha=40, stride=24, band_top=210, band_bot=940) -> None:
    """Faint vertical stripes between safe zones — stadium-jersey feel."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x in range(0, W, stride):
        d.rectangle((x, band_top, x + 2, band_bot), fill=color + (alpha,))
    if im.mode != "RGBA":
        tmp = im.convert("RGBA")
        tmp.alpha_composite(layer)
        im.paste(tmp.convert("RGB"), (0, 0))
    else:
        im.alpha_composite(layer)


def _coastal_waves(im: Image.Image, color, alpha=55) -> None:
    """Soft horizon-glow + a few faint long wave arcs."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, y in enumerate([260, 330, 420, 540, 680, 820]):
        amp = 14 + i * 3
        for x in range(0, W, 6):
            yy = y + int(amp * math.sin((x + i * 80) / 70.0))
            d.line([(x, yy), (x + 6, yy)], fill=color + (alpha,), width=2)
    layer = layer.filter(ImageFilter.GaussianBlur(2))
    if im.mode != "RGBA":
        tmp = im.convert("RGBA")
        tmp.alpha_composite(layer)
        im.paste(tmp.convert("RGB"), (0, 0))
    else:
        im.alpha_composite(layer)


def _foil_sheen(im: Image.Image, c1, c2, c3) -> Image.Image:
    """Diagonal three-stop gradient — looks like brushed gold/foil. Returns
    a new RGB image (replaces im)."""
    a = Image.new("RGB", (W, H), c1)
    _diagonal_gradient(a, c1, c2, angle_deg=18)
    b = Image.new("RGB", (W, H), c2)
    _diagonal_gradient(b, c2, c3, angle_deg=-22)
    out = Image.blend(a, b, 0.5)
    return out


# ---------------------- 6 template recipes ----------------------

def _bg_burger_poster() -> Image.Image:
    """Bold diner/grill poster — charred-dark gradient + jersey stripes + grill rule."""
    im = Image.new("RGB", (W, H), (20, 16, 16))
    _radial_gradient(im, (54, 30, 22), (10, 8, 9), falloff=1.05)
    _grain(im, strength=4, seed=11)
    # Top stadium-gold rule + bottom rule (classic diner-poster sandwich).
    d = ImageDraw.Draw(im)
    d.rectangle((0, 200, W, 208), fill=(255, 200, 60))
    d.rectangle((0, 940, W, 948), fill=(255, 200, 60))
    # Subtle jersey stripes between the rules so the photo zone breathes.
    _jersey_stripes(im, color=(220, 200, 180), alpha=18, stride=44, band_top=216, band_bot=932)
    _inner_vignette(im, strength=0.65)
    return im


def _bg_seafood_special() -> Image.Image:
    """Coastal navy with soft horizon + delicate wave arcs."""
    im = Image.new("RGB", (W, H), (10, 28, 56))
    _vertical_gradient(im, (14, 36, 72), (6, 18, 40))
    # Right-side warm spotlight where the photo sits.
    spot = Image.new("RGB", (W, H), (10, 28, 56))
    s = ImageDraw.Draw(spot)
    s.ellipse((280, 100, 1120, 920), fill=(34, 70, 120))
    spot = spot.filter(ImageFilter.GaussianBlur(140))
    im = Image.blend(im, spot, 0.50)
    _coastal_waves(im, color=(220, 235, 245), alpha=42)
    _grain(im, strength=3, seed=12)
    # Cream hairline under the title column + bottom brand rule.
    d = ImageDraw.Draw(im)
    d.line([(60, 500), (340, 500)], fill=(245, 235, 210), width=1)
    d.line([(60, 948), (W - 60, 948)], fill=(245, 235, 210), width=1)
    _inner_vignette(im, strength=0.45)
    return im


def _bg_game_day_promo() -> Image.Image:
    """Stadium-floodlight black + gold scoreboard stripes."""
    im = Image.new("RGB", (W, H), (10, 10, 14))
    _radial_gradient(im, (32, 32, 38), (4, 4, 8), falloff=1.1)
    # Strong gold top + bottom rule.
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 12), fill=(255, 200, 60))
    d.rectangle((0, H - 12, W, H), fill=(255, 200, 60))
    # Scoreboard stripes between safe zones.
    _jersey_stripes(im, color=(255, 200, 60), alpha=22, stride=32, band_top=210, band_bot=940)
    # Subtle scoreboard halftone dots — fades to middle.
    rgba = im.convert("RGBA")
    _halftone_dots(rgba, color=(255, 200, 60), alpha=55, spacing=26, max_r=2, seed=13)
    im = rgba.convert("RGB")
    _grain(im, strength=4, seed=13)
    _inner_vignette(im, strength=0.55)
    return im


def _bg_classic_diner() -> Image.Image:
    """Retro red-and-white checker border + warm cream center + thin coffee rules."""
    im = Image.new("RGB", (W, H), (250, 240, 215))
    _vertical_gradient(im, (252, 244, 220), (236, 222, 188))
    paper = _paper_texture(seed=14).point(lambda v: int(120 + (v - 120) * 0.18))
    im = Image.composite(
        Image.new("RGB", (W, H), (255, 245, 220)),
        im,
        paper,
    )
    # Red checker border top + bottom.
    _checker_border(im, c1=(200, 30, 40), c2=(252, 244, 220), square=32, band=20)
    # Thin coffee-brown rules just inside the checker bands.
    d = ImageDraw.Draw(im)
    d.line([(60, 50), (W - 60, 50)], fill=(40, 25, 5), width=2)
    d.line([(60, H - 50), (W - 60, H - 50)], fill=(40, 25, 5), width=2)
    _grain(im, strength=3, seed=14)
    _inner_vignette(im, strength=0.18)
    return im


def _bg_luxury_dark() -> Image.Image:
    """Premium matte-black with subtle gold foil sheen + thin gold accents."""
    im = Image.new("RGB", (W, H), (8, 8, 10))
    _radial_gradient(im, (24, 22, 20), (3, 3, 5), falloff=1.05)
    # Thin diagonal gold-sheen band — gives the bg a "foil-stamped" feel.
    foil = _foil_sheen(
        Image.new("RGB", (W, H)),
        c1=(28, 24, 20), c2=(82, 68, 38), c3=(28, 24, 20),
    )
    im = Image.blend(im, foil, 0.18)
    _grain(im, strength=3, seed=15)
    d = ImageDraw.Draw(im)
    # Thin gold rules at the title baseline + brand bar.
    d.line([(60, 230), (W - 60, 230)], fill=(212, 175, 55), width=2)
    d.line([(60, 948), (W - 60, 948)], fill=(212, 175, 55), width=2)
    # Tiny vertical gold accent left edge.
    d.line([(40, 230), (40, 948)], fill=(212, 175, 55), width=3)
    # Subtle corner serifs — top-left + bottom-right.
    for (x, y, dx, dy) in [(60, 60, 1, 1), (W - 60, H - 60, -1, -1)]:
        d.line([(x, y), (x + 40 * dx, y)], fill=(212, 175, 55), width=2)
        d.line([(x, y), (x, y + 40 * dy)], fill=(212, 175, 55), width=2)
    _inner_vignette(im, strength=0.65)
    return im


def _bg_bold_social() -> Image.Image:
    """High-energy Instagram gradient — sunset coral → purple → magenta with a soft glow ring."""
    im = Image.new("RGB", (W, H), (40, 18, 64))
    # Three-stop diagonal sunset.
    a = Image.new("RGB", (W, H), (255, 130, 90))
    _diagonal_gradient(a, (255, 140, 100), (240, 70, 110), angle_deg=35)
    b = Image.new("RGB", (W, H), (60, 30, 95))
    _diagonal_gradient(b, (200, 60, 130), (40, 18, 64), angle_deg=35)
    im = Image.blend(a, b, 0.55)
    # Soft glow ring behind the photo zone — gives it a "set against a spotlight" feel.
    glow = Image.new("RGB", (W, H), (40, 18, 64))
    g = ImageDraw.Draw(glow)
    g.ellipse((40, 180, W - 40, 840), fill=(255, 220, 200))
    glow = glow.filter(ImageFilter.GaussianBlur(180))
    im = Image.blend(im, glow, 0.18)
    rgba = im.convert("RGBA")
    _halftone_dots(rgba, color=(255, 255, 255), alpha=60, spacing=28, max_r=3, seed=16)
    im = rgba.convert("RGB")
    _grain(im, strength=3, seed=16)
    # Thin cream rules at safe-zone edges.
    d = ImageDraw.Draw(im)
    d.line([(60, 200), (W - 60, 200)], fill=(248, 245, 240), width=2)
    d.line([(60, 948), (W - 60, 948)], fill=(248, 245, 240), width=2)
    _inner_vignette(im, strength=0.32)
    return im


_RECIPES = {
    "burger-poster-01.png": _bg_burger_poster,
    "seafood-special-01.png": _bg_seafood_special,
    "game-day-promo-01.png": _bg_game_day_promo,
    "classic-diner-01.png": _bg_classic_diner,
    "luxury-dark-01.png": _bg_luxury_dark,
    "bold-social-01.png": _bg_bold_social,
}


def main() -> int:
    print(f"PIL v2 — seeding {len(_RECIPES)} backgrounds → {BACKGROUNDS_DIR}")
    for name, fn in _RECIPES.items():
        out = os.path.join(BACKGROUNDS_DIR, name)
        im = fn()
        if im.mode != "RGB":
            im = im.convert("RGB")
        im.save(out, format="PNG", optimize=True)
        print(f"  {name} ({os.path.getsize(out) // 1024} KB)")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
