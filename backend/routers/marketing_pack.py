"""Promote This Item — Marketing Pack 3.0 (video-only).

Sprint 16B.4 trimmed this surface to its unique capability: a 15-second
vertical promo video built from a source photo + headline. All caption /
SMS / email / GBP / hashtag generation moved to AI Designer's copy_pack
(see `routers/ai_designer.py::_write_designer_copy`) which owns the copy
surface across the entire app.

Surviving flow:
  POST /api/marketing-pack/generate          → 202 + job_id (background task)
  GET  /api/marketing-pack/job/{id}          → poll: pending|processing|completed|failed
  GET  /api/marketing-pack/{id}              → fetch a completed pack
  POST /api/marketing-pack/{id}/regenerate   → re-run pipeline with same inputs
  GET  /api/marketing-pack/items-not-promoted-recently?limit=3

Pipeline (background, 30–60 s):
  1. infer        — fill missing name/description via one text LLM call
  2. rendering_images — PIL crops source to 4 ratios (1:1, 9:16, 1.91:1, 16:9)
                    as the source frames for the video pipeline
  3. rendering_video  — _render_sync builds a 15-s slideshow with title + CTA
  4. saving       — persist marketing_packs row + stamp menu item

Removed in Sprint 16B.4:
  • _write_copy()                — moved to AI Designer copy_pack
  • PATCH /api/marketing-pack/{id} — only edited the removed copy fields
  • Result fields: caption, hashtags, sms, email, gbp

This module imports private helpers from routers.media on purpose — we reuse
the same PIL + ffmpeg + object-storage pipeline rather than duplicate it.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Header, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, ConfigDict, constr

from auth import verify_session
import storage as objstore
from routers.media import (
    TMP_DIR, _fit_to, _hex_to_rgb, _now, _render_sync, _spawn_ai_image_task,
)

router = APIRouter(prefix="/marketing-pack", tags=["marketing-pack"])

mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]

log = logging.getLogger("uvicorn.error")


# ---------------------------------------------------------------- formats
# (width, height) — the 9:16 output is referenced as BOTH ig_story AND tiktok_reel.
# These are the SOURCE FRAMES for the video; they are saved as media_assets
# so the video pipeline can read them back by id.
FORMATS: Dict[str, tuple] = {
    "ig_post":  (1080, 1080),   # Instagram feed 1:1
    "ig_story": (1080, 1920),   # IG Story / TikTok / Reel 9:16
    "fb_post":  (1200, 628),    # Facebook 1.91:1
    "hero":     (1920, 1080),   # Website hero 16:9
}


# ---------------------------------------------------------------- schemas

class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_asset_id: constr(min_length=1, max_length=64)
    menu_item_key: Optional[constr(max_length=120)] = None  # "appetizers::cafe-fries"
    name: Optional[constr(max_length=120)] = None
    description: Optional[constr(max_length=500)] = None
    price: Optional[constr(max_length=40)] = None
    headline: Optional[constr(max_length=80)] = None
    cta: Optional[constr(max_length=40)] = None


# ---------------------------------------------------------------- helpers

def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


async def _get_active_asset(asset_id: str) -> Dict[str, Any]:
    asset = await db.media_assets.find_one({"id": asset_id, "status": "active"}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Source asset not found")
    if asset.get("kind") != "image":
        raise HTTPException(status_code=400, detail="Source must be an image")
    return asset


def _font(size: int) -> ImageFont.ImageFont:
    # Use default PIL font — guaranteed to exist; aesthetic overlay is intentional + safe.
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def _draw_overlay(img: Image.Image, headline: Optional[str], price: Optional[str], cta: Optional[str]) -> Image.Image:
    """Brand overlay: a soft dark bar at the bottom with headline + price + CTA chip.
    All overlay text is best-effort — if anything fails we keep the un-overlayed image."""
    if not (headline or price or cta):
        return img
    try:
        w, h = img.size
        bar_h = int(h * 0.22)
        overlay = Image.new("RGBA", (w, bar_h), (10, 18, 32, 200))
        draw = ImageDraw.Draw(overlay)
        if headline:
            f = _font(max(34, int(w / 24)))
            draw.text((int(w * 0.06), int(bar_h * 0.18)), headline.upper()[:46], font=f, fill=(255, 255, 255, 255))
        if price:
            f = _font(max(28, int(w / 28)))
            draw.text((int(w * 0.06), int(bar_h * 0.55)), price, font=f, fill=(200, 169, 94, 255))
        if cta:
            f = _font(max(22, int(w / 38)))
            tw = draw.textlength(cta.upper()[:24], font=f)
            pad = int(w * 0.02)
            x0 = w - int(w * 0.06) - tw - pad * 2
            y0 = int(bar_h * 0.55)
            draw.rounded_rectangle([x0, y0, x0 + tw + pad * 2, y0 + int(bar_h * 0.30)],
                                   radius=6, fill=(200, 169, 94, 255))
            draw.text((x0 + pad, y0 + int(bar_h * 0.04)), cta.upper()[:24], font=f, fill=(10, 18, 32, 255))
        base = img.convert("RGBA")
        base.paste(overlay, (0, h - bar_h), overlay)
        return base.convert("RGB")
    except Exception:  # noqa: BLE001
        return img


# ---------------------------------------------------------------- LLM steps

async def _infer_missing_fields(name: Optional[str], description: Optional[str],
                                src_asset: Dict[str, Any]) -> Dict[str, str]:
    """If name/description are blank, ask the LLM to invent reasonable ones based
    on the asset's filename, tags, and (if AI-generated) the original prompt."""
    if name and description:
        return {"name": name, "description": description}
    try:
        from ai_engine.client import generate_structured
        clues = {
            "filename": src_asset.get("filename"),
            "tags": src_asset.get("tags", []),
            "folder": src_asset.get("folder"),
            "ai_prompt": src_asset.get("ai_prompt"),
        }
        sys = ("You are a New Orleans restaurant marketing copywriter for Lakeview "
               "Burgers & Seafood. Output ONLY JSON.")
        usr = ("Given these clues about a food photo, propose a short menu-item "
               f"name (2-4 words) and a one-sentence description (12-22 words):\n"
               f"{json.dumps(clues)}\n"
               f"User-provided name: {name or '(none)'}\n"
               f"User-provided description: {description or '(none)'}\n"
               "Keep the user-provided values where present. Be specific to "
               "Cajun/Creole/Southern comfort food when no clue suggests otherwise.")
        schema = '{"name":"string","description":"string"}'
        wrapped = await generate_structured(db, system_prompt=sys, user_prompt=usr, schema_hint=schema)
        out = wrapped.get("data") or {}
        return {
            "name": name or (out.get("name") or "House Special")[:120],
            "description": description or (out.get("description") or "")[:500],
        }
    except Exception as e:  # noqa: BLE001
        log.warning("[marketing-pack] infer failed, using safe defaults: %s", e)
        return {
            "name": name or "House Special",
            "description": description or "A signature dish from our kitchen.",
        }


