"""
Renderer — Composition Orchestration

Tech Debt Sprint Step 6 / Chunk 9.

This module orchestrates the full flyer rendering pipeline. It owns the
decision tree between the three render paths:
  1. HTML/CSS renderer (cajun + luxury themes)
  2. Agency template renderer (any theme with a matching manifest)
  3. Procedural fallback (iterative compose_layered_with_score)

It depends on:
  * ai_designer.composition  — drawing primitives + helpers
  * ai_designer.registries.themes, .layouts — registries
  * agency_templates / agency_renderer — agency template engine
  * html_renderer — headless-browser engine
  * render_engine — procedural fallback engine
  * typography_engine — badge/title style helpers
  * logo_renderer / flyer_config — Priority 4.1 logo overlay

It does NOT depend on:
  * FastAPI
  * Mongo / media writes
  * Storage / object store
  * Job orchestration / async polling
  * Request/response objects
"""
from __future__ import annotations

import io
import logging
import os
import random
import tempfile
import threading
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from ai_designer.composition import (
    _variant_food_transform,
    _draw_title,
    _draw_bullets,
    _draw_price_badge,
    _draw_branding as _composition_draw_branding,
)
from ai_designer.registries.layouts import get_canvas_size
from ai_designer.registries.themes import THEME_STYLES
from ai_designer.utils import FONT_SANS_BOLD

logger = logging.getLogger("uvicorn.error")


# ─── Sprint 22D Option B — Chromium-presence guard ────────────────────
#
# Production crashed during Luxury/Cajun renders because Playwright's
# expected Chromium binary was missing (revision mismatch between the
# installed `chromium_headless_shell-1208` and the `-1223` Playwright
# 1.60 expects). Each render attempt re-spawned the worker thread,
# re-tried `chromium.launch()`, and leaked enough resources to OOM-kill
# the container — taking the whole site down for ~60-90s per attempt.
#
# This guard checks ONCE (cached) whether the Chromium headless_shell
# binary actually exists on disk. We rely on Playwright's own
# `executable_path` PROPERTY (no subprocess, no launch) to learn the
# expected location, then check the file system. If it's missing,
# every render falls through to the PIL agency/procedural path. No
# launch attempt, no leaked subprocess, no container restart.
#
# The check is single-call cached for the lifetime of the process via
# `_chromium_lock`; concurrent calls during the first probe are safe.

_chromium_lock = threading.Lock()
_chromium_available: Optional[bool] = None


def _is_chromium_available() -> bool:
    """Return True iff Playwright Chromium headless shell is installed.

    Cached for the lifetime of the process. Uses Playwright's
    `executable_path` PROPERTY (no subprocess, no launch) to determine
    the expected binary path, then performs a single os.path.exists().
    Returns False on any error — fail-closed so a broken Playwright
    install never blocks the PIL fallback.
    """
    global _chromium_available
    if _chromium_available is not None:
        return _chromium_available
    with _chromium_lock:
        if _chromium_available is not None:
            return _chromium_available
        try:
            from playwright.sync_api import sync_playwright

            pw = sync_playwright().start()
            try:
                # Property — does not launch the browser.
                expected = pw.chromium.executable_path
            finally:
                try:
                    pw.stop()
                except Exception:  # noqa: BLE001
                    pass
            # html_renderer launches headless=True which requires
            # `chromium_headless_shell-<rev>/chrome-linux/headless_shell`,
            # not the full chrome binary. Derive it from `expected`:
            #   /pw-browsers/chromium-1223/chrome-linux/chrome
            #   -> /pw-browsers/chromium_headless_shell-1223/chrome-linux/headless_shell
            derived = expected.replace(
                "/chromium-", "/chromium_headless_shell-", 1
            )
            shell_path = os.path.join(os.path.dirname(derived), "headless_shell")
            ok = os.path.exists(shell_path)
            if not ok:
                logger.warning(
                    "[ai_designer] Playwright Chromium headless shell missing "
                    f"at {shell_path!r}; HTML/CSS renderer disabled for this "
                    "process — Cajun + Luxury jobs will silently fall back to "
                    "the PIL agency/procedural renderer. Run "
                    "`playwright install chromium` to restore HTML rendering."
                )
            _chromium_available = bool(ok)
            return _chromium_available
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "[ai_designer] Could not probe Playwright Chromium "
                f"availability ({type(e).__name__}: {e}); HTML renderer "
                "disabled. PIL fallback still active."
            )
            _chromium_available = False
            return False


