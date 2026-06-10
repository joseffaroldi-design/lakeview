"""Media Studio router — image/video uploads, AI image generation, video rendering.

Endpoints (all under /api/media):
  POST   /upload              — multipart file upload (images + video)
  GET    /assets              — list with q/kind/folder/tags filters
  GET    /file/{asset_id}     — stream the file
  GET    /thumb/{asset_id}    — thumbnail (auto-generated for images, frame for video)
  PATCH  /assets/{asset_id}   — rename, retag, archive, favorite, set folder
  DELETE /assets/{asset_id}   — hard delete (file + record)
  POST   /assets/{asset_id}/duplicate

  POST   /ai-image            — enqueue async job (returns 202 + job_id immediately)
  GET    /ai-image/job/{id}   — poll for AI image job status / result
  POST   /video/render        — start a slideshow render job from N media_assets
  GET    /video/jobs          — list render jobs
  GET    /video/jobs/{job_id} — single job status
  POST   /edit                — apply crop/resize/rotate/flip/adjustments/text+logo overlay/bg-removal → new asset
  POST   /export-social       — bulk-resize one image to 1+ social presets (IG/FB/TikTok/GBP/Flyer)
  GET    /social-formats      — list preset metadata (id, label, w, h)
  GET    /folders             — distinct folders + counts
  GET    /stats               — media analytics
"""
from __future__ import annotations

import asyncio
import io
import os
import shutil
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header, Cookie, UploadFile, File, Form, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, constr
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageOps

from auth import verify_session
import storage as objstore

router = APIRouter(prefix="/media", tags=["media"])

mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]

# /tmp scratch space — only for ffmpeg pipelines that require filesystem inputs.
# All canonical media is stored in Emergent Object Storage.
TMP_DIR = Path(tempfile.gettempdir()) / "media_scratch"
TMP_DIR.mkdir(parents=True, exist_ok=True)

# Sanity check at import — warn loudly if ffmpeg is missing so operators see it in logs.
if shutil.which("ffmpeg") is None:
    import logging
    logging.getLogger("uvicorn.error").warning(
        "[media] ffmpeg binary not found on PATH — video rendering and video thumbnails will fail. "
        "Install with: apt-get install -y ffmpeg"
    )

