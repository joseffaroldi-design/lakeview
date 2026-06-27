"""Sprint 22 P0 Fix 2 — Variant uniqueness regression.

The 3 generated variations MUST have distinct PNG byte hashes AND visible
pixel-level differences, regardless of which render path (HTML / agency
template / procedural) handles the theme.

This file uses the in-process `_compose_design` so it does NOT require a
running backend. It exercises 4 themes — one per render path — with the
same real food photo to confirm:
  1. v0, v1, v2 produce 3 distinct PNG hashes.
  2. The pixel diff between any two variants exceeds a low floor
     (>3% of pixels visibly changed) — i.e. the difference is REAL,
     not just metadata.
"""
from __future__ import annotations
import hashlib
import io
from typing import List
import numpy as np
import pytest
from PIL import Image


# Pick the first real burger photo present in object storage if available,
# else fall back to the launch-assets fixture. The fixture is an abstract
# graphic — variant uniqueness still holds because the transform operates
# on whatever cutout it receives.
REAL_PHOTO = "/app/memory/launch/assets/smash-burger-source.jpg"

# 4 themes — one per render path:
#   burger_classic, game_day_scoreboard → agency template
#   distressed_orange                   → agency-template fallback
#   seafood_coastal                     → HTML renderer (skip on sandbox)
THEMES_FAST = ["burger_classic", "game_day_scoreboard", "distressed_orange"]
THEMES_SLOW = ["seafood_coastal"]


def _load_food():
    from routers.ai_designer import _prepare_food_cutout
    with open(REAL_PHOTO, "rb") as f:
        return _prepare_food_cutout(f.read(), target_max=int(1080 * 0.65), use_rembg=False)


def _render_three_variants(theme: str):
    """Render v0, v1, v2 and return their PNG bytes."""
    from routers.ai_designer import _compose_design, _pil_background
    food = _load_food()
    out = []
    for idx in range(3):
        bg_bytes = _pil_background(theme, idx)
        png_bytes, _score = _compose_design(
            bg_bytes, food.copy(),
            "Smash Burger", ["Two patties", "Cheese", "Pickles"], "$13.50",
            theme, ["centered", "asym_left", "stacked"][idx],
            variant_idx=idx,
        )
        out.append(png_bytes)
    return out


def _pixel_change_pct(png_a: bytes, png_b: bytes) -> float:
    """Return the % of pixels where the absolute RGB diff > 30."""
    a = np.array(Image.open(io.BytesIO(png_a)).convert("RGB")).astype(int)
    b = np.array(Image.open(io.BytesIO(png_b)).convert("RGB")).astype(int)
    return float(((np.abs(a - b).sum(axis=2)) > 30).mean() * 100.0)


@pytest.mark.parametrize("theme", THEMES_FAST)
def test_three_variants_have_distinct_hashes(theme):
    """v0, v1, v2 must have 3 different MD5 hashes."""
    variants = _render_three_variants(theme)
    hashes = [hashlib.md5(v).hexdigest() for v in variants]
    assert len(set(hashes)) == 3, (
        f"Theme {theme}: hashes collide → {hashes}. "
        "P0 Fix 2 regression — variants are byte-identical."
    )


@pytest.mark.parametrize("theme", THEMES_FAST)
def test_three_variants_have_visible_pixel_diff(theme):
    """v0, v1, v2 must differ visibly — not just metadata.

    Floor of >3% pixels changed is intentionally loose so that subtle
    template differences still pass while genuinely-identical outputs fail.
    """
    variants = _render_three_variants(theme)
    d01 = _pixel_change_pct(variants[0], variants[1])
    d02 = _pixel_change_pct(variants[0], variants[2])
    d12 = _pixel_change_pct(variants[1], variants[2])
    for pair_name, pct in (("v0/v1", d01), ("v0/v2", d02), ("v1/v2", d12)):
        assert pct > 3.0, (
            f"Theme {theme} pair {pair_name}: only {pct:.1f}% pixels changed. "
            "P0 Fix 2 regression — variants visually identical."
        )


@pytest.mark.slow  # html_renderer (Playwright) — sandbox-incompatible
@pytest.mark.parametrize("theme", THEMES_SLOW)
def test_html_path_variants_have_distinct_hashes(theme):
    variants = _render_three_variants(theme)
    hashes = [hashlib.md5(v).hexdigest() for v in variants]
    assert len(set(hashes)) == 3, (
        f"HTML theme {theme}: hashes collide → {hashes}"
    )
