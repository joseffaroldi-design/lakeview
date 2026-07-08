"""Regression guard for platform canvas sizes.

Feb 2026: `facebook_post` used to silently fall back to (1024, 1024)
because the key did not exist. Ensure the fixed sizes stay pinned.
"""
from ai_designer.registries.layouts import PLATFORM_SIZES, get_canvas_size


def test_facebook_post_is_landscape_1200x630():
    assert get_canvas_size("facebook_post") == (1200, 630)
    assert get_canvas_size("facebook_landscape") == (1200, 630)


def test_facebook_feed_and_legacy_are_square_1200x1200():
    assert get_canvas_size("facebook_feed") == (1200, 1200)
    # Legacy alias kept to preserve historical output for saved jobs.
    assert get_canvas_size("facebook") == (1200, 1200)


def test_other_platform_sizes_unchanged():
    assert get_canvas_size("instagram_post") == (1024, 1024)
    assert get_canvas_size("instagram_story") == (1080, 1920)
    assert get_canvas_size("tiktok") == (1080, 1920)
    assert get_canvas_size("twitter") == (1200, 675)
    assert get_canvas_size("email") == (600, 600)


def test_unknown_platform_defaults_to_instagram_square():
    assert get_canvas_size("does_not_exist") == (1024, 1024)


def test_no_duplicate_dimensions_across_facebook_variants():
    # Every declared FB key must resolve to a known FB dimension.
    fb_keys = [k for k in PLATFORM_SIZES if k.startswith("facebook")]
    assert set(fb_keys) == {
        "facebook",
        "facebook_feed",
        "facebook_post",
        "facebook_landscape",
    }
    for k in fb_keys:
        assert PLATFORM_SIZES[k] in {(1200, 1200), (1200, 630)}
