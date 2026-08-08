"""Simple marketing flyer API.

Photo -> explicit template -> text/price -> render -> save.
No design agent, creative director, hidden theme selection, or LLM is required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Cookie, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, constr

from auth import verify_session
from config import db
from routers.settings import get_settings_document
from services.template_renderer import TEMPLATES, normalize_template, render_marketing_job

router = APIRouter(prefix="/marketing", tags=["marketing"])


class FlyerGenerateIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_asset_id: constr(min_length=1, max_length=64)
    item_name: constr(min_length=1, max_length=120)
    features: List[constr(max_length=80)] = Field(default_factory=list)
    price: Optional[constr(max_length=40)] = None
    headline: Optional[constr(max_length=160)] = None
    template_id: Optional[constr(max_length=60)] = None
    item_key: Optional[constr(max_length=200)] = None
    platform: constr(max_length=40) = "instagram_square"
    cta: Optional[constr(max_length=80)] = None
    variations: int = Field(default=1, ge=1, le=3)


@router.get("/stats")
async def marketing_stats(
    authorization: str = Header(None), session_token: str = Cookie(None)
):
    """Small dashboard summary. Reads historical generation rows during migration."""
    await verify_session(authorization, session_token)
    total_generations = await db.ai_generations.count_documents({})
    platform_pipeline = [
        {"$group": {"_id": "$brief.platform", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    goal_pipeline = [
        {"$group": {"_id": "$brief.goal", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    platforms = await db.ai_generations.aggregate(platform_pipeline).to_list(20)
    goals = await db.ai_generations.aggregate(goal_pipeline).to_list(20)
    return {
        "flyers_generated": total_generations,
        "most_used_platform": platforms[0]["_id"] if platforms else None,
        "most_used_goal": goals[0]["_id"] if goals else None,
    }


@router.get("/flyers/templates")
async def list_templates(
    authorization: str = Header(None), session_token: str = Cookie(None)
):
    await verify_session(authorization, session_token)
    themes = [
        {"id": t["id"], "name": t["name"], "description": t["description"], "hidden": False, "pack": "lakeview"}
        for t in TEMPLATES
    ]
    return {
        "templates": TEMPLATES,
        "themes": themes,
        "packs": [{"id": "lakeview", "name": "Lakeview Templates", "themes": [t["id"] for t in TEMPLATES]}],
        "engine": "deterministic_template",
    }


@router.post("/flyers/generate")
async def generate_flyer(
    body: FlyerGenerateIn,
    background: BackgroundTasks,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    asset = await db.media_assets.find_one({"id": body.source_asset_id, "status": "active"}, {"_id": 0, "id": 1, "kind": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Source image not found")
    if asset.get("kind") != "image":
        raise HTTPException(status_code=400, detail="Source asset must be an image")

    settings = await get_settings_document()
    template_id = normalize_template(body.template_id or settings.get("marketing", {}).get("default_template") or "luxury")
    now = datetime.now(timezone.utc).isoformat()
    job_id = str(uuid.uuid4())
    doc = {
        "id": job_id,
        "status": "queued",
        "progress": 5,
        "current_step": "queued",
        "source_asset_id": body.source_asset_id,
        "item_name": body.item_name,
        "features": body.features[:3],
        "price": body.price or "",
        "headline": body.headline,
        "template_id": template_id,
        "item_key": body.item_key,
        "platform": body.platform,
        "cta": body.cta or settings.get("homepage", {}).get("default_cta") or "Order Now",
        "brand": settings.get("business_name") or "Lakeview Burgers & Seafood",
        "variations": body.variations,
        "created_at": now,
        "updated_at": now,
    }
    await db.marketing_flyer_jobs.insert_one(doc)
    background.add_task(render_marketing_job, job_id)
    return {"job_id": job_id, "status": "queued", "template_id": template_id}


@router.get("/flyers/job/{job_id}")
async def get_flyer_job(
    job_id: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    job = await db.marketing_flyer_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Flyer job not found")
    return job
