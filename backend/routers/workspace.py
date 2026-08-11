"""Sprint 20A Phase 4 — Marketing Workspace router.

The Workspace turns each menu item into a marketing project that
organises every asset already generated for it. Projects are created
lazily on the first list call and stay idempotent; they store no
duplicated data — just an `item_key` and a couple of cached counts that
the list endpoint can recompute on demand.

Endpoints
---------
* GET  /api/workspace/projects                  → list projects (lazy backfill)
* GET  /api/workspace/projects/{item_key}       → single project + summary
* GET  /api/workspace/projects/{item_key}/designs   → linked flyer media_assets
* GET  /api/workspace/projects/{item_key}/videos    → linked video media_assets
* GET  /api/workspace/projects/{item_key}/captions  → captions from marketing_packs
* POST /api/workspace/projects/{item_key}/hero      → pin a flyer as hero
* POST /api/workspace/backfill                  → idempotent rebuild for ops
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Header, HTTPException, Query
from pydantic import BaseModel

from auth import verify_session
from config import db


router = APIRouter(prefix="/workspace", tags=["workspace"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def _item_key(category: str, name: str) -> str:
    return f"{_slug(category) or 'menu'}::{_slug(name)}"


# --------------------------------------------------- asset-linking helpers

def _name_matches(asset: Dict[str, Any], item_name: str, item_key: str) -> bool:
    """True if the asset is plausibly linked to the project's menu item."""
    if not asset:
        return False
    if (asset.get("item_name") or "").strip().lower() == item_name.strip().lower():
        return True
    tags = asset.get("tags") or []
    if any(isinstance(t, str) and t.startswith("item_key:") and t.endswith(item_key) for t in tags):
        return True
    if asset.get("menu_item_key") == item_key:
        return True
    fn = (asset.get("filename") or "").lower()
    if _slug(item_name) and _slug(item_name) in _slug(fn):
        return True
    return False


async def _assets_for_item(item_name: str, item_key: str, *, kind: str) -> List[Dict[str, Any]]:
    """Find all media assets whose item_name OR tag/filename matches."""
    item_name_lc = item_name.strip().lower()
    or_clauses = [
        {"item_name": {"$regex": f"^{re.escape(item_name)}$", "$options": "i"}},
        {"tags": f"item_key:{item_key}"},
        {"menu_item_key": item_key},
    ]
    if _slug(item_name):
        or_clauses.append({"filename": {"$regex": _slug(item_name), "$options": "i"}})
    cursor = db.media_assets.find(
        {"kind": kind, "status": "active", "$or": or_clauses},
        {"_id": 0},
    ).sort("uploaded_at", -1).limit(200)
    out = await cursor.to_list(length=200)
    # Belt-and-braces: filter out anything that slipped through unrelated.
    return [a for a in out if _name_matches(a, item_name, item_key)]


# --------------------------------------------------- project shape

class Project(BaseModel):
    item_key: str
    item_name: str
    category: str
    category_slug: str
    price: Optional[str]
    active: bool = True
    hero_asset_id: Optional[str] = None
    favorite_theme: Optional[str] = None
    favorite_flyer_id: Optional[str] = None
    flyer_count: int = 0
    video_count: int = 0
    caption_count: int = 0
    last_promoted_at: Optional[str] = None
    last_generated_at: Optional[str] = None
    quality_score: Optional[float] = None
    is_featured_today: bool = False
    created_at: str
    updated_at: str


async def _menu_items() -> List[Dict[str, Any]]:
    """Flatten the menu into (item_key, item_name, category, category_slug, price)."""
    cats = await db.menu_categories.find({}).sort("sort_order", 1).to_list(length=None)
    out: List[Dict[str, Any]] = []
    for cat in cats:
        cat_name = cat.get("display_name") or cat.get("name") or ""
        cat_slug = cat.get("slug") or _slug(cat_name)
        for it in (cat.get("items") or []):
            name = (it.get("name") or "").strip()
            if not name:
                continue
            price = it.get("price")
            price_str = (
                f"${price:.2f}" if isinstance(price, (int, float))
                else (price or "")
            )
            out.append({
                "item_key": _item_key(cat_slug or cat_name, name),
                "item_name": name,
                "category": cat_name,
                "category_slug": cat_slug,
                "price": price_str,
                "active": bool(it.get("is_active", True)),
            })
    return out


async def _featured_asset_id() -> Optional[str]:
    """Today's Featured asset id — used to flag the project that owns it."""
    try:
        from routers.html_template import featured  # type: ignore
        data = await featured()
        return data.get("asset_id")
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------- backfill (idempotent)

