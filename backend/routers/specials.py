"""Specials CRUD (protected)."""
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, Header, Cookie

from config import db
from auth import verify_session
from models import Special, SpecialCreate, SpecialUpdate

router = APIRouter(prefix="/specials")


@router.post("", response_model=Special)
async def create_special(special: SpecialCreate, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    special_obj = Special(**special.model_dump())
    doc = special_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.specials.insert_one(doc)
    return special_obj


@router.get("", response_model=List[Special])
async def get_specials(active_only: bool = False):
    query = {"is_active": True} if active_only else {}
    specials = await db.specials.find(query, {"_id": 0}).to_list(100)
    for special in specials:
        if isinstance(special.get('created_at'), str):
            special['created_at'] = datetime.fromisoformat(special['created_at'])
    return specials


@router.get("/{special_id}", response_model=Special)
async def get_special(special_id: str):
    special = await db.specials.find_one({"id": special_id}, {"_id": 0})
    if not special:
        raise HTTPException(status_code=404, detail="Special not found")
    if isinstance(special.get('created_at'), str):
        special['created_at'] = datetime.fromisoformat(special['created_at'])
    return special


@router.put("/{special_id}", response_model=Special)
async def update_special(special_id: str, update: SpecialUpdate, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    result = await db.specials.update_one({"id": special_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Special not found")

    special = await db.specials.find_one({"id": special_id}, {"_id": 0})
    if isinstance(special.get('created_at'), str):
        special['created_at'] = datetime.fromisoformat(special['created_at'])
    return special


@router.delete("/{special_id}")
async def delete_special(special_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    result = await db.specials.delete_one({"id": special_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Special not found")
    return {"message": "Special deleted successfully"}
