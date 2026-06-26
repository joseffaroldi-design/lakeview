"""Sprint 18 — Quality Score Engine

A pure-PIL/NumPy scorer that evaluates a finalized flyer composition
against agency-grade design heuristics. Used by the iterative render
loop to:
   1. Score every candidate composition (0–100 + per-metric breakdown).
   2. Identify the weakest metric so the loop can target a fix.
   3. Return the highest-scoring layout to the user.

Scoring philosophy
------------------
The 10 sub-metrics are all 0–100 floats. The overall score is a
weighted average — Food Prominence, Typography Hierarchy and
Composition dominate (~60% of the weight). Everything else nudges.

The scorer NEVER mutates the input canvas; it only inspects pixels.

Cost budget
-----------
Target: ~30 ms on a 1024² canvas. Achieved by:
   * Downsampling to 256² before pixel inspection.
   * Using numpy histograms / variance, never per-pixel Python loops.

Outputs
-------
   {
     "score": 78.4,
     "label": "Very Good",  # Excellent | Very Good | Needs Attention
     "metrics": { "food_prominence": 82.1, "typography": 71.4, ... },
     "weakest": "typography",
   }
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image

log = logging.getLogger("uvicorn.error")


# --------------------------------------------------------------- weights
# Per user spec: Food prominence + Typography + Composition weigh more
# heavily than decoration. These sum to 1.0.
_WEIGHTS: Dict[str, float] = {
    "food_prominence":    0.20,
    "typography_hierarchy": 0.18,
    "composition":          0.16,
    "focal_point":          0.10,
    "balance":              0.08,
    "whitespace":           0.08,
    "contrast":             0.07,
    "readability":          0.06,
    "badge_placement":      0.04,
    "visual_flow":          0.03,
}
assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-6, "weights must sum to 1.0"


# --------------------------------------------------------------- inputs

@dataclass
class CompositionInfo:
    """Geometric metadata the render engine knows about the layout.
    All coordinates are in the SAME pixel space as the canvas.
    """
    canvas_size: int                                 # square edge length
    food_bbox: Tuple[int, int, int, int]             # x0,y0,x1,y1 of the food
    title_bbox: Optional[Tuple[int, int, int, int]]  # rendered title rect
    badge_centre: Tuple[int, int]
    badge_radius: int
    bullets_bbox: Optional[Tuple[int, int, int, int]] = None
    has_overlay: bool = False


# --------------------------------------------------------------- helpers

def _downsample(img: Image.Image, target: int = 256) -> np.ndarray:
    """Resize to a square `target` edge and return a (target,target,3) uint8.
    Pure RGB — alpha is composited onto a neutral mid-gray so transparent
    regions don't get counted as black.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    if img.size != (target, target):
        img = img.resize((target, target), Image.BILINEAR)
    base = Image.new("RGB", img.size, (128, 128, 128))
    base.paste(img, mask=img.split()[-1])
    return np.asarray(base, dtype=np.uint8)


def _luminance(arr: np.ndarray) -> np.ndarray:
    """Rec. 709 luminance, returns float32 0..255."""
    return (0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]).astype(np.float32)


# --------------------------------------------------------------- metrics

