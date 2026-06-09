"""Media Studio router — image/video uploads, AI image generation, video rendering.

Endpoints (all under /api/media):
  POST   /upload              — multipart file upload (images + video)
  GET    /assets              — list with q/kind/folder/tags filters
  GET    /file/{asset_id}     — stream the file
  GET    /thumb/{asset_id}    — thumbnail (auto-generated for images, frame for video)
  PATCH  /assets/{asset_id}   — rename, retag, archive, favorite, set folder
  DELETE /assets/{asset_id}   — hard delete (file + record)
  POST   /assets/{asset_id}/duplicate

  POST   /ai-image            — generate AI image(s) via emergent LLM (gpt-image-1)
  POST   /video/render        — start a slideshow render job from N media_assets
  GET    /video/jobs          — list render jobs
  GET    /video/jobs/{job_id} — single job status
  GET    /folders             — distinct folders + counts
  GET    /stats               — media analytics
"""
from __future__ import annotations

import asyncio
import io
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header, Cookie, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, constr
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image

from auth import verify_session

router = APIRouter(prefix="/media", tags=["media"])

mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]

STORAGE_DIR = Path(os.environ.get("MEDIA_STORAGE_DIR", "/app/backend/media_storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
THUMBS_DIR = STORAGE_DIR / ".thumbs"
THUMBS_DIR.mkdir(exist_ok=True)
RENDERS_DIR = STORAGE_DIR / ".renders"
RENDERS_DIR.mkdir(exist_ok=True)

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


async def _ensure_thumb(asset: Dict[str, Any]) -> Path:
    """Generate and cache a 360px-wide thumbnail. Returns its path."""
    thumb_path = THUMBS_DIR / f"{asset['id']}.jpg"
    if thumb_path.exists():
        return thumb_path
    src = STORAGE_DIR / asset["storage_path"]
    try:
        if asset["kind"] == "image":
            with Image.open(src) as img:
                img = img.convert("RGB")
                w, h = img.size
                if w > 360:
                    h = int(h * 360 / w); w = 360
                img.thumbnail((w, h), Image.LANCZOS)
                img.save(thumb_path, "JPEG", quality=82, optimize=True)
        else:  # video — extract frame at 1s
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-ss", "1",
                 "-i", str(src), "-vframes", "1", "-vf", "scale=360:-2",
                 str(thumb_path)],
                check=False, timeout=20,
            )
    except Exception:  # noqa: BLE001
        # If thumbnail generation fails, leave it — caller falls back to /file
        pass
    return thumb_path


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
        kind = "image"; max_bytes = MAX_IMAGE_BYTES
    elif mime in ALLOWED_VIDEO:
        kind = "video"; max_bytes = MAX_VIDEO_BYTES
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported content_type '{mime}'. Allowed: JPG/PNG/WEBP/MP4/MOV/WEBM.")

    asset_id = str(uuid.uuid4())
    ext = _ext_from_mime(mime)
    rel_path = f"{asset_id}.{ext}"
    dest = STORAGE_DIR / rel_path

    # Stream to disk in chunks (avoids loading the whole file in memory)
    size = 0
    with dest.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"File exceeds {max_bytes // (1024*1024)} MB limit.")
            f.write(chunk)

    width = height = None
    duration_seconds = None
    if kind == "image":
        try:
            with Image.open(dest) as img:
                width, height = img.size
        except Exception:  # noqa: BLE001
            pass
    else:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height,duration",
                 "-of", "csv=s=,:p=0", str(dest)],
                capture_output=True, text=True, timeout=15,
            )
            parts = r.stdout.strip().split(",")
            if len(parts) >= 2:
                width = int(parts[0]); height = int(parts[1])
            if len(parts) >= 3 and parts[2] not in ("N/A", ""):
                duration_seconds = float(parts[2])
        except Exception:  # noqa: BLE001
            pass

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    folder = folder if folder in DEFAULT_FOLDERS else "Custom"

    doc = {
        "id": asset_id,
        "filename": file.filename or rel_path,
        "kind": kind,
        "mime": mime,
        "size_bytes": size,
        "width": width,
        "height": height,
        "duration_seconds": duration_seconds,
        "folder": folder,
        "tags": tag_list,
        "storage_path": rel_path,
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
    path = STORAGE_DIR / asset["storage_path"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(str(path), media_type=asset.get("mime"), filename=asset.get("filename"))


@router.get("/thumb/{asset_id}")
async def get_thumb(asset_id: str):
    asset = await db.media_assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    thumb = await _ensure_thumb(asset)
    if not thumb.exists():
        # Fallback to original
        return await get_file(asset_id)
    return FileResponse(str(thumb), media_type="image/jpeg")


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
    await verify_session(authorization, session_token)
    asset = await db.media_assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    try:
        (STORAGE_DIR / asset["storage_path"]).unlink(missing_ok=True)
        (THUMBS_DIR / f"{asset_id}.jpg").unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass
    await db.media_assets.delete_one({"id": asset_id})
    return {"deleted": 1, "id": asset_id}


@router.post("/assets/{asset_id}/duplicate")
async def duplicate_asset(asset_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    src = await db.media_assets.find_one({"id": asset_id}, {"_id": 0})
    if not src:
        raise HTTPException(status_code=404, detail="Asset not found")
    new_id = str(uuid.uuid4())
    ext = src["storage_path"].rsplit(".", 1)[-1]
    new_rel = f"{new_id}.{ext}"
    shutil.copy(STORAGE_DIR / src["storage_path"], STORAGE_DIR / new_rel)
    clone = {**src, "id": new_id, "storage_path": new_rel,
             "filename": f"{src['filename']} (Copy)", "is_favorite": False,
             "uploaded_at": _now(), "updated_at": _now()}
    await db.media_assets.insert_one(clone)
    return {k: v for k, v in clone.items() if k != "_id"}


# ===================== AI Image Generation =====================

class AiImageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    prompt: constr(min_length=3, max_length=2000)
    style: Optional[constr(max_length=60)] = "Food photography, natural light, appetizing, restaurant menu hero shot"
    count: int = Field(default=1, ge=1, le=4)
    quality: constr(pattern=r"^(low|medium|high)$") = "medium"
    folder: Optional[constr(max_length=60)] = "Promotions"
    headline: Optional[constr(max_length=200)] = None
    tags: Optional[List[str]] = None


@router.post("/ai-image")
async def generate_ai_image(
    body: AiImageRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY not configured.")

    from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration

    full_prompt = body.prompt
    if body.style:
        full_prompt += f". Style: {body.style}"
    if body.headline:
        full_prompt += f". Include headline: '{body.headline}' tastefully overlaid in restaurant typography."

    client = OpenAIImageGeneration(api_key=key)
    try:
        image_bytes_list = await client.generate_images(
            prompt=full_prompt, model="gpt-image-1",
            number_of_images=body.count, quality=body.quality,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI image generation failed: {e}")

    saved = []
    for img_bytes in image_bytes_list:
        aid = str(uuid.uuid4())
        rel = f"{aid}.png"
        path = STORAGE_DIR / rel
        path.write_bytes(img_bytes)
        # measure
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
            "storage_path": rel,
            "is_favorite": False, "status": "active",
            "source": "ai_image",
            "ai_prompt": full_prompt,
            "uploaded_at": _now(), "updated_at": _now(),
        }
        await db.media_assets.insert_one(doc)
        saved.append({k: v for k, v in doc.items() if k != "_id"})
    return {"assets": saved, "count": len(saved)}


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


def _render_sync(job: Dict[str, Any], ordered: list, W: int, H: int) -> Path:
    """Blocking ffmpeg pipeline — runs inside asyncio.to_thread."""
    per = max(2.0, job["duration_seconds"] / max(1, len(ordered)))
    clip_paths = []
    for i, asset in enumerate(ordered):
        src = STORAGE_DIR / asset["storage_path"]
        clip = RENDERS_DIR / f"{job['id']}_{i}.mp4"
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
        subprocess.run(cmd, check=True, timeout=60)
        clip_paths.append(clip)

    concat_file = RENDERS_DIR / f"{job['id']}_list.txt"
    concat_file.write_text("\n".join(f"file '{p}'" for p in clip_paths))
    out_path = RENDERS_DIR / f"{job['id']}.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(concat_file), "-c", "copy", str(out_path)],
        check=True, timeout=120,
    )

    if job.get("title"):
        titled = RENDERS_DIR / f"{job['id']}_titled.mp4"
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
            pass  # drawtext is best-effort — keep the concat output if it fails

    # Cleanup intermediates
    for c in clip_paths:
        c.unlink(missing_ok=True)
    concat_file.unlink(missing_ok=True)
    return out_path


async def _run_render_job(job_id: str):
    """Background worker — composites a slideshow using ffmpeg (off the event loop)."""
    job = await db.render_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        return
    try:
        await db.render_jobs.update_one({"id": job_id}, {"$set": {"status": "processing", "progress": 0.1, "updated_at": _now()}})
        assets = await db.media_assets.find({"id": {"$in": job["asset_ids"]}}, {"_id": 0}).to_list(20)
        assets_by_id = {a["id"]: a for a in assets}
        ordered = [assets_by_id[aid] for aid in job["asset_ids"] if aid in assets_by_id]
        if not ordered:
            raise RuntimeError("No usable source assets")
        W, H = _aspect_dims(job["aspect"])
        # Run blocking ffmpeg pipeline in a worker thread to keep the loop free.
        out_path = await asyncio.to_thread(_render_sync, job, ordered, W, H)

        new_id = str(uuid.uuid4())
        rel = f"{new_id}.mp4"
        shutil.move(str(out_path), STORAGE_DIR / rel)
        asset_doc = {
            "id": new_id,
            "filename": f"render-{job['template']}-{new_id[:6]}.mp4",
            "kind": "video", "mime": "video/mp4",
            "size_bytes": (STORAGE_DIR / rel).stat().st_size,
            "width": W, "height": H, "duration_seconds": job["duration_seconds"],
            "folder": "Promotions", "tags": ["rendered", job.get("template") or "menu_item_spotlight"],
            "storage_path": rel, "is_favorite": False, "status": "active",
            "source": "video_render", "render_job_id": job_id,
            "uploaded_at": _now(), "updated_at": _now(),
        }
        await db.media_assets.insert_one(asset_doc)
        await db.render_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "completed", "progress": 1.0, "output_asset_id": new_id,
                      "completed_at": _now(), "updated_at": _now()}},
        )
    except subprocess.CalledProcessError as e:
        await db.render_jobs.update_one(
            {"id": job_id}, {"$set": {"status": "failed", "error": f"ffmpeg exit {e.returncode}", "updated_at": _now()}},
        )
    except Exception as e:  # noqa: BLE001
        await db.render_jobs.update_one(
            {"id": job_id}, {"$set": {"status": "failed", "error": str(e), "updated_at": _now()}},
        )


@router.post("/video/render")
async def start_render(
    body: VideoRenderRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
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
