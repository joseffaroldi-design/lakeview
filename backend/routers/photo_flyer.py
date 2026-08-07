"""Simple Photo → Flyer backend.

This is the stable V1 surface used by the dashboard. The browser only needs
one feature namespace:

  POST /api/photo-flyer/analyze
  POST /api/photo-flyer/analyze-existing
  GET  /api/photo-flyer/themes
  POST /api/photo-flyer/generate
  GET  /api/photo-flyer/job/{id}

Historical AI Designer/theme code remains intact behind this facade so old
assets can still be regenerated without making the frontend depend on the
legacy subsystem directly.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, File, Form, Header, HTTPException, UploadFile
from PIL import Image
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, constr

import storage as objstore
from auth import verify_session
from services.menu_matcher import match_food_to_menu
from services.photo_enhance import enhance_photo
from services.vision_client import analyze_food_photo

# Compatibility engine. These imports are intentionally backend-only.
from routers.ai_designer import (
    GenerateRequest as FlyerGenerateRequest,
    enqueue_generate as _legacy_generate,
    get_job as _legacy_get_job,
    list_themes as _legacy_list_themes,
)

router = APIRouter(prefix="/photo-flyer", tags=["photo-flyer"])
log = logging.getLogger("uvicorn.error")

mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]

ALLOWED = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_BYTES = 15 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bytes_io(data: bytes):
    import io
    return io.BytesIO(data)


async def _persist_image(
    image_bytes: bytes,
    mime: str,
    filename: str,
    source: str,
    tags: list,
) -> dict:
    asset_id = str(uuid.uuid4())
    ext = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }.get(mime, "jpg")
    storage_path = objstore.make_path("uploads", asset_id, ext)
    await asyncio.to_thread(objstore.put_bytes, storage_path, image_bytes, mime)

    width = height = None
    try:
        with Image.open(_bytes_io(image_bytes)) as img:
            width, height = img.size
    except Exception:  # noqa: BLE001
        pass

    doc = {
        "id": asset_id,
        "filename": filename or f"{asset_id}.{ext}",
        "kind": "image",
        "mime": mime,
        "size_bytes": len(image_bytes),
        "width": width,
        "height": height,
        "duration_seconds": None,
        "folder": "Custom",
        "tags": tags,
        "source": source,
        "storage_path": storage_path,
        "status": "active",
        "uploaded_at": _now(),
        "updated_at": _now(),
    }
    await db.media_assets.insert_one(doc)
    return {k: v for k, v in doc.items()}


@router.post("/analyze")
async def analyze_photo(
    file: UploadFile = File(...),
    folder: str = Form("Custom"),
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Upload, enhance and identify a food photo."""
    await verify_session(authorization, session_token)

    mime = (file.content_type or "").lower()
    if mime not in ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{mime}'. Allowed: JPG, PNG, WEBP.",
        )

    raw = b""
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        raw += chunk
        if len(raw) > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Image exceeds {MAX_BYTES // (1024 * 1024)} MB limit.",
            )
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload.")

    try:
        original = await _persist_image(
            raw,
            mime,
            file.filename or "original.jpg",
            source="photo_flyer_original",
            tags=["photo-flyer", "original"],
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("photo_flyer original persist failed")
        raise HTTPException(status_code=502, detail=f"Storage error: {exc}")

    try:
        enhanced_bytes, enhance_info = enhance_photo(raw)
    except Exception as exc:  # noqa: BLE001
        log.exception("photo_enhance failed; using original")
        enhanced_bytes = raw
        enhance_info = {"mode": "fallback", "error": str(exc)[:160]}

    try:
        enhanced = await _persist_image(
            enhanced_bytes,
            "image/jpeg",
            f"enhanced-{original['filename']}",
            source="photo_flyer_enhanced",
            tags=["photo-flyer", "enhanced"],
        )
    except Exception:  # noqa: BLE001
        log.exception("photo_flyer enhanced persist failed")
        enhanced = None

    vision = await analyze_food_photo(enhanced_bytes if enhanced is not None else raw)
    menu_match = await match_food_to_menu(vision.get("food_type", ""), db)

    return {
        "original_asset_id": original["id"],
        "enhanced_asset_id": (enhanced or original)["id"],
        "enhance_info": enhance_info,
        "vision_ok": bool(vision.get("vision_ok")),
        "vision_error": vision.get("error"),
        "food_type": vision.get("food_type") or "",
        "confidence": vision.get("confidence", 0.0),
        "features": vision.get("features", []),
        "suggested_theme": vision.get("suggested_theme") or "modern",
        "dominant_colors": vision.get("dominant_colors", []),
        "menu_match": menu_match,
    }


class AnalyzeExistingRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    asset_id: constr(min_length=1, max_length=64)


@router.post("/analyze-existing")
async def analyze_existing(
    body: AnalyzeExistingRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Analyze an existing image from the media library without duplicating it."""
    await verify_session(authorization, session_token)

    row = await db.media_assets.find_one({"id": body.asset_id}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found.")
    if row.get("kind") != "image":
        raise HTTPException(status_code=400, detail="Asset is not an image.")
    if row.get("status") == "archived":
        raise HTTPException(status_code=400, detail="Asset is archived.")

    storage_path = row.get("storage_path")
    if not storage_path:
        raise HTTPException(status_code=502, detail="Asset has no storage path.")

    try:
        image_bytes, _ = await asyncio.to_thread(objstore.get_bytes, storage_path)
    except Exception as exc:  # noqa: BLE001
        log.exception("photo_flyer existing asset fetch failed")
        raise HTTPException(status_code=502, detail=f"Storage error: {exc}")

    vision = await analyze_food_photo(image_bytes)
    menu_match = await match_food_to_menu(vision.get("food_type", ""), db)

    return {
        "original_asset_id": body.asset_id,
        "enhanced_asset_id": body.asset_id,
        "enhance_info": {"mode": "library_reuse"},
        "vision_ok": bool(vision.get("vision_ok")),
        "vision_error": vision.get("error"),
        "food_type": vision.get("food_type") or "",
        "confidence": vision.get("confidence", 0.0),
        "features": vision.get("features", []),
        "suggested_theme": vision.get("suggested_theme") or "modern",
        "dominant_colors": vision.get("dominant_colors", []),
        "menu_match": menu_match,
    }


@router.get("/themes")
async def list_flyer_themes(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Return selectable flyer styles through the stable Photo Flyer API."""
    return await _legacy_list_themes(authorization, session_token)


@router.post("/generate", status_code=202)
async def generate_flyer(
    body: FlyerGenerateRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Start a flyer render through the stable Photo Flyer API."""
    return await _legacy_generate(body, authorization, session_token)


@router.get("/job/{job_id}")
async def get_flyer_job(
    job_id: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Poll a flyer render job through the stable Photo Flyer API."""
    return await _legacy_get_job(job_id, authorization, session_token)
