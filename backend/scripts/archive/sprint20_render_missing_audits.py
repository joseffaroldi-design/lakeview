"""Sprint 20 Phase 0 — render the 2 agency templates that none of the 5
acceptance items mapped to (luxury-dark-01, bold-social-01), so the
template audit has direct visual samples for ALL 6 templates.

Outputs:
    /tmp/v2_luxury-dark.jpg
    /tmp/v2_bold-social.jpg
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

import agency_templates as at  # noqa: E402
from agency_renderer import compose_with_template  # noqa: E402


def _seed_food() -> Image.Image:
    """Pick the largest real food JPEG from media_storage as a stand-in
    hero asset. Falls back to a synthetic blob if no assets exist."""
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
    d = ImageDraw.Draw(im)
    d.ellipse((100, 200, 1100, 1400), fill=(180, 110, 60, 255))
    return im


SAMPLES = [
    ("luxury-dark-01", "Wagyu Filet Mignon",
     ["8oz prime cut", "House demi-glace", "Roasted shallots"], "$48.00", "luxury-dark"),
    ("bold-social-01", "Loaded Nachos",
     ["Pulled pork", "House queso", "Pickled jalapeños"], "$14.50", "bold-social"),
]


def main() -> None:
    food = _seed_food()
    for tid, name, features, price, slug in SAMPLES:
        t = at.load_template(tid)
        out = compose_with_template(
            t, food_rgba=food, item_name=name, features=features, price=price,
            brand="Lakeview Burgers & Seafood", cta="Order Now",
        )
        path = f"/tmp/v2_{slug}.jpg"
        out.convert("RGB").save(path, quality=92)
        print(f"  wrote {path}  ({t.label})")


if __name__ == "__main__":
    main()
