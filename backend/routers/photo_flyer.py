"""Photo → Flyer orchestrator (Sprint 16D).

ONE endpoint: `POST /api/photo-flyer/analyze`. It accepts a single image
upload and produces everything the new front-end UX needs to skip the
manual designer form:

  1. Save the ORIGINAL bytes as a media_assets row (kind=image)
  2. PIL-enhance the bytes (lighting / contrast / sharpen / denoise)
  3. Save the ENHANCED bytes as a second media_assets row
  4. Run Gemini 3 Flash vision on the enhanced bytes (graceful on failure)
  5. Fuzzy-match the detected food name against the live menu

The actual flyer generation, copy generation, and video generation happen
later via the existing /api/ai-designer/generate and
/api/marketing-pack/generate routes — this router NEVER duplicates them.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, File, Form, Header, HTTPException, UploadFile
from PIL import Image
from motor.motor_asyncio import AsyncIOMotorClient

import storage as objstore
from auth import verify_session
from services.menu_matcher import match_food_to_menu
from services.photo_enhance import enhance_photo
from services.vision_client import analyze_food_photo

router = APIRouter(prefix="/photo-flyer", tags=["photo-flyer"])
log = logging.getLogger("uvicorn.error")

mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]

ALLOWED = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_BYTES = 15 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _persist_image(image_bytes: bytes, mime: str, filename: str,
                         source: str, tags: list) -> dict:
    """Drop bytes into object storage + insert a media_assets row. Returns
    the row dict (id, filename, kind, storage_path, ...)."""
    asset_id = str(uuid.uuid4())
    ext = {
        "image/jpeg": "jpg", "image/jpg": "jpg",
        "image/png": "png", "image/webp": "webp",
    }.get(mime, "jpg")
    storage_path = objstore.make_path("uploads", asset_id, ext)
    objstore.put_bytes(storage_path, image_bytes, mime)

    width = height = None
    try:
        with Image.open(__import_io__(image_bytes)) as img:
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


def __import_io__(b: bytes):
    """Lazy io.BytesIO wrapper so PIL can read in-memory."""
    import io as _io
    return _io.BytesIO(b)


@router.post("/analyze")
async def analyze_photo(
    file: UploadFile = File(...),
    folder: str = Form("Custom"),  # accepted for parity, ignored (stored as Custom)
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Upload + PIL-enhance + Gemini vision + menu lookup, all in one call.

    Returns enough information for the UI to skip the manual designer form
    and jump straight to "Generate flyer". The Generate step reuses the
    existing /api/ai-designer/generate route — this orchestrator never
    duplicates the flyer pipeline.
    """
    await verify_session(authorization, session_token)

    mime = (file.content_type or "").lower()
    if mime not in ALLOWED:
        raise HTTPException(status_code=400,
                            detail=f"Unsupported file type '{mime}'. "
                                   "Allowed: JPG, PNG, WEBP.")

    # Read the upload into memory (capped at MAX_BYTES).
    raw = b""
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        raw += chunk
        if len(raw) > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Image exceeds {MAX_BYTES // (1024 * 1024)} MB limit.")
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload.")

    log.info("PHOTO_FLYER_ANALYZE_START filename=%r mime=%s size=%d",
             file.filename, mime, len(raw))

    # 1) Persist the original
    try:
        original = await _persist_image(
            raw, mime, file.filename or "original.jpg",
            source="photo_flyer_original", tags=["photo-flyer", "original"])
    except Exception as e:  # noqa: BLE001
        log.exception("photo_flyer original persist failed")
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")

    # 2) PIL-enhance
    try:
        enhanced_bytes, enhance_info = enhance_photo(raw)
    except Exception as e:  # noqa: BLE001
        log.exception("photo_enhance failed; falling back to original bytes")
        enhanced_bytes, enhance_info = raw, {"mode": "fallback", "error": str(e)[:160]}

    # 3) Persist the enhanced asset
    try:
        enhanced = await _persist_image(
            enhanced_bytes, "image/jpeg",
            f"enhanced-{original['filename']}",
            source="photo_flyer_enhanced",
            tags=["photo-flyer", "enhanced"])
    except Exception:  # noqa: BLE001
        log.exception("photo_flyer enhanced persist failed")
        # Non-fatal — caller can still use the original
        enhanced = None

    # 4) Vision on the enhanced bytes (or original if enhancement failed)
    vision_source = enhanced_bytes if enhanced is not None else raw
    vision = await analyze_food_photo(vision_source)

    # 5) Menu fuzzy match (only if vision returned a name)
    menu_match = await match_food_to_menu(vision.get("food_type", ""), db)

    payload = {
        "original_asset_id": original["id"],
        "enhanced_asset_id": (enhanced or original)["id"],
        "enhance_info": enhance_info,
        "vision_ok": bool(vision.get("vision_ok")),
        "vision_error": vision.get("error"),
        "food_type": vision.get("food_type") or "",
        "confidence": vision.get("confidence", 0.0),
        "features": vision.get("features", []),
        "suggested_theme": vision.get("suggested_theme") or "comic_pop",
        "dominant_colors": vision.get("dominant_colors", []),
        "menu_match": menu_match,
    }
    log.info("PHOTO_FLYER_ANALYZE_OK original=%s enhanced=%s food=%r "
             "vision_ok=%s menu=%s",
             original["id"][:8], (enhanced or original)["id"][:8],
             payload["food_type"], payload["vision_ok"],
             menu_match.get("matched"))
    return payload
