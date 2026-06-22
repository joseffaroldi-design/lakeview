"""AI Ads — minimal surface after Sprint 15B carcass removal.

Sprint 15B: 9 of 10 routes were never called from the frontend (legacy from
pre-Marketing-Pack era). Only `/api/ai-ads/stats` survives — it's still used
by `HomeTab.jsx` to render the "most-used platform / goal" KPI tiles.

Removed routes (all returned 410 Gone or were unused):
  /templates, /generate/{kind}, /assets (GET/POST), /assets/{id} (PUT/DELETE),
  /assets/{id}/duplicate, /assets/bulk, /assets/export

The `ai_generations` collection is retained — it backs the /stats KPIs.
"""
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Cookie, Header

from config import db
from auth import verify_session

router = APIRouter(prefix="/ai-ads")

LEGACY_SOURCE = "ai_ads_legacy"


@router.get("/stats")
async def get_stats(authorization: str = Header(None), session_token: str = Cookie(None)):
    """Quick KPI summary surfaced on the Home dashboard."""
    await verify_session(authorization, session_token)
    total_campaigns = await db.ai_campaigns.count_documents({})
    total_generations = await db.ai_generations.count_documents({})

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    gens_this_month = await db.ai_generations.count_documents({"created_at": {"$gte": month_start}})

    platform_pipeline = [
        {"$group": {"_id": "$brief.platform", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    platforms = await db.ai_generations.aggregate(platform_pipeline).to_list(20)
    most_used_platform = platforms[0]["_id"] if platforms else None

    goal_pipeline = [
        {"$group": {"_id": "$brief.goal", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    goals_agg = await db.ai_generations.aggregate(goal_pipeline).to_list(20)
    most_used_goal = goals_agg[0]["_id"] if goals_agg else None

    kind_pipeline = [
        {"$match": {"source": LEGACY_SOURCE}},
        {"$group": {"_id": "$kind", "count": {"$sum": 1}}},
    ]
    asset_kinds_raw = await db.media_assets.aggregate(kind_pipeline).to_list(20)
    asset_counts: Dict[str, int] = {a["_id"]: a["count"] for a in asset_kinds_raw}

    return {
        "total_campaigns": total_campaigns,
        "ads_generated": total_generations,
        "generations_this_month": gens_this_month,
        "most_used_platform": most_used_platform,
        "most_used_goal": most_used_goal,
        "asset_counts": asset_counts,
        "platforms_breakdown": {p["_id"]: p["count"] for p in platforms if p["_id"]},
        "goals_breakdown": {g["_id"]: g["count"] for g in goals_agg if g["_id"]},
    }
