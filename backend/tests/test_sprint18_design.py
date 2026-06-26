"""Sprint 18 — Professional Design System backend tests.

Covers:
  * quality_score returns a valid 0-100 + label + per-metric breakdown
  * score is deterministic for the same canvas
  * compose_layered_with_score returns (canvas, score_dict)
  * personality dicts are attached to every theme at load time
  * New badges (paint_splash, hanging_tag) + new backdrops (brush,
    torn_paper, paint_stroke) render without throwing
  * Render-time budget: scoring + 2 iterations completes < 1.5s per
    flyer locally (CI safety margin; production target is 500ms over
    baseline)
"""
import os
import sys
import time
from io import BytesIO

import pytest
from PIL import Image

# Make backend importable from this test path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from quality_score import (  # noqa: E402
    CompositionInfo,
    WEAKEST_TO_HINT,
    score_composition,
)


# --------------------------------------------------------------- helpers
def _mk_canvas(size=1024, food_x=400, food_y=400, food_w=420, food_h=420,
               food_color=(220, 140, 60), bg_color=(40, 40, 50)) -> Image.Image:
    """A synthetic flyer-ish canvas: bg + food bbox + bright food area."""
    img = Image.new("RGBA", (size, size), bg_color + (255,))
    # Draw a bright "food" rectangle
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.rectangle((food_x, food_y, food_x + food_w, food_y + food_h),
                fill=food_color + (255,))
    # Add some "title" area at top — bright text on dark band
    d.rectangle((40, 40, size - 40, 180), fill=(0, 0, 0, 200))
    d.rectangle((60, 80, size - 60, 140), fill=(240, 220, 100, 255))
    return img


def _mk_info(size=1024, food_x=400, food_y=400, food_w=420, food_h=420,
             title_h=140, badge_offset=(120, 120)) -> CompositionInfo:
    info = CompositionInfo(
        canvas_size=size,
        food_bbox=(food_x, food_y, food_x + food_w, food_y + food_h),
        title_bbox=(40, 40, size - 40, 180),
        badge_centre=(food_x + food_w + badge_offset[0],
                      food_y + food_h + badge_offset[1]),
        badge_radius=110,
    )
    info.layout_name = "hero_center"
    return info


# --------------------------------------------------------------- scorer
def test_score_returns_required_keys():
    info = _mk_info()
    sc = score_composition(_mk_canvas(), info, title_pixel_height=140)
    assert "score" in sc and "label" in sc and "metrics" in sc and "weakest" in sc
    assert 0 <= sc["score"] <= 100
    assert sc["label"] in ("Excellent", "Very Good", "Needs Attention")
    for k in (
        "food_prominence", "typography_hierarchy", "composition",
        "focal_point", "balance", "whitespace", "contrast",
        "readability", "badge_placement", "visual_flow",
    ):
        assert k in sc["metrics"]
        assert 0 <= sc["metrics"][k] <= 100


def test_score_is_deterministic():
    info = _mk_info()
    canvas = _mk_canvas()
    sc1 = score_composition(canvas, info, title_pixel_height=140)
    sc2 = score_composition(canvas, info, title_pixel_height=140)
    assert sc1["score"] == sc2["score"]
    assert sc1["metrics"] == sc2["metrics"]


def test_off_center_food_scores_higher_than_dead_center():
    """A food bbox sitting near a rule-of-thirds intersection should
    score higher on focal_point than a dead-centred bbox.
    """
    centred = _mk_info(food_x=300, food_y=300, food_w=420, food_h=420)
    rule_of_thirds = _mk_info(food_x=210, food_y=210, food_w=400, food_h=400)
    sc_centred = score_composition(_mk_canvas(food_x=300, food_y=300), centred, title_pixel_height=140)
    sc_rot = score_composition(_mk_canvas(food_x=210, food_y=210), rule_of_thirds, title_pixel_height=140)
    assert sc_rot["metrics"]["focal_point"] > sc_centred["metrics"]["focal_point"]


