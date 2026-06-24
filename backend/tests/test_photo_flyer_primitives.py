"""Unit tests for the 3 Photo→Flyer primitives.

Sprint 16D Step 1 gate. No network calls, no live LLM, no live DB —
everything mocked/in-memory so the suite runs in milliseconds.
"""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest
from PIL import Image

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND))

from services.menu_matcher import match_food_to_menu  # noqa: E402
from services.photo_enhance import enhance_photo  # noqa: E402
from services.vision_client import (  # noqa: E402
    VALID_THEMES, _validate, analyze_food_photo,
)


def _run(coro):
    return asyncio.run(coro)


# ---------- photo_enhance --------------------------------------------------

def _make_photo(w=800, h=600, color=(200, 100, 60), seed: int = 0) -> bytes:
    """Photo with real visual features — gradient + patches. NOT solid color."""
    img = Image.new("RGB", (w, h), color)
    pixels = img.load()
    for x in range(0, w, 16):
        for y in range(0, h, 16):
            c = ((color[0] + (x * 3) % 50) % 256,
                 (color[1] + (y * 7) % 80) % 256,
                 (color[2] + (x + y + seed) % 100) % 256)
            for dx in range(16):
                for dy in range(16):
                    if x + dx < w and y + dy < h:
                        pixels[x + dx, y + dy] = c
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


class TestEnhancePhoto:
    def test_returns_jpeg_bytes(self):
        out, info = enhance_photo(_make_photo())
        assert isinstance(out, bytes) and len(out) > 1000
        # Re-open the output to confirm it's a valid JPEG
        Image.open(io.BytesIO(out)).verify()

    def test_preserves_mode_and_orientation(self):
        src = _make_photo(640, 480)
        out, info = enhance_photo(src)
        assert info["src_size"] == (640, 480)
        assert info["out_size"] == (640, 480)  # below cap
        out_img = Image.open(io.BytesIO(out))
        assert out_img.mode == "RGB"

    def test_caps_oversize_images(self):
        src = _make_photo(4000, 3000)
        out, info = enhance_photo(src, max_dim=2400)
        # Longest side must be ≤ max_dim
        assert max(info["out_size"]) == 2400, info

    def test_changes_pixels(self):
        """Enhancement must actually modify the image (autocontrast / sharpen
        produce different output than input)."""
        src = _make_photo()
        out, _ = enhance_photo(src)
        assert out != src, "enhancement was a no-op"

    def test_handles_non_rgb_input(self):
        """RGBA / L / CMYK photos should still come out as RGB JPEG."""
        img = Image.new("RGBA", (200, 200), (220, 110, 90, 255))
        for x in range(0, 200, 20):
            for y in range(0, 200, 20):
                img.putpixel((x, y), (50, 50, 50, 255))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        out, _ = enhance_photo(buf.getvalue())
        out_img = Image.open(io.BytesIO(out))
        assert out_img.mode == "RGB"


# ---------- vision_client._validate (pure function) ------------------------

class TestVisionValidate:
    def test_happy_path_passes_through(self):
        raw = {
            "food_type": "Smash Burger",
            "confidence": 0.94,
            "features": ["American Cheese", "Pickled Onions",
                         "House Aioli", "Comes With Fries"],
            "suggested_theme": "comic_pop",
            "dominant_colors": ["#cc4422", "#f5d56b", "#3a3a3a"],
        }
        out = _validate(raw)
        assert out["food_type"] == "Smash Burger"
        assert out["confidence"] == 0.94
        assert len(out["features"]) == 4
        assert out["suggested_theme"] == "comic_pop"
        assert out["dominant_colors"] == ["#cc4422", "#f5d56b", "#3a3a3a"]

    def test_clamps_confidence_out_of_range(self):
        assert _validate({"confidence": 1.5})["confidence"] == 1.0
        assert _validate({"confidence": -0.5})["confidence"] == 0.0
        assert _validate({"confidence": "nan"})["confidence"] == 0.0
        assert _validate({})["confidence"] == 0.0

    def test_caps_feature_count_and_strips_generic(self):
        raw = {"features": ["food", "meal", "Cheese", "Onions", "Bun",
                            "Pickles", "Aioli", "Sauce", "MORE"]}
        out = _validate(raw)
        assert "food" not in [f.lower() for f in out["features"]]
        assert "meal" not in [f.lower() for f in out["features"]]
        assert len(out["features"]) <= 6

    def test_feature_string_split(self):
        raw = {"features": "Cheese, Onions; Aioli\nFries"}
        out = _validate(raw)
        assert "Cheese" in out["features"]
        assert "Onions" in out["features"]
        assert "Aioli" in out["features"]
        assert "Fries" in out["features"]

    def test_invalid_theme_falls_back_to_comic_pop(self):
        out = _validate({"suggested_theme": "luxury_marble"})
        assert out["suggested_theme"] == "comic_pop"
        # All 5 valid themes accepted
        for t in VALID_THEMES:
            assert _validate({"suggested_theme": t})["suggested_theme"] == t

    def test_theme_normalisation(self):
        assert _validate({"suggested_theme": "BOLD-PURPLE-POP"})["suggested_theme"] == "bold_purple_pop"

    def test_dominant_colors_validation(self):
        out = _validate({"dominant_colors": ["#abcdef", "ffeedd", "not-a-color",
                                              "#123", "#aabbccdd"]})
        # Only #abcdef and ffeedd (normalised to #ffeedd) pass
        assert out["dominant_colors"] == ["#abcdef", "#ffeedd"]


