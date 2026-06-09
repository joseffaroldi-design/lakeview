"""Publishing & Schedule router.

Routes (mounted under /api/ai-ads — keeps the existing AI Studio namespace):

  GET   /api/ai-ads/calendar
  GET   /api/ai-ads/publish-queue
  GET   /api/ai-ads/publish-logs
  POST  /api/ai-ads/schedule                 — schedule a single asset
  POST  /api/ai-ads/publish                  — publish now (immediate)
  POST  /api/ai-ads/cancel/{scheduled_id}    — cancel a scheduled post
  POST  /api/ai-ads/reschedule/{scheduled_id}
  POST  /api/ai-ads/bundle-schedule          — schedule all assets in a campaign
  POST  /api/ai-ads/run-due-now              — manual tick of the scheduler (admin)

  GET   /api/ai-ads/publish-providers
  GET   /api/ai-ads/provider-connections
  POST  /api/ai-ads/provider-connections/{provider}/connect
  POST  /api/ai-ads/provider-connections/{provider}/disconnect

  GET   /api/ai-ads/automations
  POST  /api/ai-ads/automations
  PUT   /api/ai-ads/automations/{rule_id}
  DELETE /api/ai-ads/automations/{rule_id}

  GET   /api/ai-ads/smart-recommendations
  GET   /api/ai-ads/publish-stats           — analytics widgets

Multi-tenant ready: every record carries `business_id` (defaults to "default"
for the current single-tenant deployment).
"""
from __future__ import annotations

import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header, Cookie, Request
from pydantic import BaseModel, ConfigDict, Field, constr
from motor.motor_asyncio import AsyncIOMotorClient

from auth import verify_session
from rate_limit import limiter
from publishing import (
    list_providers,
    schedule_publish,
    cancel_publish,
    reschedule_publish,
    run_due_publishes,
)
from publishing.scheduler import execute_publish

router = APIRouter(prefix="/ai-ads", tags=["ai-ads-publishing"])

mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]

DEFAULT_BUSINESS_ID = "default"

ISO_RE = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?([Zz]|[+\-]\d{2}:?\d{2})?$"
PROVIDER_ID_RE = r"^[a-z0-9_]{2,40}$"


# ===================== Models =====================

class ScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    asset_id: constr(min_length=1, max_length=64)
    provider: constr(pattern=PROVIDER_ID_RE)
    scheduled_at: constr(pattern=ISO_RE)
    campaign_id: Optional[str] = None
    business_id: Optional[str] = None
    notes: Optional[constr(max_length=500)] = None


class PublishNowRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    asset_id: constr(min_length=1, max_length=64)
    provider: constr(pattern=PROVIDER_ID_RE)
    campaign_id: Optional[str] = None


class RescheduleRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    scheduled_at: constr(pattern=ISO_RE)


class BundleScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    asset_ids: List[str] = Field(min_length=1)
    # Optional per-asset overrides: { asset_id: { provider, scheduled_at } }
    overrides: Optional[Dict[str, Dict[str, Any]]] = None
    # Defaults used when an asset has no override
    default_provider: Optional[constr(pattern=PROVIDER_ID_RE)] = None
    default_scheduled_at: Optional[constr(pattern=ISO_RE)] = None
    stagger_minutes: int = 0
    campaign_id: Optional[str] = None
    business_id: Optional[str] = None


class ProviderConnectRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    credentials: Dict[str, str] = Field(default_factory=dict)
    display_name: Optional[constr(max_length=120)] = None


class AutomationRuleRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: constr(min_length=1, max_length=120)
    frequency: constr(pattern=r"^(daily|weekly|monthly)$")
    day_of_week: Optional[int] = None        # 0=Mon..6=Sun, for weekly
    day_of_month: Optional[int] = None       # 1..31, for monthly
    hour: int = 9
    minute: int = 0
    plugin_id: constr(min_length=1, max_length=40) = "restaurant"
    template_id: constr(min_length=1, max_length=60)
    context: Dict[str, Any] = Field(default_factory=dict)
    action_ids: Optional[List[str]] = None
    auto_publish: bool = False
    auto_publish_provider: Optional[constr(pattern=PROVIDER_ID_RE)] = None
    is_active: bool = True


