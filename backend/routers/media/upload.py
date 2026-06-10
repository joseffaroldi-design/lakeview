"""Upload endpoint — multipart image/video uploads."""
from __future__ import annotations

import logging
import subprocess
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Cookie, File, Form, Header, HTTPException, UploadFile
from PIL import Image

from auth import verify_session
import storage as objstore
from .shared import (
    ALLOWED_IMAGE, ALLOWED_VIDEO, DEFAULT_FOLDERS,
    MAX_IMAGE_BYTES, MAX_VIDEO_BYTES, TMP_DIR, _ext_from_mime, _now, db,
)

router = APIRouter()
log = logging.getLogger("uvicorn.error")


@router.post("/upload")
async def upload_media(
    file: UploadFile = File(...),
    folder: str = Form("Custom"),
    tags: str = Form(""),
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    log.info("UPLOAD_REQUEST_START filename=%r content_type=%r folder=%r",
             file.filename, file.content_type, folder)
    mime = (file.content_type or "").lower()
    if mime in ALLOWED_IMAGE:
        kind = "image"
        max_bytes = MAX_IMAGE_BYTES
    elif mime in ALLOWED_VIDEO:
        kind = "video"
        max_bytes = MAX_VIDEO_BYTES
    else:
        log.warning("UPLOAD_FAILURE filename=%r reason=unsupported_mime mime=%r", file.filename, mime)
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{mime}'. Allowed: JPG, PNG, WEBP, MP4, MOV, WEBM.")

    asset_id = str(uuid.uuid4())
    ext = _ext_from_mime(mime)
    storage_path = objstore.make_path("uploads", asset_id, ext)

    # Stream to a /tmp scratch file (avoid loading the whole file in memory
    # for 100 MB videos), enforce the size limit incrementally, then upload.
    scratch = TMP_DIR / f"{asset_id}.{ext}"
    size = 0
    try:
        with scratch.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    scratch.unlink(missing_ok=True)
                    log.warning("UPLOAD_FAILURE filename=%r reason=too_large size=%d", file.filename, size)
                    raise HTTPException(status_code=413, detail=f"File exceeds {max_bytes // (1024*1024)} MB limit.")
                f.write(chunk)

        log.info("UPLOAD_FILE_VALIDATED asset_id=%s filename=%r mime=%s size=%d", asset_id, file.filename, mime, size)

        width = height = None
        duration_seconds = None
        if kind == "image":
            try:
                with Image.open(scratch) as img:
                    width, height = img.size
            except Exception:  # noqa: BLE001
                pass
        else:
            try:
                r = subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=width,height,duration",
                     "-of", "csv=s=,:p=0", str(scratch)],
                    capture_output=True, text=True, timeout=15,
                )
                parts = r.stdout.strip().split(",")
                if len(parts) >= 2:
                    width = int(parts[0])
                    height = int(parts[1])
                if len(parts) >= 3 and parts[2] not in ("N/A", ""):
                    duration_seconds = float(parts[2])
            except Exception:  # noqa: BLE001
                pass

        # Upload to persistent object storage
        log.info("UPLOAD_STORAGE_START asset_id=%s path=%s", asset_id, storage_path)
        try:
            objstore.put_bytes(storage_path, scratch.read_bytes(), mime)
        except Exception as e:  # noqa: BLE001
            log.exception("UPLOAD_FAILURE asset_id=%s reason=storage_put_failed", asset_id)
            raise HTTPException(
                status_code=502,
                detail=f"Storage upload failed: {str(e)[:160]}",
            )
        log.info("UPLOAD_STORAGE_SUCCESS asset_id=%s path=%s", asset_id, storage_path)
    finally:
        scratch.unlink(missing_ok=True)

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    folder = folder if folder in DEFAULT_FOLDERS else "Custom"

    doc: Dict[str, Any] = {
        "id": asset_id,
        "filename": file.filename or f"{asset_id}.{ext}",
        "kind": kind,
        "mime": mime,
        "size_bytes": size,
        "width": width,
        "height": height,
        "duration_seconds": duration_seconds,
        "folder": folder,
        "tags": tag_list,
        "storage_path": storage_path,
        "is_favorite": False,
        "status": "active",
        "source": "upload",
        "uploaded_at": _now(),
        "updated_at": _now(),
    }
    log.info("UPLOAD_DB_INSERT_START asset_id=%s", asset_id)
    try:
        await db.media_assets.insert_one(doc)
    except Exception as e:  # noqa: BLE001
        log.exception("UPLOAD_FAILURE asset_id=%s reason=db_insert_failed", asset_id)
        raise HTTPException(status_code=500, detail=f"Asset record could not be saved: {str(e)[:160]}")
    log.info("UPLOAD_DB_INSERT_SUCCESS asset_id=%s", asset_id)
    response = {k: v for k, v in doc.items() if k != "_id"}
    log.info("UPLOAD_RESPONSE_SENT asset_id=%s filename=%r", asset_id, file.filename)
    return response
