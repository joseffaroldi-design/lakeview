"""Sprint 20A — smoke-render Cajun + Luxury HTML templates with the
new headless-browser engine and write the PNGs to /tmp for visual audit.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from html_renderer import render_flyer, shutdown  # noqa: E402


def _seed_food() -> str | None:
    folder = "/app/backend/media_storage"
    if not os.path.isdir(folder):
        return None
    candidates = []
    for fn in os.listdir(folder):
        if fn.endswith((".jpg", ".jpeg", ".png")):
            p = os.path.join(folder, fn)
            try:
                candidates.append((os.path.getsize(p), p))
            except OSError:
                continue
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


SAMPLES = [
    ("cajun",  "Cajun Shrimp Po-Boy",
     ["Fried Gulf Shrimp", "House Remoulade", "Pickled Slaw"], "$14.50"),
    ("luxury", "Wagyu Filet Mignon",
     ["8oz Prime Cut", "House Demi-Glace", "Roasted Shallots"], "$48.00"),
    ("cajun",  "Smash Burger",
     ["Smash Patty", "American Cheese", "House Pickles"], "$11.00"),
    ("luxury", "Café Fries",
     ["Roast Beef Gravy", "Cheddar", "Sour Cream"], "$13.25"),
]


def main() -> None:
    food = _seed_food()
    print(f"  seed_food = {food}")
    for theme, name, feats, price in SAMPLES:
        out_path = f"/tmp/htmlflyer_{theme}_{name.replace(' ', '_').lower()}.png"
        t0 = time.perf_counter()
        png = render_flyer(
            theme,
            item_name=name,
            features=feats,
            price=price,
            brand="Lakeview Burgers & Seafood",
            cta="Order Now · Mon-Sat 11-9",
            food_image_path=food,
        )
        dt = (time.perf_counter() - t0) * 1000
        with open(out_path, "wb") as f:
            f.write(png)
        print(f"  rendered {theme:8s} {name:25s} → {out_path}  ({dt:.0f} ms, {len(png)//1024} KB)")
    shutdown()


if __name__ == "__main__":
    main()
