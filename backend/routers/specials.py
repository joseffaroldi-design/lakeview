"""Specials — read-only legacy surface (Phase 12A).

Writes were retired when SpecialsTab was removed from the dashboard. A "special"
is now modeled as a `marketing_pack` with `tag="special"`. The two endpoints
below remain only to keep the public homepage working without a deploy gap.
"""
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException

from config import db
from models import Special

router = APIRouter(prefix="/specials")


@router.get("", response_model=List[Special])
async def get_specials(active_only: bool = False):
    query = {"is_active": True} if active_only else {}
    specials = await db.specials.find(query, {"_id": 0}).to_list(100)
    for special in specials:
        if isinstance(special.get("created_at"), str):
            special["created_at"] = datetime.fromisoformat(special["created_at"])
    return specials


@router.get("/{special_id}", response_model=Special)
async def get_special(special_id: str):
    special = await db.specials.find_one({"id": special_id}, {"_id": 0})
    if not special:
        raise HTTPException(status_code=404, detail="Special not found")
    if isinstance(special.get("created_at"), str):
        special["created_at"] = datetime.fromisoformat(special["created_at"])
    return special
