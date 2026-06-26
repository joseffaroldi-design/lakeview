"""Live HTML template preview endpoint — Sprint 20A polish.

Lets a designer iterate on an `html_renderer` Jinja2 template by
hot-rendering the same template + a sample item payload at design time.
Returns a PNG byte stream so the frontend can simply `<img src=…>` the
result on every keystroke.

GET  /api/html-template/themes
        → list of supported themes the HTML engine knows about

POST /api/html-template/preview
        → render one flyer with the supplied item payload + theme.
          Body:
            { theme, item_name, features[], price, brand, cta,
              food_image_id? }
          Returns: PNG bytes (image/png)
"""
from __future__ import annotations

import asyncio
import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

import html_renderer as _html


router = APIRouter(prefix="/html-template", tags=["html-template"])


class PreviewBody(BaseModel):
    theme: str = Field(..., description="A supported HTML theme id (cajun, luxury, seafood, …)")
    item_name: str = ""
    features: List[str] = []
    price: str = ""
    brand: str = "Lakeview Burgers & Seafood"
    cta: str = "Order Now · Mon-Sat 11-9"
    food_image_path: Optional[str] = None
    output_size: int = 1024
    render_size: int = 2048


@router.get("/themes")
def list_themes():
    """Return the list of themes the HTML renderer currently supports.
    Used by the Template Designer UI to populate the theme dropdown."""
    return {
        "themes": _html.SUPPORTED_THEMES,
        "engine": "html_css",
        "note": (
            "Themes not in this list flow through the PIL/agency "
            "renderer at request time."
        ),
    }


def _resolve_food_path(provided: Optional[str]) -> Optional[str]:
    if provided and os.path.exists(provided):
        return provided
    media_dir = "/app/backend/media_storage"
    if not os.path.isdir(media_dir):
        return None
    candidates = []
    for fn in os.listdir(media_dir):
        if fn.endswith((".jpg", ".jpeg", ".png")):
            p = os.path.join(media_dir, fn)
            try:
                candidates.append((os.path.getsize(p), p))
            except OSError:
                continue
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _render_blocking(body: "PreviewBody", food_path: Optional[str]) -> bytes:
    return _html.render_flyer(
        body.theme,
        item_name=body.item_name,
        features=body.features,
        price=body.price,
        brand=body.brand,
        cta=body.cta,
        food_image_path=food_path,
        output_size=int(body.output_size),
        render_size=int(body.render_size),
    )


@router.post("/preview")
async def preview(body: PreviewBody):
    """Hot-render one flyer through the HTML/CSS engine.

    `render_flyer` internally detects the running asyncio loop and
    offloads Playwright to a worker thread, but we still await it via
    `to_thread` so this request handler stays non-blocking."""
    if not _html.is_supported(body.theme):
        raise HTTPException(
            status_code=400,
            detail=(
                f"theme={body.theme!r} is not supported by the HTML "
                f"renderer. Supported: {_html.SUPPORTED_THEMES}"
            ),
        )

    food_path = _resolve_food_path(body.food_image_path)

    try:
        png = await asyncio.to_thread(_render_blocking, body, food_path)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"render failed: {e}")

    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "no-store"})