# ---------------------------------------------------------------- pipeline

async def _save_format_asset(src_bytes: bytes, fmt_key: str, item: Dict[str, str],
                             menu_item_key: Optional[str], pack_id: str) -> Dict[str, Any]:
    """Crop + overlay + upload one source frame for the video pipeline.
    Returns the inserted media_asset row. The 4 frames are kept as
    media_assets so `_render_pack_video` can read them back by id; they
    are NOT surfaced in the /generate API response (Sprint 16B.4)."""
    w, h = FORMATS[fmt_key]
    with Image.open(io.BytesIO(src_bytes)) as base:
        base = base.convert("RGB")
        fitted = _fit_to(base, w, h, "cover", (10, 18, 32))
        overlay_headline = item.get("headline") or item.get("name")
        with_overlay = _draw_overlay(fitted, overlay_headline, item.get("price"), item.get("cta"))
        buf = io.BytesIO()
        with_overlay.save(buf, format="JPEG", quality=90, optimize=True)
    out_bytes = buf.getvalue()
    aid = str(uuid.uuid4())
    storage_path = objstore.make_path("marketing_pack", aid, "jpg")
    objstore.put_bytes(storage_path, out_bytes, "image/jpeg")
    tags = ["marketing-pack", fmt_key, f"pack:{pack_id}"]
    if fmt_key == "ig_story":
        tags.append("tiktok_reel")  # the 9:16 is dual-labeled
    if menu_item_key:
        tags.append(f"item:{menu_item_key}")
    doc = {
        "id": aid,
        "filename": f"{_slugify(item['name'])}-{fmt_key}-{aid[:6]}.jpg",
        "kind": "image", "mime": "image/jpeg",
        "size_bytes": len(out_bytes),
        "width": w, "height": h, "duration_seconds": None,
        "folder": "Marketing Packs",
        "tags": tags,
        "storage_path": storage_path,
        "is_favorite": False, "status": "active",
        "source": "marketing_pack",
        "marketing_pack_id": pack_id,
        "uploaded_at": _now(), "updated_at": _now(),
    }
    await db.media_assets.insert_one(doc)
    return doc


