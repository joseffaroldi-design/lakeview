"""Phase Cleanup-Week endpoints — Home aggregate, suggestions, archive failures, health roll-up.

Tiny standalone router so we don't bloat ai_ads.py / media.py further.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Header, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from auth import verify_session

router = APIRouter(prefix="/home")

_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = _client[os.environ["DB_NAME"]]


def _iso(days_ago: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


@router.get("/summary")
async def home_summary(authorization: str = Header(None), session_token: str = Cookie(None)):
    """Single aggregate used by Home — bundles all the counts the Home page needs."""
    await verify_session(authorization, session_token)
    now_iso = datetime.now(timezone.utc).isoformat()
    today_prefix = now_iso[:10]
    week_ago = _iso(7)

    # Real failures = not archived. (Stale failures auto-archive via /api/home/archive-failed.)
    real_failures_q = {
        "status": "failed",
        "archived": {"$ne": True},
    }
    real_failures = await db.scheduled_posts.count_documents(real_failures_q)
    scheduled_today = await db.scheduled_posts.count_documents({
        "status": {"$in": ["scheduled", "publishing"]},
        "scheduled_at": {"$regex": f"^{today_prefix}"},
    })
    active_specials = await db.specials.count_documents({"active": True})
    new_subs = await db.newsletter_subscribers.count_documents({"subscribed_at": {"$gte": week_ago}})
    new_inq = await db.catering_inquiries.count_documents({"created_at": {"$gte": week_ago}})

    return {
        "today": {
            "scheduled": scheduled_today,
            "active_promos": active_specials,
            "new_subscribers": new_subs,
            "new_inquiries": new_inq,
            "real_failures": real_failures,
        },
    }


@router.get("/health")
async def home_health(authorization: str = Header(None), session_token: str = Cookie(None)):
    """Composite health pill — green/yellow/red based on subsystem state."""
    await verify_session(authorization, session_token)
    import shutil
    from bootstrap import rembg_state

    ffmpeg_ok = shutil.which("ffmpeg") is not None
    rembg = rembg_state()
    llm_key_ok = bool(os.environ.get("EMERGENT_LLM_KEY"))

    # Provider health: count "is_connected" provider_connections
    providers_connected = await db.provider_connections.count_documents({"is_connected": True})
    # Scheduler health: any unrecoverable failed_posts in last hour?
    recent_failed = await db.scheduled_posts.count_documents({
        "status": "failed", "archived": {"$ne": True},
        "updated_at": {"$gte": _iso(0)[:13]},  # last hour roughly
    })

    issues = []
    if not ffmpeg_ok:
        issues.append("Video rendering offline")
    if not llm_key_ok:
        issues.append("AI key missing")
    if not rembg.get("model_ready"):
        issues.append("Background removal warming up")
    if providers_connected == 0:
        issues.append("No social accounts connected")

    if not ffmpeg_ok or not llm_key_ok:
        level = "red"
    elif issues:
        level = "yellow"
    else:
        level = "green"

    return {
        "level": level,
        "issues": issues,
        "ffmpeg_ok": ffmpeg_ok,
        "rembg_ok": rembg.get("model_ready", False),
        "llm_ok": llm_key_ok,
        "providers_connected": providers_connected,
        "recent_failed": recent_failed,
    }


@router.get("/promote-suggestions")
async def promote_suggestions(
    limit: int = 3,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Top N menu items to promote — ranked by 'time since last promotion'."""
    await verify_session(authorization, session_token)
    # Menu lives in `menu_categories` (verified collection name)
    menu = await db.menu_categories.find({}, {"_id": 0}).to_list(1000)

    flat: List[Dict[str, Any]] = []
    for cat in menu:
        for it in cat.get("items", []) or []:
            flat.append({
                "id": it.get("id") or it.get("name"),
                "name": it.get("name"),
                "category": cat.get("display_name") or cat.get("slug"),
                "description": it.get("description", ""),
                "price": it.get("price"),
            })

    if not flat:
        return {"items": [], "reason": "No menu items yet — add items in Menu Editor."}

    # Look up last promotion timestamp per item from ai_assets/ai_campaigns
    last_promoted: Dict[str, str] = {}
    async for doc in db.ai_campaigns.find({}, {"_id": 0, "subject": 1, "created_at": 1}):
        subj = (doc.get("subject") or "").lower()
        for it in flat:
            if it["name"].lower() in subj:
                ts = doc.get("created_at", "")
                if it["name"] not in last_promoted or last_promoted[it["name"]] < ts:
                    last_promoted[it["name"]] = ts

    now_iso = datetime.now(timezone.utc).isoformat()
    enriched = []
    for it in flat:
        last = last_promoted.get(it["name"])
        days_since = None
        if last:
            try:
                days_since = (datetime.now(timezone.utc) - datetime.fromisoformat(last.replace("Z", "+00:00"))).days
            except Exception:  # noqa: BLE001
                days_since = None
        score = days_since if days_since is not None else 999
        reason = (
            f"Not promoted in {days_since} days" if days_since is not None
            else "Never promoted — perfect first push"
        )
        enriched.append({**it, "days_since_promoted": days_since, "score": score, "reason": reason})

    enriched.sort(key=lambda x: -x["score"])
    return {"items": enriched[:max(1, min(limit, 10))], "generated_at": now_iso}


@router.post("/archive-failed")
async def archive_failed(
    older_than_days: int = 7,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Bulk-archive all failed scheduled_posts older than N days."""
    await verify_session(authorization, session_token)
    cutoff = _iso(older_than_days)
    r = await db.scheduled_posts.update_many(
        {"status": "failed", "archived": {"$ne": True}, "updated_at": {"$lt": cutoff}},
        {"$set": {"archived": True, "archived_at": _iso(0)}},
    )
    return {"archived_count": r.modified_count, "older_than_days": older_than_days}


@router.post("/dismiss-failed/{post_id}")
async def dismiss_failed(post_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    """Archive a single failed post."""
    await verify_session(authorization, session_token)
    r = await db.scheduled_posts.update_one(
        {"id": post_id, "status": "failed"},
        {"$set": {"archived": True, "archived_at": _iso(0)}},
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Post not found or not failed")
    return {"archived": True}
