"""Seed PIL-generated placeholder backgrounds for the 6 agency templates.

These are PROFESSIONAL placeholder backgrounds — they intentionally look
like designer-curated layouts (clean gradients, subtle texture, no busy
decorations) so the template-slot system produces agency-grade output
even before real Canva/Figma assets are uploaded.

Run from /app/backend:
    python scripts/seed_agency_template_backgrounds.py
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFilter

BACKGROUNDS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "agency_templates", "backgrounds",
)
os.makedirs(BACKGROUNDS_DIR, exist_ok=True)


def _vertical_gradient(im: Image.Image, c1: tuple, c2: tuple) -> None:
    """Linear vertical gradient."""
    px = im.load()
    h = im.size[1]
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        for x in range(im.size[0]):
            px[x, y] = (r, g, b)


def _radial_gradient(im: Image.Image, c_center: tuple, c_edge: tuple, falloff: float = 0.95) -> None:
    """Smooth radial gradient from center."""
    px = im.load()
    w, h = im.size
    cx, cy = w // 2, h // 2
    max_r = ((w // 2) ** 2 + (h // 2) ** 2) ** 0.5
    for y in range(h):
        for x in range(w):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            t = min(1.0, (d / max_r) / falloff)
            r = int(c_center[0] + (c_edge[0] - c_center[0]) * t)
            g = int(c_center[1] + (c_edge[1] - c_center[1]) * t)
            b = int(c_center[2] + (c_edge[2] - c_center[2]) * t)
            px[x, y] = (r, g, b)


def _noise(im: Image.Image, strength: int = 6, seed: int = 1) -> None:
    """Subtle grain — adds *just* enough texture so the bg doesn't read as plastic."""
    rng = random.Random(seed)
    px = im.load()
    w, h = im.size
    step = 2
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b = px[x, y]
            n = rng.randint(-strength, strength)
            px[x, y] = (
                max(0, min(255, r + n)),
                max(0, min(255, g + n)),
                max(0, min(255, b + n)),
            )


def _thin_rule(draw: ImageDraw.ImageDraw, y: int, w: int, color: tuple, padding: int = 60) -> None:
    """Thin horizontal accent line (designers love these)."""
    draw.line([(padding, y), (w - padding, y)], fill=color, width=1)


# ---------- Per-template background painters ----------

def _bg_burger_poster() -> Image.Image:
    """Dark charcoal gradient, subtle vignette, paper grain."""
    im = Image.new("RGB", (1024, 1024), (16, 16, 18))
    _radial_gradient(im, (38, 26, 24), (10, 10, 12), falloff=1.05)
    _noise(im, strength=4, seed=1)
    d = ImageDraw.Draw(im)
    # Hairline accents at the title baseline + photo bottom
    _thin_rule(d, 210, 1024, (200, 30, 40, 255), padding=60)
    _thin_rule(d, 948, 1024, (245, 235, 210, 255), padding=60)
    return im


def _bg_seafood_special() -> Image.Image:
    """Coastal navy with a soft horizon glow on the right half (where photo lives)."""
    im = Image.new("RGB", (1024, 1024), (12, 30, 60))
    # Photo zone gets a slightly lighter wash so the food cut-out reads cleanly.
    _vertical_gradient(im, (16, 36, 72), (8, 22, 48))
    # Right-side spotlight (where the photo will sit).
    spot = Image.new("RGB", (1024, 1024), (12, 30, 60))
    spot_d = ImageDraw.Draw(spot)
    spot_d.ellipse((280, 100, 1100, 920), fill=(28, 56, 100))
    spot = spot.filter(ImageFilter.GaussianBlur(120))
    im = Image.blend(im, spot, 0.55)
    _noise(im, strength=3, seed=2)
    d = ImageDraw.Draw(im)
    # Thin gold rule under the title column
    _thin_rule(d, 500, 380, (245, 235, 210, 255), padding=60)
    _thin_rule(d, 948, 1024, (245, 235, 210, 255), padding=60)
    return im


def _bg_game_day_promo() -> Image.Image:
    """Stadium-floodlight black with a subtle gold sheen at the top, edge vignette."""
    im = Image.new("RGB", (1024, 1024), (12, 12, 16))
    _radial_gradient(im, (28, 28, 34), (6, 6, 10), falloff=1.1)
    # Top stripe of stadium gold
    d_top = ImageDraw.Draw(im)
    d_top.rectangle((0, 0, 1024, 12), fill=(255, 200, 60))
    d_top.rectangle((0, 1012, 1024, 1024), fill=(255, 200, 60))
    _noise(im, strength=4, seed=3)
    d = ImageDraw.Draw(im)
    _thin_rule(d, 210, 1024, (255, 200, 60, 255), padding=60)
    _thin_rule(d, 948, 1024, (255, 200, 60, 255), padding=60)
    return im


def _bg_classic_diner() -> Image.Image:
    """Warm cream gradient — vintage diner menu feel, no busy patterns."""
    im = Image.new("RGB", (1024, 1024), (244, 232, 200))
    _vertical_gradient(im, (250, 240, 215), (236, 222, 188))
    _noise(im, strength=4, seed=4)
    d = ImageDraw.Draw(im)
    # Two thin brown rules — classic diner menu styling
    _thin_rule(d, 210, 1024, (40, 25, 5, 255), padding=80)
    _thin_rule(d, 940, 1024, (40, 25, 5, 255), padding=80)
    # Footer border bar
    d.rectangle((0, 970, 1024, 1024), fill=(40, 25, 5))
    return im


def _bg_luxury_dark() -> Image.Image:
    """Black-and-gold luxury — deep matte black with the title baseline rule."""
    im = Image.new("RGB", (1024, 1024), (10, 10, 12))
    _radial_gradient(im, (22, 20, 18), (4, 4, 6), falloff=1.05)
    _noise(im, strength=3, seed=5)
    d = ImageDraw.Draw(im)
    # Gold accent rules
    _thin_rule(d, 230, 1024, (212, 175, 55, 255), padding=60)
    _thin_rule(d, 948, 1024, (212, 175, 55, 255), padding=60)
    # Tiny vertical accent on left
    d.line([(40, 230), (40, 948)], fill=(212, 175, 55), width=2)
    return im


def _bg_bold_social() -> Image.Image:
    """Saturated coral-purple gradient — Instagram-ready, NOT the chaotic confetti the old social theme used."""
    im = Image.new("RGB", (1024, 1024), (38, 18, 60))
    # Strong diagonal-ish gradient via blended radial
    _radial_gradient(im, (255, 130, 130), (38, 18, 60), falloff=1.4)
    # Apply a vertical blend for the "instagram sunset" feel
    g = Image.new("RGB", (1024, 1024), (38, 18, 60))
    _vertical_gradient(g, (255, 140, 100), (60, 30, 95))
    im = Image.blend(im, g, 0.55)
    _noise(im, strength=4, seed=6)
    d = ImageDraw.Draw(im)
    _thin_rule(d, 200, 1024, (248, 245, 240, 255), padding=60)
    _thin_rule(d, 948, 1024, (248, 245, 240, 255), padding=60)
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
    print(f"Seeding {len(_RECIPES)} agency template backgrounds → {BACKGROUNDS_DIR}")
    for name, fn in _RECIPES.items():
        out = os.path.join(BACKGROUNDS_DIR, name)
        im = fn()
        im.save(out, format="PNG", optimize=True)
        print(f"  {name} ({os.path.getsize(out) // 1024} KB)")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