async def _render_pack_video(pack_id: str, image_asset_ids: List[str], item: Dict[str, str]) -> Optional[str]:
    """15-s vertical slideshow using existing _render_sync. Returns new asset_id or None on failure.

    On memory-constrained production pods, set MARKETING_PACK_VIDEO=0 to skip
    video rendering entirely (the 4 image formats + all text copy still ship).
    MARKETING_PACK_VIDEO_RES=720 reduces output from 1080x1920 → 720x1280,
    cutting ffmpeg peak RSS by roughly 60%."""
    if os.environ.get("MARKETING_PACK_VIDEO", "1").lower() in ("0", "false", "no"):
        log.info("[marketing-pack] MARKETING_PACK_VIDEO=0 — skipping video render for %s", pack_id)
        return None
    res = os.environ.get("MARKETING_PACK_VIDEO_RES", "720")
    width = 1080 if res == "1080" else 720
    height = 1920 if res == "1080" else 1280
    assets = await db.media_assets.find({"id": {"$in": image_asset_ids}}, {"_id": 0}).to_list(20)
    by_id = {a["id"]: a for a in assets}
    # Order: hero → ig_post → fb_post → ig_story (story last for the strong vertical kicker)
    desired_order = ["hero", "ig_post", "fb_post", "ig_story"]
    ordered: List[Dict[str, Any]] = []
    for fmt in desired_order:
        for a in assets:
            if fmt in (a.get("tags") or []):
                ordered.append(a)
                break
    if not ordered:
        ordered = [by_id[i] for i in image_asset_ids if i in by_id][:4]
    if not ordered:
        return None
    job = {
        "id": pack_id,
        "duration_seconds": 15.0,
        "title": (item.get("headline") or item.get("name") or "")[:60],
        "cta": (item.get("cta") or "Order Now")[:24],
        "template": "marketing_pack",
    }
    work_dir = TMP_DIR / f"pack_{pack_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        out_path = await asyncio.to_thread(_render_sync, job, ordered, width, height, work_dir)
        video_bytes = out_path.read_bytes()
        new_id = str(uuid.uuid4())
        storage_path = objstore.make_path("marketing_pack", new_id, "mp4")
        objstore.put_bytes(storage_path, video_bytes, "video/mp4")
        doc = {
            "id": new_id,
            "filename": f"{_slugify(item['name'])}-promo-{new_id[:6]}.mp4",
            "kind": "video", "mime": "video/mp4",
            "size_bytes": len(video_bytes),
            "width": width, "height": height, "duration_seconds": 15.0,
            "folder": "Marketing Packs",
            "tags": ["marketing-pack", "promo-video", f"pack:{pack_id}"],
            "storage_path": storage_path,
            "is_favorite": False, "status": "active",
            "source": "marketing_pack",
            "marketing_pack_id": pack_id,
            "uploaded_at": _now(), "updated_at": _now(),
        }
        await db.media_assets.insert_one(doc)
        return new_id
    except Exception as e:  # noqa: BLE001
        log.warning("[marketing-pack] video render failed for %s: %s", pack_id, e)
        return None
    finally:
        import shutil as _sh
        _sh.rmtree(work_dir, ignore_errors=True)


