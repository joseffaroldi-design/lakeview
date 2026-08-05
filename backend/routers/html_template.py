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

POST /api/html-template/bulk-render
        → kick off a background job that renders every menu item with
          the chosen theme. Returns a job_id.

GET  /api/html-template/bulk-render/{job_id}
        → poll the bulk-render job status (queued | running | done | failed)
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from pydantic import BaseModel, Field

import html_renderer as _html
from config import db
import storage as objstore


router = APIRouter(prefix="/html-template", tags=["html-template"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


# ---------------------------------------------------------------- bulk render

class BulkRenderBody(BaseModel):
    theme: str = Field(..., description="HTML theme to apply across the whole menu")
    limit: int = Field(default=50, ge=1, le=100)
    output_size: int = Field(default=1024)
    render_size: int = Field(default=2048)


def _flatten_menu_items(categories: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for cat in categories or []:
        for it in cat.get("items", []) or []:
            name = (it.get("name") or "").strip()
            if not name:
                continue
            price = it.get("price")
            price_str = (
                f"${price:.2f}" if isinstance(price, (int, float))
                else (price or "")
            )
            # Build feature chips out of the description — split on common
            # delimiters and keep the first 3 short phrases.
            desc = (it.get("description") or "").strip()
            chunks: List[str] = []
            for sep in ["·", "•", "|", "/", ","]:
                if sep in desc:
                    chunks = [c.strip().strip(".") for c in desc.split(sep)]
                    break
            if not chunks and desc:
                # No delimiter — split on ' and ' / first 2 sentences
                chunks = [s.strip() for s in desc.replace(" and ", ", ").split(",")]
            features = [c for c in (chunks or [desc])[:3] if c]
            out.append({
                "name": name,
                "category": cat.get("display_name") or cat.get("name") or "",
                "price": price_str,
                "features": features,
            })
            if len(out) >= limit:
                return out
    return out


async def _run_bulk_render(job_id: str, body: BulkRenderBody) -> None:
    async def update(**fields: Any) -> None:
        fields["updated_at"] = _now_iso()
        await db.html_bulk_jobs.update_one({"id": job_id}, {"$set": fields})

    categories = await db.menu_categories.find({}).sort("sort_order", 1).to_list(length=None)
    items = _flatten_menu_items(categories, body.limit)

    if not items:
        await update(status="failed", error="no menu items found")
        return

    food_path = _resolve_food_path(None)
    await update(status="running", total=len(items), completed=0, results=[])

    results: List[Dict[str, Any]] = []
    for idx, it in enumerate(items):
        t0 = time.perf_counter()
        try:
            png = await asyncio.to_thread(
                _html.render_flyer,
                body.theme,
                item_name=it["name"],
                features=it["features"],
                price=it["price"],
                brand="Lakeview Burgers & Seafood",
                cta="Order Now · Mon-Sat 11-9",
                food_image_path=food_path,
                output_size=body.output_size,
                render_size=body.render_size,
            )
            asset_id = str(uuid.uuid4())
            storage_path = objstore.make_path("html_bulk", asset_id, "png")
            await asyncio.to_thread(objstore.put_bytes, storage_path, png, "image/png")
            now = _now_iso()
            await db.media_assets.insert_one({
                "id": asset_id,
                "filename": f"{it['name']}.png",
                "kind": "image", "mime": "image/png",
                "size_bytes": len(png),
                "width": body.output_size, "height": body.output_size,
                "duration_seconds": None,
                "folder": "Bulk · HTML Template",
                "tags": ["bulk-render", f"theme:{body.theme}", f"job:{job_id}"],
                "storage_path": storage_path,
                "is_favorite": False, "status": "active",
                "source": "html_bulk",
                "theme": body.theme,
                "item_name": it["name"],
                "uploaded_at": now, "updated_at": now,
            })
            ms = round((time.perf_counter() - t0) * 1000, 1)
            results.append({
                "item_name": it["name"],
                "category": it["category"],
                "asset_id": asset_id,
                "render_ms": ms,
                "ok": True,
            })
        except Exception as e:  # noqa: BLE001
            results.append({
                "item_name": it["name"],
                "category": it["category"],
                "ok": False,
                "error": str(e),
            })
        await update(completed=idx + 1, results=results)

    await update(status="done", finished_at=_now_iso())


@router.post("/bulk-render")
async def bulk_render(body: BulkRenderBody, background: BackgroundTasks):
    """Render every menu item with the chosen HTML theme. Runs as a
    background asyncio task; poll `/bulk-render/{job_id}` for progress."""
    if not _html.is_supported(body.theme):
        raise HTTPException(
            status_code=400,
            detail=f"theme={body.theme!r} not supported by the HTML renderer."
        )
    job_id = str(uuid.uuid4())
    now = _now_iso()
    await db.html_bulk_jobs.insert_one({
        "id": job_id,
        "theme": body.theme,
        "status": "queued",
        "total": 0, "completed": 0,
        "results": [],
        "created_at": now, "updated_at": now,
    })
    background.add_task(_run_bulk_render, job_id, body)
    return {"job_id": job_id, "status": "queued"}


@router.get("/bulk-render/{job_id}")
async def bulk_render_status(job_id: str):
    job = await db.html_bulk_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


# ---------------------------------------------------------------- featured

def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _daily_index(day_key: str, pool_size: int) -> int:
    """Deterministic per-day pick that survives process restarts and
    matches across separate Python interpreters.

    Previously used Python's built-in ``hash()``, which is randomised by
    ``PYTHONHASHSEED`` on each process — meaning multiple workers or
    server restarts could rotate to different flyers mid-day. This uses
    SHA-256 on the day key so the same day always maps to the same index
    regardless of which process serves the request.
    """
    if pool_size <= 0:
        return 0
    digest = hashlib.sha256(day_key.encode("utf-8")).digest()
    # First 8 bytes → big-endian unsigned int → modulo pool size.
    n = int.from_bytes(digest[:8], "big", signed=False)
    return n % pool_size


@router.get("/featured")
async def featured(window_days: int = 0):
    """Today's Special — deterministically rotate through active bulk-rendered
    flyers. Returns the flyer that should appear on the homepage hero today.

    Selection: take EVERY active HTML-bulk asset by default (window_days=0),
    or only those within the last `window_days` if a positive value is passed.
    Sort by `uploaded_at` desc, pick index `hash(today) % count`.
    Same flyer all day; new flyer tomorrow.

    Feb 2026 (Phase 2G) — the previous default was `window_days=14`, but the
    existing bulk pool is > 30 days old, which silently collapsed the
    rotation to a single flyer via the fallback branch. Widening the default
    to "no age restriction" restores the deterministic daily rotation across
    the ~57 assets without generating a new pool or deleting anything. If a
    caller wants the historical 14-day window, they can pass ?window_days=14.
    """
    now = datetime.now(timezone.utc)

    query: Dict[str, Any] = {"source": "html_bulk", "status": "active"}
    if window_days and window_days > 0:
        cutoff = (now - timedelta(days=window_days)).isoformat()
        query["uploaded_at"] = {"$gte": cutoff}

    cursor = db.media_assets.find(
        query,
        {"_id": 0, "id": 1, "filename": 1, "storage_path": 1, "item_name": 1,
         "theme": 1, "uploaded_at": 1, "width": 1, "height": 1},
    ).sort("uploaded_at", -1).limit(200)
    assets = await cursor.to_list(length=200)
    if not assets:
        # Fallback: most recent regardless of window (should be unreachable
        # when window_days=0, but preserved for the explicit-window case).
        latest = await db.media_assets.find_one(
            {"source": "html_bulk", "status": "active"},
            {"_id": 0, "id": 1, "filename": 1, "storage_path": 1, "item_name": 1,
             "theme": 1, "uploaded_at": 1, "width": 1, "height": 1},
            sort=[("uploaded_at", -1)],
        )
        if not latest:
            raise HTTPException(status_code=404, detail="No bulk-rendered flyers in the library yet")
        assets = [latest]

    idx = _daily_index(_today_str(), len(assets))
    pick = assets[idx]
    return {
        "asset_id": pick["id"],
        "item_name": pick.get("item_name") or pick.get("filename") or "Today's Special",
        "theme": pick.get("theme"),
        "uploaded_at": pick.get("uploaded_at"),
        "image_url": f"/api/media/file/{pick['id']}",
        "pool_size": len(assets),
        "rotated_for": _today_str(),
    }
