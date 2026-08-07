"""Today's Pick — Daily automated menu item recommendation with pre-drafted marketing copy + graphics.

Sprint 13A → Sprint 14A: Full automation.

Flow:
  - Daily 5:30 AM: Cron generates 3 PIL graphics (no AI, deterministic)
  - Daily 6:00 AM: Cron generates copy (FB, IG, GBP, SMS, Email)
  - Owner opens app: Graphic + copy ready. Zero wait time.
  - GET /api/todays-pick/today          → Fetch today's pick (with graphics + copy)
  - POST /api/todays-pick/override      → Owner picks different item from top 5
  - PATCH /api/todays-pick/metrics      → Track acceptance/rejection/posted
  - POST /api/todays-pick/analytics     → Track usage events (viewed, posted, etc.)
  - GET /api/todays-pick/alternatives   → Top 5 eligible items for "Pick Different"

Selection Logic:
  1. Scan menu_categories.items[]
  2. Find item with oldest promotion date (from marketing_packs)
  3. Exclude items promoted in last 7 days
  4. Exclude disabled items (if field exists)
  5. Generate 3 PIL graphics (modern theme, 3 layouts)
  6. Generate marketing copy (FB, IG, Google Business, SMS, Email, Hashtags)
  7. Store graphics + copy in todays_pick collection with date key

Sprint 14A: Added PIL graphic generation, analytics tracking, deep links.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Header, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image
from pydantic import BaseModel, Field

from auth import verify_session
from ai_engine.client import generate_structured
import storage as objstore

# Item 4 (Feb 2026): PIL composition helpers extracted to
# services.todays_pick_graphics. Re-exported here for backward compat
# with any callers still importing the old paths. Snapshot-verified
# byte-identical output — see tests/test_todays_pick_graphics_snapshot.py.
from services.todays_pick_graphics import (  # noqa: F401 — re-exports
    CANVAS,
    VARIATION_LABELS,
    RESTAURANT_BRANDING,
    FONT_SERIF_BOLD,
    FONT_SERIF,
    FONT_SANS_BOLD,
    FONT_SANS,
    THEME,
    LAYOUTS,
    _font,
    _wrap_text,
    _generate_simple_background,
    _draw_title,
    _draw_price_badge,
    _draw_branding,
    _compose_simple_design,
)

router = APIRouter(prefix="/todays-pick", tags=["todays-pick"])

mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]

log = logging.getLogger("uvicorn.error")


# ---------------------------------------------------------------- schemas

class OverrideRequest(BaseModel):
    item_key: str = Field(..., description="Category::Item identifier, e.g., 'appetizers::cafe-fries'")
    reason: Optional[str] = Field(None, max_length=200)


class MetricsUpdate(BaseModel):
    accepted: Optional[bool] = None
    rejected: Optional[bool] = None
    posted: Optional[bool] = None


class AnalyticsEvent(BaseModel):
    """Sprint 14A: Track usage before deciding what to delete."""
    event: str = Field(..., description="Event name: todays_pick_viewed, todays_pick_posted, ai_designer_opened, library_opened, etc.")
    metadata: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------- helpers

def _today_key() -> str:
    """Returns YYYY-MM-DD for today (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _flatten_menu_items() -> List[Dict[str, Any]]:
    """Flatten menu_categories.items[] into a single list with category context."""
    categories = await db.menu_categories.find({}, {"_id": 0}).to_list(100)
    flat = []
    for cat in categories:
        cat_name = cat.get("display_name") or cat.get("slug", "")
        for item in cat.get("items", []):
            # Skip if disabled (future-proof)
            if item.get("disabled") or item.get("hidden"):
                continue
            item_name = item.get("name", "")
            if not item_name:
                continue
            item_key = f"{cat.get('slug', '')}::{item_name.lower().replace(' ', '-')}"
            flat.append({
                "item_key": item_key,
                "name": item_name,
                "description": item.get("description", ""),
                "price": item.get("price", ""),
                "category": cat_name,
                "photo_url": item.get("photo_url"),  # May be None
            })
    return flat


async def _get_promotion_history() -> Dict[str, Dict[str, Any]]:
    """Returns {item_name.lower(): {'last_promoted': iso_timestamp, 'count': int}}."""
    history = {}
    async for pack in db.marketing_packs.find(
        {"status": "completed"},
        {"_id": 0, "item.name": 1, "updated_at": 1}
    ):
        item_name = ((pack.get("item") or {}).get("name") or "").lower()
        if not item_name:
            continue
        ts = pack.get("updated_at", "")
        if item_name not in history or history[item_name]["last_promoted"] < ts:
            history[item_name] = {
                "last_promoted": ts,
                "count": history.get(item_name, {}).get("count", 0) + 1,
            }
    return history


async def _select_top_items(limit: int = 5) -> List[Dict[str, Any]]:
    """Return top N items ranked by days since last promotion."""
    flat = await _flatten_menu_items()
    if not flat:
        return []
    
    history = await _get_promotion_history()
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    
    enriched = []
    for item in flat:
        item_lower = item["name"].lower()
        last_promo = history.get(item_lower, {}).get("last_promoted")
        
        # Exclude items promoted in last 7 days
        if last_promo:
            try:
                last_dt = datetime.fromisoformat(last_promo.replace("Z", "+00:00"))
                if last_dt > week_ago:
                    continue  # Too recent
                days_since = (now - last_dt).days
            except Exception:
                days_since = 999
        else:
            days_since = 999  # Never promoted
        
        enriched.append({
            **item,
            "days_since_promoted": days_since,
            "last_promoted": last_promo,
            "score": days_since,
        })
    
    # Sort by score descending (oldest first)
    enriched.sort(key=lambda x: -x["score"])
    return enriched[:limit]


async def _generate_graphics_for_item(item: Dict[str, Any]) -> List[Dict[str, str]]:
    """Generate 3 PIL marketing graphics for an item (Sprint 14A)."""
    log.info("Generating graphics for Today's Pick: %s", item["name"])
    
    graphics = []
    for idx, layout in enumerate(LAYOUTS):
        try:
            # Generate graphic
            img_bytes = await asyncio.to_thread(
                _compose_simple_design,
                item["name"],
                item.get("price"),
                layout,
                THEME
            )
            
            # Upload to storage
            asset_id = str(uuid.uuid4())
            storage_path = objstore.make_path("todays_pick", asset_id, "jpg")
            # Production hotfix — objstore.put_bytes is a blocking
            # requests.put. Offload to a worker thread so it doesn't
            # starve the event loop.
            await asyncio.to_thread(
                objstore.put_bytes, storage_path, img_bytes, "image/jpeg",
            )
            
            # Create media_assets entry
            doc = {
                "id": asset_id,
                "filename": f"todays-pick-{_today_key()}-{VARIATION_LABELS[idx]}.jpg",
                "kind": "image",
                "mime": "image/jpeg",
                "size_bytes": len(img_bytes),
                "width": CANVAS,
                "height": CANVAS,
                "duration_seconds": None,
                "folder": "Today's Pick",
                "tags": ["todays-pick", f"variation-{VARIATION_LABELS[idx]}"],
                "storage_path": storage_path,
                "is_favorite": False,
                "status": "active",
                "source": "todays_pick",
                "uploaded_at": _now(),
                "updated_at": _now(),
            }
            await db.media_assets.insert_one(doc)
            
            graphics.append({
                "variation": VARIATION_LABELS[idx],
                "asset_id": asset_id,
                "url": f"/api/media/download/{asset_id}",
                "thumb_url": f"/api/media/thumb/{asset_id}",
            })
            
            log.info("Generated graphic %s for Today's Pick", VARIATION_LABELS[idx])
        except Exception as e:
            log.error("Failed to generate graphic %s: %s", VARIATION_LABELS[idx], e)
            # Continue with other variations even if one fails
    
    return graphics


async def _generate_copy_for_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Generate marketing copy for a single item using LLM."""
    log.info("Generating copy for Today's Pick: %s", item["name"])
    
    system_prompt = (
        "You are a marketing copywriter for Lakeview Burgers & Seafood, "
        "a family-owned New Orleans restaurant. Write compelling, authentic copy "
        "that captures Gulf Coast flavor and local pride."
    )
    
    user_prompt = (
        f"Item: {item['name']}\n"
        f"Description: {item.get('description', 'N/A')}\n"
        f"Price: {item.get('price', 'N/A')}\n"
        f"Category: {item.get('category', 'N/A')}\n"
        f"Context: This item hasn't been promoted in {item.get('days_since_promoted', 'many')} days.\n\n"
        "Generate marketing copy for all channels:\n"
        " - caption: 30-60 words for Instagram/Facebook, conversational, 1-2 emojis max.\n"
        " - hashtags: 8-12 relevant hashtags as strings (no '#' prefix).\n"
        " - sms: under 140 chars, punchy call-to-action.\n"
        " - email_subject: 4-7 words, attention-grabbing.\n"
        " - email_body: 60-120 words, friendly tone, includes price.\n"
        " - gbp: 80-180 words for Google Business Profile, includes clear offer.\n"
    )
    
    schema = (
        '{"caption":"string","hashtags":["string"],"sms":"string",'
        '"email_subject":"string","email_body":"string","gbp":"string"}'
    )
    
    try:
        result = await generate_structured(
            db,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_hint=schema,
        )
        out = result.get("data", {})
        return {
            "caption": (out.get("caption") or "").strip()[:1500],
            "hashtags": [h.lstrip("#").strip() for h in (out.get("hashtags") or [])][:15],
            "sms": (out.get("sms") or "").strip()[:160],
            "email": {
                "subject": (out.get("email_subject") or "").strip()[:120],
                "body": (out.get("email_body") or "").strip()[:2000],
            },
            "gbp": (out.get("gbp") or "").strip()[:1500],
        }
    except Exception as e:
        log.error("Copy generation failed for %s: %s", item["name"], e)
        return {
            "caption": f"Try our delicious {item['name']} today!",
            "hashtags": ["lakeview", "nola", "seafood", "burgers"],
            "sms": f"Try {item['name']} - {item.get('price', '')}",
            "email": {
                "subject": f"Don't miss our {item['name']}",
                "body": f"Come taste our {item['name']} today. {item.get('description', '')}",
            },
            "gbp": f"Featured today: {item['name']}. {item.get('description', '')} ${item.get('price', '')}",
        }
    """Generate marketing copy for a single item using LLM."""
    log.info("Generating copy for Today's Pick: %s", item["name"])
    
    system_prompt = (
        "You are a marketing copywriter for Lakeview Burgers & Seafood, "
        "a family-owned New Orleans restaurant. Write compelling, authentic copy "
        "that captures Gulf Coast flavor and local pride."
    )
    
    user_prompt = (
        f"Item: {item['name']}\n"
        f"Description: {item.get('description', 'N/A')}\n"
        f"Price: {item.get('price', 'N/A')}\n"
        f"Category: {item.get('category', 'N/A')}\n"
        f"Context: This item hasn't been promoted in {item.get('days_since_promoted', 'many')} days.\n\n"
        "Generate marketing copy for all channels:\n"
        " - caption: 30-60 words for Instagram/Facebook, conversational, 1-2 emojis max.\n"
        " - hashtags: 8-12 relevant hashtags as strings (no '#' prefix).\n"
        " - sms: under 140 chars, punchy call-to-action.\n"
        " - email_subject: 4-7 words, attention-grabbing.\n"
        " - email_body: 60-120 words, friendly tone, includes price.\n"
        " - gbp: 80-180 words for Google Business Profile, includes clear offer.\n"
    )
    
    schema = (
        '{"caption":"string","hashtags":["string"],"sms":"string",'
        '"email_subject":"string","email_body":"string","gbp":"string"}'
    )
    
    try:
        result = await generate_structured(
            db,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_hint=schema,
        )
        out = result.get("data", {})
        return {
            "caption": (out.get("caption") or "").strip()[:1500],
            "hashtags": [h.lstrip("#").strip() for h in (out.get("hashtags") or [])][:15],
            "sms": (out.get("sms") or "").strip()[:160],
            "email": {
                "subject": (out.get("email_subject") or "").strip()[:120],
                "body": (out.get("email_body") or "").strip()[:2000],
            },
            "gbp": (out.get("gbp") or "").strip()[:1500],
        }
    except Exception as e:
        log.error("Copy generation failed for %s: %s", item["name"], e)
        return {
            "caption": f"Try our delicious {item['name']} today!",
            "hashtags": ["lakeview", "nola", "seafood", "burgers"],
            "sms": f"Try {item['name']} - {item.get('price', '')}",
            "email": {
                "subject": f"Don't miss our {item['name']}",
                "body": f"Come taste our {item['name']} today. {item.get('description', '')}",
            },
            "gbp": f"Featured today: {item['name']}. {item.get('description', '')} ${item.get('price', '')}",
        }


async def _create_todays_pick(item: Dict[str, Any], is_override: bool = False, 
                              original_key: Optional[str] = None, reason: Optional[str] = None) -> Dict[str, Any]:
    """Create or update today's pick with generated copy + graphics (Sprint 14A)."""
    today = _today_key()
    
    # Generate graphics first
    graphics = await _generate_graphics_for_item(item)
    
    # Then generate copy
    copy = await _generate_copy_for_item(item)
    
    doc = {
        "id": f"pick-{today}",
        "date": today,
        "original_item_key": original_key or item["item_key"],
        "selected_item_key": item["item_key"],
        "was_overridden": is_override,
        "override_reason": reason,
        "item": {
            "name": item["name"],
            "description": item.get("description", ""),
            "price": item.get("price", ""),
            "category": item.get("category", ""),
            "photo_url": item.get("photo_url"),
            "days_since_promoted": item.get("days_since_promoted"),
        },
        "graphics": graphics,  # Sprint 14A: Pre-generated graphics
        "copy": copy,
        "status": "ready",
        "metrics": {
            "accepted": False,
            "rejected": False,
            "posted": False,
        },
        "created_at": _now(),
        "updated_at": _now(),
    }
    
    # Upsert by date
    await db.todays_pick.update_one(
        {"date": today},
        {"$set": doc},
        upsert=True
    )
    
    log.info("Today's Pick created/updated for %s: %s (with %d graphics)", today, item["name"], len(graphics))
    return doc


# ---------------------------------------------------------------- public function for cron

async def generate_todays_pick_job():
    """Called by APScheduler daily at 6 AM. Selects item + generates copy."""
    try:
        log.info("TODAYS_PICK_CRON: Starting daily pick generation")
        
        # Check if today's pick already exists
        today = _today_key()
        existing = await db.todays_pick.find_one({"date": today}, {"_id": 0})
        if existing:
            log.info("Today's pick already exists for %s, skipping", today)
            return
        
        top_items = await _select_top_items(limit=5)
        if not top_items:
            log.warning("No eligible items found for Today's Pick")
            return
        
        winner = top_items[0]
        await _create_todays_pick(winner)
        
        # Track metric
        await db.llm_usage.insert_one({
            "id": str(uuid.uuid4()),
            "event": "TODAYS_PICK_CREATED",
            "date": today,
            "item_name": winner["name"],
            "created_at": _now(),
        })
        
        log.info("TODAYS_PICK_CRON: Successfully created pick for %s", winner["name"])
    except Exception as e:
        log.error("TODAYS_PICK_CRON failed: %s", e, exc_info=True)


# ---------------------------------------------------------------- endpoints

@router.get("/today")
async def get_todays_pick(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Fetch today's pick. If none exists, generate on-demand."""
    await verify_session(authorization, session_token)
    
    today = _today_key()
    pick = await db.todays_pick.find_one({"date": today}, {"_id": 0})
    
    if not pick:
        # Generate on-demand if cron hasn't run yet
        log.info("Today's pick not found, generating on-demand")
        top_items = await _select_top_items(limit=5)
        if not top_items:
            raise HTTPException(status_code=404, detail="No eligible items for Today's Pick")
        pick = await _create_todays_pick(top_items[0])
    
    return pick


@router.get("/alternatives")
async def get_alternatives(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Return top 5 eligible items for 'Pick Different Item' flow."""
    await verify_session(authorization, session_token)
    
    items = await _select_top_items(limit=5)
    return {"items": items, "count": len(items)}


@router.post("/override")
async def override_pick(
    body: OverrideRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Owner manually selects a different item. Keeps original for audit."""
    await verify_session(authorization, session_token)
    
    today = _today_key()
    existing = await db.todays_pick.find_one({"date": today}, {"_id": 0})
    
    if not existing:
        raise HTTPException(status_code=404, detail="No pick exists for today")
    
    # Find the selected item
    flat = await _flatten_menu_items()
    selected = next((it for it in flat if it["item_key"] == body.item_key), None)
    if not selected:
        raise HTTPException(status_code=404, detail="Selected item not found in menu")
    
    # Enrich with promotion data
    history = await _get_promotion_history()
    last_promo = history.get(selected["name"].lower(), {}).get("last_promoted")
    if last_promo:
        try:
            last_dt = datetime.fromisoformat(last_promo.replace("Z", "+00:00"))
            selected["days_since_promoted"] = (datetime.now(timezone.utc) - last_dt).days
        except Exception:
            selected["days_since_promoted"] = 999
    else:
        selected["days_since_promoted"] = 999
    
    # Create new pick with override flag
    new_pick = await _create_todays_pick(
        selected,
        is_override=True,
        original_key=existing["original_item_key"],
        reason=body.reason,
    )
    
    # Track metric
    await db.llm_usage.insert_one({
        "id": str(uuid.uuid4()),
        "event": "TODAYS_PICK_OVERRIDDEN",
        "date": today,
        "from_item": existing["item"]["name"],
        "to_item": selected["name"],
        "reason": body.reason,
        "created_at": _now(),
    })
    
    return new_pick


@router.patch("/metrics")
async def update_metrics(
    body: MetricsUpdate,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Track user actions: accepted, rejected, posted."""
    await verify_session(authorization, session_token)
    
    today = _today_key()
    existing = await db.todays_pick.find_one({"date": today}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="No pick for today")
    
    updates = {}
    events = []
    
    if body.accepted is not None:
        updates["metrics.accepted"] = body.accepted
        if body.accepted:
            events.append("TODAYS_PICK_ACCEPTED")
    
    if body.rejected is not None:
        updates["metrics.rejected"] = body.rejected
        if body.rejected:
            events.append("TODAYS_PICK_REJECTED")
    
    if body.posted is not None:
        updates["metrics.posted"] = body.posted
        if body.posted:
            events.append("TODAYS_PICK_POSTED")
    
    if updates:
        updates["updated_at"] = _now()
        await db.todays_pick.update_one({"date": today}, {"$set": updates})
    
    # Track events
    for event in events:
        await db.llm_usage.insert_one({
            "id": str(uuid.uuid4()),
            "event": event,
            "date": today,
            "item_name": existing["item"]["name"],
            "created_at": _now(),
        })
    
    updated = await db.todays_pick.find_one({"date": today}, {"_id": 0})
    return updated


@router.post("/analytics")
async def track_analytics(
    body: AnalyticsEvent,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Sprint 14A: Track usage events before deciding what to delete.
    
    Events:
    - todays_pick_viewed
    - todays_pick_posted
    - todays_pick_caption_copied
    - todays_pick_facebook_opened
    - todays_pick_instagram_opened
    - ai_designer_opened
    - recent_design_reopened
    - library_opened
    - promote_this_item_opened
    """
    await verify_session(authorization, session_token)
    
    event_doc = {
        "id": str(uuid.uuid4()),
        "event": body.event,
        "metadata": body.metadata or {},
        "created_at": _now(),
    }
    
    await db.usage_analytics.insert_one(event_doc)
    
    log.info("Analytics tracked: %s", body.event)
    
    return {"status": "tracked", "event": body.event}
