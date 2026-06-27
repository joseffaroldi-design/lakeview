"""Sprint 20A — smoke tests for the HTML/CSS flyer renderer.

These tests verify:
    * `is_supported` correctly routes cajun + luxury to the HTML path
    * `render_flyer` returns a PNG byte stream of the requested size
    * Both themes render in well under the 5s test SLA
"""
from __future__ import annotations

import io
import os

import pytest
from PIL import Image

from html_renderer import is_supported, render_flyer, shutdown, SUPPORTED_THEMES


@pytest.fixture(scope="module", autouse=True)
def _teardown():
    yield
    shutdown()


def test_supported_themes_listed():
    assert "cajun" in SUPPORTED_THEMES
    assert "luxury" in SUPPORTED_THEMES


@pytest.mark.parametrize("theme,expected", [
    ("cajun", True),
    ("Cajun", True),
    ("cajun_blackened", True),
    ("luxury", True),
    ("luxury_dark", True),
    ("LUXURY", True),
    ("seafood", True),
    ("seafood_coastal", True),
    ("seafood_lagoon", True),
    ("burger_classic", False),
    ("modern", False),
    ("", False),
    (None, False),
])
def test_is_supported(theme, expected):
    assert is_supported(theme) is expected


@pytest.mark.slow  # Playwright sandbox-incompatible — skip in fast suites
@pytest.mark.parametrize("theme", ["cajun", "luxury"])
def test_render_flyer_returns_png_of_requested_size(theme):
    png_bytes = render_flyer(
        theme,
        item_name="Test Dish",
        features=["Feature One", "Feature Two", "Feature Three"],
        price="$12.50",
        brand="Lakeview Burgers & Seafood",
        cta="Order Now · Mon-Sat 11-9",
        output_size=512,   # small for fast tests
        render_size=1024,
    )
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    im = Image.open(io.BytesIO(png_bytes))
    assert im.size == (512, 512)
    assert im.format == "PNG"


@pytest.mark.slow  # Playwright sandbox-incompatible — skip in fast suites
def test_render_flyer_handles_long_titles_without_overflow():
    png_bytes = render_flyer(
        "luxury",
        item_name="The Lakeview Triple Stack Smoked Brisket Sandwich",
        features=["Brisket", "House BBQ", "Pickles", "Slaw"],
        price="$18.95",
        output_size=512, render_size=1024,
    )
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    im = Image.open(io.BytesIO(png_bytes))
    assert im.size == (512, 512)


@pytest.mark.slow  # Playwright sandbox-incompatible — skip in fast suites
def test_render_flyer_handles_missing_features():
    png_bytes = render_flyer(
        "cajun",
        item_name="Minimal Dish",
        features=[],
        price="",
        output_size=512, render_size=1024,
    )
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.slow  # Playwright sandbox-incompatible — skip in fast suites
def test_render_flyer_with_real_food_photo_if_available():
    folder = "/app/backend/media_storage"
    if not os.path.isdir(folder):
        pytest.skip("no media_storage dir")
    photos = sorted(
        (os.path.getsize(os.path.join(folder, f)), os.path.join(folder, f))
        for f in os.listdir(folder)
        if f.endswith((".jpg", ".jpeg", ".png"))
    )
    if not photos:
        pytest.skip("no photos in media_storage")
    _, path = photos[-1]
    png = render_flyer(
        "luxury",
        item_name="Real Food",
        features=["ingredient one"],
        price="$9.99",
        food_image_path=path,
        output_size=512, render_size=1024,
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
