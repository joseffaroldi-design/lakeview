"""Library management — bulk delete + reference inspection.

Adds two admin endpoints for the Library "Clear / Delete Unused / Delete
Selected" flows:
  • POST /media/usage        — inspect which assets are referenced where
  • POST /media/bulk-delete  — safely delete a set of assets (skips
                                referenced ones unless force=true)

Reference sources:
  1. `site_images.slots` — asset_id → slot mapping (Website Images feature)
  2. `menu_categories.items[].photos` — per-item photo galleries

The Library uses the same allowlist for both endpoints so admins never see
a stale "no references" answer that then blocks the delete.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Cookie, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from auth import verify_session
from .shared import db

router = APIRouter()
log = logging.getLogger("uvicorn.error")


class UsageIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    asset_ids: List[str] = Field(default_factory=list)


class BulkDeleteIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # When present, only these ids are considered for deletion.
    # When empty AND `only_unused=True`, EVERY unused active asset is deleted
    # (this is how the "Clear Current Library" button works).
    asset_ids: List[str] = Field(default_factory=list)
    only_unused: bool = True
    # `force=True` allows deletion of referenced assets. The UI must show a
    # much stronger confirmation before sending this flag.
    force: bool = False


async def _collect_references() -> Dict[str, List[dict]]:
    """Scan the app for every place an asset_id is referenced. Returns
    { asset_id: [ {type, label}, ... ] }.

    Cheap enough to run on every /usage request — Lakeview has a single
    site-images doc and ~10 menu categories max.
    """
    refs: Dict[str, List[dict]] = {}

    # Site Images (single doc, keyed by slot).
    site_doc = await db.site_images.find_one({"id": "main"}, {"_id": 0, "slots": 1})
    slots = (site_doc or {}).get("slots", {}) if site_doc else {}
    for slot_key, entry in slots.items():
        aid = (entry or {}).get("asset_id")
        if aid:
            refs.setdefault(aid, []).append({"type": "site_image", "label": slot_key})

    # Menu item photo galleries.
    async for cat in db.menu_categories.find({}, {"_id": 0, "id": 1, "display_name": 1, "items": 1}):
        for item in cat.get("items") or []:
            photos = item.get("photos") or []
            for aid in photos:
                if not aid:
                    continue
                refs.setdefault(aid, []).append({
                    "type": "menu_item",
                    "label": f"{cat.get('display_name') or cat.get('id')} · {item.get('name') or 'item'}",
                })

    return refs


@router.post("/usage")
async def get_usage(
    body: UsageIn,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Return per-asset reference info for the supplied ids (or, if the
    list is empty, for every reference currently active in the system).
    """
    await verify_session(authorization, session_token)
    all_refs = await _collect_references()

    if body.asset_ids:
        payload = {aid: all_refs.get(aid, []) for aid in body.asset_ids}
    else:
        payload = all_refs

    total = sum(len(v) for v in payload.values())
    return {"usage": payload, "total_references": total}


@router.post("/bulk-delete")
async def bulk_delete(
    body: BulkDeleteIn,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Permanently delete a set of assets from the Library.

    Modes:
      • asset_ids + only_unused=True  → deletes only ids that are NOT
        referenced anywhere. Referenced ids are returned in `skipped`.
      • asset_ids + force=True        → deletes every supplied id even if
        referenced. Callers are expected to have shown a strong
        confirmation dialog. `site_images` fallbacks + menu photo lookups
        remain graceful (missing assets resolve to null/skip on read).
      • [] + only_unused=True         → "Clear Unused" — deletes every
        unreferenced active image asset in the Library.
      • [] + force=True               → not allowed (avoids catastrophic
        "delete everything" without an explicit id list).

    Note: `storage.py` for Emergent Object Storage has no delete API, so
    this endpoint removes the DB rows but the underlying bytes remain
    until purged out-of-band. Behaviour is documented in the UI.
    """
    await verify_session(authorization, session_token)

    if not body.asset_ids and body.force:
        raise HTTPException(
            status_code=400,
            detail="Refusing to force-delete every asset. Supply an explicit asset_ids list.",
        )

    # Pull the candidate set from Mongo. Restrict to active image assets
    # so we can never nuke ai-ads legacy rows or archived items.
    query = {"kind": "image", "status": {"$ne": "archived"}}
    if body.asset_ids:
        query["id"] = {"$in": body.asset_ids}
    candidate_docs = await db.media_assets.find(query, {"_id": 0, "id": 1}).to_list(2000)
    candidate_ids = [d["id"] for d in candidate_docs]

    refs = await _collect_references()
    referenced = {aid for aid in candidate_ids if refs.get(aid)}
    unused = [aid for aid in candidate_ids if aid not in referenced]

    if body.force:
        to_delete = candidate_ids
        skipped: List[str] = []
    else:
        to_delete = unused
        skipped = sorted(referenced)

    # Also report ids the client asked for that don't exist / aren't
    # eligible (already deleted, wrong kind, etc.) so the UI can show a
    # complete picture.
    missing: List[str] = []
    if body.asset_ids:
        missing = sorted(set(body.asset_ids) - set(candidate_ids))

    deleted = 0
    if to_delete:
        result = await db.media_assets.delete_many({"id": {"$in": to_delete}})
        deleted = int(getattr(result, "deleted_count", 0) or 0)

    log.info(
        "MEDIA_BULK_DELETE requested=%d deleted=%d skipped_referenced=%d missing=%d force=%s",
        len(body.asset_ids or candidate_ids), deleted, len(skipped), len(missing), body.force,
    )

    return {
        "requested": len(body.asset_ids) if body.asset_ids else len(candidate_ids),
        "deleted": deleted,
        "skipped_referenced": skipped,
        "missing": missing,
        "force": body.force,
        "storage_note": (
            "DB records removed. Underlying file bytes remain in Emergent "
            "Object Storage until purged out-of-band."
        ),
    }
