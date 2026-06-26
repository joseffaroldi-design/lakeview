"""Sprint 20 Phase 0.5 — Validation harness for the polished agency engine.

Renders all 25 Lakeview acceptance menu items via the agency template
pipeline (with the polish updates from Phase 0.5) + scores each render
with the internal Quality Score engine, then writes:

    /tmp/sprint20p05_renders/*.jpg
    /tmp/sprint20p05_results.json

Run from /app/backend:
    python scripts/sprint20p05_validation.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

import agency_templates as at  # noqa: E402
from agency_renderer import compose_with_template  # noqa: E402
from quality_score import CompositionInfo, score_composition  # noqa: E402


# 25 representative Lakeview menu items (same list used by Sprint 19).
ITEMS = [
    ("Café Fries",                         "Appetizers", "luxury",              ["with Roast Beef Gravy", "Cheddar", "Sour Cream"], "$13.25"),
    ("Chicken Wings (6)",                  "Appetizers", "game_day_scoreboard", ["Buffalo", "BBQ", "Asian Glaze"],                    "$11.00"),
    ("Chicken Wings (12)",                 "Appetizers", "game_day_scoreboard", ["Buffalo", "BBQ", "Asian Glaze", "Lemon Pepper"],   "$20.00"),
    ("Fresh Mozzarella Cheese Sticks",     "Appetizers", "luxury",              ["Marinara", "House-breaded"],                       "$10.50"),
    ("Fried Louisiana Okra",               "Appetizers", "luxury",              ["Cornmeal-breaded", "Cajun salt"],                  "$8.00"),
    ("Fried Onion Rings",                  "Appetizers", "luxury",              ["Beer-battered", "House remoulade"],                "$7.50"),
    ("Fried Pickles",                      "Appetizers", "luxury",              ["Buttermilk dredged", "Ranch dip"],                 "$7.00"),
    ("Chicken Andouille Gumbo",            "Soups",      "luxury",              ["Andouille sausage", "Holy trinity"],               "$8.00"),
    ("Corn & Crab Bisque",                 "Soups",      "seafood_coastal",     ["Sweet corn", "Lump crab"],                         "$9.00"),
    ("Seafood Gumbo",                      "Soups",      "seafood_coastal",     ["Shrimp", "Crab", "Andouille"],                     "$9.00"),
    ("Caesar Salad",                       "Salads",     "luxury",              ["Romaine", "Parmesan", "House Caesar"],             "$10.00"),
    ("Garden Salad",                       "Salads",     "luxury",              ["Mixed greens", "Cherry tomato", "Cucumber"],       "$10.00"),
    ("Spinach Salad",                      "Salads",     "luxury",              ["Baby spinach", "Egg", "Bacon"],                    "$10.00"),
    ("Grilled Tuna or Shrimp",             "Salads",     "seafood_coastal",     ["Gulf shrimp", "Yellowfin tuna"],                   "$12.95"),
    ("Fried Oysters or Shrimp",            "Salads",     "seafood_coastal",     ["Cornmeal-fried", "Gulf-sourced"],                  "$12.95"),
    ("Grilled Blackened Chicken",          "Salads",     "luxury",              ["Cajun-rubbed", "Char-grilled"],                    "$10.00"),
    ("Classic Burger (8oz)",               "Burgers",    "burger_classic",      ["All-natural beef", "Brioche bun"],                 "$13.00"),
    ("Extra Patty",                        "Burgers",    "burger_classic",      ["8oz add-on"],                                      "$5.00"),
    ("Bacon Cheeseburger",                 "Burgers",    "burger_classic",      ["Smoked bacon", "Cheddar"],                         "$15.00"),
    ("Mushroom Swiss Burger",              "Burgers",    "burger_classic",      ["Sautéed mushrooms", "Swiss"],                      "$15.00"),
    ("Smash Burger",                       "Burgers",    "burger_classic",      ["Smash patty", "American cheese", "Pickles"],       "$11.00"),
    ("Chicken Sandwich",                   "Sandwiches", "modern",              ["Grilled or fried", "House bun"],                   "$12.00"),
    ("Chicken Parmesan",                   "Sandwiches", "modern",              ["Parmesan crust", "Marinara"],                      "$13.00"),
    ("Shrimp Po-Boy",                      "Sandwiches", "seafood_coastal",     ["Fried Gulf shrimp", "Remoulade"],                  "$14.50"),
    ("Cuban",                              "Sandwiches", "modern",              ["Slow-roasted pork", "Swiss", "Pickles"],           "$13.00"),
]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _seed_food() -> Image.Image:
    folder = "/app/backend/media_storage"
    if os.path.isdir(folder):
        candidates = []
        for fn in os.listdir(folder):
            if fn.endswith((".jpg", ".jpeg", ".png")):
                p = os.path.join(folder, fn)
                try:
                    candidates.append((os.path.getsize(p), p))
                except OSError:
                    continue
        if candidates:
            candidates.sort(reverse=True)
            return Image.open(candidates[0][1]).convert("RGBA")
    im = Image.new("RGBA", (1200, 1500), (0, 0, 0, 0))
    from PIL import ImageDraw
    ImageDraw.Draw(im).ellipse((100, 200, 1100, 1400), fill=(180, 110, 60, 255))
    return im


def _info_for_template(template) -> CompositionInfo:
    """Build CompositionInfo from the manifest's slot rects so the
    Quality Score engine can score agency renders on the same 0-100 scale
    as procedural."""
    s = template.slots
    p = s["photo"]
    t = s.get("title")
    pr = s["price"]
    title_bbox = None
    if t:
        title_bbox = (t["x"], t["y"], t["x"] + t["w"], t["y"] + t["h"])
    return CompositionInfo(
        canvas_size=template.canvas[0],
        food_bbox=(p["x"], p["y"], p["x"] + p["w"], p["y"] + p["h"]),
        title_bbox=title_bbox,
        badge_centre=(pr["cx"], pr["cy"]),
        badge_radius=pr["radius"],
        bullets_bbox=None,
        has_overlay=bool(template.overlay_paths),
    )


def main() -> None:
    out_dir = "/tmp/sprint20p05_renders"
    os.makedirs(out_dir, exist_ok=True)
    food = _seed_food()
    results: List[Dict] = []
    print(f"  {'item':38s} {'template':22s} {'score':>6} {'render_ms':>10}")
    print("-" * 86)
    for name, cat, theme, features, price in ITEMS:
        t = at.pick_template_for(category=None, theme_hint=theme)
        if t is None:
            t = at.pick_template_for("general")
        t0 = time.perf_counter()
        canvas = compose_with_template(
            t, food_rgba=food, item_name=name, features=features, price=price,
            brand="LAKEVIEW BURGERS & SEAFOOD", cta="Order Now · Mon-Sat 11-9",
        )
        dt_ms = (time.perf_counter() - t0) * 1000
        info = _info_for_template(t)
        title_h = getattr(canvas, "title_pixel_height", None)
        scored = score_composition(canvas, info, title_pixel_height=title_h)
        slug = _slug(name)
        path = f"{out_dir}/{slug}.jpg"
        canvas.convert("RGB").save(path, quality=92)
        results.append({
            "item": name,
            "category": cat,
            "theme_hint": theme,
            "template_id": t.id,
            "template_label": t.label,
            "score": scored["score"],
            "label": scored["label"],
            "weakest": scored["weakest"],
            "metrics": scored["metrics"],
            "render_ms": round(dt_ms, 1),
            "path": path,
        })
        print(f"  {name[:38]:38s} {t.id[:22]:22s} {scored['score']:>6.1f} {dt_ms:>10.1f}")
    summary = {
        "n": len(results),
        "avg_score": round(sum(r["score"] for r in results) / len(results), 1),
        "avg_render_ms": round(sum(r["render_ms"] for r in results) / len(results), 1),
        "by_template": {},
        "strongest": sorted(results, key=lambda r: -r["score"])[:5],
        "weakest": sorted(results, key=lambda r: r["score"])[:5],
    }
    by_t: Dict[str, List[float]] = {}
    for r in results:
        by_t.setdefault(r["template_id"], []).append(r["score"])
    summary["by_template"] = {tid: {"n": len(v), "avg": round(sum(v) / len(v), 1)}
                              for tid, v in by_t.items()}
    print("-" * 86)
    print(f"  n={summary['n']}  avg_score={summary['avg_score']}  avg_render={summary['avg_render_ms']} ms")
    print(f"  by template: {summary['by_template']}")

    with open("/tmp/sprint20p05_results.json", "w") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)
    print("  → /tmp/sprint20p05_results.json")


if __name__ == "__main__":
    main()
