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

    # Sprint 12D: Publishing pipeline retired. Replace scheduled/publish metrics
    # with marketing-pack, media, and customer metrics — the actual things the
    # owner cares about.
    packs_today = await db.marketing_packs.count_documents({
        "status": "completed", "updated_at": {"$gte": today_prefix},
    })
    packs_this_week = await db.marketing_packs.count_documents({
        "status": "completed", "updated_at": {"$gte": week_ago},
    })
    failed_packs_recent = await db.marketing_packs.count_documents({
        "status": "failed", "updated_at": {"$gte": week_ago},
    })
    media_this_week = await db.media_assets.count_documents({
        "status": "active", "uploaded_at": {"$gte": week_ago},
    })
    active_specials = await db.marketing_packs.count_documents({"tag": "special", "is_active": True})
    new_subs = await db.newsletter_subscribers.count_documents({"subscribed_at": {"$gte": week_ago}})
    new_inq = await db.catering_inquiries.count_documents({"created_at": {"$gte": week_ago}})

    return {
        "today": {
            "packs_today": packs_today,
            "packs_this_week": packs_this_week,
            "active_promos": active_specials,
            "new_subscribers": new_subs,
            "new_inquiries": new_inq,
            "failed_packs_recent": failed_packs_recent,
            "media_this_week": media_this_week,
            # Legacy keys retained for one release so the frontend keeps rendering
            "scheduled": 0,
            "real_failures": failed_packs_recent,
        },
    }


@router.get("/health")
async def home_health(authorization: str = Header(None), session_token: str = Cookie(None)):
    """Composite health pill — green/yellow/red based on subsystem state.

    Sprint 15B: ffmpeg and rembg are no longer "red" triggers. They're optional
    subsystems used by Marketing Pack slideshow (ffmpeg) and AI Designer food
    cutout (rembg). Today's Pick and the rest of the platform run without them.
    Only a missing LLM key — which kills *everything* — keeps the pill red.
    """
    await verify_session(authorization, session_token)
    import shutil
    from bootstrap import rembg_state

    ffmpeg_ok = shutil.which("ffmpeg") is not None
    rembg = rembg_state()
    llm_key_ok = bool(os.environ.get("EMERGENT_LLM_KEY"))

    issues = []
    if not ffmpeg_ok:
        issues.append("Slideshow video rendering offline (ffmpeg missing)")
    if not llm_key_ok:
        issues.append("AI key missing")
    if not rembg.get("model_ready"):
        issues.append("Background removal warming up")

    # Only LLM key drives "red" — without it, no AI features work at all.
    if not llm_key_ok:
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

    # Sprint 12D: ai_campaigns collection retired; use marketing_packs as the
    # source of truth for "last promoted" per item.
    last_promoted: Dict[str, str] = {}
    async for doc in db.marketing_packs.find(
        {"status": "completed"}, {"_id": 0, "item.name": 1, "updated_at": 1}
    ):
        name = ((doc.get("item") or {}).get("name") or "").lower()
        if not name:
            continue
        ts = doc.get("updated_at", "")
        for it in flat:
            if it["name"].lower() == name:
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


# Sprint 12D: /archive-failed and /dismiss-failed removed with the publishing pipeline.