async def _run_pack_job(pack_id: str, body: GenerateRequest) -> None:
    """Background worker — drives the full pipeline and updates the pack row in place."""
    async def update(**fields: Any) -> None:
        fields["updated_at"] = _now()
        await db.marketing_packs.update_one({"id": pack_id}, {"$set": fields})

    async def fail(code: str, user_message: str, technical: str = "", retryable: bool = True) -> None:
        err = {
            "code": code, "status": 500, "retryable": retryable,
            "retry_action": "retry" if retryable else None,
            "user_message": user_message, "technical": technical, "context": {},
        }
        await update(status="failed", error=err)

    try:
        import time as _t
        log.info("MARKETING_PACK_START pack_id=%s asset=%s", pack_id, body.source_asset_id)
        src = await db.media_assets.find_one({"id": body.source_asset_id, "status": "active"}, {"_id": 0})
        if not src or src.get("kind") != "image":
            await fail("asset_missing",
                       "The source image is missing or isn't an image. Pick another one and try again.",
                       f"asset {body.source_asset_id} not found or not an image", retryable=False)
            return

        # --- Step 1: infer
        ts = _t.time()
        log.info("MARKETING_PACK_STEP pack_id=%s step=inferring", pack_id)
        await update(status="processing", current_step="inferring", progress=10)
        inferred = await _infer_missing_fields(body.name, body.description, src)
        item = {
            "name": inferred["name"],
            "description": inferred["description"],
            "price": body.price,
            "headline": body.headline,
            "cta": body.cta or "Order Now",
        }
        await update(item=item)
        log.info("MARKETING_PACK_STEP_OK pack_id=%s step=inferring dur_ms=%d", pack_id, int((_t.time()-ts)*1000))

        # --- Step 2: render 4 source frames (1:1, 9:16, 1.91:1, 16:9) for the video
        ts = _t.time()
        log.info("MARKETING_PACK_STEP pack_id=%s step=rendering_images", pack_id)
        await update(current_step="rendering_images", progress=35)
        try:
            src_bytes, _ = objstore.get_bytes(src["storage_path"])
        except FileNotFoundError:
            await fail("asset_missing",
                       "The source image file is gone from storage. Re-upload and try again.",
                       f"object missing: {src['storage_path']}", retryable=False)
            return
        result_assets: Dict[str, str] = {}
        for fmt in FORMATS:
            row = await _save_format_asset(src_bytes, fmt, item, body.menu_item_key, pack_id)
            result_assets[f"{fmt}_asset_id"] = row["id"]
        # Dual label: tiktok_reel reuses the 9:16
        result_assets["tiktok_reel_asset_id"] = result_assets["ig_story_asset_id"]
        log.info("MARKETING_PACK_STEP_OK pack_id=%s step=rendering_images dur_ms=%d image_count=%d",
                 pack_id, int((_t.time()-ts)*1000), len(FORMATS))

        # --- Step 3: render 15s video (the unique surface this router owns)
        ts = _t.time()
        log.info("MARKETING_PACK_STEP pack_id=%s step=rendering_video", pack_id)
        await update(current_step="rendering_video", progress=65)
        image_ids = [result_assets[f"{f}_asset_id"] for f in FORMATS]
        video_id = await _render_pack_video(pack_id, image_ids, item)
        if video_id:
            result_assets["video_asset_id"] = video_id
        log.info("MARKETING_PACK_STEP_OK pack_id=%s step=rendering_video dur_ms=%d video_ok=%s",
                 pack_id, int((_t.time()-ts)*1000), bool(video_id))

        # --- Step 4: save (no copy fields — AI Designer copy_pack owns that)
        await update(current_step="saving", progress=95)
        result = dict(result_assets)
        await update(status="completed", current_step="done", progress=100, result=result)

        # Billing Resilience: record actual estimated cost against the virtual balance
        try:
            import billing
            cost = billing.estimate_marketing_pack_cost()["total_cost"]
            await billing.record_usage(
                db,
                surface="marketing_pack",
                model="gpt-5",
                operation="pack_generation",
                cost_usd=cost,
                input_tokens=billing.MARKETING_PACK_TEXT_INPUT_TOKENS,
                output_tokens=billing.MARKETING_PACK_TEXT_OUTPUT_TOKENS,
                pipeline_id=pack_id,
            )
        except Exception as _e:  # noqa: BLE001
            log.warning("[marketing-pack] billing.record_usage failed: %s", _e)

        # Stamp menu item with last_promoted_at
        if body.menu_item_key:
            await db.menu_promotions.update_one(
                {"item_key": body.menu_item_key},
                {"$set": {"item_key": body.menu_item_key, "last_promoted_at": _now(), "last_pack_id": pack_id}},
                upsert=True,
            )
    except Exception as e:  # noqa: BLE001
        log.exception("[marketing-pack] pipeline crashed for %s", pack_id)
        # Try to classify — turns raw litellm/OpenAI errors into actionable
        # user messages (budget_exhausted, rate_limited, safety_reject, etc).
        try:
            from errors import classify_llm_error
            classified = classify_llm_error(e, surface="marketing pack")
            await update(status="failed", error={
                "code": classified.code,
                "status": classified.status,
                "retryable": classified.retryable,
                "retry_action": classified.retry_action,
                "user_message": classified.user_message,
                "technical": classified.technical,
                "context": classified.context,
            })
        except Exception:  # classifier itself broke — fall back to generic
            await fail("unknown",
                       "Something went wrong while building your pack. Try again — if it keeps failing, change the photo or shorten the description.",
                       str(e)[:400], retryable=True)


