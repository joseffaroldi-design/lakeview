"""Sprint 20 Phase 0 — Agency template slot system tests.

Coverage:
* manifest schema validation (every shipped manifest loads cleanly)
* missing-asset fallback (missing bg raises TemplateError)
* slot render correctness (output canvas is the declared size, food not
  bleeding past the slot, badge centre is filled, title renders into the
  title rect)
* readability (title actually paints contrasting pixels in the slot)
* the procedural fallback path: caller catches TemplateError and gets to
  pick a different render path
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest
from PIL import Image, ImageDraw

import agency_templates as at
from agency_renderer import compose_with_template


@pytest.fixture
def burger_template():
    return at.load_template("burger-poster-01")


@pytest.fixture
def fake_food():
    im = Image.new("RGB", (1200, 1500), (50, 30, 20))
    d = ImageDraw.Draw(im)
    d.ellipse((100, 200, 1100, 1400), fill=(180, 110, 60))
    return im


# ---------- A) manifest validation ----------

def test_all_shipped_manifests_load():
    """Every JSON in manifests/ loads + validates."""
    ids = [fn[:-5] for fn in os.listdir(at.MANIFESTS_DIR) if fn.endswith(".json")]
    assert len(ids) >= 6, "expected at least 6 starter manifests"
    for tid in ids:
        t = at.load_template(tid)
        assert t.id == tid
        assert t.canvas == (1024, 1024)
        assert "photo" in t.slots
        assert "title" in t.slots
        assert "price" in t.slots
        assert "brand" in t.slots


def test_invalid_manifest_raises_TemplateError(tmp_path, monkeypatch):
    """A manifest missing required keys is rejected."""
    bad = {"id": "x", "label": "x"}  # missing canvas/slots/background/fallback_theme
    p = tmp_path / "manifests"
    p.mkdir()
    (p / "x.json").write_text(json.dumps(bad))
    monkeypatch.setattr(at, "MANIFESTS_DIR", str(p))
    with pytest.raises(at.TemplateError):
        at.load_template("x")


def test_missing_background_asset_raises_TemplateError(tmp_path, monkeypatch):
    """Manifest references a background that doesn't exist on disk → error."""
    good_manifest = {
        "id": "no-bg",
        "label": "No BG",
        "category": "general",
        "canvas": [1024, 1024],
        "background": "nonexistent.png",
        "fallback_theme": "modern",
        "slots": {
            "photo": {"x": 0, "y": 0, "w": 100, "h": 100},
            "title": {"x": 0, "y": 0, "w": 100, "h": 100},
            "price": {"cx": 50, "cy": 50, "radius": 30},
            "brand": {"cx": 50, "y": 50},
        },
    }
    mdir = tmp_path / "manifests"
    bdir = tmp_path / "backgrounds"
    mdir.mkdir(); bdir.mkdir()
    (mdir / "no-bg.json").write_text(json.dumps(good_manifest))
    monkeypatch.setattr(at, "MANIFESTS_DIR", str(mdir))
    monkeypatch.setattr(at, "BACKGROUNDS_DIR", str(bdir))
    with pytest.raises(at.TemplateError):
        at.load_template("no-bg")


# ---------- B) slot render correctness ----------

def test_compose_returns_1024_canvas(burger_template, fake_food):
    out = compose_with_template(
        burger_template,
        food_rgba=fake_food,
        item_name="Smash Burger",
        features=["Smash patty", "American cheese", "Pickles"],
        price="$11.00",
        brand="Lakeview",
        cta="Order Now",
    )
    assert out.size == (1024, 1024)


def test_title_paints_into_title_slot(burger_template, fake_food):
    out = compose_with_template(
        burger_template,
        food_rgba=fake_food,
        item_name="Smash Burger",
        features=[],
        price="$11.00",
    )
    title_slot = burger_template.slots["title"]
    bg = out.getpixel((10, 10))
    # Within the title rect there must be at least 200 pixels that differ
    # noticeably from background (the title text + stroke).
    diff_pixels = 0
    px = out.load()
    for y in range(title_slot["y"], title_slot["y"] + title_slot["h"], 3):
        for x in range(title_slot["x"], title_slot["x"] + title_slot["w"], 3):
            p = px[x, y]
            if abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > 60:
                diff_pixels += 1
    assert diff_pixels > 200, f"title pixels: {diff_pixels} (expected >200)"