async def _ensure_projects() -> int:
    """Upsert one project per menu item. Idempotent.
    Returns the number of NEW projects created (existing ones untouched)."""
    items = await _menu_items()
    created = 0
    now = _now_iso()
    for it in items:
        existing = await db.marketing_projects.find_one({"item_key": it["item_key"]}, {"_id": 0, "item_key": 1})
        if existing:
            # Refresh the menu metadata fields (price, category) but keep
            # mutable workspace fields alone.
            await db.marketing_projects.update_one(
                {"item_key": it["item_key"]},
                {"$set": {
                    "item_name": it["item_name"],
                    "category": it["category"],
                    "category_slug": it["category_slug"],
                    "price": it["price"],
                    "active": it["active"],
                    "updated_at": now,
                }},
            )
            continue
        doc = {
            **it,
            "hero_asset_id": None,
            "favorite_theme": None,
            "favorite_flyer_id": None,
            "created_at": now,
            "updated_at": now,
        }
        await db.marketing_projects.insert_one(doc)
        created += 1
    return created


# --------------------------------------------------- project hydration

async def _hydrate_project(proj: Dict[str, Any], featured_id: Optional[str]) -> Dict[str, Any]:
    """Attach counts + derived fields. One project at a time keeps the
    aggregate query small; the list endpoint amortises with concurrent
    asyncio.gather."""
    item_key = proj["item_key"]
    item_name = proj["item_name"]

    flyers = await _assets_for_item(item_name, item_key, kind="image")
    videos = await _assets_for_item(item_name, item_key, kind="video")

    # captions live inside marketing_packs.result.captions[*]
    pack = await db.marketing_packs.find_one(
        {"menu_item_key": item_key, "status": "complete"},
        {"_id": 0, "result": 1, "updated_at": 1},
        sort=[("updated_at", -1)],
    )
    caption_count = 0
    if pack and isinstance(pack.get("result"), dict):
        caps = pack["result"].get("captions") or pack["result"].get("copy") or {}
        if isinstance(caps, dict):
            caption_count = sum(1 for v in caps.values() if v)
        elif isinstance(caps, list):
            caption_count = len(caps)

    # Hero asset: pinned > most-recent flyer
    hero_id = proj.get("hero_asset_id")
    if not hero_id and flyers:
        hero_id = flyers[0]["id"]

    # Favorite theme + favorite flyer come from design_memory.
    fav = await db.design_memory.find_one(
        {"item_key": {"$regex": f"::{_slug(item_name)}", "$options": "i"}},
        {"_id": 0, "theme": 1, "favorite_flyer_id": 1, "updated_at": 1},
        sort=[("updated_at", -1)],
    )
    fav_theme = (fav or {}).get("theme") or proj.get("favorite_theme")
    fav_flyer = (fav or {}).get("favorite_flyer_id") or proj.get("favorite_flyer_id")

    # last_promoted_at from menu_promotions
    promo = await db.menu_promotions.find_one(
        {"item_key": {"$regex": f"::{_slug(item_name)}", "$options": "i"}},
        {"_id": 0, "last_promoted_at": 1},
    )
    last_promoted = (promo or {}).get("last_promoted_at")
    last_generated = flyers[0].get("uploaded_at") if flyers else None

    return {
        **proj,
        "hero_asset_id": hero_id,
        "favorite_theme": fav_theme,
        "favorite_flyer_id": fav_flyer,
        "flyer_count": len(flyers),
        "video_count": len(videos),
        "caption_count": caption_count,
        "last_promoted_at": last_promoted,
        "last_generated_at": last_generated,
        "quality_score": None,
        "is_featured_today": bool(featured_id) and (hero_id == featured_id),
    }


# --------------------------------------------------- endpoints