# ---------- vision_client.analyze_food_photo (mocked LLM) ------------------

class _FakeBudgetExceeded(Exception):
    def __str__(self):
        return ("Failed to generate chat completion: litellm.BadRequestError: "
                "OpenAIException - Budget has been exceeded!")


class _FakeChat:
    """Stand-in for LlmChat — controls what send_message returns."""

    def __init__(self, raise_exc=None, response="{}", **_):
        self._raise = raise_exc
        self._response = response

    def with_model(self, *_args, **_kw):
        return self

    async def send_message(self, _msg):
        if self._raise:
            raise self._raise
        return self._response


class TestAnalyzeFoodPhoto:
    def test_happy_path(self, monkeypatch):
        ok_response = (
            '{"food_type":"Shrimp Taco","confidence":0.91,'
            '"features":["Shrimp","Lettuce","Cheese","Pico de Gallo"],'
            '"suggested_theme":"bold_purple_pop",'
            '"dominant_colors":["#cc4422","#fce889","#3a553a"]}'
        )
        import services.vision_client as vc

        def fake_chat_factory(**kwargs):
            return _FakeChat(response=ok_response)

        monkeypatch.setenv("EMERGENT_LLM_KEY", "fake-key")
        monkeypatch.setattr("emergentintegrations.llm.chat.LlmChat",
                            fake_chat_factory)

        result = _run(analyze_food_photo(_make_photo()))
        assert result["vision_ok"] is True
        assert result["food_type"] == "Shrimp Taco"
        assert "Shrimp" in result["features"]
        assert result["suggested_theme"] == "bold_purple_pop"

    def test_budget_exceeded_degrades_gracefully(self, monkeypatch):
        monkeypatch.setenv("EMERGENT_LLM_KEY", "fake-key")
        monkeypatch.setattr("emergentintegrations.llm.chat.LlmChat",
                            lambda **kw: _FakeChat(raise_exc=_FakeBudgetExceeded()))
        result = _run(analyze_food_photo(_make_photo()))
        assert result["vision_ok"] is False
        assert "budget" in result["error"].lower()
        # Safe defaults still present so the UI has a contract to render
        assert result["features"] == []
        assert result["suggested_theme"] in VALID_THEMES
        assert result["confidence"] == 0.0

    def test_bad_json_response_degrades(self, monkeypatch):
        monkeypatch.setenv("EMERGENT_LLM_KEY", "fake-key")
        monkeypatch.setattr("emergentintegrations.llm.chat.LlmChat",
                            lambda **kw: _FakeChat(response="i refuse to give json"))
        result = _run(analyze_food_photo(_make_photo()))
        assert result["vision_ok"] is False
        assert "json" in result["error"].lower()

    def test_missing_api_key_degrades(self, monkeypatch):
        monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
        result = _run(analyze_food_photo(_make_photo()))
        assert result["vision_ok"] is False
        assert "EMERGENT_LLM_KEY" in result["error"]

    def test_markdown_wrapped_json_is_extracted(self, monkeypatch):
        wrapped = ('```json\n{"food_type":"Burger","confidence":0.8,"features":'
                   '["Cheese"],"suggested_theme":"comic_pop","dominant_colors":["#aabbcc"]}\n```')
        monkeypatch.setenv("EMERGENT_LLM_KEY", "fake-key")
        monkeypatch.setattr("emergentintegrations.llm.chat.LlmChat",
                            lambda **kw: _FakeChat(response=wrapped))
        result = _run(analyze_food_photo(_make_photo()))
        assert result["vision_ok"] is True
        assert result["food_type"] == "Burger"


