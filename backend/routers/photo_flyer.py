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
    # Production hotfix — put_bytes does a synchronous requests.put with a
    # 180s timeout. Running it directly inside this async coroutine blocks
    # the FastAPI event loop for the whole upload, starving every other
    # request and causing Cloudflare 502s under any concurrent load. Run
    # it in a worker thread so the loop stays responsive.
    await asyncio.to_thread(objstore.put_bytes, storage_path, image_bytes, mime)

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


# ---------------------------------------------------------------------------
# Analyze-Existing: run vision on a photo that's already in the media library.
# Feb 2026 UX redesign — Step 1 of the wizard now supports picking from the
# library instead of re-uploading. This endpoint mirrors /analyze but skips
# the persist + enhance steps because those bytes are already stored.
# ---------------------------------------------------------------------------

class AnalyzeExistingRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    asset_id: constr(min_length=1, max_length=64)


@router.post("/analyze-existing")
async def analyze_existing(
    body: AnalyzeExistingRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Run vision + menu-match on a media_assets row the user already owns.

    Behaviour mirrors /analyze but is a no-write path: we do NOT re-upload,
    re-enhance, or create new rows. The returned payload uses the SAME
    asset_id for both `original_asset_id` and `enhanced_asset_id` so the
    downstream Review step can render the same photo in both slots.
    """
    await verify_session(authorization, session_token)

    row = await db.media_assets.find_one({"id": body.asset_id}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found.")
    if row.get("kind") != "image":
        raise HTTPException(status_code=400,
                            detail=f"Asset is a {row.get('kind')!r}, not an image.")
    if row.get("status") == "archived":
        raise HTTPException(status_code=400, detail="Asset is archived.")

    storage_path = row.get("storage_path")
    if not storage_path:
        raise HTTPException(status_code=502,
                            detail="Asset has no storage path — cannot analyze.")

    # storage.get_bytes does a synchronous requests.get with a long timeout —
    # run it in a worker thread so the event loop stays responsive.
    # NOTE: returns (bytes, content_type); we only need the bytes here.
    try:
        image_bytes, _ = await asyncio.to_thread(objstore.get_bytes, storage_path)
    except Exception as e:  # noqa: BLE001
        log.exception("photo_flyer analyze-existing storage fetch failed")
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")

    log.info("PHOTO_FLYER_ANALYZE_EXISTING_START asset=%s size=%d",
             body.asset_id[:8], len(image_bytes))

    vision = await analyze_food_photo(image_bytes)
    menu_match = await match_food_to_menu(vision.get("food_type", ""), db)

    payload = {
        "original_asset_id": body.asset_id,
        "enhanced_asset_id": body.asset_id,
        "enhance_info": {"mode": "library_reuse"},
        "vision_ok": bool(vision.get("vision_ok")),
        "vision_error": vision.get("error"),
        "food_type": vision.get("food_type") or "",
        "confidence": vision.get("confidence", 0.0),
        "features": vision.get("features", []),
        "suggested_theme": vision.get("suggested_theme") or "comic_pop",
        "dominant_colors": vision.get("dominant_colors", []),
        "menu_match": menu_match,
    }
    log.info("PHOTO_FLYER_ANALYZE_EXISTING_OK asset=%s food=%r "
             "vision_ok=%s menu=%s",
             body.asset_id[:8], payload["food_type"], payload["vision_ok"],
             menu_match.get("matched"))
    return payload