@router.get("/projects")
async def list_projects(
    backfill: bool = Query(default=True, description="Ensure every menu item has a project."),
    include_inactive: bool = Query(default=False),
):
    if backfill:
        await _ensure_projects()

    q: Dict[str, Any] = {}
    if not include_inactive:
        q["active"] = True
    raw = await db.marketing_projects.find(q, {"_id": 0}).sort([("category", 1), ("item_name", 1)]).to_list(length=200)
    featured_id = await _featured_asset_id()

    # ---- Batch queries — list view must load in < 1s for 50-100 projects.
    # We pull *one* dataset per kind/collection and bucket by lowercased
    # item_name in Python; that keeps mongo round-trips constant (~4)
    # instead of O(N_projects).
    names_lc = {p["item_name"].strip().lower(): p["item_key"] for p in raw}
    slugs = {_slug(p["item_name"]): p["item_key"] for p in raw}

    def _bucket_for_asset(a: Dict[str, Any]) -> Optional[str]:
        nm = (a.get("item_name") or "").strip().lower()
        if nm in names_lc:
            return names_lc[nm]
        for t in (a.get("tags") or []):
            if isinstance(t, str) and t.startswith("item_key:"):
                k = t.split(":", 2)[-1]
                if k in {p["item_key"] for p in raw}:
                    return k
        mk = a.get("menu_item_key")
        if mk in {p["item_key"] for p in raw}:
            return mk
        fn_slug = _slug(a.get("filename") or "")
        for s, key in slugs.items():
            if s and s in fn_slug:
                return key
        return None

    # 1) flyer + video counts via a single sweep of recent active assets.
    asset_cursor = db.media_assets.find(
        {"status": "active", "kind": {"$in": ["image", "video"]}},
        {"_id": 0, "id": 1, "kind": 1, "item_name": 1, "tags": 1,
         "menu_item_key": 1, "filename": 1, "uploaded_at": 1},
    ).sort("uploaded_at", -1).limit(5000)
    flyer_counts: Dict[str, int] = {}
    video_counts: Dict[str, int] = {}
    hero_candidates: Dict[str, str] = {}     # latest flyer asset_id per key
    last_generated: Dict[str, str] = {}
    async for a in asset_cursor:
        key = _bucket_for_asset(a)
        if not key:
            continue
        if a.get("kind") == "image":
            flyer_counts[key] = flyer_counts.get(key, 0) + 1
            if key not in hero_candidates:
                hero_candidates[key] = a["id"]
                last_generated[key] = a.get("uploaded_at")
        elif a.get("kind") == "video":
            video_counts[key] = video_counts.get(key, 0) + 1

    # 2) caption counts via a single marketing_packs sweep.
    caption_counts: Dict[str, int] = {}
    pack_cursor = db.marketing_packs.find(
        {"status": "complete"},
        {"_id": 0, "menu_item_key": 1, "result": 1, "item": 1},
    ).limit(2000)
    async for pk in pack_cursor:
        item_key = pk.get("menu_item_key")
        if not item_key or item_key not in {p["item_key"] for p in raw}:
            # Also try matching by item name embedded in the pack.
            it = pk.get("item") or {}
            cand_name = (it.get("name") or "").strip().lower()
            item_key = names_lc.get(cand_name)
            if not item_key:
                continue
        result = pk.get("result") or {}
        copy = result.get("captions") or result.get("copy") or {}
        n = 0
        if isinstance(copy, dict):
            n = sum(1 for v in copy.values() if v)
        elif isinstance(copy, list):
            n = len(copy)
        caption_counts[item_key] = max(caption_counts.get(item_key, 0), n)

    # 3) favorite theme / favorite flyer via a single design_memory sweep.
    fav_by_slug: Dict[str, Dict[str, Any]] = {}
    async for dm in db.design_memory.find({}, {"_id": 0, "item_key": 1, "theme": 1,
                                               "favorite_flyer_id": 1, "updated_at": 1}):
        ikey = dm.get("item_key") or ""
        # split on `::` and take the item-slug side
        if "::" in ikey:
            slug = ikey.split("::", 1)[1]
        else:
            slug = ikey
        # Drop trailing 6-char hash if present (legacy pattern: foo-bar-abc123)
        slug_clean = re.sub(r"-[a-f0-9]{6}$", "", slug)
        for s in (slug_clean, slug):
            if s in slugs:
                cur = fav_by_slug.get(s)
                if not cur or (dm.get("updated_at") or "") > (cur.get("updated_at") or ""):
                    fav_by_slug[s] = dm
                break

    # 4) last_promoted_at via a single menu_promotions sweep.
    promo_by_slug: Dict[str, str] = {}
    async for mp in db.menu_promotions.find({}, {"_id": 0, "item_key": 1, "last_promoted_at": 1}):
        ikey = mp.get("item_key") or ""
        if "::" in ikey:
            slug = ikey.split("::", 1)[1]
        else:
            slug = ikey
        slug_clean = re.sub(r"-[a-f0-9]{6}$", "", slug)
        for s in (slug_clean, slug):
            if s in slugs:
                promo_by_slug[s] = mp.get("last_promoted_at")
                break

    # ---- Compose
    out: List[Dict[str, Any]] = []
    for p in raw:
        key = p["item_key"]
        name_slug = _slug(p["item_name"])
        fav = fav_by_slug.get(name_slug) or {}
        hero_id = p.get("hero_asset_id") or hero_candidates.get(key)
        out.append({
            **p,
            "hero_asset_id": hero_id,
            "favorite_theme": fav.get("theme") or p.get("favorite_theme"),
            "favorite_flyer_id": fav.get("favorite_flyer_id") or p.get("favorite_flyer_id"),
            "flyer_count": flyer_counts.get(key, 0),
            "video_count": video_counts.get(key, 0),
            "caption_count": caption_counts.get(key, 0),
            "last_promoted_at": promo_by_slug.get(name_slug),
            "last_generated_at": last_generated.get(key),
            "quality_score": None,
            "is_featured_today": bool(featured_id) and (hero_id == featured_id),
        })

    return {"projects": out, "total": len(out), "featured_asset_id": featured_id}