ALLOWED_IMAGE = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_VIDEO = {"video/mp4", "video/quicktime", "video/webm"}
MAX_IMAGE_BYTES = 15 * 1024 * 1024     # 15 MB
MAX_VIDEO_BYTES = 100 * 1024 * 1024    # 100 MB
DEFAULT_FOLDERS = ["Menu Items", "Promotions", "Catering", "Events", "Logos", "Social Media", "Custom"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ext_from_mime(mime: str) -> str:
    return {
        "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp",
        "video/mp4": "mp4", "video/quicktime": "mov", "video/webm": "webm",
    }.get(mime, "bin")


@contextmanager
def _local_copy(storage_path: str, suffix: str = ""):
    """Yield a local tmp file path for an asset. Downloads from object storage
    or copies from legacy local disk. Cleans up on exit."""
    tmp = TMP_DIR / f"{uuid.uuid4().hex}{suffix or '.' + storage_path.rsplit('.', 1)[-1] if '.' in storage_path else ''}"
    try:
        objstore.download_to_tmp(storage_path, tmp)
        yield tmp
    finally:
        tmp.unlink(missing_ok=True)


async def _ensure_thumb_bytes(asset: Dict[str, Any]) -> Optional[bytes]:
    """Return JPEG thumbnail bytes for an asset. Generates lazily from the
    canonical asset bytes and caches in object storage at
    `lakeview/thumbs/{asset_id}.jpg` so subsequent fetches are O(1)."""
    thumb_path = objstore.make_path("thumbs", asset["id"], "jpg")
    # Cached?
    try:
        data, _ = objstore.get_bytes(thumb_path)
        return data
    except FileNotFoundError:
        pass
    except Exception:  # noqa: BLE001
        pass
    # Generate
    try:
        src_bytes, _ = objstore.get_bytes(asset["storage_path"])
    except FileNotFoundError:
        return None
    out = io.BytesIO()
    try:
        if asset["kind"] == "image":
            with Image.open(io.BytesIO(src_bytes)) as img:
                img = img.convert("RGB")
                w, h = img.size
                if w > 360:
                    h = int(h * 360 / w)
                    w = 360
                img.thumbnail((w, h), Image.LANCZOS)
                img.save(out, "JPEG", quality=82, optimize=True)
        else:  # video — extract frame at 1s via ffmpeg
            with _local_copy(asset["storage_path"]) as src_tmp:
                thumb_tmp = TMP_DIR / f"{uuid.uuid4().hex}.jpg"
                try:
                    subprocess.run(
                        ["ffmpeg", "-y", "-loglevel", "error", "-ss", "1",
                         "-i", str(src_tmp), "-vframes", "1", "-vf", "scale=360:-2",
                         str(thumb_tmp)],
                        check=False, timeout=20,
                    )
                    if thumb_tmp.exists():
                        out.write(thumb_tmp.read_bytes())
                finally:
                    thumb_tmp.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        return None
    data = out.getvalue()
    if not data:
        return None
    try:
        objstore.put_bytes(thumb_path, data, "image/jpeg")
    except Exception:  # noqa: BLE001
        pass  # Cache write is best-effort
    return data


# ===================== Upload + list + read =====================

@router.post("/upload")
async def upload_media(
    file: UploadFile = File(...),
    folder: str = Form("Custom"),
    tags: str = Form(""),
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    mime = (file.content_type or "").lower()
    if mime in ALLOWED_IMAGE:
        kind = "image"
        max_bytes = MAX_IMAGE_BYTES
    elif mime in ALLOWED_VIDEO:
        kind = "video"
        max_bytes = MAX_VIDEO_BYTES
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported content_type '{mime}'. Allowed: JPG/PNG/WEBP/MP4/MOV/WEBM.")

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
                    raise HTTPException(status_code=413, detail=f"File exceeds {max_bytes // (1024*1024)} MB limit.")
                f.write(chunk)

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
        objstore.put_bytes(storage_path, scratch.read_bytes(), mime)
    finally:
        scratch.unlink(missing_ok=True)

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    folder = folder if folder in DEFAULT_FOLDERS else "Custom"

    doc = {
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
    await db.media_assets.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.get("/assets")
async def list_assets(
    q: Optional[str] = None,
    kind: Optional[str] = None,
    folder: Optional[str] = None,
    status: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    limit: int = 200,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    query: Dict[str, Any] = {}
    if kind:
        query["kind"] = kind
    if folder:
        query["folder"] = folder
    if status:
        query["status"] = status
    else:
        query["status"] = {"$ne": "archived"}
    if is_favorite is not None:
        query["is_favorite"] = is_favorite
    if q:
        query["$or"] = [
            {"filename": {"$regex": q, "$options": "i"}},
            {"tags": {"$regex": q, "$options": "i"}},
        ]
    cursor = db.media_assets.find(query, {"_id": 0}).sort("uploaded_at", -1).limit(min(limit, 500))
    return {"assets": await cursor.to_list(500)}


@router.get("/file/{asset_id}")
async def get_file(asset_id: str):
    """Public — assets are publicly addressable by id (uuid4 is unguessable)."""
    asset = await db.media_assets.find_one({"id": asset_id}, {"_id": 0, "storage_path": 1, "mime": 1, "filename": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    try:
        data, _ = objstore.get_bytes(asset["storage_path"])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File missing in storage")
    headers = {"Content-Disposition": f'inline; filename="{asset.get("filename", asset_id)}"'}
    return Response(content=data, media_type=asset.get("mime") or "application/octet-stream", headers=headers)


@router.get("/thumb/{asset_id}")
async def get_thumb(asset_id: str):
    asset = await db.media_assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    thumb = await _ensure_thumb_bytes(asset)
    if thumb:
        return Response(content=thumb, media_type="image/jpeg")
    # Fallback to original (e.g. thumb generation failed)
    return await get_file(asset_id)


class AssetPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    filename: Optional[constr(min_length=1, max_length=200)] = None
    folder: Optional[constr(max_length=60)] = None
    tags: Optional[List[str]] = None
    is_favorite: Optional[bool] = None
    status: Optional[constr(pattern=r"^(active|archived)$")] = None


@router.patch("/assets/{asset_id}")
async def patch_asset(
    asset_id: str, body: AssetPatch,
    authorization: str = Header(None), session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    update = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    update["updated_at"] = _now()
    res = await db.media_assets.update_one({"id": asset_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Asset not found")
    return await db.media_assets.find_one({"id": asset_id}, {"_id": 0})


@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    """Soft-delete — Mongo row goes status='archived', file remains in storage
    (Emergent Object Storage has no delete API; bytes stay until purged out-of-band)."""
    await verify_session(authorization, session_token)
    res = await db.media_assets.update_one(
        {"id": asset_id},
        {"$set": {"status": "archived", "updated_at": _now()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"deleted": 1, "id": asset_id, "mode": "soft"}


@router.post("/assets/{asset_id}/duplicate")
async def duplicate_asset(asset_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    src = await db.media_assets.find_one({"id": asset_id}, {"_id": 0})
    if not src:
        raise HTTPException(status_code=404, detail="Asset not found")
    new_id = str(uuid.uuid4())
    ext = src["storage_path"].rsplit(".", 1)[-1]
    new_path = objstore.make_path(src.get("source", "uploads"), new_id, ext)
    try:
        data, _ = objstore.get_bytes(src["storage_path"])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Source file missing in storage")
    objstore.put_bytes(new_path, data, src.get("mime") or "application/octet-stream")
    clone = {**src, "id": new_id, "storage_path": new_path,
             "filename": f"{src['filename']} (Copy)", "is_favorite": False,
             "uploaded_at": _now(), "updated_at": _now()}
    await db.media_assets.insert_one(clone)
    return {k: v for k, v in clone.items() if k != "_id"}


# ===================== AI Image Generation =====================

class AiImageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    prompt: constr(min_length=3, max_length=2000)
    style: Optional[constr(max_length=200)] = "Food photography, natural light, appetizing, restaurant menu hero shot"
    count: int = Field(default=1, ge=1, le=4)
    quality: constr(pattern=r"^(low|medium|high)$") = "medium"
    folder: Optional[constr(max_length=60)] = "Promotions"
    headline: Optional[constr(max_length=200)] = None
    tags: Optional[List[str]] = None


# ---- Async job architecture ------------------------------------------------
# AI image generation takes ~60-85s end-to-end, which exceeds Cloudflare's 60s
# idle-connection limit in production. We therefore enqueue a background job,
# return 202 + job_id immediately, and let the frontend poll until done.
# State lives in the `ai_image_jobs` collection.

_ai_image_tasks: set = set()


def _spawn_ai_image_task(coro):
    """Fire-and-forget background task with a strong reference so it isn't GC'd."""
    task = asyncio.create_task(coro)
    _ai_image_tasks.add(task)
    task.add_done_callback(_ai_image_tasks.discard)
    return task


async def _run_ai_image_job(job_id: str, body: AiImageRequest) -> None:
    """Background worker — does the actual generation and updates job state."""
    import logging
    img_log = logging.getLogger("uvicorn.error")

    async def _update(**fields: Any) -> None:
        fields["updated_at"] = _now()
        await db.ai_image_jobs.update_one({"id": job_id}, {"$set": fields})

    async def _fail(err) -> None:
        await _update(status="failed", error=err.to_payload(), progress=0)

    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        from errors import StructuredError, report_failure
        err = StructuredError(
            code="key_missing", status=500, retryable=False,
            user_message="AI image generation isn't configured on this server. Ask your admin to set EMERGENT_LLM_KEY.",
            technical="EMERGENT_LLM_KEY env var is empty",
        )
        await report_failure(db, surface="ai_image", err=err)
        await _fail(err)
        return

    from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration

    full_prompt = body.prompt
    if body.style:
        full_prompt += f". Style: {body.style}"
    if body.headline:
        full_prompt += f". Include headline: '{body.headline}' tastefully overlaid in restaurant typography."

    await _update(status="processing", progress=10)

    client = OpenAIImageGeneration(api_key=key)
    try:
        # Background path — no Cloudflare in the loop, so we can afford a generous
        # ceiling. 180s comfortably covers worst-case 4×high-quality runs.
        image_bytes_list = await asyncio.wait_for(
            client.generate_images(
                prompt=full_prompt, model="gpt-image-1",
                number_of_images=body.count, quality=body.quality,
            ),
            timeout=180.0,
        )
    except asyncio.TimeoutError:
        from errors import StructuredError, report_failure
        err = StructuredError(
            code="timeout", status=504, retryable=True, retry_action="retry",
            user_message="Image generation took too long (over 3 minutes). Try a shorter prompt, lower quality, or fewer images.",
            technical="client.generate_images timed out after 180s",
        )
        await report_failure(db, surface="ai_image", err=err,
                             prompt=full_prompt[:120], quality=body.quality, count=body.count)
        await _fail(err)
        return
    except Exception as e:  # noqa: BLE001
        from errors import classify_llm_error, report_failure
        err = classify_llm_error(e, surface="image generation")
        img_log.exception("[ai-image] job=%s generation raised — code=%s", job_id, err.code)
        await report_failure(db, surface="ai_image", err=err,
                             prompt=full_prompt[:120], quality=body.quality, count=body.count)
        await _fail(err)
        return

    if not image_bytes_list:
        from errors import StructuredError, report_failure
        err = StructuredError(
            code="provider_empty", status=502, retryable=True, retry_action="retry",
            user_message="The AI provider returned no images. Please try again.",
            technical="empty image_bytes_list from provider",
        )
        await report_failure(db, surface="ai_image", err=err, prompt=full_prompt[:120])
        await _fail(err)
        return

    await _update(progress=80)

    saved = []
    for img_bytes in image_bytes_list:
        aid = str(uuid.uuid4())
        storage_path = objstore.make_path("ai_images", aid, "png")
        objstore.put_bytes(storage_path, img_bytes, "image/png")
        try:
            with Image.open(io.BytesIO(img_bytes)) as im:
                w, h = im.size
        except Exception:  # noqa: BLE001
            w = h = None
        doc = {
            "id": aid,
            "filename": f"ai-{(body.headline or body.prompt)[:40].replace(' ', '-')}-{aid[:6]}.png",
            "kind": "image",
            "mime": "image/png",
            "size_bytes": len(img_bytes),
            "width": w, "height": h, "duration_seconds": None,
            "folder": body.folder or "Promotions",
            "tags": (body.tags or []) + ["ai-generated"],
            "storage_path": storage_path,
            "is_favorite": False, "status": "active",
            "source": "ai_image",
            "ai_prompt": full_prompt,
            "uploaded_at": _now(), "updated_at": _now(),
        }
        await db.media_assets.insert_one(doc)
        saved.append({k: v for k, v in doc.items() if k != "_id"})

    img_log.info("[ai-image] job=%s generated %s image(s)", job_id, len(saved))
    await _update(
        status="completed",
        progress=100,
        result={"assets": saved, "count": len(saved)},
    )


@router.post("/ai-image", status_code=202)
async def enqueue_ai_image(
    body: AiImageRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Enqueue an AI image generation job and return immediately.

    Returns 202 with `{job_id, status: "pending"}` in under 1 second so Cloudflare
    never times out. The frontend polls `GET /ai-image/job/{job_id}` until the
    job reaches `completed` or `failed`.
    """
    await verify_session(authorization, session_token)

    # Fail fast if the key is missing — surface a structured error synchronously
    # so the form shows it immediately instead of via a polled job.
    if not os.environ.get("EMERGENT_LLM_KEY"):
        from errors import StructuredError, report_failure
        err = StructuredError(
            code="key_missing", status=500, retryable=False,
            user_message="AI image generation isn't configured on this server. Ask your admin to set EMERGENT_LLM_KEY.",
            technical="EMERGENT_LLM_KEY env var is empty",
        )
        await report_failure(db, surface="ai_image", err=err)
        raise HTTPException(status_code=err.status, detail=err.to_payload())

    job_id = str(uuid.uuid4())
    now = _now()
    await db.ai_image_jobs.insert_one({
        "id": job_id,
        "status": "pending",
        "prompt": body.prompt,
        "headline": body.headline,
        "style": body.style,
        "count": body.count,
        "quality": body.quality,
        "folder": body.folder,
        "tags": body.tags or [],
        "progress": 0,
        "created_at": now,
        "updated_at": now,
        "result": None,
        "error": None,
    })

    _spawn_ai_image_task(_run_ai_image_job(job_id, body))

    return {"job_id": job_id, "status": "pending"}


@router.get("/ai-image/job/{job_id}")
async def get_ai_image_job(
    job_id: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Poll endpoint — returns full job state, including `result` once complete
    or `error` (structured) on failure."""
    await verify_session(authorization, session_token)
    job = await db.ai_image_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _classify_image_error(exc: Exception) -> Dict[str, Any]:
    """Deprecated — kept only for the test fixture in test_phase8_media_studio.py.
    All production code paths now use errors.classify_llm_error directly."""
    from errors import classify_llm_error
    err = classify_llm_error(exc, surface="image generation")
    return {"code": err.code, "status": err.status, "user_message": err.user_message}


# ===================== Video Rendering =====================

class VideoRenderRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    asset_ids: List[str] = Field(min_length=1, max_length=12)
    duration_seconds: int = Field(default=30, ge=10, le=120)
    aspect: constr(pattern=r"^(1:1|4:5|9:16|16:9)$") = "9:16"
    title: Optional[constr(max_length=120)] = None
    subtitle: Optional[constr(max_length=240)] = None
    cta: Optional[constr(max_length=120)] = None
    template: Optional[constr(max_length=60)] = "menu_item_spotlight"


def _aspect_dims(aspect: str) -> tuple:
    return {
        "1:1": (1080, 1080), "4:5": (1080, 1350),
        "9:16": (1080, 1920), "16:9": (1920, 1080),
    }[aspect]


def _render_sync(job: Dict[str, Any], ordered: list, W: int, H: int, work_dir: Path) -> Path:
    """Blocking ffmpeg pipeline — runs inside asyncio.to_thread. All file paths
    live under `work_dir` (a /tmp subdir) for the duration of the render."""
    per = max(2.0, job["duration_seconds"] / max(1, len(ordered)))
    src_paths: List[Path] = []
    # Download each source asset to the work dir
    for i, asset in enumerate(ordered):
        ext = asset["storage_path"].rsplit(".", 1)[-1] if "." in asset["storage_path"] else "bin"
        local = work_dir / f"src_{i}.{ext}"
        objstore.download_to_tmp(asset["storage_path"], local)
        src_paths.append(local)

    clip_paths = []
    for i, (asset, src) in enumerate(zip(ordered, src_paths)):
        clip = work_dir / f"clip_{i}.mp4"
        if asset["kind"] == "image":
            cmd = ["ffmpeg", "-y", "-loglevel", "error",
                   "-loop", "1", "-i", str(src),
                   "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=yuv420p",
                   "-t", f"{per:.2f}", "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                   str(clip)]
        else:
            cmd = ["ffmpeg", "-y", "-loglevel", "error",
                   "-i", str(src),
                   "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=yuv420p",
                   "-t", f"{per:.2f}", "-r", "30", "-an", "-c:v", "libx264",
                   str(clip)]
        subprocess.run(cmd, check=True, timeout=60, capture_output=True)
        clip_paths.append(clip)

    concat_file = work_dir / "concat.txt"
    concat_file.write_text("\n".join(f"file '{p}'" for p in clip_paths))
    out_path = work_dir / "final.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(concat_file), "-c", "copy", str(out_path)],
        check=True, timeout=120, capture_output=True,
    )

    if job.get("title"):
        titled = work_dir / "titled.mp4"
        txt = (job.get("title") or "").replace(":", r"\:").replace("'", r"\'")
        cta = (job.get("cta") or "").replace(":", r"\:").replace("'", r"\'")
        vf = (
            f"drawtext=text='{txt}':fontcolor=white:fontsize=60:"
            f"x=(w-text_w)/2:y=h*0.08:box=1:boxcolor=black@0.5:boxborderw=20:enable='lte(t,3.0)'"
        )
        if cta:
            vf += (
                f",drawtext=text='{cta}':fontcolor=white:fontsize=44:"
                f"x=(w-text_w)/2:y=h*0.88:box=1:boxcolor=#C8A95E@0.85:boxborderw=15"
            )
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(out_path),
                 "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(titled)],
                check=True, timeout=120,
            )
            if titled.exists() and titled.stat().st_size > 1000:
                out_path = titled
        except subprocess.CalledProcessError:
            pass  # drawtext is best-effort

    return out_path


async def _run_render_job(job_id: str):
    """Background worker — composites a slideshow using ffmpeg (off the event loop)."""
    job = await db.render_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        return
    work_dir = TMP_DIR / f"render_{job_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        await db.render_jobs.update_one({"id": job_id}, {"$set": {"status": "processing", "progress": 0.1, "updated_at": _now()}})
        assets = await db.media_assets.find({"id": {"$in": job["asset_ids"]}}, {"_id": 0}).to_list(20)
        assets_by_id = {a["id"]: a for a in assets}
        ordered = [assets_by_id[aid] for aid in job["asset_ids"] if aid in assets_by_id]
        if not ordered:
            raise RuntimeError("No usable source assets")
        W, H = _aspect_dims(job["aspect"])
        out_path = await asyncio.to_thread(_render_sync, job, ordered, W, H, work_dir)

        # Upload the result to persistent object storage
        new_id = str(uuid.uuid4())
        storage_path = objstore.make_path("renders", new_id, "mp4")
        video_bytes = out_path.read_bytes()
        objstore.put_bytes(storage_path, video_bytes, "video/mp4")

        asset_doc = {
            "id": new_id,
            "filename": f"render-{job['template']}-{new_id[:6]}.mp4",
            "kind": "video", "mime": "video/mp4",
            "size_bytes": len(video_bytes),
            "width": W, "height": H, "duration_seconds": job["duration_seconds"],
            "folder": "Promotions", "tags": ["rendered", job.get("template") or "menu_item_spotlight"],
            "storage_path": storage_path, "is_favorite": False, "status": "active",
            "source": "video_render", "render_job_id": job_id,
            "uploaded_at": _now(), "updated_at": _now(),
        }
        await db.media_assets.insert_one(asset_doc)
        await db.render_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "completed", "progress": 1.0, "output_asset_id": new_id,
                      "completed_at": _now(), "updated_at": _now()}},
        )
    except FileNotFoundError as e:
        from errors import classify_render_error, report_failure
        err = await report_failure(db, surface="video_render",
                                   err=classify_render_error(e),
                                   job_id=job_id)
        await db.render_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "failed", "error": err.to_payload(), "updated_at": _now()}},
        )
    except subprocess.CalledProcessError as e:
        from errors import classify_render_error, report_failure
        stderr = (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, (bytes, bytearray)) else (e.stderr or "")
        err = await report_failure(db, surface="video_render",
                                   err=classify_render_error(returncode=e.returncode, stderr=stderr),
                                   job_id=job_id, returncode=e.returncode)
        await db.render_jobs.update_one(
            {"id": job_id}, {"$set": {"status": "failed", "error": err.to_payload(), "updated_at": _now()}},
        )
    except Exception as e:  # noqa: BLE001
        from errors import classify_render_error, report_failure
        err = await report_failure(db, surface="video_render",
                                   err=classify_render_error(e),
                                   job_id=job_id)
        await db.render_jobs.update_one(
            {"id": job_id}, {"$set": {"status": "failed", "error": err.to_payload(), "updated_at": _now()}},
        )
    finally:
        # Always cleanup the scratch dir
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:  # noqa: BLE001
            pass


@router.post("/video/render")
async def start_render(
    body: VideoRenderRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    if shutil.which("ffmpeg") is None:
        from errors import StructuredError, report_failure
        err = await report_failure(db, surface="video_render",
                                   err=StructuredError(
                                       code="ffmpeg_missing", status=503, retryable=True,
                                       retry_action="restart_backend",
                                       user_message="Video rendering is unavailable: ffmpeg isn't installed on the server. The backend will auto-install it on the next restart. Try again in 30 seconds.",
                                       technical="shutil.which('ffmpeg') returned None at request time",
                                   ))
        raise HTTPException(status_code=err.status, detail=err.to_payload())
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id, "asset_ids": body.asset_ids,
        "duration_seconds": body.duration_seconds, "aspect": body.aspect,
        "title": body.title, "subtitle": body.subtitle, "cta": body.cta,
        "template": body.template,
        "status": "queued", "progress": 0.0, "error": None,
        "output_asset_id": None,
        "created_at": _now(), "updated_at": _now(),
    }
    await db.render_jobs.insert_one(job)
    asyncio.create_task(_run_render_job(job_id))
    return {k: v for k, v in job.items() if k != "_id"}


@router.get("/video/jobs")
async def list_render_jobs(
    limit: int = 50,
    authorization: str = Header(None), session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    docs = await db.render_jobs.find({}, {"_id": 0}).sort("created_at", -1).limit(min(limit, 200)).to_list(200)
    return {"jobs": docs}


@router.get("/video/jobs/{job_id}")
async def get_render_job(job_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    job = await db.render_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ===================== Folders + Stats =====================

@router.get("/folders")
async def list_folders(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    agg = await db.media_assets.aggregate([
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$folder", "count": {"$sum": 1}}},
    ]).to_list(50)
    counts = {row["_id"]: row["count"] for row in agg if row.get("_id")}
    out = [{"name": f, "count": counts.get(f, 0)} for f in DEFAULT_FOLDERS]
    return {"folders": out}


@router.get("/stats")
async def media_stats(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    images_total = await db.media_assets.count_documents({"kind": "image", "status": "active"})
    videos_total = await db.media_assets.count_documents({"kind": "video", "status": "active"})
    ai_images = await db.media_assets.count_documents({"source": "ai_image", "status": "active"})
    rendered = await db.media_assets.count_documents({"source": "video_render", "status": "active"})
    jobs_active = await db.render_jobs.count_documents({"status": {"$in": ["queued", "processing"]}})
    return {
        "images_uploaded": images_total - ai_images,
        "videos_uploaded": videos_total - rendered,
        "ai_images_generated": ai_images,
        "videos_rendered": rendered,
        "active_render_jobs": jobs_active,
        "total_assets": images_total + videos_total,
    }


# ===================== AI Image Editor =====================

SOCIAL_FORMATS: Dict[str, tuple] = {
    "ig_post_1_1":      (1080, 1080),
    "ig_portrait_4_5":  (1080, 1350),
    "ig_reel_9_16":     (1080, 1920),
    "fb_post":          (1200, 630),
    "fb_story":         (1080, 1920),
    "tiktok_9_16":      (1080, 1920),
    "gbp_image":        (1200, 900),
    "flyer_8_5_11":     (2550, 3300),
}

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _load_font(size: int) -> ImageFont.ImageFont:
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size=size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def _hex_to_rgb(s: str, default=(255, 255, 255)) -> tuple:
    try:
        s = s.lstrip("#")
        if len(s) == 3:
            s = "".join(c * 2 for c in s)
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:  # noqa: BLE001
        return default


class CropBox(BaseModel):
    model_config = ConfigDict(extra="ignore")
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(gt=0)
    h: int = Field(gt=0)


class TextOverlay(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: constr(min_length=1, max_length=200)
    x_pct: float = Field(default=0.5, ge=0.0, le=1.0)  # 0..1, anchor center
    y_pct: float = Field(default=0.85, ge=0.0, le=1.0)
    size_pct: float = Field(default=0.06, ge=0.02, le=0.25)  # of image height
    color: constr(pattern=r"^#?[0-9a-fA-F]{3,8}$") = "#FFFFFF"
    background: Optional[constr(pattern=r"^#?[0-9a-fA-F]{3,8}$")] = None  # box bg
    background_opacity: float = Field(default=0.55, ge=0.0, le=1.0)
    align: constr(pattern=r"^(left|center|right)$") = "center"


class LogoOverlay(BaseModel):
    model_config = ConfigDict(extra="ignore")
    logo_asset_id: str
    x_pct: float = Field(default=0.05, ge=0.0, le=1.0)  # anchor: top-left of logo
    y_pct: float = Field(default=0.05, ge=0.0, le=1.0)
    width_pct: float = Field(default=0.18, ge=0.05, le=0.6)  # of image width
    opacity: float = Field(default=1.0, ge=0.2, le=1.0)


class EditImageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_asset_id: str
    crop: Optional[CropBox] = None
    resize_w: Optional[int] = Field(default=None, gt=0, le=5000)
    resize_h: Optional[int] = Field(default=None, gt=0, le=5000)
    rotate: int = Field(default=0)  # 0/90/180/270
    flip_horizontal: bool = False
    brightness: float = Field(default=1.0, ge=0.3, le=2.0)
    contrast: float = Field(default=1.0, ge=0.3, le=2.0)
    saturation: float = Field(default=1.0, ge=0.0, le=2.0)
    sharpness: float = Field(default=1.0, ge=0.0, le=3.0)
    remove_background: bool = False
    bg_color: Optional[constr(pattern=r"^#?[0-9a-fA-F]{3,8}$")] = None  # fill after bg removal
    text_overlay: Optional[TextOverlay] = None
    logo_overlay: Optional[LogoOverlay] = None
    folder: Optional[constr(max_length=60)] = None
    filename: Optional[constr(max_length=160)] = None
    tags: Optional[List[str]] = None


def _apply_edits(img: Image.Image, body: EditImageRequest, logo_path: Optional[Path]) -> Image.Image:
    """Pure-PIL pipeline. Returns RGB(A) image. Background removal handled by caller."""
    # Crop
    if body.crop:
        c = body.crop
        x2 = min(img.width, c.x + c.w)
        y2 = min(img.height, c.y + c.h)
        img = img.crop((c.x, c.y, x2, y2))

    # Rotate (0/90/180/270)
    if body.rotate in (90, 180, 270):
        img = img.rotate(-body.rotate, expand=True)

    # Flip
    if body.flip_horizontal:
        img = ImageOps.mirror(img)

    # Resize
    if body.resize_w or body.resize_h:
        target_w = body.resize_w or int(img.width * (body.resize_h / img.height))
        target_h = body.resize_h or int(img.height * (body.resize_w / img.width))
        img = img.resize((target_w, target_h), Image.LANCZOS)

    # Adjustments — must be RGB for ImageEnhance.Color
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    if body.brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(body.brightness)
    if body.contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(body.contrast)
    if body.saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(body.saturation)
    if body.sharpness != 1.0:
        img = ImageEnhance.Sharpness(img).enhance(body.sharpness)

    # Logo overlay
    if body.logo_overlay and logo_path and logo_path.exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            target_w = int(img.width * body.logo_overlay.width_pct)
            ratio = target_w / max(1, logo.width)
            target_h = max(1, int(logo.height * ratio))
            logo = logo.resize((target_w, target_h), Image.LANCZOS)
            if body.logo_overlay.opacity < 1.0:
                alpha = logo.split()[3].point(lambda p: int(p * body.logo_overlay.opacity))
                logo.putalpha(alpha)
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            x = int(img.width * body.logo_overlay.x_pct)
            y = int(img.height * body.logo_overlay.y_pct)
            img.paste(logo, (x, y), logo)
        except Exception:  # noqa: BLE001
            pass

    # Text overlay
    if body.text_overlay:
        t = body.text_overlay
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font_size = max(10, int(img.height * t.size_pct))
        font = _load_font(font_size)
        # Measure
        try:
            bbox = draw.textbbox((0, 0), t.text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:  # noqa: BLE001
            tw, th = font_size * len(t.text) // 2, font_size
        cx = int(img.width * t.x_pct)
        cy = int(img.height * t.y_pct)
        if t.align == "left":
            tx = cx
        elif t.align == "right":
            tx = cx - tw
        else:
            tx = cx - tw // 2
        ty = cy - th // 2
        # Box background
        if t.background:
            pad = max(8, font_size // 4)
            r, g, b = _hex_to_rgb(t.background, (0, 0, 0))
            a = int(255 * t.background_opacity)
            draw.rectangle([tx - pad, ty - pad, tx + tw + pad, ty + th + pad], fill=(r, g, b, a))
        # Text — black stroke for readability
        fill = _hex_to_rgb(t.color, (255, 255, 255))
        try:
            draw.text((tx, ty), t.text, font=font, fill=fill + (255,),
                      stroke_width=max(1, font_size // 24), stroke_fill=(0, 0, 0, 220))
        except TypeError:  # very old PIL
            draw.text((tx, ty), t.text, font=font, fill=fill + (255,))
        img = Image.alpha_composite(img, overlay)

    return img


def _remove_background(src: Path) -> bytes:
    """Run rembg in a thread (CPU bound, downloads model on first call)."""
    from rembg import remove
    with open(src, "rb") as f:
        return remove(f.read())


@router.post("/edit")
async def edit_image(
    body: EditImageRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Apply crop/rotate/resize/adjustments/text/logo/background-removal. Saves a NEW asset."""
    await verify_session(authorization, session_token)
    from errors import StructuredError, report_failure
    src_asset = await db.media_assets.find_one({"id": body.source_asset_id}, {"_id": 0})
    if not src_asset or src_asset.get("kind") != "image":
        err = await report_failure(db, surface="image_edit", err=StructuredError(
            code="asset_missing", status=404, retryable=False, retry_action="pick_assets",
            user_message="The image you tried to edit was deleted or isn't an image. Pick a different source from the Asset Library.",
            technical=f"media_assets({body.source_asset_id}) not found or wrong kind",
        ), source_asset_id=body.source_asset_id)
        raise HTTPException(status_code=err.status, detail=err.to_payload())
    # Download source to /tmp scratch for PIL/rembg
    src_scratch = TMP_DIR / f"src_{uuid.uuid4().hex}.{src_asset['storage_path'].rsplit('.', 1)[-1]}"
    try:
        objstore.download_to_tmp(src_asset["storage_path"], src_scratch)
    except FileNotFoundError:
        err = await report_failure(db, surface="image_edit", err=StructuredError(
            code="asset_missing", status=404, retryable=False, retry_action="pick_assets",
            user_message="The image file is missing in storage. Re-upload it and try again.",
            technical=f"object missing: {src_asset['storage_path']}",
        ), source_asset_id=body.source_asset_id)
        raise HTTPException(status_code=err.status, detail=err.to_payload())

    logo_scratch: Optional[Path] = None
    if body.logo_overlay:
        logo_asset = await db.media_assets.find_one({"id": body.logo_overlay.logo_asset_id}, {"_id": 0})
        if logo_asset and logo_asset.get("kind") == "image":
            logo_scratch = TMP_DIR / f"logo_{uuid.uuid4().hex}.{logo_asset['storage_path'].rsplit('.', 1)[-1]}"
            try:
                objstore.download_to_tmp(logo_asset["storage_path"], logo_scratch)
            except FileNotFoundError:
                logo_scratch = None

    try:
        # Background removal first (separate thread — slow)
        if body.remove_background:
            try:
                png_bytes = await asyncio.to_thread(_remove_background, src_scratch)
                base = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
            except Exception as e:  # noqa: BLE001
                err = await report_failure(db, surface="image_edit", err=StructuredError(
                    code="provider_unavailable", status=502, retryable=True, retry_action="retry",
                    user_message="Background removal failed. The AI model may still be downloading — wait 30 seconds and try again. (First-ever run can take 60s.)",
                    technical=str(e)[:400],
                ), source_asset_id=body.source_asset_id)
                raise HTTPException(status_code=err.status, detail=err.to_payload())
            if body.bg_color:
                bg = Image.new("RGBA", base.size, _hex_to_rgb(body.bg_color, (255, 255, 255)) + (255,))
                base = Image.alpha_composite(bg, base)
        else:
            base = Image.open(src_scratch)
            base.load()

        edited = None
        try:
            edited = await asyncio.to_thread(_apply_edits, base, body, logo_scratch)
        except Exception as e:  # noqa: BLE001
            err = await report_failure(db, surface="image_edit", err=StructuredError(
                code="asset_invalid", status=500, retryable=True, retry_action="retry",
                user_message="The image editor crashed while applying changes. Try simpler adjustments (smaller crop, less text) or use a different source image.",
                technical=str(e)[:400],
            ), source_asset_id=body.source_asset_id)
            raise HTTPException(status_code=err.status, detail=err.to_payload())
        finally:
            if edited is not None and base is not edited:
                try:
                    base.close()
                except Exception:  # noqa: BLE001
                    pass

        # Save — PNG if alpha channel present, otherwise JPEG
        has_alpha = edited.mode == "RGBA" and edited.getextrema()[3][0] < 255
        new_id = str(uuid.uuid4())
        if has_alpha or body.remove_background:
            ext = "png"
            save_kwargs = {"format": "PNG", "optimize": True}
            mime = "image/png"
        else:
            if edited.mode == "RGBA":
                edited = edited.convert("RGB")
            ext = "jpg"
            save_kwargs = {"format": "JPEG", "quality": 90, "optimize": True}
            mime = "image/jpeg"
        storage_path = objstore.make_path("edits", new_id, ext)
        buf = io.BytesIO()
        edited.save(buf, **save_kwargs)
        out_bytes = buf.getvalue()
        objstore.put_bytes(storage_path, out_bytes, mime)

        src_name = src_asset.get("filename", "edited.png").rsplit(".", 1)[0]
        final_filename = body.filename or f"{src_name}-edited-{new_id[:6]}.{ext}"
        tags = (body.tags or []) + ["edited"]
        if body.remove_background:
            tags.append("bg-removed")

        doc = {
            "id": new_id,
            "filename": final_filename,
            "kind": "image",
            "mime": mime,
            "size_bytes": len(out_bytes),
            "width": edited.width, "height": edited.height, "duration_seconds": None,
            "folder": body.folder or src_asset.get("folder", "Custom"),
            "tags": tags,
            "storage_path": storage_path,
            "is_favorite": False, "status": "active",
            "source": "image_edit",
            "source_asset_id": body.source_asset_id,
            "edit_params": body.model_dump(exclude_none=True, exclude={"source_asset_id"}),
            "uploaded_at": _now(), "updated_at": _now(),
        }
        await db.media_assets.insert_one(doc)
        return {k: v for k, v in doc.items() if k != "_id"}
    finally:
        src_scratch.unlink(missing_ok=True)
        if logo_scratch:
            logo_scratch.unlink(missing_ok=True)


# ===================== Social Format Export =====================

class SocialExportRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_asset_id: str
    formats: List[constr(min_length=2, max_length=40)] = Field(min_length=1, max_length=12)
    fit: constr(pattern=r"^(cover|contain)$") = "cover"
    bg_color: constr(pattern=r"^#?[0-9a-fA-F]{3,8}$") = "#FFFFFF"
    folder: Optional[constr(max_length=60)] = "Social Media"


def _fit_to(img: Image.Image, target_w: int, target_h: int, mode: str, bg: tuple) -> Image.Image:
    """`cover` = scale+crop to fill; `contain` = scale+pad with bg."""
    src_ratio = img.width / img.height
    tgt_ratio = target_w / target_h
    if mode == "cover":
        if src_ratio > tgt_ratio:
            new_h = target_h
            new_w = int(target_h * src_ratio)
        else:
            new_w = target_w
            new_h = int(target_w / src_ratio)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        x = (new_w - target_w) // 2
        y = (new_h - target_h) // 2
        return resized.crop((x, y, x + target_w, y + target_h))
    # contain
    if src_ratio > tgt_ratio:
        new_w = target_w
        new_h = int(target_w / src_ratio)
    else:
        new_h = target_h
        new_w = int(target_h * src_ratio)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), bg)
    canvas.paste(resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
    return canvas


@router.post("/export-social")
async def export_social(
    body: SocialExportRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Generate sized copies of one image for IG/FB/TikTok/GBP/Flyer."""
    await verify_session(authorization, session_token)
    from errors import StructuredError, report_failure
    src_asset = await db.media_assets.find_one({"id": body.source_asset_id}, {"_id": 0})
    if not src_asset or src_asset.get("kind") != "image":
        err = await report_failure(db, surface="social_export", err=StructuredError(
            code="asset_missing", status=404, retryable=False, retry_action="pick_assets",
            user_message="The source image was deleted or isn't an image. Pick a different one from the Asset Library.",
            technical=f"media_assets({body.source_asset_id}) not found or wrong kind",
        ), source_asset_id=body.source_asset_id)
        raise HTTPException(status_code=err.status, detail=err.to_payload())
    src_scratch = TMP_DIR / f"src_{uuid.uuid4().hex}.{src_asset['storage_path'].rsplit('.', 1)[-1]}"
    try:
        try:
            objstore.download_to_tmp(src_asset["storage_path"], src_scratch)
        except FileNotFoundError:
            err = await report_failure(db, surface="social_export", err=StructuredError(
                code="asset_missing", status=404, retryable=False, retry_action="pick_assets",
                user_message="The image file is missing in storage. Re-upload it and try again.",
                technical=f"object missing: {src_asset['storage_path']}",
            ), source_asset_id=body.source_asset_id)
            raise HTTPException(status_code=err.status, detail=err.to_payload())

        bg = _hex_to_rgb(body.bg_color, (255, 255, 255))
        unknown = [f for f in body.formats if f not in SOCIAL_FORMATS]
        if unknown:
            err = await report_failure(db, surface="social_export", err=StructuredError(
                code="prompt_invalid", status=400, retryable=False,
                user_message=f"These social format names aren't supported: {', '.join(unknown)}. Use the preset chips in the UI.",
                technical=f"unknown formats requested: {unknown}",
            ), formats=body.formats)
            raise HTTPException(status_code=err.status, detail=err.to_payload())

        saved: List[Dict[str, Any]] = []
        try:
            base = Image.open(src_scratch).convert("RGB")
            base.load()
        except Exception as e:  # noqa: BLE001
            err = await report_failure(db, surface="social_export", err=StructuredError(
                code="asset_invalid", status=422, retryable=False, retry_action="pick_assets",
                user_message="The source image is corrupted or in an unsupported format. Re-upload it or pick a different one.",
                technical=str(e)[:300],
            ), source_asset_id=body.source_asset_id)
            raise HTTPException(status_code=err.status, detail=err.to_payload())

        for fmt in body.formats:
            tw, th = SOCIAL_FORMATS[fmt]
            out = await asyncio.to_thread(_fit_to, base, tw, th, body.fit, bg)
            aid = str(uuid.uuid4())
            storage_path = objstore.make_path("exports", aid, "jpg")
            buf = io.BytesIO()
            out.save(buf, format="JPEG", quality=90, optimize=True)
            out_bytes = buf.getvalue()
            objstore.put_bytes(storage_path, out_bytes, "image/jpeg")
            src_name = src_asset.get("filename", "image").rsplit(".", 1)[0]
            doc = {
                "id": aid,
                "filename": f"{src_name}-{fmt}-{aid[:6]}.jpg",
                "kind": "image", "mime": "image/jpeg",
                "size_bytes": len(out_bytes),
                "width": tw, "height": th, "duration_seconds": None,
                "folder": body.folder or "Social Media",
                "tags": [fmt, "social-export", body.fit],
                "storage_path": storage_path,
                "is_favorite": False, "status": "active",
                "source": "social_export",
                "source_asset_id": body.source_asset_id,
                "uploaded_at": _now(), "updated_at": _now(),
            }
            await db.media_assets.insert_one(doc)
            saved.append({k: v for k, v in doc.items() if k != "_id"})
    finally:
        src_scratch.unlink(missing_ok=True)

    return {"assets": saved, "count": len(saved)}


@router.get("/social-formats")
async def list_social_formats(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    labels = {
        "ig_post_1_1":      "Instagram Post (1:1)",
        "ig_portrait_4_5":  "Instagram Portrait (4:5)",
        "ig_reel_9_16":     "Instagram Reel / Story (9:16)",
        "fb_post":          "Facebook Post (1200×630)",
        "fb_story":         "Facebook Story (9:16)",
        "tiktok_9_16":      "TikTok Vertical (9:16)",
        "gbp_image":        "Google Business Profile (4:3)",
        "flyer_8_5_11":     "Flyer 8.5×11\" @ 300 DPI",
    }
    return {
        "formats": [
            {"id": k, "label": labels[k], "width": w, "height": h}
            for k, (w, h) in SOCIAL_FORMATS.items()
        ]
    }


# ===================== Health & Maintenance =====================

@router.get("/health")
async def media_health(authorization: str = Header(None), session_token: str = Cookie(None)):
    """Operational health probe — exposes ffmpeg + rembg + storage + render + AI image queues."""
    await verify_session(authorization, session_token)
    ffmpeg_path = shutil.which("ffmpeg")

    # rembg state (lazy import so health works even if bootstrap fails)
    rembg = {"available": False, "model_ready": False, "error": "not initialized"}
    try:
        from bootstrap import rembg_state
        rembg = rembg_state()
    except Exception as e:  # noqa: BLE001
        rembg["error"] = str(e)[:200]

    # Object storage probe (PUT + GET roundtrip)
    storage_health = await asyncio.to_thread(objstore.health)

    # Render queue
    render_q = {"queued": 0, "processing": 0, "completed_recent": 0, "failed_recent": 0}
    # AI image queue
    aij_q = {"pending": 0, "processing": 0, "completed_recent": 0, "failed_recent": 0}
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    try:
        render_q["queued"] = await db.render_jobs.count_documents({"status": "queued"})
        render_q["processing"] = await db.render_jobs.count_documents({"status": "processing"})
        render_q["completed_recent"] = await db.render_jobs.count_documents({"status": "completed", "updated_at": {"$gte": since}})
        render_q["failed_recent"] = await db.render_jobs.count_documents({"status": "failed", "updated_at": {"$gte": since}})
        aij_q["pending"] = await db.ai_image_jobs.count_documents({"status": "pending"})
        aij_q["processing"] = await db.ai_image_jobs.count_documents({"status": "processing"})
        aij_q["completed_recent"] = await db.ai_image_jobs.count_documents({"status": "completed", "updated_at": {"$gte": since}})
        aij_q["failed_recent"] = await db.ai_image_jobs.count_documents({"status": "failed", "updated_at": {"$gte": since}})
    except Exception:  # noqa: BLE001
        pass

    # Stale-job counts (over 5 min in pending/processing without progress) → janitor will sweep at next startup
    stale_threshold = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    try:
        stale_aij = await db.ai_image_jobs.count_documents({"status": {"$in": ["pending", "processing"]}, "updated_at": {"$lt": stale_threshold}})
        stale_render = await db.render_jobs.count_documents({"status": {"$in": ["queued", "processing"]}, "updated_at": {"$lt": stale_threshold}})
    except Exception:  # noqa: BLE001
        stale_aij = stale_render = 0

    asset_count = await db.media_assets.count_documents({"status": "active"})

    healthy = (
        ffmpeg_path is not None
        and rembg.get("model_ready")
        and storage_health.get("reachable")
        and render_q["processing"] < 10
        and stale_aij == 0
        and stale_render == 0
    )
    return {
        "healthy": healthy,
        "ffmpeg_available": ffmpeg_path is not None,
        "ffmpeg_path": ffmpeg_path,
        "rembg_available": rembg.get("available", False),
        "rembg_model_ready": rembg.get("model_ready", False),
        "rembg_error": rembg.get("error"),
        "storage": storage_health,
        "asset_count": asset_count,
        "stale_ai_image_jobs": stale_aij,
        "stale_render_jobs": stale_render,
        "render_queue": render_q,
        "ai_image_queue": aij_q,
    }


async def cleanup_orphan_render_jobs():
    """Mark queued/processing jobs as failed at startup — they're from a previous worker process."""
    orphan_err = {
        "code": "unknown", "status": 500, "retryable": True, "retry_action": "retry_render",
        "user_message": "This render was interrupted by a server restart. Click Try again to re-queue it.",
        "technical": "backend restarted with job in queued/processing state",
        "context": {},
    }
    r = await db.render_jobs.update_many(
        {"status": {"$in": ["queued", "processing"]}},
        {"$set": {"status": "failed",
                  "error": orphan_err,
                  "updated_at": _now()}},
    )
    if r.modified_count > 0:
        import logging
        logging.getLogger("uvicorn.error").info(
            f"[media] Marked {r.modified_count} orphan render job(s) as failed at startup"
        )


async def cleanup_orphan_ai_image_jobs():
    """Mark pending/processing AI image jobs as failed at startup. The background
    `asyncio.create_task` lives only in the previous process; once we restart,
    those tasks are gone forever. Without this sweep the UI polls indefinitely.

    Threshold: any job currently in pending/processing is orphaned by definition
    when the server (re)starts — no live process is driving it. We don't filter
    by age because the new process starts with an empty task set."""
    orphan_err = {
        "code": "unknown",
        "status": 500,
        "retryable": True,
        "retry_action": "retry",
        "user_message": "This image generation was interrupted by a server restart. Click Try again to regenerate.",
        "technical": "backend restarted with job in pending/processing state",
        "context": {},
    }
    r = await db.ai_image_jobs.update_many(
        {"status": {"$in": ["pending", "processing"]}},
        {"$set": {"status": "failed", "error": orphan_err, "progress": 0, "updated_at": _now()}},
    )
    if r.modified_count > 0:
        import logging
        logging.getLogger("uvicorn.error").info(
            f"[media] Marked {r.modified_count} orphan ai_image_job(s) as failed at startup"
        )


@router.get("/audit")
async def list_audit_failures(
    surface: Optional[str] = None,
    code: Optional[str] = None,
    limit: int = 50,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Recent failures across all surfaces — for the admin to spot patterns."""
    await verify_session(authorization, session_token)
    q: Dict[str, Any] = {}
    if surface:
        q["surface"] = surface
    if code:
        q["code"] = code
    cursor = db.failure_audit_log.find(q, {"_id": 0}).sort("created_at", -1).limit(min(limit, 200))
    entries = await cursor.to_list(min(limit, 200))
    # Aggregate by code for quick triage
    by_code: Dict[str, int] = {}
    for e in entries:
        by_code[e.get("code", "unknown")] = by_code.get(e.get("code", "unknown"), 0) + 1
    return {
        "entries": entries,
        "count": len(entries),
        "by_code": by_code,
    }

