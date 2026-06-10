"""Video render — slideshow job + polling, orphan cleanup."""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import uuid
from typing import List, Optional

from fastapi import APIRouter, Cookie, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, constr

from auth import verify_session
import storage as objstore
from .shared import TMP_DIR, _aspect_dims, _now, _render_sync, db

router = APIRouter()


class VideoRenderRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    asset_ids: List[str] = Field(min_length=1, max_length=12)
    duration_seconds: int = Field(default=30, ge=10, le=120)
    aspect: constr(pattern=r"^(1:1|4:5|9:16|16:9)$") = "9:16"
    title: Optional[constr(max_length=120)] = None
    subtitle: Optional[constr(max_length=240)] = None
    cta: Optional[constr(max_length=120)] = None
    template: Optional[constr(max_length=60)] = "menu_item_spotlight"


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