@router.get("/projects/{item_key}")
async def get_project(item_key: str):
    proj = await db.marketing_projects.find_one({"item_key": item_key}, {"_id": 0})
    if not proj:
        # Try to auto-create on demand if the key matches a menu item.
        await _ensure_projects()
        proj = await db.marketing_projects.find_one({"item_key": item_key}, {"_id": 0})
        if not proj:
            raise HTTPException(status_code=404, detail=f"project not found: {item_key}")
    featured_id = await _featured_asset_id()
    return await _hydrate_project(proj, featured_id)


@router.get("/projects/{item_key}/designs")
async def project_designs(item_key: str, limit: int = Query(default=50, ge=1, le=200)):
    proj = await db.marketing_projects.find_one({"item_key": item_key}, {"_id": 0, "item_name": 1})
    if not proj:
        raise HTTPException(status_code=404, detail="project not found")
    out = await _assets_for_item(proj["item_name"], item_key, kind="image")
    return {"designs": out[:limit], "total": len(out)}


@router.get("/projects/{item_key}/videos")
async def project_videos(item_key: str, limit: int = Query(default=50, ge=1, le=200)):
    proj = await db.marketing_projects.find_one({"item_key": item_key}, {"_id": 0, "item_name": 1})
    if not proj:
        raise HTTPException(status_code=404, detail="project not found")
    out = await _assets_for_item(proj["item_name"], item_key, kind="video")
    return {"videos": out[:limit], "total": len(out)}


@router.get("/projects/{item_key}/captions")
async def project_captions(item_key: str):
    proj = await db.marketing_projects.find_one({"item_key": item_key}, {"_id": 0, "item_name": 1})
    if not proj:
        raise HTTPException(status_code=404, detail="project not found")
    packs = await db.marketing_packs.find(
        {"menu_item_key": item_key, "status": "complete"},
        {"_id": 0, "id": 1, "result": 1, "updated_at": 1, "item": 1},
    ).sort("updated_at", -1).limit(10).to_list(length=10)

    # Flatten the latest pack's captions to a simple list of channels.
    latest = packs[0] if packs else None
    captions: List[Dict[str, Any]] = []
    if latest and isinstance(latest.get("result"), dict):
        result = latest["result"]
        copy = result.get("captions") or result.get("copy") or {}
        if isinstance(copy, dict):
            for channel, text in copy.items():
                if text:
                    captions.append({"channel": channel, "text": text})
        elif isinstance(copy, list):
            for c in copy:
                if isinstance(c, dict):
                    captions.append(c)

    return {
        "captions": captions,
        "history": [{"id": p["id"], "updated_at": p["updated_at"]} for p in packs],
        "total": len(captions),
    }


class HeroBody(BaseModel):
    asset_id: str


@router.post("/projects/{item_key}/hero")
async def set_hero(
    item_key: str,
    body: HeroBody,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    proj = await db.marketing_projects.find_one({"item_key": item_key}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=404, detail="project not found")
    asset = await db.media_assets.find_one({"id": body.asset_id, "status": "active"}, {"_id": 0, "id": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found or archived")
    await db.marketing_projects.update_one(
        {"item_key": item_key},
        {"$set": {"hero_asset_id": body.asset_id, "updated_at": _now_iso()}},
    )
    return {"ok": True, "hero_asset_id": body.asset_id}


@router.post("/backfill")
async def backfill_projects(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Ops endpoint — idempotent rebuild of the marketing_projects collection
    from the current menu. Safe to call any time."""
    await verify_session(authorization, session_token)
    created = await _ensure_projects()
    total = await db.marketing_projects.count_documents({})
    return {"created": created, "total": total}
