"""Sprint 16H — Shared foreground overlay primitives.

Each function paints into an RGBA `canvas` (size = CANVAS×CANVAS) and uses
`variant_idx` to seed `random.Random` so the same variant is always
reproducible but the three variants of a theme each look different.

All primitives draw IN FRONT of the food (the router calls
`overlay_fn` after the food is composited), so they read as
atmosphere/particles around the dish.

Naming convention: `<style>(canvas, draw, variant_idx, **opts)`.
"""
from __future__ import annotations

import math
import random
from typing import Tuple

from PIL import Image, ImageDraw, ImageFilter

from ._shared import CANVAS

# ----------------------------------------------------------------- helpers

def _rng(theme_id: str, variant_idx: int) -> random.Random:
    """Reproducible per-(theme, variant) RNG so each render is consistent."""
    return random.Random(hash((theme_id, variant_idx)) & 0xFFFFFFFF)


def _scatter(draw: ImageDraw.ImageDraw, rng: random.Random, color, count: int,
             *, region: Tuple[int, int, int, int], min_r: int = 2, max_r: int = 6,
             alpha_jitter: bool = True) -> None:
    """Scatter `count` dots within (x0,y0,x1,y1)."""
    x0, y0, x1, y1 = region
    base_a = color[3] if len(color) == 4 else 255
    for _ in range(count):
        x = rng.randint(x0, x1)
        y = rng.randint(y0, y1)
        r = rng.randint(min_r, max_r)
        a = base_a
        if alpha_jitter:
            a = int(base_a * rng.uniform(0.45, 1.0))
        c = (color[0], color[1], color[2], a)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=c)


# ----------------------------------------------------------------- BURGER PACK

def grill_smoke(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                variant_idx: int, *, theme_id: str = "burger") -> None:
    """Soft upward smoke wisps from the bottom-centre."""
    rng = _rng(theme_id, variant_idx)
    smoke = Image.new("L", canvas.size, 0)
    sd = ImageDraw.Draw(smoke)
    base_x = CANVAS // 2 + rng.randint(-100, 100)
    for _ in range(rng.randint(4, 7)):
        cx = base_x + rng.randint(-150, 150)
        cy = CANVAS - rng.randint(20, 220)
        rw = rng.randint(60, 140)
        rh = rng.randint(110, 220)
        sd.ellipse((cx - rw, cy - rh, cx + rw, cy + rh), fill=rng.randint(70, 130))
    smoke = smoke.filter(ImageFilter.GaussianBlur(36))
    # White smoke for dark themes, slightly warm grey otherwise
    tint = (245, 240, 230) if rng.random() < 0.5 else (210, 200, 190)
    layer = Image.new("RGBA", canvas.size, tint + (255,))
    layer.putalpha(smoke)
    canvas.alpha_composite(layer)


def grease_splatter(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                    variant_idx: int, *, theme_id: str = "burger",
                    color=(28, 14, 4, 220)) -> None:
    """Random small dark splatter dots around the edges."""
    rng = _rng(theme_id + "_splat", variant_idx)
    # Top + bottom strips, avoiding the centre where food sits
    _scatter(draw, rng, color, count=rng.randint(8, 14),
             region=(60, 60, CANVAS - 60, 200), min_r=2, max_r=7)
    _scatter(draw, rng, color, count=rng.randint(8, 14),
             region=(60, CANVAS - 200, CANVAS - 60, CANVAS - 60), min_r=2, max_r=7)


def seasoning_flakes(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                     variant_idx: int, *, theme_id: str = "burger",
                     color=(220, 60, 30, 240)) -> None:
    """Tiny red/orange flecks suspended around the food (like paprika)."""
    rng = _rng(theme_id + "_flake", variant_idx)
    _scatter(draw, rng, color, count=rng.randint(30, 50),
             region=(80, 100, CANVAS - 80, CANVAS - 100), min_r=1, max_r=3)


# ----------------------------------------------------------------- SEAFOOD PACK

