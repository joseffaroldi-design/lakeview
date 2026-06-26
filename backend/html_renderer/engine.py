"""HTML/CSS flyer rendering engine (Sprint 20A, post-PIL pivot).

Renders flyers by hydrating a Jinja2 HTML template + CSS and shooting it
with a headless Chromium browser via Playwright. Produces a 2048×2048
PNG (4× retina, print-ready) which we then resize down to 1024×1024 PNG
for the public flyer endpoint — preserves crisp text/edges that the
procedural PIL engine cannot achieve.

Why HTML/CSS:
    * Real Google-quality typography (Playfair Display, Cinzel, Oswald,
      Inter) with proper kerning, ligatures, and CSS letter-spacing.
    * Flexbox / grid for layout — no slot-coordinate maths.
    * SVG decorative accents (gold rules, badges, ornaments) crisp at
      any resolution.
    * Designers can iterate on a template by editing CSS, with no Python
      restart and no PIL knowledge required.

Public surface:
    render_flyer(theme, *, item_name, features, price, brand, cta,
                 food_image_path=None, food_image_url=None) -> bytes (PNG)
    is_supported(theme) -> bool
    SUPPORTED_THEMES: list[str]
"""
from __future__ import annotations

import base64
import io
import os
import threading
from pathlib import Path
from typing import Iterable, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
TEMPLATES = ROOT / "templates"
FONTS_DIR = ROOT / "fonts"

# Cajun + Luxury are the launch themes for the HTML renderer. Every
# other theme continues to flow through the PIL/agency renderer.
SUPPORTED_THEMES = ["cajun", "luxury", "cajun_blackened", "luxury_dark"]


def is_supported(theme: str) -> bool:
    if not theme:
        return False
    t = theme.strip().lower()
    if t in SUPPORTED_THEMES:
        return True
    return any(t.startswith(s) for s in ("cajun", "luxury"))


# -------------------------------------------------------------- jinja env
_jinja = Environment(
    loader=FileSystemLoader(str(TEMPLATES)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _font_face_block() -> str:
    """Emit @font-face declarations referencing the locally bundled
    .ttf files via base64 data URLs — this is the most reliable way to
    guarantee the headless browser has the fonts before rendering."""
    families = [
        ("Playfair Display", "PlayfairDisplay-Bold.ttf"),
        ("Cinzel", "Cinzel-Bold.ttf"),
        ("Oswald", "Oswald-Bold.ttf"),
        ("Inter", "Inter-Regular.ttf"),
        ("Bebas Neue", "BebasNeue-Regular.ttf"),
    ]
    out = []
    for fam, fn in families:
        p = FONTS_DIR / fn
        if not p.exists():
            continue
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        out.append(
            f"@font-face {{ font-family: '{fam}'; font-style: normal; "
            f"font-weight: 100 900; "
            f"src: url(data:font/ttf;base64,{data}) format('truetype'); }}"
        )
    return "\n".join(out)


_FONT_FACE_BLOCK = _font_face_block()


def _food_image_data_url(path: Optional[str], url: Optional[str]) -> str:
    """Inline the food image as a data URL — eliminates any cross-origin
    / file-protocol concerns inside the headless browser."""
    if url and (url.startswith("http://") or url.startswith("https://")):
        return url
    if path and os.path.exists(path):
        try:
            ext = os.path.splitext(path)[1].lower().lstrip(".") or "jpeg"
            if ext == "jpg":
                ext = "jpeg"
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            return f"data:image/{ext};base64,{data}"
        except OSError:
            pass
    # Tiny transparent placeholder
    return ("data:image/svg+xml;base64,"
            + base64.b64encode(
                b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
                b'<rect width="100" height="100" fill="#222"/></svg>'
            ).decode("ascii"))


def _resolve_template(theme: str) -> str:
    t = (theme or "").strip().lower()
    if t.startswith("luxury") or t == "luxury_dark":
        return "luxury.html"
    return "cajun.html"  # default for the cajun family


# ---------------------------------------------- playwright singleton

_PW_LOCK = threading.Lock()
_PW = None  # type: ignore
_BROWSER = None  # type: ignore


def _ensure_browser():
    """Lazily start a long-lived headless Chromium. Reused across renders
    to avoid the ~600ms cold-start cost."""
    global _PW, _BROWSER
    with _PW_LOCK:
        if _BROWSER is not None:
            try:
                # Probe — if browser died, restart it.
                _ = _BROWSER.contexts
                return _BROWSER
            except Exception:  # noqa: BLE001
                _BROWSER = None
                _PW = None
        _PW = sync_playwright().start()
        _BROWSER = _PW.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        return _BROWSER


def shutdown() -> None:
    """For tests / clean shutdown."""
    global _PW, _BROWSER
    with _PW_LOCK:
        try:
            if _BROWSER is not None:
                _BROWSER.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if _PW is not None:
                _PW.stop()
        except Exception:  # noqa: BLE001
            pass
        _BROWSER = None
        _PW = None


# ---------------------------------------------- public render API

def render_flyer(
    theme: str,
    *,
    item_name: str,
    features: Iterable[str] = (),
    price: str = "",
    brand: str = "Lakeview Burgers & Seafood",
    cta: str = "Order Now · Mon-Sat 11-9",
    food_image_path: Optional[str] = None,
    food_image_url: Optional[str] = None,
    output_size: int = 1024,
    render_size: int = 2048,
    return_format: str = "PNG",
) -> bytes:
    """Render a flyer to bytes.

    `render_size` is the internal browser viewport (default 2048 → 4×
    retina); we downscale to `output_size` (default 1024) using PIL's
    LANCZOS to preserve sharpness.
    """
    feats: List[str] = [str(f) for f in features if f]
    template_name = _resolve_template(theme)
    template = _jinja.get_template(template_name)
    html = template.render(
        item_name=item_name or "",
        features=feats,
        price=price or "",
        brand=brand or "",
        cta=cta or "",
        food_image=_food_image_data_url(food_image_path, food_image_url),
        font_face_block=_FONT_FACE_BLOCK,
        theme=(theme or "").lower(),
    )

    browser = _ensure_browser()
    context = browser.new_context(
        viewport={"width": render_size, "height": render_size},
        device_scale_factor=1.0,
    )
    try:
        page = context.new_page()
        page.set_content(html, wait_until="load", timeout=15_000)
        # Wait until fonts are loaded (CSS Font Loading API)
        page.evaluate("document.fonts.ready")
        png_bytes = page.screenshot(
            type="png",
            full_page=False,
            clip={"x": 0, "y": 0, "width": render_size, "height": render_size},
            omit_background=False,
        )
    finally:
        context.close()

    # Downscale 2048 → 1024 with LANCZOS for crisp output.
    if output_size != render_size:
        im = Image.open(io.BytesIO(png_bytes))
        im = im.resize((output_size, output_size), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, format=return_format)
        return out.getvalue()
    return png_bytes


__all__ = [
    "SUPPORTED_THEMES",
    "is_supported",
    "render_flyer",
    "shutdown",
]
