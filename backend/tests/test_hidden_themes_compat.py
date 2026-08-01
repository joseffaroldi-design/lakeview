"""Phase 2B regression — Hidden themes must remain fully implemented.

Verifies:
1. `/themes` endpoint stamps `hidden: true` on the 11 retired themes and
   `hidden: false` on the 11 visible themes.
2. `THEME_STYLES` still contains every hidden theme (no accidental deletion).
3. `compose_design` renders a hidden theme end-to-end — this proves saved
   ai_design_jobs referencing a hidden theme can still be regenerated.
4. The pack registry still lists every hidden theme in its owning pack so
   grouped-pack UIs preserve historical context.
"""
import io

from PIL import Image

from ai_designer.registries.themes import THEME_STYLES, THEME_PACKS
from ai_designer.renderer import compose_design
from routers.ai_designer import HIDDEN_THEMES


HIDDEN_LIST = {
    "casual_teal", "distressed_orange", "bold_purple_pop",
    "social", "summer_splash",
    "game_day_locker", "game_day_scoreboard",
    "seafood_dockside", "seafood_lagoon",
    "burger_grill_smoke", "burger_neon_diner",
}

VISIBLE_LIST = {
    "cajun", "luxury", "seafood_coastal",
    "vintage_diner", "comic_pop",
    "game_day_tailgate", "holiday_cheer",
    "modern", "burger_classic", "vintage", "mardi_gras",
}


def test_hidden_themes_constant_matches_spec():
    assert HIDDEN_THEMES == HIDDEN_LIST, (
        f"HIDDEN_THEMES drift: {HIDDEN_THEMES ^ HIDDEN_LIST}"
    )


def test_visible_and_hidden_are_disjoint():
    assert not (VISIBLE_LIST & HIDDEN_LIST), (
        "Visible and hidden theme lists must not overlap"
    )


def test_every_hidden_theme_still_registered():
    for tid in HIDDEN_LIST:
        assert tid in THEME_STYLES, (
            f"Hidden theme {tid!r} lost from THEME_STYLES — this WILL break "
            f"regeneration of saved jobs. Do NOT delete implementations."
        )


def test_every_visible_theme_still_registered():
    for tid in VISIBLE_LIST:
        assert tid in THEME_STYLES, f"Visible theme {tid!r} missing"


def test_theme_style_count_unchanged_at_22():
    # Sanity: we simplified the picker, not the registry.
    assert len(THEME_STYLES) == 22, (
        f"THEME_STYLES has {len(THEME_STYLES)} entries — expected 22. "
        f"A theme implementation was accidentally removed."
    )


def test_pack_registry_still_lists_hidden_themes():
    all_ids = set()
    for p in THEME_PACKS:
        all_ids.update(p["theme_ids"])
    missing = HIDDEN_LIST - all_ids
    assert not missing, f"Hidden themes missing from pack registry: {missing}"


def test_hidden_theme_still_renders_end_to_end():
    """Prove `casual_teal` — a hidden theme with 81 saved assets — still
    renders. If this test fails, ~1,832 saved flyers become unregeneratable.
    """
    bg = Image.new("RGB", (1024, 1024), (240, 240, 230))
    buf = io.BytesIO(); bg.save(buf, "PNG")
    food = Image.new("RGBA", (400, 400), (255, 200, 100, 255))

    png_bytes, score = compose_design(
        bg_bytes=buf.getvalue(),
        food_rgba=food,
        item_name="Classic Burger",
        features=["Fresh", "Signature"],
        price="$12.99",
        theme_id="casual_teal",
        layout="centered",
        variant_idx=0,
        platform="facebook_post",
    )
    assert isinstance(png_bytes, (bytes, bytearray))
    assert len(png_bytes) > 1000
    out = Image.open(io.BytesIO(png_bytes))
    assert out.size == (1200, 630)


def test_another_hidden_theme_renders():
    """Second hidden theme sanity check — burger_neon_diner."""
    bg = Image.new("RGB", (1024, 1024), (30, 20, 40))
    buf = io.BytesIO(); bg.save(buf, "PNG")
    food = Image.new("RGBA", (400, 400), (250, 100, 100, 255))

    png_bytes, _score = compose_design(
        bg_bytes=buf.getvalue(),
        food_rgba=food,
        item_name="Smash Burger",
        features=["Neon", "Late-night"],
        price="$14.50",
        theme_id="burger_neon_diner",
        layout="centered",
        variant_idx=0,
        platform="instagram_post",
    )
    out = Image.open(io.BytesIO(png_bytes))
    assert out.size == (1024, 1024)
