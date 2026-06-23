"""Health probe + failure audit list.

Sprint 15B: render_jobs and ai_image_jobs collections removed with MediaStudio.
Queue counters retained at zero for API back-compat.
"""
from __future__ import annotations

import asyncio
import shutil
from typing import Any, Dict, Optional

from fastapi import APIRouter, Cookie, Header

from auth import verify_session
import storage as objstore
from .shared import db

router = APIRouter()


@router.get("/health")
async def media_health(authorization: str = Header(None), session_token: str = Cookie(None)):
    """Operational health probe — exposes ffmpeg + rembg + storage."""
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

    asset_count = await db.media_assets.count_documents({"status": "active"})

    # Sprint 15B: render_jobs / ai_image_jobs collections dropped; queues retained at 0 for back-compat.
    empty_queue = {"queued": 0, "processing": 0, "completed_recent": 0, "failed_recent": 0}
    aij_empty_queue = {"pending": 0, "processing": 0, "completed_recent": 0, "failed_recent": 0}

    # Sprint 15B.3 made rembg opt-in (lazy-loaded only when an owner explicitly
    # checks "Remove background"). Its absence is NOT a failure — `healthy`
    # tracks only the critical path: object storage + ffmpeg. rembg state is
    # still returned in the payload below for admin visibility.
    healthy = (
        ffmpeg_path is not None
        and storage_health.get("reachable")
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
        "stale_ai_image_jobs": 0,
        "stale_render_jobs": 0,
        "render_queue": empty_queue,
        "ai_image_queue": aij_empty_queue,
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
    by_code: Dict[str, int] = {}
    for e in entries:
        by_code[e.get("code", "unknown")] = by_code.get(e.get("code", "unknown"), 0) + 1
    return {
        "entries": entries,
        "count": len(entries),
        "by_code": by_code,
    }