def water_droplets(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                   variant_idx: int, *, theme_id: str = "seafood") -> None:
    """Translucent rounded blobs with a tiny highlight — water beads."""
    rng = _rng(theme_id, variant_idx)
    for _ in range(rng.randint(10, 18)):
        # Anywhere except the dead centre (where food sits)
        x = rng.randint(80, CANVAS - 80)
        y = rng.randint(80, CANVAS - 80)
        if int(CANVAS * 0.30) < x < int(CANVAS * 0.70) and int(CANVAS * 0.30) < y < int(CANVAS * 0.70):
            continue
        r = rng.randint(6, 14)
        # Bead body — pale blue/white with low alpha
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(210, 230, 240, 95),
                     outline=(230, 245, 255, 160), width=2)
        # Specular highlight
        hr = max(2, r // 3)
        draw.ellipse((x - r // 2, y - r // 2 - 1, x - r // 2 + hr, y - r // 2 - 1 + hr),
                     fill=(255, 255, 255, 200))


def bubbles(canvas: Image.Image, draw: ImageDraw.ImageDraw,
            variant_idx: int, *, theme_id: str = "seafood") -> None:
    """Rising hollow circles from one side — underwater feel."""
    rng = _rng(theme_id + "_bub", variant_idx)
    side_x = rng.choice([80, CANVAS - 80])
    for _ in range(rng.randint(8, 14)):
        x = side_x + rng.randint(-40, 40)
        y = rng.randint(120, CANVAS - 60)
        r = rng.randint(5, 12)
        draw.ellipse((x - r, y - r, x + r, y + r),
                     outline=(220, 240, 250, 200), width=2)


def sea_salt_dust(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                  variant_idx: int, *, theme_id: str = "seafood") -> None:
    rng = _rng(theme_id + "_salt", variant_idx)
    _scatter(draw, rng, (250, 250, 240, 220), count=rng.randint(40, 70),
             region=(80, 80, CANVAS - 80, CANVAS - 80), min_r=1, max_r=2)


# ----------------------------------------------------------------- GAME DAY PACK

def stadium_light_rays(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                       variant_idx: int, *, theme_id: str = "game_day") -> None:
    """Diagonal soft light rays from the top corner."""
    rng = _rng(theme_id, variant_idx)
    origin_x = rng.choice([120, CANVAS - 120])
    rays = Image.new("L", canvas.size, 0)
    rd = ImageDraw.Draw(rays)
    for _ in range(rng.randint(4, 7)):
        angle = math.radians(rng.uniform(50, 80) * (1 if origin_x < CANVAS // 2 else -1)
                             + (180 if origin_x > CANVAS // 2 else 0))
        length = rng.randint(700, 1100)
        width = rng.randint(40, 90)
        end_x = origin_x + int(math.cos(angle) * length)
        end_y = 60 + int(math.sin(angle) * length)
        rd.line((origin_x, 60, end_x, end_y), fill=rng.randint(40, 90), width=width)
    rays = rays.filter(ImageFilter.GaussianBlur(28))
    layer = Image.new("RGBA", canvas.size, (252, 220, 120, 255))
    layer.putalpha(rays)
    canvas.alpha_composite(layer)


def confetti_burst(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                   variant_idx: int, *, theme_id: str = "game_day",
                   palette=((252, 200, 60), (220, 40, 50), (40, 80, 200), (252, 240, 210))) -> None:
    """Small rotated rectangles scattered like confetti."""
    rng = _rng(theme_id + "_conf", variant_idx)
    for _ in range(rng.randint(28, 48)):
        x = rng.randint(40, CANVAS - 40)
        y = rng.randint(40, CANVAS - 40)
        # Skip the centre square
        if int(CANVAS * 0.28) < x < int(CANVAS * 0.72) and int(CANVAS * 0.30) < y < int(CANVAS * 0.70):
            continue
        w = rng.randint(6, 14)
        h = rng.randint(3, 7)
        c = rng.choice(palette) + (rng.randint(170, 240),)
        # Draw axis-aligned (cheap) — rotation would need PIL transforms
        draw.rectangle((x, y, x + w, y + h), fill=c)


def chalk_dust(canvas: Image.Image, draw: ImageDraw.ImageDraw,
               variant_idx: int, *, theme_id: str = "game_day") -> None:
    rng = _rng(theme_id + "_chalk", variant_idx)
    _scatter(draw, rng, (252, 240, 210, 180), count=rng.randint(60, 100),
             region=(60, 60, CANVAS - 60, CANVAS - 60), min_r=1, max_r=2)


# ----------------------------------------------------------------- SEASONAL PACK

def mardi_gras_glitter(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                       variant_idx: int, *, theme_id: str = "seasonal") -> None:
    """Tiny purple/green/gold sparkles foreground."""
    rng = _rng(theme_id + "_mg", variant_idx)
    palette = [(252, 220, 60), (60, 160, 80), (180, 60, 220)]
    for _ in range(rng.randint(50, 80)):
        x = rng.randint(40, CANVAS - 40)
        y = rng.randint(40, CANVAS - 40)
        if int(CANVAS * 0.28) < x < int(CANVAS * 0.72) and int(CANVAS * 0.30) < y < int(CANVAS * 0.70):
            continue
        c = rng.choice(palette) + (rng.randint(160, 230),)
        s = rng.randint(2, 5)
        # Diamond shape
        draw.polygon([(x, y - s), (x + s, y), (x, y + s), (x - s, y)], fill=c)


def snow_particles(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                   variant_idx: int, *, theme_id: str = "seasonal") -> None:
    rng = _rng(theme_id + "_snow", variant_idx)
    for _ in range(rng.randint(40, 70)):
        x = rng.randint(20, CANVAS - 20)
        y = rng.randint(20, CANVAS - 20)
        if int(CANVAS * 0.30) < x < int(CANVAS * 0.70) and int(CANVAS * 0.34) < y < int(CANVAS * 0.66):
            continue
        r = rng.randint(1, 4)
        a = rng.randint(150, 230)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(252, 250, 245, a))


def summer_sun_rays(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                    variant_idx: int, *, theme_id: str = "seasonal") -> None:
    rng = _rng(theme_id + "_sun", variant_idx)
    rays = Image.new("L", canvas.size, 0)
    rd = ImageDraw.Draw(rays)
    origin_x = CANVAS // 2 + rng.randint(-200, 200)
    for _ in range(rng.randint(5, 9)):
        angle = math.radians(rng.uniform(60, 120))
        length = rng.randint(600, 900)
        ex = origin_x + int(math.cos(angle) * length)
        ey = -40 + int(math.sin(angle) * length)
        rd.line((origin_x, -40, ex, ey), fill=rng.randint(40, 80), width=rng.randint(30, 60))
    rays = rays.filter(ImageFilter.GaussianBlur(34))
    layer = Image.new("RGBA", canvas.size, (252, 220, 100, 255))
    layer.putalpha(rays)
    canvas.alpha_composite(layer)


# ----------------------------------------------------------------- CLASSIC / FLYER (defaults)

def halftone_corner_dust(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                         variant_idx: int, *, theme_id: str = "classic") -> None:
    """Subtle halftone pattern in two opposite corners — Phase 1 default for
    Classic + Flyer packs so they also pick up *some* art direction."""
    rng = _rng(theme_id + "_ht", variant_idx)
    color = (240, 230, 215, 110)
    # Top-right corner
    for x in range(CANVAS - 280, CANVAS - 60, 16):
        for y in range(60, 240, 16):
            r = 3 + int(rng.random() * 2)
            a = int(110 * (1 - (x - (CANVAS - 280)) / 220) * (1 - (y - 60) / 180))
            if a > 4:
                draw.ellipse((x - r, y - r, x + r, y + r),
                             fill=(color[0], color[1], color[2], a))
    # Bottom-left corner — light specks
    _scatter(draw, rng, (255, 245, 220, 90), count=rng.randint(18, 30),
             region=(60, CANVAS - 240, 280, CANVAS - 60), min_r=2, max_r=4)


# ----------------------------------------------------------------- COMPOSED

def make_burger_overlay(theme_id: str):
    """Stack: grill_smoke + grease_splatter + seasoning_flakes."""
    def _fn(canvas, draw, variant_idx):
        # Variant choice: every variant gets smoke; splatter/flakes alternate
        grill_smoke(canvas, draw, variant_idx, theme_id=theme_id)
        if variant_idx % 2 == 0:
            grease_splatter(canvas, draw, variant_idx, theme_id=theme_id)
        if variant_idx != 1:
            seasoning_flakes(canvas, draw, variant_idx, theme_id=theme_id)
    return _fn


def make_seafood_overlay(theme_id: str):
    def _fn(canvas, draw, variant_idx):
        water_droplets(canvas, draw, variant_idx, theme_id=theme_id)
        if variant_idx == 0:
            bubbles(canvas, draw, variant_idx, theme_id=theme_id)
        if variant_idx % 2 == 1:
            sea_salt_dust(canvas, draw, variant_idx, theme_id=theme_id)
    return _fn


def make_game_day_overlay(theme_id: str):
    def _fn(canvas, draw, variant_idx):
        if variant_idx % 2 == 0:
            stadium_light_rays(canvas, draw, variant_idx, theme_id=theme_id)
        confetti_burst(canvas, draw, variant_idx, theme_id=theme_id)
        if variant_idx == 2:
            chalk_dust(canvas, draw, variant_idx, theme_id=theme_id)
    return _fn


def make_seasonal_overlay(theme_id: str):
    """Mardi Gras / Summer / Holiday — pick by theme id."""
    def _fn(canvas, draw, variant_idx):
        if theme_id == "mardi_gras":
            mardi_gras_glitter(canvas, draw, variant_idx, theme_id=theme_id)
        elif theme_id == "summer_splash":
            summer_sun_rays(canvas, draw, variant_idx, theme_id=theme_id)
            if variant_idx == 1:
                water_droplets(canvas, draw, variant_idx, theme_id=theme_id)
        elif theme_id == "holiday_cheer":
            snow_particles(canvas, draw, variant_idx, theme_id=theme_id)
        else:
            mardi_gras_glitter(canvas, draw, variant_idx, theme_id=theme_id)
    return _fn


def make_classic_overlay(theme_id: str):
    def _fn(canvas, draw, variant_idx):
        halftone_corner_dust(canvas, draw, variant_idx, theme_id=theme_id)
    return _fn


def make_flyer_overlay(theme_id: str):
    """Flyer pack — slightly punchier than classic (use grease splatter on the
    distressed theme, halftone on the rest)."""
    def _fn(canvas, draw, variant_idx):
        if theme_id == "distressed_orange":
            grease_splatter(canvas, draw, variant_idx, theme_id=theme_id,
                            color=(40, 25, 20, 200))
            halftone_corner_dust(canvas, draw, variant_idx, theme_id=theme_id)
        elif theme_id == "comic_pop":
            confetti_burst(canvas, draw, variant_idx, theme_id=theme_id,
                           palette=((255, 235, 70), (255, 255, 255), (240, 60, 140)))
        else:
            halftone_corner_dust(canvas, draw, variant_idx, theme_id=theme_id)
    return _fn
