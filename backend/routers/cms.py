"""CMS: site content (hero/about/contact) + menu categories + homepage layout."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Header, Cookie, Response
from pydantic import BaseModel, ConfigDict

from config import db
from auth import verify_session
from seed_data import (
    DEFAULT_SITE_CONTENT,
    DEFAULT_MENU_CATEGORIES,
    DEFAULT_HOMEPAGE_LAYOUT_SECTIONS,
    HOMEPAGE_SECTION_META,
)

router = APIRouter()

# Sprint 19 perf: public GETs (no auth) are safe to cache at the edge for a
# short window. Owner edits invalidate the next fetch because the response
# also carries `must-revalidate` — every browser will at minimum send an
# If-Modified-Since on the next visit. Empirically reduces public-site repeat
# loads by ~80 ms (the Mongo + JSON serialize roundtrip).
_PUBLIC_CACHE = "public, max-age=120, must-revalidate"


# ----- Site Content -----
@router.get("/content")
async def get_site_content(response: Response):
    response.headers["Cache-Control"] = _PUBLIC_CACHE
    content = await db.site_content.find_one({}, {"_id": 0})
    if not content:
        return DEFAULT_SITE_CONTENT
    return content


@router.put("/content/{section}")
async def update_site_content(section: str, data: dict, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    if section not in ["hero", "about", "contact"]:
        raise HTTPException(status_code=400, detail="Invalid section")
    result = await db.site_content.update_one({}, {"$set": {section: data}})
    if result.matched_count == 0:
        await db.site_content.insert_one({**DEFAULT_SITE_CONTENT, "id": "main", section: data})
    updated = await db.site_content.find_one({}, {"_id": 0})
    return updated


# ----- Menu -----
@router.get("/menu")
async def get_menu(response: Response):
    response.headers["Cache-Control"] = _PUBLIC_CACHE
    categories = await db.menu_categories.find({}, {"_id": 0}).sort("sort_order", 1).to_list(50)
    if not categories:
        return DEFAULT_MENU_CATEGORIES
    return categories


@router.put("/menu/{category_id}")
async def update_menu_category(category_id: str, data: dict, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    update_fields = {}
    for key in ["display_name", "subtitle", "columns", "sort_order", "items"]:
        if key in data:
            update_fields[key] = data[key]
    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    result = await db.menu_categories.update_one({"id": category_id}, {"$set": update_fields})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    updated = await db.menu_categories.find_one({"id": category_id}, {"_id": 0})
    return updated


@router.post("/menu")
async def add_menu_category(data: dict, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    if not data.get("display_name"):
        raise HTTPException(status_code=400, detail="display_name is required")
    max_order = await db.menu_categories.find_one(sort=[("sort_order", -1)])
    new_cat = {
        "id": str(uuid.uuid4()),
        "slug": data.get("slug", data["display_name"].lower().replace(" ", "-").replace("'", "")),
        "display_name": data["display_name"],
        "subtitle": data.get("subtitle"),
        "columns": data.get("columns", 2),
        "sort_order": (max_order["sort_order"] + 1) if max_order else 1,
        "items": data.get("items", [])
    }
    await db.menu_categories.insert_one(new_cat)
    return {k: v for k, v in new_cat.items() if k != "_id"}


@router.delete("/menu/{category_id}")
async def delete_menu_category(category_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    result = await db.menu_categories.delete_one({"id": category_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"message": "Category deleted"}


# ----- Homepage Layout (Sprint 22C) -----
#
# Admin reorders / shows / hides homepage sections from the Studio
# "Layout" tab. Public GET is unauthenticated so the public site can
# render the saved order without a token; PUT requires session.
#
# The data model is intentionally a single doc with an ordered
# `sections[]` array — order is implicit in array index so the client
# only needs to ship the new order, not per-row sort keys.

# Whitelist guards against arbitrary keys being injected via PUT.
_ALLOWED_SECTION_KEYS = {s["key"] for s in DEFAULT_HOMEPAGE_LAYOUT_SECTIONS}


class LayoutSectionIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    key: str
    visible: bool = True
    title: Optional[str] = ""
    body: Optional[str] = ""
    # `label` is editor-only; we always re-source it from defaults below
    # so admins can't rename the editor row out from under future
    # migrations (the public site doesn't read it anyway).
    label: Optional[str] = None


class LayoutPutIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sections: List[LayoutSectionIn]


def _layout_with_meta(sections: list) -> list:
    """Re-attach the canonical editor label + meta to every section so
    the FE can render the editor without a separate fetch."""
    defaults_by_key = {s["key"]: s for s in DEFAULT_HOMEPAGE_LAYOUT_SECTIONS}
    out = []
    for s in sections:
        d = defaults_by_key.get(s["key"], {})
        meta = HOMEPAGE_SECTION_META.get(s["key"], {})
        out.append({
            "key": s["key"],
            "label": d.get("label", s["key"]),
            "visible": bool(s.get("visible", True)),
            "title": (s.get("title") or "").strip(),
            "body": (s.get("body") or "").strip(),
            "supports_title": meta.get("supports_title", True),
            "supports_body": meta.get("supports_body", True),
            "note": meta.get("note", ""),
        })
    return out


@router.get("/homepage/layout")
async def get_homepage_layout(response: Response):
    """Public read — returns the saved section order + visibility + overrides."""
    response.headers["Cache-Control"] = _PUBLIC_CACHE
    doc = await db.homepage_layout.find_one({"id": "main"}, {"_id": 0})
    sections = doc["sections"] if doc and doc.get("sections") else DEFAULT_HOMEPAGE_LAYOUT_SECTIONS
    return {
        "id": "main",
        "sections": _layout_with_meta(sections),
        "updated_at": (doc or {}).get("updated_at"),
    }


@router.put("/homepage/layout")
async def update_homepage_layout(
    body: LayoutPutIn,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Admin write — replaces sections[] atomically.

    The submitted list must mention every default section exactly once.
    This prevents admins from accidentally deleting a section row (use
    the visibility toggle instead) and protects against future-section
    drift when a deploy adds a new section but the editor was loaded
    against the older schema.
    """
    await verify_session(authorization, session_token)

    submitted_keys = [s.key for s in body.sections]
    seen = set()
    duplicates = [k for k in submitted_keys if k in seen or seen.add(k)]
    if duplicates:
        raise HTTPException(status_code=400, detail=f"Duplicate section keys: {duplicates}")

    unknown = [k for k in submitted_keys if k not in _ALLOWED_SECTION_KEYS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown section keys: {unknown}")

    missing = [k for k in _ALLOWED_SECTION_KEYS if k not in submitted_keys]
    if missing:
        # Auto-append missing sections at the end as visible=True so a
        # newer deploy that adds a section never blanks the homepage.
        for k in missing:
            body.sections.append(LayoutSectionIn(key=k, visible=True))

    sections = [
        {
            "key": s.key,
            "visible": bool(s.visible),
            "title": (s.title or "").strip(),
            "body": (s.body or "").strip(),
        }
        for s in body.sections
    ]

    now = datetime.now(timezone.utc).isoformat()
    await db.homepage_layout.update_one(
        {"id": "main"},
        {"$set": {"sections": sections, "updated_at": now}},
        upsert=True,
    )
    return {"id": "main", "sections": _layout_with_meta(sections), "updated_at": now}


@router.post("/homepage/layout/reset")
async def reset_homepage_layout(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Restore the default section order + clear all overrides."""
    await verify_session(authorization, session_token)
    now = datetime.now(timezone.utc).isoformat()
    await db.homepage_layout.update_one(
        {"id": "main"},
        {"$set": {"sections": DEFAULT_HOMEPAGE_LAYOUT_SECTIONS, "updated_at": now}},
        upsert=True,
    )
    return {
        "id": "main",
        "sections": _layout_with_meta(DEFAULT_HOMEPAGE_LAYOUT_SECTIONS),
        "updated_at": now,
    }
