"""Site image slot mapping — admin-editable images for the public site.

Reuses the existing media pipeline (/api/media/upload → media_assets) and
adds a thin slot→asset mapping layer so admins can point each public-site
image slot at any asset already in the Library (or a freshly uploaded one).

Public GET is unauthenticated and returns { slot: resolved_url_or_null }.
Missing/removed assets return null so the FE silently falls back to its
hard-coded defaults.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Cookie, Response
from pydantic import BaseModel, ConfigDict

from config import db
from auth import verify_session

router = APIRouter(prefix="/site-images")

# Canonical slot allowlist — must match the `SLOT_KEYS` array in
# `frontend/src/config/siteImages.js`. Any change here must be mirrored on
# the FE (and vice-versa).
ALLOWED_SLOTS = {
    "hero",       # Menu-page hero (large photo at top of /menu)
    "homeHero",   # Homepage hero (burger photo on / )
    "burger",     # Favorites: Lakeview Burger
    "poboy",      # Favorites: Shrimp Po'boy
    "fries",      # Favorites: Café Fries
    "tenders",    # Favorites: Chicken Tenders
    "tacos",      # Favorites: Shrimp Tacos
    "catering",   # Catering block photo
    "about",      # Our Story photo
}

# Short cache — same policy as /api/content. Owner edits invalidate on next
# fetch because `must-revalidate` forces an If-Modified-Since revalidation.
_PUBLIC_CACHE = "public, max-age=60, must-revalidate"


class SlotAssignIn(BaseModel):
    """Admin assigns a slot to either an existing media asset (preferred)
    or a raw URL (fallback for e.g. externally-hosted CDN photos)."""

    model_config = ConfigDict(extra="ignore")
    asset_id: Optional[str] = None
    url: Optional[str] = None


def _asset_url(asset_id: str) -> str:
    """Canonical URL for serving an asset. Uses the existing media route so
    we never duplicate storage or expose raw storage paths."""
    return f"/api/media/file/{asset_id}"


async def _resolve_slot(entry: dict) -> Optional[str]:
    """Turn a stored slot entry into a usable URL, or None if the referenced
    asset has been deleted / never existed."""
    if not entry:
        return None
    if entry.get("asset_id"):
        # Verify the asset still exists so we don't return a dead link.
        asset = await db.media_assets.find_one(
            {"id": entry["asset_id"], "status": "active"}, {"_id": 0, "id": 1},
        )
        if not asset:
            return None
        return _asset_url(entry["asset_id"])
    if entry.get("url"):
        return entry["url"]
    return None


@router.get("")
async def get_site_images(response: Response):
    """Public — returns { slot: url_or_null } for every allowed slot.

    Slots without a valid override are returned as `null` so the FE can
    quietly fall back to its hard-coded defaults without a second request.
    """
    response.headers["Cache-Control"] = _PUBLIC_CACHE
    doc = await db.site_images.find_one({"id": "main"}, {"_id": 0})
    slots = (doc or {}).get("slots", {}) if doc else {}

    resolved: dict = {}
    for slot in ALLOWED_SLOTS:
        entry = slots.get(slot)
        resolved[slot] = await _resolve_slot(entry)
    return {
        "slots": resolved,
        "updated_at": (doc or {}).get("updated_at") if doc else None,
    }


@router.put("/{slot}")
async def set_site_image(
    slot: str,
    body: SlotAssignIn,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Admin — assign an asset (or raw URL) to a slot.

    Prefers `asset_id` when provided; validates that the asset exists in
    media_assets before persisting so we can't point a slot at a phantom.
    """
    await verify_session(authorization, session_token)

    if slot not in ALLOWED_SLOTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown slot '{slot}'. Allowed: {sorted(ALLOWED_SLOTS)}",
        )
    if not body.asset_id and not body.url:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'asset_id' or 'url'.",
        )

    entry: dict = {}
    if body.asset_id:
        asset = await db.media_assets.find_one(
            {"id": body.asset_id, "status": "active"}, {"_id": 0, "id": 1, "kind": 1},
        )
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        if asset.get("kind") not in (None, "image"):
            raise HTTPException(status_code=400, detail="Only image assets can be assigned to a slot")
        entry["asset_id"] = body.asset_id
    else:
        # Only allow http(s) URLs — cheap safety net against javascript: / data: injection.
        u = (body.url or "").strip()
        if not (u.startswith("http://") or u.startswith("https://") or u.startswith("/")):
            raise HTTPException(status_code=400, detail="URL must be http(s) or a site-relative path")
        entry["url"] = u

    now = datetime.now(timezone.utc).isoformat()
    entry["updated_at"] = now

    await db.site_images.update_one(
        {"id": "main"},
        {"$set": {f"slots.{slot}": entry, "updated_at": now}},
        upsert=True,
    )
    resolved_url = await _resolve_slot(entry)
    return {"slot": slot, "url": resolved_url, "updated_at": now}


@router.post("/{slot}/reset")
async def reset_site_image(
    slot: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Admin — clear the override for a slot. The public site will fall
    back to its hard-coded default on the next fetch."""
    await verify_session(authorization, session_token)
    if slot not in ALLOWED_SLOTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown slot '{slot}'. Allowed: {sorted(ALLOWED_SLOTS)}",
        )
    now = datetime.now(timezone.utc).isoformat()
    await db.site_images.update_one(
        {"id": "main"},
        {"$unset": {f"slots.{slot}": ""}, "$set": {"updated_at": now}},
        upsert=True,
    )
    return {"slot": slot, "url": None, "updated_at": now}
