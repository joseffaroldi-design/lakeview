"""Asset CRUD + file streaming + folders + stats."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, constr

from auth import verify_session
import storage as objstore
from .shared import DEFAULT_FOLDERS, _ensure_thumb_bytes, _now, db

router = APIRouter()


@router.get("/assets")
async def list_assets(
    q: Optional[str] = None,
    kind: Optional[str] = None,
    folder: Optional[str] = None,
    status: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    # Sprint 17B — Smart Menu Workflow filters
    theme: Optional[str] = None,
    item_key: Optional[str] = None,
    since: Optional[str] = None,  # ISO date string (uploaded_at >= since)
    sort: Optional[str] = None,   # "smart" (default) | "uploaded_at"
    limit: int = 200,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    query: Dict[str, Any] = {}
    if kind:
        query["kind"] = kind
    if folder:
        query["folder"] = folder
    if status:
        query["status"] = status
    else:
        query["status"] = {"$ne": "archived"}
    if is_favorite is not None:
        query["is_favorite"] = is_favorite
    if theme:
        # Match both the new top-level field and legacy tag form for back-compat.
        query["$or"] = [{"theme": theme}, {"tags": f"theme:{theme}"}]
    if item_key:
        query["item_key"] = item_key
    if since:
        query["uploaded_at"] = {"$gte": since}
    if q:
        text_or = [
            {"filename": {"$regex": q, "$options": "i"}},
            {"tags": {"$regex": q, "$options": "i"}},
            {"item_name": {"$regex": q, "$options": "i"}},
        ]
        if "$or" in query:
            query = {"$and": [{"$or": query.pop("$or")}, {"$or": text_or}, query]}
        else:
            query["$or"] = text_or
    # Sprint 12C: media_assets now also holds legacy ai-ads text rows
    # (source=ai_ads_legacy). Hide them from the Media Studio list — they're
    # only ever read via /api/ai-ads/assets.
    query["source"] = {"$ne": "ai_ads_legacy"}

    # Smart sort: favorites first, then most-recently-used/uploaded, then the rest.
    # Mongo can't sort by a derived "last_activity" so we do it client-side here.
    if sort and sort != "smart":
        cursor = db.media_assets.find(query, {"_id": 0}).sort("uploaded_at", -1).limit(min(limit, 500))
        return {"assets": await cursor.to_list(500)}

    rows = await db.media_assets.find(query, {"_id": 0}).limit(min(limit, 500)).to_list(500)

    def _activity(a: Dict[str, Any]) -> str:
        return a.get("last_used_at") or a.get("updated_at") or a.get("uploaded_at") or ""

    rows.sort(key=lambda a: (
        0 if a.get("is_favorite") else 1,  # favorites first
        _activity(a),                      # ascending placeholder — we negate via reverse
    ))
    # Within the favorites bucket and within the rest, more-recent first.
    favs = [a for a in rows if a.get("is_favorite")]
    rest = [a for a in rows if not a.get("is_favorite")]
    favs.sort(key=_activity, reverse=True)
    rest.sort(key=_activity, reverse=True)
    return {"assets": favs + rest}


@router.get("/file/{asset_id}")
async def get_file(asset_id: str):
    """Public — assets are publicly addressable by id (uuid4 is unguessable)."""
    asset = await db.media_assets.find_one({"id": asset_id}, {"_id": 0, "storage_path": 1, "mime": 1, "filename": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    try:
        data, _ = objstore.get_bytes(asset["storage_path"])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File missing in storage")
    headers = {"Content-Disposition": f'inline; filename="{asset.get("filename", asset_id)}"'}
    return Response(content=data, media_type=asset.get("mime") or "application/octet-stream", headers=headers)


@router.get("/thumb/{asset_id}")
async def get_thumb(asset_id: str):
    asset = await db.media_assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    thumb = await _ensure_thumb_bytes(asset)
    if thumb:
        return Response(content=thumb, media_type="image/jpeg")
    # Fallback to original (e.g. thumb generation failed)
    return await get_file(asset_id)


class AssetPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    filename: Optional[constr(min_length=1, max_length=200)] = None
    folder: Optional[constr(max_length=60)] = None
    tags: Optional[List[str]] = None
    is_favorite: Optional[bool] = None
    status: Optional[constr(pattern=r"^(active|archived)$")] = None


@router.patch("/assets/{asset_id}")
async def patch_asset(
    asset_id: str, body: AssetPatch,
    authorization: str = Header(None), session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    update = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    update["updated_at"] = _now()
    res = await db.media_assets.update_one({"id": asset_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Asset not found")
    return await db.media_assets.find_one({"id": asset_id}, {"_id": 0})


@router.post("/assets/{asset_id}/used")
async def mark_used(asset_id: str,
                    authorization: str = Header(None),
                    session_token: str = Cookie(None)):
    """Sprint 17B — bump last_used_at so the smart sort surfaces the
    flyers the owner actually downloads / remixes. Idempotent; rate-limit
    not required because each call just stamps `now()`."""
    await verify_session(authorization, session_token)
    res = await db.media_assets.update_one(
        {"id": asset_id},
        {"$set": {"last_used_at": _now(), "updated_at": _now()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"ok": True, "id": asset_id, "last_used_at": _now()}


@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    """Soft-delete — Mongo row goes status='archived', file remains in storage
    (Emergent Object Storage has no delete API; bytes stay until purged out-of-band)."""
    await verify_session(authorization, session_token)
    res = await db.media_assets.update_one(
        {"id": asset_id},
        {"$set": {"status": "archived", "updated_at": _now()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"deleted": 1, "id": asset_id, "mode": "soft"}


@router.post("/assets/{asset_id}/duplicate")
async def duplicate_asset(asset_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    src = await db.media_assets.find_one({"id": asset_id}, {"_id": 0})
    if not src:
        raise HTTPException(status_code=404, detail="Asset not found")
    new_id = str(uuid.uuid4())
    ext = src["storage_path"].rsplit(".", 1)[-1]
    new_path = objstore.make_path(src.get("source", "uploads"), new_id, ext)
    try:
        data, _ = objstore.get_bytes(src["storage_path"])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Source file missing in storage")
    objstore.put_bytes(new_path, data, src.get("mime") or "application/octet-stream")
    clone = {**src, "id": new_id, "storage_path": new_path,
             "filename": f"{src['filename']} (Copy)", "is_favorite": False,
             "uploaded_at": _now(), "updated_at": _now()}
    await db.media_assets.insert_one(clone)
    return {k: v for k, v in clone.items() if k != "_id"}


@router.get("/folders")
async def list_folders(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    agg = await db.media_assets.aggregate([
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$folder", "count": {"$sum": 1}}},
    ]).to_list(50)
    counts = {row["_id"]: row["count"] for row in agg if row.get("_id")}
    out = [{"name": f, "count": counts.get(f, 0)} for f in DEFAULT_FOLDERS]
    return {"folders": out}


@router.get("/stats")
async def media_stats(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    images_total = await db.media_assets.count_documents({"kind": "image", "status": "active"})
    videos_total = await db.media_assets.count_documents({"kind": "video", "status": "active"})
    ai_images = await db.media_assets.count_documents({"source": "ai_image", "status": "active"})
    rendered = await db.media_assets.count_documents({"source": "video_render", "status": "active"})
    # Sprint 15B: render_jobs collection dropped with MediaStudio. Queue counter retained at 0 for API back-compat.
    return {
        "images_uploaded": images_total - ai_images,
        "videos_uploaded": videos_total - rendered,
        "ai_images_generated": ai_images,
        "videos_rendered": rendered,
        "active_render_jobs": 0,
        "total_assets": images_total + videos_total,
    }