# ---------- menu_matcher ---------------------------------------------------

class _FakeCursor:
    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    def __aiter__(self):
        self._iter = iter(self._rows)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _FakeCollection:
    def __init__(self, rows: Optional[List[Dict[str, Any]]] = None,
                 raise_on_find: bool = False):
        self.rows = rows or []
        self.raise_on_find = raise_on_find

    def find(self, *_args, **_kwargs) -> _FakeCursor:
        if self.raise_on_find:
            raise RuntimeError("collection unavailable")
        return _FakeCursor([dict(r) for r in self.rows])


class _FakeDB:
    def __init__(self, menu_items=None, menu=None, menu_categories=None,
                 raise_menu_items=False, raise_menu=False):
        self.menu_items = _FakeCollection(menu_items, raise_menu_items)
        self.menu = _FakeCollection(menu, raise_menu)
        self.menu_categories = _FakeCollection(menu_categories)


class TestMenuMatcher:
    @pytest.fixture
    def db(self):
        return _FakeDB(menu_categories=[{
            "display_name": "Featured",
            "items": [
                {"name": "Smash Burger", "price": "$13.95",
                 "item_key": "burgers::smash-burger"},
                {"name": "Café Fries", "price": "$8.50"},
                {"name": "Shrimp Taco", "price": "$9.95",
                 "item_key": "tacos::shrimp-taco"},
                {"name": "Chicken Wings", "price": "$10.95"},
                {"name": "Fried Oyster Plate", "price": "$18.95"},
            ],
        }])

    def test_exact_match(self, db):
        out = _run(match_food_to_menu("Smash Burger", db))
        assert out["matched"] is True
        assert out["name"] == "Smash Burger"
        assert out["price"] == "$13.95"
        assert out["confidence"] == 1.0
        assert out["item_key"] == "burgers::smash-burger"

    def test_close_match(self, db):
        out = _run(match_food_to_menu("Shrimp Tacos", db))
        assert out["matched"] is True
        assert out["name"] == "Shrimp Taco"

    def test_loose_match_with_tokens(self, db):
        # AI returns "Fried Oysters" — should match "Fried Oyster Plate"
        out = _run(match_food_to_menu("Fried Oysters", db))
        assert out["matched"] is True
        assert out["name"] == "Fried Oyster Plate"

    def test_no_match_below_threshold(self, db):
        out = _run(match_food_to_menu("Tiramisu", db))
        assert out["matched"] is False
        assert out["price"] is None
        assert out["tried"] == 5

    def test_empty_food_type_returns_no_match(self, db):
        out = _run(match_food_to_menu("", db))
        assert out["matched"] is False

    def test_empty_db_returns_no_match(self):
        out = _run(match_food_to_menu("Smash Burger", _FakeDB(menu_items=[])))
        assert out["matched"] is False
        assert out["tried"] == 0

    def test_menu_items_collection_fails_falls_back_to_menu(self):
        """If menu_items.find raises, the matcher tries the legacy
        embedded `menu` collection."""
        db = _FakeDB(
            raise_menu_items=True,
            menu=[{
                "name": "Burgers",
                "items": [{"name": "Smash Burger", "price": "$13.95"}],
            }],
        )
        out = _run(match_food_to_menu("Smash Burger", db))
        assert out["matched"] is True
        assert out["name"] == "Smash Burger"

    def test_ambiguous_match_returns_no_match(self):
        """When two candidates are within 0.08 of each other, the matcher
        refuses to commit (prevents wrong-price autofill)."""
        db = _FakeDB(menu_items=[
            {"name": "Cheese Burger", "price": "$11.95"},
            {"name": "Chicken Burger", "price": "$10.95"},
        ])
        out = _run(match_food_to_menu("Burger", db))
        assert out["matched"] is False, out
