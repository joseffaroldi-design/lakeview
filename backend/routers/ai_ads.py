"""AI Ad Builder routes — Phase 1 foundation.

Endpoints:
  POST /api/ai-ads/generate              — master generation (5 headlines + ...)
  POST /api/ai-ads/campaigns             — save / upsert a campaign
  GET  /api/ai-ads/campaigns             — list saved campaigns
  GET  /api/ai-ads/campaigns/{id}        — fetch one campaign
  DELETE /api/ai-ads/campaigns/{id}      — delete a campaign
  GET  /api/ai-ads/templates             — list templates + catalog (goals/platforms/tones)
  GET  /api/ai-ads/config                — current model config
  PUT  /api/ai-ads/config                — update model config (future settings UI)
  GET  /api/ai-ads/stats                 — Phase 5 stats (placeholder now)
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any, Dict

from fastapi import APIRouter, HTTPException, Header, Cookie, Request
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
    """Quick KPI summary. Full Phase-5 stats arrive later."""
    await verify_session(authorization, session_token)
    total_campaigns = await db.ai_campaigns.count_documents({})
    total_generations = await db.ai_generations.count_documents({})
    return {
        "total_campaigns": total_campaigns,
        "ads_generated": total_generations,
    }
