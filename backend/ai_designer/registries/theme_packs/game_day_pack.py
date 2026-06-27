"""Game Day pack — scoreboard, tailgate, locker-room/sports-bar promos."""
from __future__ import annotations

from PIL import Image, ImageDraw

from ._shared import (
    CANVAS, FONT_BEBAS_NEUE, FONT_BUNGEE, FONT_PERMANENT_MARKER,
    FONT_SANS_BOLD,
)

PACK = {
    "id": "game_day",
    "label": "Game Day",
    "category": "sports",
    "enabled": True,
    "description": "Stadium energy — scoreboard digits, team-stripe palettes, bold price calls.",
}


# ---------------------------------------------------------------- background renderers

def _bg_scoreboard(canvas: Image.Image, draw: ImageDraw.ImageDraw, variant_idx: int) -> None:
    from routers.ai_designer import _radial_gradient, _halftone_dots
    canvas.paste(Image.new("RGB", canvas.size, (12, 12, 16)))
    _radial_gradient(canvas, (28, 28, 36), (4, 4, 8), CANVAS // 2,
                     int(CANVAS * 0.5), int(CANVAS * 0.9))
    # gold scoreboard frame
    draw.rectangle((40, 40, CANVAS - 40, CANVAS - 40),
                   outline=(252, 200, 60, 240), width=6)
    draw.rectangle((60, 60, CANVAS - 60, CANVAS - 60),
                   outline=(252, 200, 60, 140), width=2)
    if variant_idx == 0:
        # LED dot matrix top + bottom
        _halftone_dots(draw, (252, 200, 60, 240),
                       start_xy=(80, 80), end_xy=(CANVAS - 80, 200),
                       spacing=20, max_r=6)
        _halftone_dots(draw, (252, 200, 60, 240),
                       start_xy=(80, CANVAS - 200), end_xy=(CANVAS - 80, CANVAS - 80),
                       spacing=20, max_r=6)
    elif variant_idx == 1:
        # Red/blue vertical team stripes on sides
        for x in (80, 110):
            draw.rectangle((x, 80, x + 12, CANVAS - 80), fill=(220, 40, 50, 220))
        for x in (CANVAS - 122, CANVAS - 92):
            draw.rectangle((x, 80, x + 12, CANVAS - 80), fill=(40, 80, 200, 220))
    else:
        # Center "VS" plate
        draw.rounded_rectangle(
            (CANVAS // 2 - 80, CANVAS // 2 - 60, CANVAS // 2 + 80, CANVAS // 2 + 60),
            radius=12, outline=(252, 200, 60, 230), width=4,
        )
        for y in (90, 110, CANVAS - 110, CANVAS - 90):
            draw.line((100, y, CANVAS - 100, y), fill=(252, 200, 60, 90), width=2)


def _bg_tailgate(canvas: Image.Image, draw: ImageDraw.ImageDraw, variant_idx: int) -> None:
    from routers.ai_designer import _star, _lightning_bolt, _distressed_grain
    # half red, half blue split
    draw.rectangle((0, 0, CANVAS // 2, CANVAS), fill=(190, 30, 40))
    draw.rectangle((CANVAS // 2, 0, CANVAS, CANVAS), fill=(30, 60, 150))
    # cream center diagonal
    draw.polygon(
        [(CANVAS // 2 - 60, 0), (CANVAS // 2 + 60, 0),
         (CANVAS // 2 + 60, CANVAS), (CANVAS // 2 - 60, CANVAS)],
        fill=(252, 240, 210),
    )
    if variant_idx == 0:
        for cx in (160, CANVAS - 160):
            for cy in (160, CANVAS - 160):
                _star(draw, (252, 240, 210, 240), cx=cx, cy=cy, r=30)
    elif variant_idx == 1:
        _lightning_bolt(draw, (252, 220, 60, 240), tip=(220, 280), size=180)
        _lightning_bolt(draw, (252, 220, 60, 240), tip=(CANVAS - 220, CANVAS - 100), size=180)
    else:
        _distressed_grain(canvas, (12, 12, 16, 30), density=1400)
        for cx, cy in [(CANVAS // 2, 140), (CANVAS // 2, CANVAS - 140)]:
            _star(draw, (190, 30, 40, 240), cx=cx, cy=cy, r=28)


def _bg_locker_chalk(canvas: Image.Image, draw: ImageDraw.ImageDraw, variant_idx: int) -> None:
    from routers.ai_designer import _radial_gradient, _star, _distressed_grain
    _radial_gradient(canvas, (45, 50, 52), (20, 22, 24), CANVAS // 2,
                     int(CANVAS * 0.55), int(CANVAS * 0.95))
    _distressed_grain(canvas, (252, 240, 210, 20), density=1500)
    if variant_idx == 0:
        # Chalkboard play diagram — arrows + circles
        for cx, cy in [(140, 160), (CANVAS - 140, 160),
                       (140, CANVAS - 160), (CANVAS - 140, CANVAS - 160)]:
            draw.ellipse((cx - 22, cy - 22, cx + 22, cy + 22),
                         outline=(252, 240, 210, 220), width=3)
        draw.line((180, 200, CANVAS - 180, CANVAS - 200),
                  fill=(252, 220, 60, 200), width=3)
        draw.line((CANVAS - 180, 200, 180, CANVAS - 200),
                  fill=(252, 220, 60, 200), width=3)
    elif variant_idx == 1:
        # Locker-row vertical bars
        for x in range(80, CANVAS - 80, 90):
            draw.rectangle((x, 80, x + 70, CANVAS - 80),
                           outline=(252, 240, 210, 90), width=2)
        for cx in (160, CANVAS - 160):
            _star(draw, (252, 220, 60, 240), cx=cx, cy=CANVAS // 2, r=28)
    else:
        # Yardline numbers (10s)
        for i, y in enumerate(range(140, CANVAS - 120, 120)):
            draw.line((90, y, CANVAS - 90, y), fill=(252, 240, 210, 60), width=2)
            label = str((i + 1) * 10)
            draw.text((110, y - 28), label, fill=(252, 220, 60, 200))


# ---------------------------------------------------------------- theme dicts

THEMES = {
    "game_day_scoreboard": {
        "label": "Scoreboard Gold",
        "best_use": "Bar specials during games, watch-party menus",
        "bg_color": (12, 12, 16),
        "title": {"font": FONT_BUNGEE, "color": (252, 200, 60), "size": 112,
                  "stroke_width": 4, "stroke_fill": (12, 12, 16),
                  "letter_spacing": 4, "shadow": (252, 200, 60, 120)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (252, 240, 210), "size": 34, "marker": "▸",
                  "marker_color": (252, 200, 60), "letter_spacing": 2},
        "price": {"bg": (252, 200, 60), "fg": (12, 12, 16), "ring": (252, 240, 210), "font": FONT_BUNGEE},
        "branding_color": (252, 200, 60),
        "icons": True,
        "background_fn": _bg_scoreboard,
    },
    "game_day_tailgate": {
        "label": "Tailgate Split",
        "best_use": "Tailgate menus, rivalry-week promos, big plates",
        "bg_color": (190, 30, 40),
        "title": {"font": FONT_BEBAS_NEUE, "color": (12, 12, 16), "size": 110,
                  "stroke_width": 3, "stroke_fill": (252, 240, 210),
                  "letter_spacing": 5, "shadow": (12, 12, 16, 150)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (12, 12, 16), "size": 32, "marker": "★",
                  "marker_color": (190, 30, 40), "letter_spacing": 2},
        "price": {"bg": (252, 220, 60), "fg": (12, 12, 16), "ring": (190, 30, 40), "font": FONT_BEBAS_NEUE},
        "branding_color": (12, 12, 16),
        "icons": True,
        "background_fn": _bg_tailgate,
    },
    "game_day_locker": {
        "label": "Locker-Room Chalk",
        "best_use": "Sports-bar wings, late-night menus, halftime drops",
        "bg_color": (28, 30, 32),
        "title": {"font": FONT_PERMANENT_MARKER, "color": (252, 240, 210), "size": 106,
                  "stroke_width": 3, "stroke_fill": (12, 12, 16),
                  "letter_spacing": 3, "shadow": (252, 220, 60, 90)},
        "body":  {"font": FONT_BEBAS_NEUE, "color": (252, 240, 210), "size": 32, "marker": "→",
                  "marker_color": (252, 220, 60), "letter_spacing": 2},
        "price": {"bg": (252, 220, 60), "fg": (12, 12, 16), "ring": (252, 240, 210), "font": FONT_PERMANENT_MARKER},
        "branding_color": (252, 220, 60),
        "icons": True,
        "background_fn": _bg_locker_chalk,
    },
}

_ = FONT_SANS_BOLD  # reserved for future variants

# Sprint 16H — attach foreground overlay (stadium lights / confetti / chalk).
from ._overlays import make_game_day_overlay  # noqa: E402

for _tid in THEMES:
    THEMES[_tid]["overlay_fn"] = make_game_day_overlay(_tid)
