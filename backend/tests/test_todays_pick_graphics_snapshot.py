"""Item 4 (Feb 2026) — Snapshot regression tests for todays_pick graphics
compose path. Ensures the byte output of `_compose_simple_design` remains
stable across the Item 4 router-split refactor.

We seed `random.seed(...)` before every compose call because
`_generate_simple_background` uses `random.randint` for its texture dots.
Without seeding the output is non-deterministic and can't be snapshot-tested.

Snapshots are stored as SHA-256 hex digests in this file's SNAPSHOT_HASHES
map. If the refactor is truly behavior-preserving, no digest changes.
"""
import hashlib
import importlib
import io
import random
import sys

import pytest


LAYOUTS_TO_TEST = ["centered", "asym_left", "stacked"]

# Snapshot hashes captured against the pre-split router (todays_pick.py
# helpers still inline). Recomputing after the split MUST yield the same
# digests — that's the whole point.
#
# If you legitimately need to change these values (e.g., font substitution,
# canvas dimension change, theme tweak), regenerate this map by running:
#   pytest tests/test_todays_pick_graphics_snapshot.py::test_capture -v
# then paste the printed dict here.
SNAPSHOT_HASHES = {
    "centered|Gulf Shrimp Basket|18.00|99":   "418d08b1277dd663",
    "centered|Chef Special|None|1":           "7719872fc2834203",
    "centered|Signature Burger|14.50|7":      "56a4f9bcb94e135d",
    "centered|Test Dish|12.99|42":            "9faaa62e7cdc5cb4",
    "asym_left|Gulf Shrimp Basket|18.00|99":  "e301a10094046c9c",
    "asym_left|Chef Special|None|1":          "750c2d4ccafb190a",
    "asym_left|Signature Burger|14.50|7":     "ca5cd5ff48332a9f",
    "asym_left|Test Dish|12.99|42":           "19fb12842e92abe5",
    "stacked|Gulf Shrimp Basket|18.00|99":    "218f75ff59001fbd",
    "stacked|Chef Special|None|1":            "a2eee3ef72030c19",
    "stacked|Signature Burger|14.50|7":       "82604cc7c9a46abd",
    "stacked|Test Dish|12.99|42":             "b2a778126047d539",
}


@pytest.mark.parametrize("layout,name,price,seed,expected_prefix", [
    (layout, name, price, seed, SNAPSHOT_HASHES[f"{layout}|{name}|{price}|{seed}"])
    for layout in LAYOUTS_TO_TEST
    for name, price, seed in [
        ("Gulf Shrimp Basket", "18.00", 99),
        ("Chef Special", None, 1),
        ("Signature Burger", "14.50", 7),
        ("Test Dish", "12.99", 42),
    ]
])
def test_compose_snapshot_matches_prerefactor(compose_and_theme, layout, name, price, seed, expected_prefix):
    """The heart of Item 4: after the router split, the SHA-256 of the
    composed PNG bytes MUST match the pre-split baseline captured above.
    Any drift means a rendering regression."""
    compose, theme = compose_and_theme
    got = _sha256_of(compose, theme, name, price, layout, seed)
    assert got.startswith(expected_prefix), (
        f"Snapshot regression for layout={layout}, name={name!r}, price={price!r}, seed={seed}\n"
        f"  Expected prefix: {expected_prefix}\n"
        f"  Got:             {got[:16]}\n"
        f"  Full digest:     {got}"
    )


def _load_compose():
    """Import `_compose_simple_design` — post-split it may live in
    `services.todays_pick_graphics` or still in `routers.todays_pick`."""
    try:
        mod = importlib.import_module("services.todays_pick_graphics")
        return mod._compose_simple_design, mod
    except (ImportError, AttributeError):
        pass
    mod = importlib.import_module("routers.todays_pick")
    return mod._compose_simple_design, mod


@pytest.fixture(scope="module")
def compose_and_theme():
    compose, mod = _load_compose()
    theme = getattr(mod, "THEME", None)
    if theme is None:
        # fallback if THEME moved to graphics module
        mod2 = importlib.import_module("services.todays_pick_graphics")
        theme = mod2.THEME
    return compose, theme


def _sha256_of(compose, theme, item_name, price, layout, seed):
    random.seed(seed)
    png_bytes = compose(item_name, price, layout, theme)
    return hashlib.sha256(png_bytes).hexdigest()


@pytest.mark.parametrize("layout", LAYOUTS_TO_TEST)
def test_compose_returns_bytes(compose_and_theme, layout):
    compose, theme = compose_and_theme
    random.seed(42)
    result = compose("Test Dish", "12.99", layout, theme)
    assert isinstance(result, (bytes, bytearray))
    assert len(result) > 500
    # JPEG magic number
    assert result[:3] == b"\xff\xd8\xff"


@pytest.mark.parametrize("layout", LAYOUTS_TO_TEST)
def test_compose_dimensions(compose_and_theme, layout):
    """Sanity: output must be 1024x1024 as the caller (public Today's
    Featured card + Home page tile) expects."""
    from PIL import Image
    compose, theme = compose_and_theme
    random.seed(7)
    result = compose("Signature Burger", "14.50", layout, theme)
    img = Image.open(io.BytesIO(result))
    assert img.size == (1024, 1024), f"Expected 1024x1024, got {img.size}"


@pytest.mark.parametrize("layout", LAYOUTS_TO_TEST)
def test_compose_deterministic_with_seed(compose_and_theme, layout):
    """Same input + same seed => identical bytes. This is the property
    the router-split refactor must preserve."""
    compose, theme = compose_and_theme
    h1 = _sha256_of(compose, theme, "Gulf Shrimp Basket", "18.00", layout, seed=99)
    h2 = _sha256_of(compose, theme, "Gulf Shrimp Basket", "18.00", layout, seed=99)
    assert h1 == h2, (
        f"Non-deterministic output for layout={layout}. Same seed produced "
        f"different bytes. The refactor may have introduced a random source "
        f"not controlled by random.seed()."
    )


def test_compose_no_price(compose_and_theme):
    """Item name only, no price — must not raise."""
    compose, theme = compose_and_theme
    random.seed(1)
    result = compose("Chef's Special", None, "centered", theme)
    assert len(result) > 500
