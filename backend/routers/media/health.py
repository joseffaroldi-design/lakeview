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
    """Operational health probe for the mounted media feature set."""
    await verify_session(authorization, session_token)
    ffmpeg_path = shutil.which("ffmpeg")

    # Read-only object storage reachability probe.
    storage_health = await asyncio.to_thread(objstore.health)

    asset_count = await db.media_assets.count_documents({"status": "active"})

    # Sprint 15B: render_jobs / ai_image_jobs collections dropped; queues retained at 0 for back-compat.
    empty_queue = {"queued": 0, "processing": 0, "completed_recent": 0, "failed_recent": 0}
    aij_empty_queue = {"pending": 0, "processing": 0, "completed_recent": 0, "failed_recent": 0}

    healthy = (
        ffmpeg_path is not None
        and storage_health.get("reachable")
    )
    return {
        "healthy": healthy,
        "ffmpeg_available": ffmpeg_path is not None,
        "ffmpeg_path": ffmpeg_path,
        "rembg_available": False,
        "rembg_model_ready": False,
        "rembg_error": "disabled in the core deployment",
        "storage": storage_health,
        "image_provider": None,
        "provider_status": "disabled",
        "api_key_loaded": False,
        "image_providers": {"active": None, "providers": [], "disabled": True},
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
