"""CMS: site content (hero/about/contact) + menu categories."""
import uuid
from fastapi import APIRouter, HTTPException, Header, Cookie

from config import db
from auth import verify_session
from seed_data import DEFAULT_SITE_CONTENT, DEFAULT_MENU_CATEGORIES

router = APIRouter()


# ----- Site Content -----
@router.get("/content")
async def get_site_content():
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
async def get_menu():
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