def _score_food_prominence(canvas_lum: np.ndarray,
                           info: CompositionInfo) -> float:
    """Sweet spot per spec: food occupies 60-75% of *visual attention*.
    We approximate visual attention via two signals:
        a) Pixel area: how much of the canvas the food bbox covers.
        b) Energy: how much of the high-luminance (food is usually well-lit)
           is inside vs outside the bbox.
    """
    H, W = canvas_lum.shape
    x0, y0, x1, y1 = info.food_bbox
    # Normalize bbox to the downsampled grid.
    s = info.canvas_size
    nx0 = max(0, int(x0 / s * W))
    ny0 = max(0, int(y0 / s * H))
    nx1 = min(W, int(x1 / s * W))
    ny1 = min(H, int(y1 / s * H))
    bbox_area = max(0, nx1 - nx0) * max(0, ny1 - ny0)
    total_area = W * H
    area_frac = bbox_area / max(1, total_area)

    # Score area against a triangular sweet-spot 0.30 → 0.55 (food bbox vs
    # canvas — the actual food blob is denser than its bbox).
    if area_frac < 0.15:
        area_s = max(0.0, area_frac / 0.15) * 50.0
    elif area_frac < 0.30:
        area_s = 50.0 + (area_frac - 0.15) / 0.15 * 30.0
    elif area_frac <= 0.55:
        area_s = 80.0 + (1.0 - abs(area_frac - 0.42) / 0.13) * 20.0
    elif area_frac <= 0.75:
        area_s = 100.0 - (area_frac - 0.55) / 0.20 * 30.0
    else:
        area_s = max(0.0, 70.0 - (area_frac - 0.75) * 200.0)

    # Energy: how much luminance > 140 is inside the bbox vs outside.
    bright = canvas_lum > 140
    if not bright.any():
        energy_s = 60.0
    else:
        inside = bright[ny0:ny1, nx0:nx1].sum()
        outside = bright.sum() - inside
        ratio = inside / max(1, inside + outside)
        # 0.4-0.7 is "food dominates the light" range.
        if ratio < 0.25:
            energy_s = ratio / 0.25 * 50.0
        elif ratio < 0.40:
            energy_s = 50.0 + (ratio - 0.25) / 0.15 * 30.0
        elif ratio <= 0.70:
            energy_s = 80.0 + (1.0 - abs(ratio - 0.55) / 0.15) * 20.0
        else:
            energy_s = max(50.0, 100.0 - (ratio - 0.70) * 150.0)

    return float(0.65 * area_s + 0.35 * energy_s)


def _score_focal_point(info: CompositionInfo) -> float:
    """Reward rule-of-thirds placement; penalize dead-centre."""
    s = info.canvas_size
    cx = (info.food_bbox[0] + info.food_bbox[2]) / 2 / s
    cy = (info.food_bbox[1] + info.food_bbox[3]) / 2 / s
    # 4 rule-of-thirds intersections
    targets = [(1/3, 1/3), (2/3, 1/3), (1/3, 2/3), (2/3, 2/3)]
    dist = min(((cx - tx) ** 2 + (cy - ty) ** 2) ** 0.5 for tx, ty in targets)
    # Hard penalty if dead-centre (≤ 0.05 from (0.5,0.5))
    centre_dist = ((cx - 0.5) ** 2 + (cy - 0.5) ** 2) ** 0.5
    centre_penalty = max(0, 20 - centre_dist * 200) if centre_dist < 0.10 else 0
    # Reward proximity to a thirds intersection (best at 0, worst at 0.30+).
    nearness = max(0.0, 1.0 - dist / 0.30)
    return float(max(0.0, 100.0 * nearness - centre_penalty))


def _score_composition(info: CompositionInfo) -> float:
    """Off-centre bias + controlled overlap rewards.
    The food's centre should be offset from the canvas centre AND the
    title or badge should slightly overlap the food bbox.
    """
    s = info.canvas_size
    cx = (info.food_bbox[0] + info.food_bbox[2]) / 2 / s
    cy = (info.food_bbox[1] + info.food_bbox[3]) / 2 / s
    # Distance from centre — reward 0.10..0.25 offset; penalize > 0.35.
    offset = ((cx - 0.5) ** 2 + (cy - 0.5) ** 2) ** 0.5
    if offset < 0.05:
        offset_s = 30.0
    elif offset < 0.10:
        offset_s = 50.0 + (offset - 0.05) / 0.05 * 30.0
    elif offset <= 0.25:
        offset_s = 80.0 + (1.0 - abs(offset - 0.17) / 0.08) * 20.0
    else:
        offset_s = max(40.0, 100.0 - (offset - 0.25) * 200.0)

    # Overlap signal: badge centre lies inside or within 30 px of food bbox.
    bx, by = info.badge_centre
    fx0, fy0, fx1, fy1 = info.food_bbox
    badge_in = fx0 - 30 <= bx <= fx1 + 30 and fy0 - 30 <= by <= fy1 + 30
    overlap_s = 90.0 if badge_in else 60.0
    return float(0.6 * offset_s + 0.4 * overlap_s)