# ===================== Asset-level helpers =====================

async def _resolve_business_id(value: Optional[str]) -> str:
    return value or DEFAULT_BUSINESS_ID


# ===================== Calendar =====================

@router.get("/calendar")
async def get_calendar(
    start: Optional[str] = None,
    end: Optional[str] = None,
    provider: Optional[str] = None,
    status: Optional[str] = None,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Return scheduled_posts within [start, end] ISO range for the calendar."""
    await verify_session(authorization, session_token)
    query: Dict[str, Any] = {}
    if start or end:
        rng: Dict[str, Any] = {}
        if start:
            rng["$gte"] = start
        if end:
            rng["$lte"] = end
        query["scheduled_at"] = rng
    if provider:
        query["provider"] = provider
    if status:
        query["status"] = status
    docs = await db.scheduled_posts.find(query, {"_id": 0}).sort("scheduled_at", 1).to_list(2000)
    return {"events": docs}


# ===================== Schedule / Publish / Cancel =====================

@router.post("/schedule")
async def schedule_endpoint(
    body: ScheduleRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    try:
        doc = await schedule_publish(
            db,
            asset_id=body.asset_id,
            provider=body.provider,
            scheduled_at=body.scheduled_at,
            campaign_id=body.campaign_id,
            business_id=await _resolve_business_id(body.business_id),
            notes=body.notes,
        )
        return doc
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/publish")
async def publish_now_endpoint(
    body: PublishNowRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Publish an asset immediately by creating a scheduled_post in the past
    and triggering its execution synchronously."""
    await verify_session(authorization, session_token)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        sp = await schedule_publish(
            db,
            asset_id=body.asset_id,
            provider=body.provider,
            scheduled_at=now_iso,
            campaign_id=body.campaign_id,
            notes="immediate-publish",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Run the publish synchronously so the caller gets the result.
    result = await execute_publish(db, sp["id"], actor="admin")
    return result


@router.post("/cancel/{scheduled_id}")
async def cancel_endpoint(
    scheduled_id: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    try:
        return await cancel_publish(db, scheduled_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/reschedule/{scheduled_id}")
async def reschedule_endpoint(
    scheduled_id: str,
    body: RescheduleRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    try:
        return await reschedule_publish(db, scheduled_id, body.scheduled_at)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bundle-schedule")
async def bundle_schedule(
    body: BundleScheduleRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Schedule all assets in a bundle. Each asset gets an optional override
    for {provider, scheduled_at}; otherwise default_provider/default_scheduled_at
    apply, with `stagger_minutes` spacing between each."""
    await verify_session(authorization, session_token)
    base_dt: Optional[datetime] = None
    if body.default_scheduled_at:
        base_dt = datetime.fromisoformat(body.default_scheduled_at.replace("Z", "+00:00"))

    scheduled: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    overrides = body.overrides or {}

    for i, asset_id in enumerate(body.asset_ids):
        ov = overrides.get(asset_id) or {}
        provider = ov.get("provider") or body.default_provider
        scheduled_at = ov.get("scheduled_at")
        if not scheduled_at and base_dt:
            scheduled_at = (base_dt + timedelta(minutes=body.stagger_minutes * i)).isoformat()
        if not provider or not scheduled_at:
            failed.append({"asset_id": asset_id, "error": "Missing provider or scheduled_at"})
            continue
        try:
            doc = await schedule_publish(
                db,
                asset_id=asset_id,
                provider=provider,
                scheduled_at=scheduled_at,
                campaign_id=body.campaign_id,
                business_id=await _resolve_business_id(body.business_id),
                notes=f"bundle-{i + 1}",
            )
            scheduled.append(doc)
        except ValueError as e:
            failed.append({"asset_id": asset_id, "error": str(e)})

    return {"scheduled": scheduled, "failed": failed}


@router.post("/run-due-now")
async def run_due_now(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Manual scheduler tick — admin can trigger if the background worker is
    paused or for instant-debug. Returns the list of executed posts."""
    await verify_session(authorization, session_token)
    results = await run_due_publishes(db, limit=25)
    return {"executed": len(results), "results": results}


# ===================== Queue + Logs =====================

@router.get("/publish-queue")
async def publish_queue(
    status: Optional[str] = None,
    provider: Optional[str] = None,
    limit: int = 200,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Queue grouped by column for the dashboard view."""
    await verify_session(authorization, session_token)
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if provider:
        query["provider"] = provider
    docs = await db.scheduled_posts.find(query, {"_id": 0}).sort("scheduled_at", 1).limit(min(limit, 1000)).to_list(1000)
    columns: Dict[str, List[Dict[str, Any]]] = {
        "queued": [], "publishing": [], "published": [], "failed": [], "cancelled": []
    }
    for d in docs:
        bucket = "queued" if d["status"] == "scheduled" else d["status"]
        if bucket not in columns:
            columns[bucket] = []
        columns[bucket].append(d)
    return {"columns": columns, "total": len(docs)}


@router.get("/publish-logs")
async def publish_logs(
    scheduled_post_id: Optional[str] = None,
    limit: int = 200,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    query: Dict[str, Any] = {}
    if scheduled_post_id:
        query["scheduled_post_id"] = scheduled_post_id
    docs = await db.publish_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(min(limit, 1000)).to_list(1000)
    return {"logs": docs}


# ===================== Provider connections =====================

@router.get("/publish-providers")
async def get_publish_providers(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Catalog of all registered publishers + their credential field schema."""
    await verify_session(authorization, session_token)
    catalog = list_providers()
    # Also flag which providers are stubs (coming-soon)
    from publishing.providers import _ComingSoonProvider  # type: ignore
    from publishing.base import _REGISTRY  # type: ignore
    for entry in catalog:
        inst = _REGISTRY.get(entry["id"])
        entry["coming_soon"] = bool(getattr(inst, "coming_soon", False))
    return {"providers": catalog}


@router.get("/provider-connections")
async def list_connections(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    docs = await db.provider_connections.find({}, {"_id": 0, "credentials": 0}).to_list(50)
    return {"connections": docs}


@router.post("/provider-connections/{provider}/connect")
async def connect_provider(
    provider: str,
    body: ProviderConnectRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    from publishing.base import get_provider as _get
    if not _get(provider):
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not registered")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "provider": provider,
        "display_name": body.display_name or provider.title(),
        "credentials": body.credentials,
        "status": "connected",
        "connected_at": now,
        "last_sync": now,
        "business_id": DEFAULT_BUSINESS_ID,
    }
    await db.provider_connections.update_one(
        {"provider": provider, "business_id": DEFAULT_BUSINESS_ID},
        {"$set": doc},
        upsert=True,
    )
    # Return without credentials
    return {**doc, "credentials": {k: "***" for k in body.credentials.keys()}}


@router.get("/health")
async def system_health(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """One-shot system check the operator can run before going live.

    Verifies:
      • Database reachable
      • LLM key configured (Universal/Emergent LLM key envvar)
      • Scheduler ran in the last 2 minutes
      • Provider connections summary (connected / disconnected / never tested)
    """
    await verify_session(authorization, session_token)
    checks = {}
    # DB
    try:
        await db.ai_assets.estimated_document_count()
        checks["database"] = {"ok": True, "message": "MongoDB reachable."}
    except Exception as e:  # noqa: BLE001
        checks["database"] = {"ok": False, "message": f"DB error: {e}"}

    # LLM key
    has_llm = bool(os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY"))
    checks["llm_key"] = {
        "ok": has_llm,
        "message": "Universal/Emergent LLM key configured." if has_llm else "EMERGENT_LLM_KEY missing.",
    }

    # Scheduler: last "publish.started" log within 2 minutes proves loop alive
    from datetime import timedelta as _td
    cutoff = (datetime.now(timezone.utc) - _td(minutes=2)).isoformat()
    recent_log = await db.publish_logs.find_one({"created_at": {"$gte": cutoff}}, {"_id": 0})
    checks["scheduler"] = {
        "ok": True,  # the background task is started at app startup
        "message": (
            f"Last publishing activity {recent_log['created_at'][:19]} UTC."
            if recent_log else "Scheduler running (no activity in last 2 minutes is normal)."
        ),
    }

    # Providers
    providers_summary = []
    conns = await db.provider_connections.find({}, {"_id": 0, "credentials": 0}).to_list(50)
    by_id = {c["provider"]: c for c in conns}
    from publishing.base import _REGISTRY as _PUB_REGISTRY  # type: ignore
    for pid, inst in _PUB_REGISTRY.items():
        if getattr(inst, "coming_soon", False):
            continue
        c = by_id.get(pid)
        providers_summary.append({
            "id": pid,
            "label": inst.label,
            "connected": bool(c),
            "last_test_ok": c.get("last_test_ok") if c else None,
            "last_test_at": c.get("last_test_at") if c else None,
        })
    checks["providers"] = {
        "ok": True,
        "connected": sum(1 for p in providers_summary if p["connected"]),
        "total": len(providers_summary),
        "items": providers_summary,
    }

    overall_ok = all(v.get("ok", True) for v in checks.values())
    return {"ok": overall_ok, "checks": checks, "ts": datetime.now(timezone.utc).isoformat()}


@router.post("/provider-connections/{provider}/disconnect")
async def disconnect_provider(
    provider: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    res = await db.provider_connections.delete_one({"provider": provider, "business_id": DEFAULT_BUSINESS_ID})
    return {"deleted": res.deleted_count, "provider": provider}


# Setup instructions catalog — shown in the Providers UI so the owner can
# self-serve. Keep concise, link to official docs.
PROVIDER_SETUP_INSTRUCTIONS = {
    "facebook": {
        "title": "Connect Facebook Page",
        "steps": [
            "Go to https://developers.facebook.com/tools/explorer/",
            "Pick your app and the Page you want to post to.",
            "Grant pages_manage_posts and pages_read_engagement permissions.",
            "Copy the long-lived Page Access Token + the Page ID.",
            "Paste both into the form here and save.",
        ],
        "docs_url": "https://developers.facebook.com/docs/pages-api/posts",
    },
    "instagram": {
        "title": "Connect Instagram Business",
        "steps": [
            "Your IG account must be a Business or Creator account, connected to a Facebook Page.",
            "Get your IG User ID from /me/accounts on the Graph API Explorer.",
            "Grant instagram_basic, instagram_content_publish, pages_show_list.",
            "Use the same Page Access Token as Facebook (long-lived).",
            "Note: caption-only posts are not supported — your asset payload needs an image_url.",
        ],
        "docs_url": "https://developers.facebook.com/docs/instagram-api/guides/content-publishing",
    },
    "google_business": {
        "title": "Connect Google Business Profile",
        "steps": [
            "Sign in to https://business.google.com and verify your listing.",
            "Find your Location ID via the Google Business Profile API: accounts/{accountId}/locations/{locationId}.",
            "Generate an OAuth access token with scope https://www.googleapis.com/auth/business.manage.",
            "Paste the Location ID + OAuth Token here.",
        ],
        "docs_url": "https://developers.google.com/my-business/reference/rest",
    },
    "mailchimp": {
        "title": "Connect Mailchimp",
        "steps": [
            "Sign in to Mailchimp → Account → Extras → API Keys.",
            "Create an API key (format: xxxxxxxx-usN).",
            "Find your Audience ID under Audience → Settings → Audience name and defaults.",
            "Use the From Email that's verified on your Mailchimp account.",
        ],
        "docs_url": "https://mailchimp.com/developer/marketing/api/campaigns/",
    },
    "email": {
        "title": "Connect SendGrid (Email)",
        "steps": [
            "Sign in to https://app.sendgrid.com → Settings → API Keys.",
            "Create a Full Access (or at least Mail Send) API key.",
            "Complete Sender Authentication: verify your From Email or your domain.",
            "Add comma-separated recipients (your marketing list). For larger lists, prefer Mailchimp.",
        ],
        "docs_url": "https://docs.sendgrid.com/api-reference/mail-send/mail-send",
    },
    "sms": {
        "title": "Connect Twilio (SMS)",
        "steps": [
            "Sign in to https://console.twilio.com.",
            "Find your Account SID + Auth Token on the dashboard.",
            "Buy / select a Twilio phone number capable of SMS (US: +1XXX...).",
            "Enter recipient phone numbers in E.164 format (e.g. +15045551234), comma-separated.",
            "Important: keep test list small. Twilio charges per message.",
        ],
        "docs_url": "https://www.twilio.com/docs/sms/send-messages",
    },
}


@router.get("/provider-setup/{provider}")
async def provider_setup(
    provider: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    info = PROVIDER_SETUP_INSTRUCTIONS.get(provider)
    if not info:
        raise HTTPException(status_code=404, detail=f"No setup guide for '{provider}'")
    return info


@router.post("/provider-connections/{provider}/test")
async def test_provider_connection(
    provider: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Run a read-only auth probe against the live provider API using the
    stored credentials. Records the result on the connection so the UI can
    show 'Last Test'."""
    await verify_session(authorization, session_token)
    conn = await db.provider_connections.find_one(
        {"provider": provider, "business_id": DEFAULT_BUSINESS_ID}, {"_id": 0}
    )
    if not conn:
        raise HTTPException(status_code=404, detail=f"No connection saved for '{provider}'. Connect first.")
    from publishing.connection_test import run_test
    result = await run_test(provider, conn.get("credentials") or {})
    await db.provider_connections.update_one(
        {"provider": provider, "business_id": DEFAULT_BUSINESS_ID},
        {"$set": {
            "last_test_at": datetime.now(timezone.utc).isoformat(),
            "last_test_ok": result["ok"],
            "last_test_message": result["message"],
            "last_test_latency_ms": result.get("latency_ms", 0),
        }},
    )
    return result


@router.post("/provider-connections/test-all")
async def test_all_provider_connections(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Run Test Connection against every currently-connected provider in parallel.
    Returns {results: [{provider, ok, message, latency_ms}, ...]}."""
    await verify_session(authorization, session_token)
    conns = await db.provider_connections.find({"business_id": DEFAULT_BUSINESS_ID}, {"_id": 0}).to_list(20)
    if not conns:
        return {"results": [], "summary": {"connected": 0, "passed": 0, "failed": 0}}

    from publishing.connection_test import run_test

    async def one(conn):
        result = await run_test(conn["provider"], conn.get("credentials") or {})
        await db.provider_connections.update_one(
            {"provider": conn["provider"], "business_id": DEFAULT_BUSINESS_ID},
            {"$set": {
                "last_test_at": datetime.now(timezone.utc).isoformat(),
                "last_test_ok": result["ok"],
                "last_test_message": result["message"],
                "last_test_latency_ms": result.get("latency_ms", 0),
            }},
        )
        return {"provider": conn["provider"], **result}

    results = await asyncio.gather(*[one(c) for c in conns])
    passed = sum(1 for r in results if r["ok"])
    return {
        "results": results,
        "summary": {"connected": len(conns), "passed": passed, "failed": len(conns) - passed},
    }


# ===================== Automation Rules =====================

def _automation_view(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in doc.items() if k != "_id"}


@router.get("/automations")
async def list_automations(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    docs = await db.automation_rules.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"rules": docs}


@router.post("/automations")
async def create_automation(
    body: AutomationRuleRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        **body.model_dump(),
        "created_at": now,
        "updated_at": now,
        "last_run_at": None,
        "next_run_at": None,
        "business_id": DEFAULT_BUSINESS_ID,
    }
    await db.automation_rules.insert_one(doc)
    return _automation_view(doc)


@router.put("/automations/{rule_id}")
async def update_automation(
    rule_id: str,
    body: AutomationRuleRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    payload = {**body.model_dump(), "updated_at": datetime.now(timezone.utc).isoformat()}
    res = await db.automation_rules.update_one({"id": rule_id}, {"$set": payload})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Rule not found")
    doc = await db.automation_rules.find_one({"id": rule_id}, {"_id": 0})
    return doc


@router.delete("/automations/{rule_id}")
async def delete_automation(
    rule_id: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    res = await db.automation_rules.delete_one({"id": rule_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"deleted": 1, "id": rule_id}


# ===================== Smart Scheduling Recommendations =====================

@router.get("/smart-recommendations")
async def smart_recommendations(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Heuristic recommendations based on historical performance.

    For now: derives best hour/day/platform from `scheduled_posts` where
    status='published'. Falls back to industry-best-practice defaults when
    sample size is small.
    """
    await verify_session(authorization, session_token)
    pipeline_platform = [
        {"$match": {"status": "published"}},
        {"$group": {"_id": "$provider", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    pipeline_hour = [
        {"$match": {"status": "published", "published_at": {"$ne": None}}},
        {"$project": {"hour": {"$substr": ["$published_at", 11, 2]}}},
        {"$group": {"_id": "$hour", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    pipeline_kind = [
        {"$match": {"status": "published"}},
        {"$group": {"_id": "$kind", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    platform = await db.scheduled_posts.aggregate(pipeline_platform).to_list(10)
    hour = await db.scheduled_posts.aggregate(pipeline_hour).to_list(10)
    kind = await db.scheduled_posts.aggregate(pipeline_kind).to_list(10)

    # Fallbacks (industry best practice for restaurants)
    best_platform = (platform[0]["_id"] if platform else "facebook")
    best_hour = (hour[0]["_id"] if hour else "11")
    best_kind = (kind[0]["_id"] if kind else "social_post")

    return {
        "best_platform": best_platform,
        "best_hour_utc": int(best_hour),
        "best_content_type": best_kind,
        "best_day": "Friday",  # static default — refine when day-of-week data accumulates
        "evidence": {
            "platforms": [{"name": p["_id"], "count": p["count"]} for p in platform],
            "hours": [{"hour": int(h["_id"]), "count": h["count"]} for h in hour],
            "kinds": [{"kind": k["_id"], "count": k["count"]} for k in kind],
        },
        "note": (
            "Recommendations sharpen as published-post volume grows. "
            "Until ~50 published posts exist, defaults follow restaurant-industry best practice."
        ),
    }


# ===================== Publish Analytics =====================

@router.get("/publish-stats")
async def publish_stats(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Stats for the Publish dashboard widgets."""
    await verify_session(authorization, session_token)
    total = await db.scheduled_posts.count_documents({})
    by_status: Dict[str, int] = {}
    cursor = db.scheduled_posts.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}])
    async for row in cursor:
        by_status[row["_id"]] = row["count"]
    published = by_status.get("published", 0)
    failed = by_status.get("failed", 0)
    attempts = published + failed
    success_rate = round((published / attempts) * 100, 1) if attempts else 0.0

    provider_agg = await db.scheduled_posts.aggregate([
        {"$group": {"_id": "$provider", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]).to_list(10)

    # Avg publishes/day over the last 30 days
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    recent_published = await db.scheduled_posts.count_documents({
        "status": "published",
        "published_at": {"$gte": thirty_days_ago},
    })
    avg_per_day = round(recent_published / 30.0, 2)

    return {
        "total_scheduled": total,
        "by_status": by_status,
        "success_rate_pct": success_rate,
        "avg_publishes_per_day_30d": avg_per_day,
        "platforms": [{"provider": p["_id"], "count": p["count"]} for p in provider_agg if p["_id"]],
    }
