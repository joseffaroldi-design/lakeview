"""AI Ad Builder routes — Phase 1 + Phase 2 (AI Marketing Studio).

Endpoints:
  --- Phase 1 ---
  POST /api/ai-ads/generate              — master generation (5 headlines + ...)
  POST /api/ai-ads/campaigns             — save / upsert a campaign
  GET  /api/ai-ads/campaigns             — list saved campaigns
  GET  /api/ai-ads/campaigns/{id}        — fetch one campaign
  DELETE /api/ai-ads/campaigns/{id}      — delete a campaign
  GET  /api/ai-ads/templates             — list templates + catalog
  GET  /api/ai-ads/config                — current model config
  PUT  /api/ai-ads/config                — update model config
  GET  /api/ai-ads/stats                 — usage analytics

  --- Phase 2 ---
  POST /api/ai-ads/generate/{kind}       — specialty: social/email/sms/image_concept/video_concept
  GET  /api/ai-ads/assets                — Creative Library list (with filters)
  POST /api/ai-ads/assets                — save an asset
  PUT  /api/ai-ads/assets/{id}           — patch (favorite/archive/rename/etc.)
  DELETE /api/ai-ads/assets/{id}         — delete
  GET  /api/ai-ads/providers             — provider abstraction catalog
  GET  /api/ai-ads/settings              — settings doc bag
  PUT  /api/ai-ads/settings              — update settings doc bag
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any, Dict

from fastapi import APIRouter, HTTPException, Header, Cookie, Request, Query
from pydantic import BaseModel, Field, ConfigDict, constr

from config import db
from auth import verify_session
from rate_limit import limiter
from ai_engine.client import generate_structured, get_active_model, set_active_model
from ai_engine.prompts import (
    build_master_user_prompt,
    resolve_system_prompt,
    MASTER_SCHEMA_HINT,
)
from ai_engine.templates import (
    get_templates,
    get_template,
    GOALS,
    PLATFORMS,
    TONES,
)
from ai_engine.generators import run_generator, GENERATORS
from ai_engine.providers import list_providers, get_setting, set_setting

router = APIRouter(prefix="/ai-ads")


# ----- Models -----

class GenerateRequest(BaseModel):
    name: Optional[constr(strip_whitespace=True, max_length=200)] = None
    goal: constr(strip_whitespace=True, max_length=100)
    platform: constr(strip_whitespace=True, max_length=50)
    audience: Optional[constr(strip_whitespace=True, max_length=1000)] = None
    offer: Optional[constr(strip_whitespace=True, max_length=1000)] = None
    budget: Optional[float] = None
    tone: constr(strip_whitespace=True, max_length=50)
    template_id: Optional[str] = None
    industry: Optional[constr(strip_whitespace=True, max_length=50)] = "restaurant"
    context: Optional[constr(strip_whitespace=True, max_length=4000)] = None
    variation_seed: Optional[int] = None  # incremented for "Generate More" button


class CampaignSave(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: Optional[str] = None
    name: constr(strip_whitespace=True, min_length=1, max_length=200)
    goal: str
    platform: str
    audience: Optional[str] = None
    offer: Optional[str] = None
    budget: Optional[float] = None
    tone: str
    template_id: Optional[str] = None
    industry: Optional[str] = "restaurant"
    context: Optional[str] = None
    output: Dict[str, Any]
    status: Optional[constr(pattern=r"^(draft|active|archived)$")] = "draft"
    is_favorite: Optional[bool] = False


class ModelConfig(BaseModel):
    provider: constr(strip_whitespace=True, max_length=50)
    model: constr(strip_whitespace=True, max_length=100)


# ----- Helpers -----

async def _persist_generation(brief: Dict[str, Any], output: Dict[str, Any], model_used: str) -> str:
    """Audit trail: every generation is saved with its prompt + output."""
    gen_id = str(uuid.uuid4())
    await db.ai_generations.insert_one({
        "id": gen_id,
        "brief": brief,
        "output": output,
        "model_used": model_used,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return gen_id


# ----- Routes -----

@router.get("/templates")
async def list_templates(industry: Optional[str] = None, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    return {
        "templates": get_templates(industry),
        "goals": GOALS,
        "platforms": PLATFORMS,
        "tones": TONES,
    }


@router.get("/config")
async def get_config(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    return await get_active_model(db)


@router.put("/config")
async def update_config(cfg: ModelConfig, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    return await set_active_model(db, cfg.provider, cfg.model)


@router.post("/generate")
@limiter.limit("10/minute")
async def generate_master(request: Request, body: GenerateRequest, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)

    # Apply template defaults (frontend may also do this, but server is source of truth)
    brief = body.model_dump()
    if body.template_id:
        tpl = get_template(body.template_id)
        if tpl:
            for k, v in tpl["defaults"].items():
                if not brief.get(k):
                    brief[k] = v

    system_prompt = resolve_system_prompt(brief.get("industry"))
    user_prompt = build_master_user_prompt(brief)

    try:
        result = await generate_structured(
            db,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_hint=MASTER_SCHEMA_HINT,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI generation failed: {e}")

    gen_id = await _persist_generation(brief, result["data"], result["model_used"])

    return {
        "generation_id": gen_id,
        "model_used": result["model_used"],
        "brief": brief,
        "output": result["data"],
    }


@router.post("/campaigns")
async def save_campaign(payload: CampaignSave, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)

    now = datetime.now(timezone.utc).isoformat()
    if payload.id:
        existing = await db.ai_campaigns.find_one({"id": payload.id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Campaign not found")
        update = payload.model_dump(exclude_unset=True)
        update["updated_at"] = now
        await db.ai_campaigns.update_one({"id": payload.id}, {"$set": update})
        return {**existing, **update}

    new_id = str(uuid.uuid4())
    doc = payload.model_dump()
    doc["id"] = new_id
    doc["created_at"] = now
    doc["updated_at"] = now
    await db.ai_campaigns.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.get("/campaigns")
async def list_campaigns(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    items: List[Dict[str, Any]] = await db.ai_campaigns.find({}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return {"campaigns": items, "total": len(items)}


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    item = await db.ai_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return item


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    result = await db.ai_campaigns.delete_one({"id": campaign_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"message": "Deleted"}


@router.get("/stats")
async def get_stats(authorization: str = Header(None), session_token: str = Cookie(None)):
    """Quick KPI summary + Phase 5 usage analytics."""
    await verify_session(authorization, session_token)
    total_campaigns = await db.ai_campaigns.count_documents({})
    total_generations = await db.ai_generations.count_documents({})

    # Phase 5: breakdowns
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

    # Asset counts per kind
    kind_pipeline = [
        {"$group": {"_id": "$kind", "count": {"$sum": 1}}},
    ]
    asset_kinds_raw = await db.ai_assets.aggregate(kind_pipeline).to_list(20)
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


# =====================================================
# Phase 2 — Specialty generators
# =====================================================

class SpecialtyBrief(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[constr(strip_whitespace=True, max_length=200)] = None
    goal: Optional[constr(strip_whitespace=True, max_length=100)] = None
    tone: Optional[constr(strip_whitespace=True, max_length=50)] = None
    platform: Optional[constr(strip_whitespace=True, max_length=50)] = None
    audience: Optional[constr(strip_whitespace=True, max_length=1000)] = None
    offer: Optional[constr(strip_whitespace=True, max_length=1000)] = None
    industry: Optional[constr(strip_whitespace=True, max_length=50)] = "restaurant"
    context: Optional[constr(strip_whitespace=True, max_length=4000)] = None
    # Specialty-specific:
    email_type: Optional[constr(strip_whitespace=True, max_length=50)] = None
    asset_subtype: Optional[constr(strip_whitespace=True, max_length=100)] = None
    duration_seconds: Optional[int] = None


@router.post("/generate/{kind}")
@limiter.limit("15/minute")
async def generate_specialty(kind: str, request: Request, body: SpecialtyBrief, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    if kind not in GENERATORS:
        raise HTTPException(status_code=400, detail=f"Unknown generator: {kind}")
    brief = body.model_dump()
    try:
        result = await run_generator(db, kind, brief)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI generation failed: {e}")

    gen_id = await _persist_generation({**brief, "_kind": kind}, result["data"], result["model_used"])
    return {
        "generation_id": gen_id,
        "model_used": result["model_used"],
        "kind": kind,
        "brief": brief,
        "output": result["data"],
    }


# =====================================================
# Phase 2 — Creative Library (assets)
# =====================================================

ASSET_KINDS = {"ad_copy", "social_post", "email", "sms", "image_concept", "video_concept", "image_file", "video_file"}


class AssetSave(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: Optional[str] = None
    kind: constr(strip_whitespace=True, max_length=50)  # one of ASSET_KINDS
    title: constr(strip_whitespace=True, min_length=1, max_length=200)
    platform: Optional[str] = None
    industry: Optional[str] = "restaurant"
    campaign_id: Optional[str] = None
    payload: Dict[str, Any]
    tags: Optional[List[str]] = []
    is_favorite: Optional[bool] = False
    status: Optional[constr(pattern=r"^(draft|active|archived)$")] = "active"


class AssetPatch(BaseModel):
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    is_favorite: Optional[bool] = None
    status: Optional[constr(pattern=r"^(draft|active|archived)$")] = None
    payload: Optional[Dict[str, Any]] = None


@router.get("/assets")
async def list_assets(
    kind: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    is_favorite: Optional[bool] = Query(None),
    campaign_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None, max_length=200),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    query: Dict[str, Any] = {}
    if kind:
        query["kind"] = kind
    if platform:
        query["platform"] = platform
    if industry:
        query["industry"] = industry
    if status:
        query["status"] = status
    if is_favorite is not None:
        query["is_favorite"] = is_favorite
    if campaign_id:
        query["campaign_id"] = campaign_id
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"tags": {"$elemMatch": {"$regex": q, "$options": "i"}}},
        ]
    if date_from or date_to:
        rng: Dict[str, Any] = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        query["created_at"] = rng

    items = await db.ai_assets.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"assets": items, "total": len(items)}


@router.post("/assets")
async def save_asset(payload: AssetSave, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    if payload.kind not in ASSET_KINDS:
        raise HTTPException(status_code=400, detail=f"Invalid kind. Allowed: {sorted(ASSET_KINDS)}")
    now = datetime.now(timezone.utc).isoformat()
    if payload.id:
        existing = await db.ai_assets.find_one({"id": payload.id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Asset not found")
        update = payload.model_dump(exclude_unset=True)
        update["updated_at"] = now
        await db.ai_assets.update_one({"id": payload.id}, {"$set": update})
        return {**existing, **update}

    new_id = str(uuid.uuid4())
    doc = payload.model_dump()
    doc["id"] = new_id
    doc["created_at"] = now
    doc["updated_at"] = now
    await db.ai_assets.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.put("/assets/{asset_id}")
async def patch_asset(asset_id: str, patch: AssetPatch, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    update = {k: v for k, v in patch.model_dump(exclude_unset=True).items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to patch")
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.ai_assets.update_one({"id": asset_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Asset not found")
    return await db.ai_assets.find_one({"id": asset_id}, {"_id": 0})


@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    result = await db.ai_assets.delete_one({"id": asset_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"message": "Deleted"}


@router.post("/assets/{asset_id}/duplicate")
async def duplicate_asset(asset_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    """Duplicate a creative asset (preserves payload, resets id/status/favorite/timestamps)."""
    await verify_session(authorization, session_token)
    original = await db.ai_assets.find_one({"id": asset_id}, {"_id": 0})
    if not original:
        raise HTTPException(status_code=404, detail="Asset not found")
    now = datetime.now(timezone.utc).isoformat()
    clone = {**original}
    clone["id"] = str(uuid.uuid4())
    clone["title"] = f"{original.get('title') or 'Untitled'} (Copy)"
    clone["status"] = "draft"
    clone["is_favorite"] = False
    clone["created_at"] = now
    clone["updated_at"] = now
    await db.ai_assets.insert_one(clone)
    return {k: v for k, v in clone.items() if k != "_id"}


# =====================================================
# Phase 2 — Providers + Settings
# =====================================================

@router.get("/providers")
async def get_providers(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    return {
        "text": list_providers("text"),
        "image": list_providers("image"),
        "video": list_providers("video"),
    }


class SettingsBag(BaseModel):
    model_config = ConfigDict(extra="ignore")
    default_industry: Optional[constr(max_length=50)] = None
    default_tone: Optional[constr(max_length=50)] = None
    default_platform: Optional[constr(max_length=50)] = None
    monthly_generation_limit: Optional[int] = None


@router.get("/settings")
async def get_settings(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    return {
        "default_industry": await get_setting(db, "default_industry", "restaurant"),
        "default_tone": await get_setting(db, "default_tone", "Local New Orleans Style"),
        "default_platform": await get_setting(db, "default_platform", "Facebook"),
        "monthly_generation_limit": await get_setting(db, "monthly_generation_limit", 0),
    }


@router.put("/settings")
async def update_settings(payload: SettingsBag, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    saved = {}
    for k, v in payload.model_dump(exclude_unset=True).items():
        if v is not None:
            saved[k] = await set_setting(db, k, v)
    return saved