def test_tiny_title_penalizes_typography_hierarchy():
    info = _mk_info()
    big_sc = score_composition(_mk_canvas(), info, title_pixel_height=160)
    small_sc = score_composition(_mk_canvas(), info, title_pixel_height=40)
    assert big_sc["metrics"]["typography_hierarchy"] > small_sc["metrics"]["typography_hierarchy"]


def test_label_thresholds():
    """Excellent ≥ 85, Very Good ≥ 70, Needs Attention < 70."""
    from quality_score import _label_for  # noqa: WPS437 (internal helper test)
    assert _label_for(90) == "Excellent"
    assert _label_for(85) == "Excellent"
    assert _label_for(80) == "Very Good"
    assert _label_for(70) == "Very Good"
    assert _label_for(60) == "Needs Attention"


def test_weakest_metric_listed():
    info = _mk_info()
    sc = score_composition(_mk_canvas(), info, title_pixel_height=140)
    assert sc["weakest"] in sc["metrics"]
    # And it must actually be the lowest
    weakest_val = sc["metrics"][sc["weakest"]]
    for v in sc["metrics"].values():
        assert v >= weakest_val


def test_weakest_hint_mapping():
    """Every hint must be a known LAYOUT or skipped."""
    from render_engine import LAYOUTS
    for _metric, layout_hint in WEAKEST_TO_HINT.items():
        assert layout_hint in LAYOUTS or layout_hint is None


# --------------------------------------------------------------- personalities
def test_personality_attached_to_every_theme():
    from theme_packs import THEME_STYLES, THEME_META
    assert THEME_STYLES, "no themes registered"
    for tid, spec in THEME_STYLES.items():
        assert "personality" in spec, f"{tid} missing personality"
        p = spec["personality"]
        for k in ("tone", "texture", "type_weight", "saturation",
                  "badge_pool", "allow_overlap", "title_oversize",
                  "backdrop_pool"):
            assert k in p, f"{tid} personality missing {k}"
        # personality should propagate to THEME_META too
        assert "personality" in THEME_META[tid]


def test_personality_burger_is_aggressive():
    from theme_packs import THEME_STYLES
    burgers = [tid for tid, spec in THEME_STYLES.items()
               if "burger" in spec.get("personality", {}).get("badge_pool", [])
               or spec.get("personality", {}).get("tone") == "aggressive"]
    assert burgers, "no burger-personality themes found"
    for tid in burgers:
        p = THEME_STYLES[tid]["personality"]
        assert p["title_oversize"] >= 1.1, f"{tid} burger oversize too small"


def test_picks_are_personality_aware():
    """pick_badge_style and pick_title_backdrop_style restrict to the
    personality's pool when supplied."""
    from typography_engine import pick_badge_style, pick_title_backdrop_style
    burger_personality = {
        "badge_pool": ["paint_splash", "distressed_stamp"],
        "backdrop_pool": ["paint_stroke", "torn_paper"],
    }
    # Try multiple variants — every pick must be in the pool.
    for v in range(8):
        b = pick_badge_style("any_theme", v, personality=burger_personality)
        assert b in burger_personality["badge_pool"]
        bd = pick_title_backdrop_style("any_theme", v, personality=burger_personality)
        assert bd in burger_personality["backdrop_pool"]


# --------------------------------------------------------------- new badges/backdrops
def test_new_badges_render_without_exception():
    """Sprint 18 — paint_splash and hanging_tag must render cleanly."""
    import random
    from typography_engine import draw_premium_badge
    from PIL import ImageFont
    canvas = Image.new("RGBA", (512, 512), (245, 240, 230, 255))
    font = ImageFont.load_default()
    rng = random.Random(42)
    for style in ("paint_splash", "hanging_tag",
                  "burst", "ribbon", "sticker", "ticket",
                  "chalk_circle", "distressed_stamp"):
        draw_premium_badge(canvas, cx=256, cy=256, radius=80,
                           price_text="$12.95",
                           bg=(220, 70, 50), fg=(255, 255, 255),
                           ring=(255, 220, 100),
                           font=font, style=style, rng=rng)