# ---------------------------------------------------------------- routes

@router.post("/generate", status_code=202)
async def generate_pack(
    body: GenerateRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    await _get_active_asset(body.source_asset_id)  # 404 fast if missing

    # ---- Billing Resilience: pre-flight budget check ----
    # Block generation BEFORE enqueueing the background job if virtual balance
    # cannot cover an estimated pack cost. Telemetry inside billing module.
    import billing
    cost_breakdown = billing.estimate_marketing_pack_cost()
    can_afford, status = await billing.check_can_afford(
        db, cost_breakdown["total_cost"], surface="marketing_pack",
    )
    if not can_afford:
        # 402 Payment Required — frontend interprets this to show Add Balance CTA
        from fastapi import HTTPException
        raise HTTPException(
            status_code=402,
            detail={
                "code": "budget_exhausted",
                "status": 402,
                "retryable": False,
                "retry_action": "add_balance",
                "user_message": (
                    f"Your AI credit balance (${status['current_balance_usd']:.2f}) is too low to "
                    f"generate a marketing pack (~${cost_breakdown['total_cost']:.2f}). "
                    "Open Profile → Universal Key → Add Balance in Emergent, then click "
                    "'I just topped up' on your Home dashboard."
                ),
                "technical": f"virtual_balance={status['current_balance_usd']} required={cost_breakdown['total_cost']}",
                "context": {
                    "balance_usd": status["current_balance_usd"],
                    "required_usd": cost_breakdown["total_cost"],
                    "estimated_packs_remaining": status["estimated_packs_remaining"],
                },
            },
        )

    pack_id = str(uuid.uuid4())
    now = _now()
    await db.marketing_packs.insert_one({
        "id": pack_id,
        "status": "pending",
        "progress": 0,
        "current_step": "queued",
        "source_asset_id": body.source_asset_id,
        "menu_item_key": body.menu_item_key,
        "estimated_cost_usd": cost_breakdown["total_cost"],
        "item": {
            "name": body.name, "description": body.description, "price": body.price,
            "headline": body.headline, "cta": body.cta,
        },
        "result": None,
        "error": None,
        "created_at": now, "updated_at": now,
    })
    _spawn_ai_image_task(_run_pack_job(pack_id, body))
    return {"job_id": pack_id, "status": "pending"}


@router.get("/items-not-promoted-recently")
async def items_not_promoted_recently(
    limit: int = 3,
    authorization: str = Header(None), session_token: str = Cookie(None),
):
    """Top N menu items by oldest promotion. Items never promoted come first.

    Menu items are stored as embedded arrays inside `menu_categories` documents,
    so we flatten them client-side and join against `menu_promotions` by
    `item_key = "{category_slug}::{slug(name)}"`."""
    await verify_session(authorization, session_token)
    cats = await db.menu_categories.find({}, {"_id": 0}).to_list(50)
    promos = await db.menu_promotions.find({}, {"_id": 0}).to_list(5000)
    promo_by_key = {p["item_key"]: p for p in promos}

    items: List[Dict[str, Any]] = []
    for cat in cats:
        slug = cat.get("slug") or _slugify(cat.get("display_name") or "")
        for it in (cat.get("items") or []):
            name = it.get("name") or ""
            if not name:
                continue
            key = f"{slug}::{_slugify(name)}"
            p = promo_by_key.get(key)
            items.append({
                "item_key": key,
                "name": name,
                "description": it.get("description") or "",
                "price": it.get("price") or "",
                "category_slug": slug,
                "category_display_name": cat.get("display_name") or slug,
                "last_promoted_at": (p or {}).get("last_promoted_at"),
                "last_pack_id": (p or {}).get("last_pack_id"),
            })
    items.sort(key=lambda x: (x["last_promoted_at"] is not None, x["last_promoted_at"] or ""))
    return {"items": items[: max(1, min(limit, 20))], "fallback_used": False, "source": "menu_categories"}


@router.get("/job/{pack_id}")
async def get_pack_job(pack_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    pack = await db.marketing_packs.find_one({"id": pack_id}, {"_id": 0})
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    return pack


@router.get("/{pack_id}")
async def get_pack(pack_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    pack = await db.marketing_packs.find_one({"id": pack_id}, {"_id": 0})
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    return pack


@router.post("/{pack_id}/regenerate", status_code=202)
async def regenerate_pack(
    pack_id: str, authorization: str = Header(None), session_token: str = Cookie(None),
):
    """Re-run the pipeline using the original inputs. Returns a NEW pack_id."""
    await verify_session(authorization, session_token)
    pack = await db.marketing_packs.find_one({"id": pack_id}, {"_id": 0})
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    item = pack.get("item") or {}
    body = GenerateRequest(
        source_asset_id=pack["source_asset_id"],
        menu_item_key=pack.get("menu_item_key"),
        name=item.get("name"), description=item.get("description"),
        price=item.get("price"), headline=item.get("headline"), cta=item.get("cta"),
    )
    return await generate_pack(body, authorization=authorization, session_token=session_token)


async def cleanup_orphan_marketing_packs() -> None:
    """Mark pending/processing packs as failed at startup (in-process task is gone)."""
    err = {
        "code": "unknown", "status": 500, "retryable": True, "retry_action": "retry",
        "user_message": "Your marketing pack was interrupted by a server restart. Click Try again to regenerate.",
        "technical": "backend restarted with marketing_pack in pending/processing state",
        "context": {},
    }
    r = await db.marketing_packs.update_many(
        {"status": {"$in": ["pending", "processing"]}},
        {"$set": {"status": "failed", "error": err, "progress": 0, "updated_at": _now()}},
    )
    if r.modified_count > 0:
        log.info("[marketing-pack] Marked %s orphan pack(s) as failed at startup", r.modified_count)