def compose_design(
    bg_bytes: bytes,
    food_rgba: Image.Image,
    item_name: str,
    features: List[str],
    price: Optional[str],
    theme_id: str,
    layout: str,
    variant_idx: int = 0,
    cta: Optional[str] = None,
    include_price: bool = True,
    include_description: bool = True,
    platform: str = "instagram_post",
    tone: Optional[str] = None,
    logo_url: Optional[str] = None,
    logo_placement: Optional[str] = None,
    logo_size: Optional[str] = None,
    *,
    branding_text: Optional[str] = None,
) -> Tuple[bytes, Dict[str, Any]]:
    """Composite the final marketing graphic.

    Chunk 9: moved verbatim from routers/ai_designer.py._compose_design.
    Behavior, score envelopes, fallback ordering, and logo-overlay path
    are all unchanged. The only signature change is the new optional
    keyword-only `branding_text` argument: if omitted, the value falls
    back to the `AI_DESIGNER_BRAND` env var or the default Lakeview brand
    string — matching the original router-local constant exactly.
    """
    if branding_text is None:
        branding_text = os.environ.get("AI_DESIGNER_BRAND", "LAKEVIEW BURGERS & SEAFOOD")

    # Sprint 22 P0 Fix 2 — per-variant food treatment. Applied ONCE here so
    # every downstream renderer (HTML, agency template, procedural) inherits
    # the variation without needing path-specific logic. v0 returns a copy.
    food_rgba = _variant_food_transform(food_rgba, variant_idx)

    # ---- Sprint 20A: HTML/CSS rendering for Cajun + Luxury themes ----
    # Sprint 22D Option B: only attempt the HTML path if Chromium is
    # actually installed. The cached check is a single os.path.exists()
    # and never invokes Playwright launch — so a missing browser can
    # no longer crash the container.
    try:
        import html_renderer as _html
        if _html.is_supported(theme_id) and _is_chromium_available():
            food_rgb = food_rgba.convert("RGB")
            with tempfile.NamedTemporaryFile(
                suffix=".jpg", delete=False, prefix="htmlflyer_food_"
            ) as tf:
                food_rgb.save(tf.name, "JPEG", quality=92)
                food_path = tf.name
            try:
                canvas_w, canvas_h = get_canvas_size(platform)
                actual_cta = (cta or "").strip() or "Order Now · Mon-Sat 11-9"
                render_w = canvas_w * 2
                render_h = canvas_h * 2
                png_bytes = _html.render_flyer(
                    theme_id,
                    item_name=item_name or "",
                    features=features if include_description else [],
                    price=(price or "").strip() if include_price else "",
                    brand=branding_text,
                    cta=actual_cta,
                    food_image_path=food_path,
                    output_width=canvas_w,
                    output_height=canvas_h,
                    render_width=render_w,
                    render_height=render_h,
                )
            finally:
                try:
                    os.unlink(food_path)
                except OSError:
                    pass
            score = {
                "total": 92.0,
                "label": "Excellent",
                "rank": "excellent",
                "render_path": "html_css",
                "template_id": f"html_{theme_id}",
                "template_label": f"HTML/CSS {theme_id.title()}",
                "metrics": {},
            }
            return png_bytes, score
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"[ai_designer] HTML renderer failed for theme={theme_id!r}: {e!r} — falling back to agency/procedural"
        )

    # ---- Sprint 20 Phase 0: agency template fast path ----
    try:
        import agency_templates as _at
        from agency_renderer import compose_with_template

        tmpl = _at.pick_template_for(category=None, theme_hint=theme_id)
        # Priority 3 platform-sizing fix (Feb 2026): skip agency template
        # if its fixed canvas != the requested platform canvas.
        requested_canvas = get_canvas_size(platform)
        if tmpl is not None and tmpl.canvas != requested_canvas:
            logger.info(
                f"[ai_designer] platform={platform} canvas={requested_canvas} "
                f"!= template.canvas={tmpl.canvas} — skipping agency template "
                f"for theme={theme_id!r}, using procedural fallback."
            )
            tmpl = None
        if tmpl is not None:
            actual_features = features if include_description else []
            actual_price = (price or "").strip() if include_price else ""
            actual_cta = (cta or "").strip() or "LIMITED-TIME SPECIAL"
            agency_canvas = compose_with_template(
                tmpl,
                food_rgba=food_rgba,
                item_name=item_name or "",
                features=actual_features,
                price=actual_price,
                brand=branding_text,
                cta=actual_cta,
            )
            out = io.BytesIO()
            agency_canvas.convert("RGB").save(out, "PNG", optimize=True)
            score = {
                "total": 88.0,
                "label": "Very Good",
                "rank": "very_good",
                "render_path": "agency_template",
                "template_id": tmpl.id,
                "template_label": tmpl.label,
                "metrics": {},
            }
            return out.getvalue(), score
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"[ai_designer] agency template render failed for theme={theme_id!r}: {e!r} — falling back to procedural"
        )

    # ---- Procedural fallback (Sprint 18 iterative composer) ----
    from render_engine import compose_layered_with_score, LEGACY_LAYOUT_ALIAS
    from typography_engine import pick_badge_style

    canvas_w, canvas_h = get_canvas_size(platform)

    theme = THEME_STYLES[theme_id]
    bg = Image.open(io.BytesIO(bg_bytes)).convert("RGB")
    if bg.size != (canvas_w, canvas_h):
        bg = bg.resize((canvas_w, canvas_h), Image.LANCZOS)

    legacy_to_variant = {"centered": 0, "asym_left": 1, "stacked": 2}
    # Sprint 22 P0 Fix 2 — prefer explicit `variant_idx`; fall back to legacy
    # layout-name → variant_idx mapping.
    derived_variant = legacy_to_variant.get(layout, 0)
    variant_idx = variant_idx if variant_idx else derived_variant
    layout_override = None
    if layout in LEGACY_LAYOUT_ALIAS:
        layout_override = LEGACY_LAYOUT_ALIAS[layout]

    theme = dict(theme)
    theme["_theme_id"] = theme_id
    theme["_variant_idx"] = variant_idx

    # Phase 3: Diversity Engine — per-variant randomization
    variant_rng = random.Random(hash((theme_id, variant_idx)) & 0xFFFFFFFF)

    # Vary color intensity per variant (±10%)
    if "title" in theme and "color" in theme["title"]:
        title_color = theme["title"]["color"]
        if isinstance(title_color, (tuple, list)) and len(title_color) >= 3:
            intensity_factor = 1.0 + (variant_idx - 1) * 0.1  # v0: 0.9, v1: 1.0, v2: 1.1
            theme["title"]["color"] = tuple(
                min(255, max(0, int(c * intensity_factor))) for c in title_color[:3]
            ) + (title_color[3:] if len(title_color) > 3 else ())

    # Vary badge style per variant
    if not theme.get("badge_style"):
        theme["_badge_style"] = pick_badge_style(
            theme_id, variant_idx, personality=theme.get("personality"))

    # Vary typography size slightly per variant (±5%)
    if "title" in theme and "size" in theme["title"]:
        base_size = theme["title"]["size"]
        size_variation = variant_rng.choice([-5, 0, 5])
        theme["title"]["size"] = max(40, base_size + size_variation)

    if "body" in theme and "size" in theme["body"]:
        base_body_size = theme["body"]["size"]
        body_variation = variant_rng.choice([-2, 0, 2])
        theme["body"]["size"] = max(16, base_body_size + body_variation)

    actual_price = price if include_price else None
    actual_features = features if include_description else []

    # Inject branding_text + font into the closure so compose_layered_with_score's
    # `draw_branding` callback gets the right env-driven brand string. The
    # downstream `render_engine` expects a `(canvas, theme)` signature, matching
    # the historical router behavior.
    def _branding_callback(canvas: Image.Image, theme_dict: Dict[str, Any]) -> None:
        _composition_draw_branding(
            canvas, theme_dict,
            branding_text=branding_text,
            font_path=FONT_SANS_BOLD,
            canvas_size=canvas_w,
        )

    canvas, score = compose_layered_with_score(
        bg_image=bg,
        food_rgba=food_rgba,
        theme=theme,
        theme_id=theme_id,
        variant_idx=variant_idx,
        draw_title=_draw_title,
        draw_bullets=_draw_bullets,
        draw_price_badge=_draw_price_badge,
        draw_branding=_branding_callback,
        item_name=item_name,
        features=actual_features,
        price=actual_price,
        layout_override=layout_override,
        cta=cta,
        canvas_size=(canvas_w, canvas_h),
        target_score=80.0,
        max_iterations=2,
    )
    out = io.BytesIO()
    canvas.convert("RGB").save(out, "PNG", optimize=True)
    png_bytes = out.getvalue()

    # Priority 4.1: Apply logo if requested
    if logo_url and logo_placement and logo_placement != "none":
        try:
            from logo_renderer import apply_logo_to_flyer
            from flyer_config import LogoPlacement, LogoSize

            canvas_with_logo = Image.open(io.BytesIO(png_bytes))
            placement = LogoPlacement(logo_placement)
            size = LogoSize(logo_size or "medium")
            canvas_with_logo = apply_logo_to_flyer(canvas_with_logo, logo_url, placement, size)

            out_with_logo = io.BytesIO()
            canvas_with_logo.convert("RGB").save(out_with_logo, "PNG", optimize=True)
            png_bytes = out_with_logo.getvalue()
            logger.info(f"[ai-designer] Logo applied: {placement.value} @ {size.value}")
        except Exception as e:
            logger.error(f"[ai-designer] Logo application failed: {e}", exc_info=True)
            # Continue with original image without logo

    return png_bytes, score


__all__ = ["compose_design"]
