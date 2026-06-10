"""Specials — read-only legacy surface.

Sprint 12A migrated every "special" into the `marketing_packs` collection with
`tag="special"`. Sprint 12C retires the `specials` collection entirely and
rewrites these two endpoints to read from `marketing_packs`.

The public response shape is preserved 1:1 so the Lakeview homepage / SEO JSON-LD
keeps rendering without a frontend change.

A one-release fallback to the legacy `specials` collection remains in place so
that, if the drop is ever rolled back or a doc was missed by the 12A migration,
the public site keeps showing the right item. Once the `specials` collection
is dropped this fallback returns nothing and the marketing_pack path serves
the request.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from config import db
from models import Special

router = APIRouter(prefix="/specials")


def _pack_to_special(pack: Dict[str, Any]) -> Dict[str, Any]:
    """Map a `marketing_packs` row (tag='special') to the public Special shape."""
    item = pack.get("item") or {}
    result = pack.get("result") or {}
    # If the pack has generated images, use the first one as image_url; otherwise
    # fall back to a manually-set image_url on the item itself.
    image_url = item.get("image_url")
    if not image_url:
        assets = (result.get("images") or []) if isinstance(result, dict) else []
        if assets and isinstance(assets[0], dict):
            image_url = assets[0].get("asset_url") or assets[0].get("storage_path") or None
    created = pack.get("created_at")
    if isinstance(created, str):
        try:
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            created = datetime.now(timezone.utc)
    elif not isinstance(created, datetime):
        created = datetime.now(timezone.utc)
    return {
        # Stable public id: prefer the original special id (preserved during 12A
        # migration). This keeps any external bookmarks / SEO URLs valid.
        "id": pack.get("migrated_from_special_id") or pack.get("id"),
        "title": item.get("name") or pack.get("title") or "Special",
        "description": item.get("description") or "",
        "price": item.get("price"),
        "image_url": image_url,
        "is_active": bool(pack.get("is_active", True)),
        "created_at": created,
    }


async def _fallback_legacy(active_only: bool) -> List[Dict[str, Any]]:
    """One-release fallback. Returns [] once the specials collection is dropped."""
    if "specials" not in await db.list_collection_names():
        return []
    q = {"is_active": True} if active_only else {}
    rows = await db.specials.find(q, {"_id": 0}).to_list(100)
    for r in rows:
        if isinstance(r.get("created_at"), str):
            try:
                r["created_at"] = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                r["created_at"] = datetime.now(timezone.utc)
    return rows


@router.get("", response_model=List[Special])
async def get_specials(active_only: bool = False):
    # Primary: marketing_packs where tag=special.
    pack_q: Dict[str, Any] = {"tag": "special"}
    if active_only:
        pack_q["is_active"] = True
    packs = await db.marketing_packs.find(pack_q, {"_id": 0}).sort("created_at", -1).to_list(100)
    specials = [_pack_to_special(p) for p in packs]
    if specials:
        return specials
    # Fallback (one release safety net).
    return await _fallback_legacy(active_only)


@router.get("/{special_id}", response_model=Special)
async def get_special(special_id: str):
    # Try marketing_packs by either migrated_from_special_id OR own id.
    pack = await db.marketing_packs.find_one(
        {"tag": "special", "$or": [{"migrated_from_special_id": special_id}, {"id": special_id}]},
        {"_id": 0},
    )
    if pack:
        return _pack_to_special(pack)
    # Fallback to legacy collection if it's still around.
    if "specials" in await db.list_collection_names():
        legacy = await db.specials.find_one({"id": special_id}, {"_id": 0})
        if legacy:
            if isinstance(legacy.get("created_at"), str):
                try:
                    legacy["created_at"] = datetime.fromisoformat(legacy["created_at"].replace("Z", "+00:00"))
                except Exception:  # noqa: BLE001
                    legacy["created_at"] = datetime.now(timezone.utc)
            return legacy
    raise HTTPException(status_code=404, detail="Special not found")