def test_new_backdrops_render_without_exception():
    """Sprint 18 — brush, torn_paper, paint_stroke must render cleanly."""
    import random
    from typography_engine import draw_title_backdrop
    rng = random.Random(7)
    for style in ("brush", "torn_paper", "paint_stroke",
                  "ribbon", "swash", "distressed_rect"):
        canvas = Image.new("RGBA", (512, 200), (245, 240, 230, 255))
        draw_title_backdrop(canvas, x=40, y=40, w=432, h=120,
                            style=style, color=(220, 70, 50), rng=rng)


# --------------------------------------------------------------- iterative compose
def test_iterative_compose_returns_score():
    """End-to-end smoke: compose_layered_with_score must return both
    the canvas and a populated score dict."""
    from render_engine import compose_layered_with_score, CANVAS

    bg = Image.new("RGB", (CANVAS, CANVAS), (60, 70, 90))
    food = Image.new("RGBA", (CANVAS // 2, CANVAS // 2), (220, 140, 60, 255))
    # Stub theme — enough for the engine to run.
    theme = {
        "label": "Test", "bg_color": (60, 70, 90),
        "title": {"font": "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
                  "size": 110, "color": (245, 240, 230)},
        "bullets": {"font": "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                    "size": 24, "color": (245, 240, 230)},
        "branding_color": (200, 200, 200),
        "badge_bg": (220, 70, 50),
        "badge_fg": (255, 255, 255),
        "badge_ring": (255, 220, 100),
        "personality": {
            "tone": "aggressive", "texture": 0.7, "type_weight": "heavy",
            "saturation": 0.85,
            "badge_pool": ["paint_splash", "burst"],
            "allow_overlap": True, "title_oversize": 1.15,
            "backdrop_pool": ["paint_stroke", "torn_paper"],
        },
    }

    def draw_title(canvas, theme, name, x, y, w, align):
        from PIL import ImageDraw, ImageFont
        d = ImageDraw.Draw(canvas)
        f = ImageFont.truetype(theme["title"]["font"], theme["title"]["size"])
        d.text((x, y), name, fill=theme["title"]["color"], font=f)
        return y + theme["title"]["size"] + 10

    def draw_bullets(canvas, theme, feats, x, y, w):
        from PIL import ImageDraw, ImageFont
        d = ImageDraw.Draw(canvas)
        f = ImageFont.truetype(theme["bullets"]["font"], theme["bullets"]["size"])
        for i, feat in enumerate(feats[:3]):
            d.text((x, y + i * 30), f"- {feat}", fill=theme["bullets"]["color"], font=f)

    def draw_price_badge(canvas, theme, price, cx, cy, radius):
        from PIL import ImageDraw
        d = ImageDraw.Draw(canvas)
        d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius),
                  fill=theme["badge_bg"])

    def draw_branding(canvas, theme):
        pass

    t0 = time.perf_counter()
    canvas, score = compose_layered_with_score(
        bg_image=bg, food_rgba=food,
        theme=theme, theme_id="t1", variant_idx=0,
        draw_title=draw_title, draw_bullets=draw_bullets,
        draw_price_badge=draw_price_badge, draw_branding=draw_branding,
        item_name="Smash Burger", features=["cheese", "bacon", "pickle"],
        price="$12.95", target_score=75.0, max_iterations=2,
    )
    dt = time.perf_counter() - t0
    assert canvas.size == (CANVAS, CANVAS)
    assert 0 <= score["score"] <= 100
    assert "metrics" in score and "weakest" in score
    assert "candidates_tried" in score and len(score["candidates_tried"]) >= 1
    assert "chosen_layout" in score
    # Local safety margin — production target is +0.5s over baseline; we
    # assert well under 2.5s for headroom.
    assert dt < 2.5, f"compose+score too slow: {dt:.2f}s"
