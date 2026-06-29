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
from typing import Any, Dict, Iterable, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
TEMPLATES = ROOT / "templates"
FONTS_DIR = ROOT / "fonts"

# Cajun + Luxury + Seafood are the launch themes for the HTML renderer.
# Every other theme continues to flow through the PIL/agency renderer.
SUPPORTED_THEMES = [
    "cajun", "luxury",
    "cajun_blackened", "luxury_dark",
    "seafood", "seafood_coastal", "seafood_lagoon",
]


def is_supported(theme: str) -> bool:
    if not theme:
        return False
    t = theme.strip().lower()
    if t in SUPPORTED_THEMES:
        return True
    return any(t.startswith(s) for s in ("cajun", "luxury", "seafood"))


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
    if t.startswith("seafood"):
        return "seafood.html"
    return "cajun.html"  # default for the cajun family


# ---------------------------------------------- playwright singleton
# Sync Playwright greenlets are bound to a single OS thread — we run a
# dedicated worker thread that owns the browser and consumes render jobs
# off a queue. This lets us serve renders from many request threads /
# asyncio loops without ever crossing the Playwright thread boundary.

import queue as _queue
import dataclasses
from concurrent.futures import Future

_PW_LOCK = threading.Lock()
_RENDER_QUEUE: "_queue.Queue[tuple[dict, Future[bytes]]]" = _queue.Queue()
_WORKER_THREAD: Optional[threading.Thread] = None


@dataclasses.dataclass
class _RenderJob:
    theme: str
    item_name: str
    features: List[str]
    price: str
    brand: str
    cta: str
    food_image_path: Optional[str]
    food_image_url: Optional[str]
    output_width: int
    output_height: int
    render_width: int
    render_height: int
    return_format: str
    # Sprint 22G — deterministic design-decision variation. Each lever is
    # an integer index into a per-template choice table (see luxury.html
    # / cajun.html). When the host supplies a `RenderContext`, the levers
    # are derived from `ctx.rng(...)`. Otherwise they default to 0 →
    # byte-identical to pre-22G output (snapshot regressions stay green).
    design_levers: Optional[Dict[str, int]] = None


def _worker_loop() -> None:
    """Owns the Playwright instance + browser for the process lifetime."""
    pw = sync_playwright().start()
    # Sprint 22K — prefer the host-supplied Chrome at /usr/bin/chromium
    # (declared via $PLAYWRIGHT_CHROME_EXECUTABLE_PATH) so HTML rendering
    # works on both preview and production without infra changes.
    launch_kwargs = {
        "headless": True,
        "args": ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
    }
    exe_path = (
        os.environ.get("PLAYWRIGHT_CHROME_EXECUTABLE_PATH")
        or os.environ.get("AGENT_BROWSER_EXECUTABLE_PATH")
    )
    if exe_path and os.path.exists(exe_path):
        launch_kwargs["executable_path"] = exe_path
    browser = pw.chromium.launch(**launch_kwargs)
    while True:
        job_dict, future = _RENDER_QUEUE.get()
        if job_dict is None:  # shutdown sentinel
            break
        try:
            png = _do_render(browser, _RenderJob(**job_dict))
            future.set_result(png)
        except Exception as e:  # noqa: BLE001
            future.set_exception(e)
    try:
        browser.close()
    except Exception:  # noqa: BLE001
        pass
    try:
        pw.stop()
    except Exception:  # noqa: BLE001
        pass


def _ensure_worker() -> None:
    """Lazily start the dedicated render worker thread."""
    global _WORKER_THREAD
    with _PW_LOCK:
        if _WORKER_THREAD is not None and _WORKER_THREAD.is_alive():
            return
        _WORKER_THREAD = threading.Thread(
            target=_worker_loop,
            name="html-renderer-worker",
            daemon=True,
        )
        _WORKER_THREAD.start()


