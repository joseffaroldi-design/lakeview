"""Sprint 17A — Design Memory.

Per-menu-item visual preference store. Schema is intentionally small:
we only persist VISUAL preferences, never generated copy / captions /
videos. The Creative Director router reads this memory to bias its
recommendations, and Photo→Flyer offers "Use Saved Style" when an entry
exists.

Endpoints (all `/api/design-memory/*`):
  GET    /{item_key}            -> stored prefs or 404
  PUT    /{item_key}            -> upsert prefs (small whitelist)
  DELETE /{item_key}            -> clear

`item_key` mirrors the convention used by services/menu_matcher.py:
    `<category-slug>::<name-slug>` (lowercase, dash-separated).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, constr

from auth import verify_session
from config import db

router = APIRouter(prefix="/design-memory", tags=["design-memory"])
log = logging.getLogger("uvicorn.error")


# ---------------------------------------------------------------- model
class DesignMemoryPayload(BaseModel):
    """Whitelisted visual-only preferences. Anything else is ignored."""
    model_config = ConfigDict(extra="ignore")

    theme: Optional[constr(strip_whitespace=True, max_length=80)] = None
    layout: Optional[constr(strip_whitespace=True, max_length=40)] = None
    overlay: Optional[constr(strip_whitespace=True, max_length=40)] = None
    badge: Optional[constr(strip_whitespace=True, max_length=40)] = None
    typography: Optional[constr(strip_whitespace=True, max_length=40)] = None
    crop: Optional[constr(strip_whitespace=True, max_length=40)] = None
    harmony: Optional[constr(strip_whitespace=True, max_length=40)] = None
    favorite_flyer_id: Optional[constr(strip_whitespace=True, max_length=64)] = None
    # Sprint 17B — remember the owner's last AI-Vision vs Menu reconciliation
    # choice for this item, so the banner only nags once per dish.
    vision_choice: Optional[constr(strip_whitespace=True, max_length=20)] = None


_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*::[a-z0-9][a-z0-9\-]*$")


def _validate_key(item_key: str) -> str:
    item_key = (item_key or "").strip().lower()
    if not _KEY_RE.match(item_key) or len(item_key) > 200:
        raise HTTPException(status_code=400,
                            detail=f"Invalid item_key: {item_key!r}")
    return item_key


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- routes
@router.get("/{item_key}")
async def get_memory(item_key: str,
                     authorization: str = Header(None),
                     session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    item_key = _validate_key(item_key)
    doc = await db.design_memory.find_one({"item_key": item_key}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="No saved style for this item.")
    return doc


@router.put("/{item_key}")
async def upsert_memory(item_key: str,
                        body: DesignMemoryPayload,
                        authorization: str = Header(None),
                        session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    item_key = _validate_key(item_key)

    # Only store fields the caller actually supplied (model_dump exclude_none).
    fields = {k: v for k, v in body.model_dump(exclude_none=True).items() if v}
    if not fields:
        raise HTTPException(status_code=400, detail="Empty payload — nothing to save.")

    now = _now()
    existing = await db.design_memory.find_one({"item_key": item_key}, {"_id": 0})
    use_count = (existing or {}).get("use_count", 0) + 1
    created_at = (existing or {}).get("created_at", now)

    doc = {
        "item_key": item_key,
        **fields,
        "use_count": use_count,
        "created_at": created_at,
        "updated_at": now,
    }
    await db.design_memory.update_one(
        {"item_key": item_key},
        {"$set": doc},
        upsert=True,
    )
    # Return the full merged document so the FE sees all preserved fields,
    # not just the ones the caller supplied in this PUT.
    merged = await db.design_memory.find_one({"item_key": item_key}, {"_id": 0})
    log.info("DESIGN_MEMORY_SAVED item_key=%s fields=%s use_count=%d",
             item_key, sorted(fields.keys()), use_count)
    return merged or doc


@router.delete("/{item_key}")
async def delete_memory(item_key: str,
                        authorization: str = Header(None),
                        session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    item_key = _validate_key(item_key)
    result = await db.design_memory.delete_one({"item_key": item_key})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No saved style to clear.")
    return {"ok": True, "item_key": item_key}