def _score_typography_hierarchy(info: CompositionInfo,
                                title_pixel_height: Optional[int]) -> float:
    """Strong title presence + clear size cascade.
    We approximate "presence" via the title bbox height as a fraction of
    the canvas. A very small title scores low.
    """
    if not info.title_bbox or title_pixel_height is None:
        return 50.0
    s = info.canvas_size
    h = title_pixel_height
    h_frac = h / s
    if h_frac < 0.06:
        return 35.0 + h_frac / 0.06 * 30.0
    if h_frac < 0.10:
        return 65.0 + (h_frac - 0.06) / 0.04 * 25.0
    if h_frac <= 0.22:
        return 100.0 - max(0.0, (h_frac - 0.16) * 250.0)
    return max(40.0, 90.0 - (h_frac - 0.22) * 200.0)


def _score_balance(canvas_lum: np.ndarray) -> float:
    """Visual mass: split into 4 quadrants, reward modest balance."""
    H, W = canvas_lum.shape
    inverted = 255.0 - canvas_lum  # darker = more "ink"
    tl = inverted[:H // 2, :W // 2].sum()
    tr = inverted[:H // 2, W // 2:].sum()
    bl = inverted[H // 2:, :W // 2].sum()
    br = inverted[H // 2:, W // 2:].sum()
    total = max(1.0, tl + tr + bl + br)
    fracs = np.array([tl, tr, bl, br]) / total
    # Ideal: roughly uniform 0.25 each; reward stddev < 0.10.
    std = float(fracs.std())
    if std < 0.05:
        return 95.0
    if std < 0.10:
        return 85.0
    if std < 0.18:
        return 70.0 - (std - 0.10) * 200.0
    return max(35.0, 55.0 - (std - 0.18) * 200.0)


def _score_whitespace(canvas_lum: np.ndarray) -> float:
    """Reward 20–40% "empty" canvas — neither cluttered nor sparse."""
    H, W = canvas_lum.shape
    # Use a soft threshold on edge density via simple gradient.
    gx = np.abs(np.diff(canvas_lum, axis=1))
    gy = np.abs(np.diff(canvas_lum, axis=0))
    edge = np.zeros_like(canvas_lum)
    edge[:, :-1] += gx
    edge[:-1, :] += gy
    # "Empty" pixels = low edge density
    empty_frac = float((edge < 25).sum()) / (H * W)
    if empty_frac < 0.10:
        return 30.0 + empty_frac * 300.0
    if empty_frac < 0.20:
        return 60.0 + (empty_frac - 0.10) * 250.0
    if empty_frac <= 0.40:
        return 85.0 + (1.0 - abs(empty_frac - 0.30) / 0.10) * 15.0
    if empty_frac <= 0.55:
        return 85.0 - (empty_frac - 0.40) * 100.0
    return max(35.0, 70.0 - (empty_frac - 0.55) * 200.0)


def _score_contrast(canvas_lum: np.ndarray) -> float:
    """Reward wide tonal range. Premium flyers have strong contrast."""
    p5, p95 = np.percentile(canvas_lum, [5, 95])
    spread = float(p95 - p5)
    # 0..255 spread → score
    if spread < 80:
        return 40.0 + spread / 80.0 * 30.0
    if spread < 140:
        return 70.0 + (spread - 80) / 60 * 20.0
    if spread < 200:
        return 90.0 + (spread - 140) / 60 * 10.0
    return max(70.0, 100.0 - (spread - 200) / 55.0 * 20.0)


def _score_readability(canvas_arr: np.ndarray,
                       info: CompositionInfo) -> float:
    """Inside the title bbox, the std-dev of luminance should be low
    (so text isn't fighting noisy background) and the mean should be
    distinct from text colour. We don't know the text colour cheaply
    here, so we approximate: a CALM background under the title = good.
    """
    if not info.title_bbox:
        return 70.0
    H, W = canvas_arr.shape[:2]
    s = info.canvas_size
    x0, y0, x1, y1 = info.title_bbox
    nx0 = max(0, int(x0 / s * W))
    ny0 = max(0, int(y0 / s * H))
    nx1 = min(W, int(x1 / s * W))
    ny1 = min(H, int(y1 / s * H))
    if nx1 <= nx0 or ny1 <= ny0:
        return 60.0
    lum = _luminance(canvas_arr[ny0:ny1, nx0:nx1])
    std = float(lum.std())
    if std < 20:
        return 95.0
    if std < 40:
        return 80.0
    if std < 60:
        return 65.0
    return max(40.0, 80.0 - (std - 60) * 0.5)


def _score_badge_placement(info: CompositionInfo) -> float:
    """Badge slightly overlaps food OR sits on a clear edge — both good.
    Penalty if it's deep inside the food (blocks the hero) or way out
    in a corner with nothing nearby.
    """
    s = info.canvas_size
    bx, by = info.badge_centre
    fx0, fy0, fx1, fy1 = info.food_bbox
    fcx = (fx0 + fx1) / 2
    fcy = (fy0 + fy1) / 2
    # distance to food centre normalized to canvas
    d_centre = (((bx - fcx) ** 2 + (by - fcy) ** 2) ** 0.5) / s
    # 0.18..0.32 is the sweet spot (edge overlap)
    if d_centre < 0.08:
        return 40.0 + d_centre / 0.08 * 30.0  # too central — blocks food
    if d_centre <= 0.32:
        return 95.0 - abs(d_centre - 0.22) * 100.0
    return max(45.0, 80.0 - (d_centre - 0.32) * 150.0)


def _score_visual_flow(info: CompositionInfo) -> float:
    """Title near top, food in middle, price/CTA near bottom = natural
    top-to-bottom scan. We measure the vertical order of the layout.
    """
    s = info.canvas_size
    if not info.title_bbox:
        return 60.0
    title_y = (info.title_bbox[1] + info.title_bbox[3]) / 2 / s
    food_y = (info.food_bbox[1] + info.food_bbox[3]) / 2 / s
    badge_y = info.badge_centre[1] / s
    score = 80.0
    if title_y > food_y:
        score -= 20.0  # title BELOW food = unusual
    if badge_y < title_y:
        score -= 15.0  # badge above title
    # Reward proper top→middle→bottom-ish ordering
    if title_y < food_y < badge_y + 0.05:
        score += 20.0
    return float(max(30.0, min(100.0, score)))


# --------------------------------------------------------------- aggregate

def _label_for(score: float) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Very Good"
    return "Needs Attention"


def score_composition(canvas: Image.Image,
                      info: CompositionInfo,
                      *,
                      title_pixel_height: Optional[int] = None,
                      ) -> Dict[str, object]:
    """Score the supplied composition. Returns the score+breakdown dict.
    Fast (~30 ms on 1024² via 256² downsample).
    """
    arr = _downsample(canvas, 256)
    lum = _luminance(arr)
    metrics = {
        "food_prominence":    _score_food_prominence(lum, info),
        "typography_hierarchy": _score_typography_hierarchy(info, title_pixel_height),
        "composition":          _score_composition(info),
        "focal_point":          _score_focal_point(info),
        "balance":              _score_balance(lum),
        "whitespace":           _score_whitespace(lum),
        "contrast":             _score_contrast(lum),
        "readability":          _score_readability(arr, info),
        "badge_placement":      _score_badge_placement(info),
        "visual_flow":          _score_visual_flow(info),
    }
    overall = sum(metrics[k] * _WEIGHTS[k] for k in _WEIGHTS)
    weakest = min(metrics.items(), key=lambda kv: kv[1])[0]
    return {
        "score": round(overall, 1),
        "label": _label_for(overall),
        "metrics": {k: round(v, 1) for k, v in metrics.items()},
        "weakest": weakest,
    }


# --------------------------------------------------------------- iter loop hints

# Map "weakest metric" → "layout hint that usually fixes it". Used by the
# iterative renderer to choose the next candidate layout.
WEAKEST_TO_HINT: Dict[str, str] = {
    "focal_point":        "left_focus",   # off-centre, rule-of-thirds
    "composition":        "right_focus",  # asymmetric, intentional offset
    "food_prominence":    "full_bleed",   # bigger food
    "balance":            "hero_center",  # restore balance
    "whitespace":         "bottom_hero",  # tighter copy stack
    "visual_flow":        "stacked",      # explicit top→middle→bottom
    # The rest don't have a clean layout fix; fall through to the next pick.
}


__all__ = [
    "CompositionInfo",
    "score_composition",
    "WEAKEST_TO_HINT",
]