def _do_render(browser, job: _RenderJob) -> bytes:
    """Runs in the worker thread — composes the HTML, screenshots,
    downscales."""
    feats: List[str] = [str(f) for f in job.features if f]
    template_name = _resolve_template(job.theme)
    template = _jinja.get_template(template_name)
    # Sprint 22G — pass design-decision levers to the template. Templates
    # consume them via small conditional blocks (alignment / side /
    # accent / kicker / brand-spacing). All levers default to 0 when
    # absent → byte-identical to pre-22G snapshot output.
    levers = job.design_levers or {}
    html = template.render(
        item_name=job.item_name or "",
        features=feats,
        price=job.price or "",
        brand=job.brand or "",
        cta=job.cta or "",
        food_image=_food_image_data_url(job.food_image_path, job.food_image_url),
        font_face_block=_FONT_FACE_BLOCK,
        theme=(job.theme or "").lower(),
        lever_title_align=int(levers.get("title_align", 0)),
        lever_features_side=int(levers.get("features_side", 0)),
        lever_kicker=int(levers.get("kicker", 0)),
        lever_accent=int(levers.get("accent", 0)),
        lever_brand_spacing=int(levers.get("brand_spacing", 0)),
        lever_corner_style=int(levers.get("corner_style", 0)),
        lever_archetype=int(levers.get("archetype", 0)),
    )

    context = browser.new_context(
        viewport={"width": job.render_width, "height": job.render_height},
        device_scale_factor=1.0,
    )
    try:
        page = context.new_page()
        page.set_content(html, wait_until="load", timeout=15_000)
        page.evaluate("document.fonts.ready")
        png_bytes = page.screenshot(
            type="png",
            full_page=False,
            clip={"x": 0, "y": 0, "width": job.render_width, "height": job.render_height},
            omit_background=False,
        )
    finally:
        context.close()

    if job.output_width != job.render_width or job.output_height != job.render_height:
        im = Image.open(io.BytesIO(png_bytes))
        im = im.resize((job.output_width, job.output_height), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, format=job.return_format)
        return out.getvalue()
    return png_bytes


def _ensure_browser():
    """Legacy alias kept for backwards-compat; ensures the worker is up."""
    _ensure_worker()
    return None


def shutdown() -> None:
    """For tests / clean shutdown."""
    global _WORKER_THREAD
    with _PW_LOCK:
        if _WORKER_THREAD is not None and _WORKER_THREAD.is_alive():
            try:
                _RENDER_QUEUE.put((None, Future()))
            except Exception:  # noqa: BLE001
                pass
            _WORKER_THREAD.join(timeout=5)
        _WORKER_THREAD = None


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
    output_width: int = 1024,
    output_height: int = 1024,
    render_width: int = 2048,
    render_height: int = 2048,
    return_format: str = "PNG",
    ctx: Any = None,
) -> bytes:
    """Render a flyer to bytes.

    Submits the job to the dedicated Playwright worker thread and
    blocks until the rendered PNG is returned. Safe to call from any
    thread (sync code, asyncio handlers, pytest, etc.).
    
    Supports non-square dimensions for different platforms.

    Sprint 22G — variation diversity:
    Pass a `RenderContext` to drive deterministic design-decision
    variation (title alignment, features side, kicker label, accent
    shift, brand letter-spacing, plaque corner style). Each `ctx` lever
    is salted independently so a new `job_nonce` perturbs every choice
    while the same `(job_nonce, variant_index)` reproduces byte-for-byte.
    """
    _ensure_worker()
    fut: Future = Future()
    design_levers: Optional[Dict[str, int]] = None
    if ctx is not None and hasattr(ctx, "rng"):
        # Each design choice gets an independent RNG salt so changes to
        # one lever's range don't perturb the others (Sprint 22G principle).
        # Sprint 22I — also derives a structural `archetype` (0/1/2) from
        # variant_index so within-job A/B/C take 3 different layouts.
        design_levers = {
            "title_align":    ctx.rng("html_title_align").randrange(2),
            "features_side":  ctx.rng("html_features_side").randrange(2),
            "kicker":         ctx.rng("html_kicker").randrange(4),
            "accent":         ctx.rng("html_accent").randrange(3),
            "brand_spacing":  ctx.rng("html_brand_spacing").randrange(3),
            "corner_style":   ctx.rng("html_corner_style").randrange(3),
            "archetype":      int(getattr(ctx, "variant_index", 0)) % 3,
        }
    job_dict = {
        "theme": theme,
        "item_name": item_name,
        "features": list(features),
        "price": price,
        "brand": brand,
        "cta": cta,
        "food_image_path": food_image_path,
        "food_image_url": food_image_url,
        "output_width": int(output_width),
        "output_height": int(output_height),
        "render_width": int(render_width),
        "render_height": int(render_height),
        "return_format": return_format,
        "design_levers": design_levers,
    }
    _RENDER_QUEUE.put((job_dict, fut))
    return fut.result(timeout=30)


__all__ = [
    "SUPPORTED_THEMES",
    "is_supported",
    "render_flyer",
    "shutdown",
]
