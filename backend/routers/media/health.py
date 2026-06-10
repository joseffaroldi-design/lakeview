"""Health probe + failure audit list."""
from __future__ import annotations

import asyncio
import shutil
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Cookie, Header

from auth import verify_session
import storage as objstore
from .shared import db

router = APIRouter()


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