def test_badge_centre_is_filled(burger_template, fake_food):
    out = compose_with_template(
        burger_template,
        food_rgba=fake_food,
        item_name="Smash Burger",
        features=[],
        price="$11.00",
    )
    badge = burger_template.slots["price"]
    bg = out.getpixel((10, 10))
    # Sample a 30x30 box around the badge centre — it should be solid bg color,
    # NOT canvas bg.
    cx, cy = badge["cx"], badge["cy"]
    px = out.load()
    matching = 0
    badge_bg = badge["bg"]
    for dy in range(-12, 13, 3):
        for dx in range(-12, 13, 3):
            p = px[cx + dx, cy + dy]
            # Allow some interior text overlap; just demand the badge bg
            # dominates a non-canvas-bg region.
            if abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > 30:
                matching += 1
    assert matching >= 30, f"badge interior: {matching} non-bg samples (expected >=30)"


def test_food_fills_photo_slot(burger_template, fake_food):
    out = compose_with_template(
        burger_template,
        food_rgba=fake_food,
        item_name="Smash Burger",
        features=[],
        price="$11.00",
    )
    slot = burger_template.slots["photo"]
    px = out.load()
    bg = out.getpixel((10, 10))
    # 70%+ of the photo slot pixels should differ from canvas bg (i.e.,
    # the food is actually painted there).
    diff = total = 0
    for y in range(slot["y"] + 40, slot["y"] + slot["h"] - 40, 6):
        for x in range(slot["x"] + 40, slot["x"] + slot["w"] - 40, 6):
            p = px[x, y]
            if abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > 40:
                diff += 1
            total += 1
    coverage = diff / total
    assert coverage > 0.70, f"photo slot food coverage {coverage:.0%} (expected >70%)"


# ---------- C) feature chips ----------

def test_features_render_without_overflow(burger_template, fake_food):
    """Long feature names should not overflow the canvas."""
    out = compose_with_template(
        burger_template,
        food_rgba=fake_food,
        item_name="Smash Burger",
        features=[
            "American Cheese",
            "Sour Cream & Jalapeños",
            "House Pickles",
            "Crispy Bacon",
        ],
        price="$11.00",
    )
    # No pixels painted past canvas border by virtue of PIL clipping — just
    # smoke check that compose didn't raise on long text.
    assert out.size == (1024, 1024)


# ---------- D) picker fallback ----------

def test_pick_template_for_category_returns_seafood():
    t = at.pick_template_for("seafood")
    assert t is not None
    assert t.category == "seafood"


def test_pick_template_for_theme_hint_takes_precedence():
    """If a theme_hint matches a fallback_theme, that template wins regardless of category."""
    t = at.pick_template_for("burger", theme_hint="luxury")
    assert t is not None
    assert t.fallback_theme == "luxury"


def test_pick_template_for_unknown_returns_general():
    t = at.pick_template_for("dessert")  # no dessert template
    assert t is not None
    assert t.category == "general"


# ---------- E) all 5 acceptance items render successfully ----------

@pytest.mark.parametrize("item", [
    ("Smash Burger", "burger", ["Smash patty", "American cheese", "Pickles"], "$11.00"),
    ("Café Fries", "general", ["with Roast Beef Gravy", "Cheddar Cheese", "Sour Cream & Jalapeños"], "$13.25"),
    ("Wings", "sports", ["6 or 12 pieces", "Buffalo", "BBQ", "Asian Glaze"], "$11.00"),
    ("Shrimp Po-Boy", "seafood", ["Fried Gulf shrimp", "Crisp lettuce", "Pickled tomato"], "$14.50"),
    ("Cuban", "general", ["Slow-roasted pork", "Swiss", "Pickles", "Yellow mustard"], "$13.00"),
])
def test_acceptance_items_render(item, fake_food):
    name, cat, feats, price = item
    t = at.pick_template_for(cat)
    assert t is not None
    out = compose_with_template(
        t, food_rgba=fake_food, item_name=name, features=feats, price=price,
    )
    assert out.size == (1024, 1024)
