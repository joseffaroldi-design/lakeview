"""Giveaway (Spin & Win): settings, spin, entries."""
import random
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header, Cookie

from config import db
from auth import verify_session
from models import SpinRequest
from seed_data import DEFAULT_GIVEAWAY_SETTINGS

router = APIRouter(prefix="/giveaway")


@router.get("/settings")
async def get_giveaway_settings():
    settings = await db.giveaway_settings.find_one({}, {"_id": 0})
    if not settings:
        return DEFAULT_GIVEAWAY_SETTINGS
    return settings


@router.put("/settings")
async def update_giveaway_settings(data: dict, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    allowed = ["is_active", "title", "subtitle", "start_date", "end_date", "prizes"]
    update_fields = {k: v for k, v in data.items() if k in allowed}
    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields")
    result = await db.giveaway_settings.update_one({}, {"$set": update_fields})
    if result.matched_count == 0:
        await db.giveaway_settings.insert_one({**DEFAULT_GIVEAWAY_SETTINGS, **update_fields})
    updated = await db.giveaway_settings.find_one({}, {"_id": 0})
    return updated


@router.post("/spin")
async def spin_wheel(data: SpinRequest):
    settings = await db.giveaway_settings.find_one({}, {"_id": 0})
    if not settings or not settings.get("is_active"):
        raise HTTPException(status_code=400, detail="Giveaway is not active")

    email = data.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")

    existing = await db.giveaway_entries.find_one({"email": email})
    if existing:
        return {"already_entered": True, "prize": existing.get("prize"), "message": "You've already spun! Your prize: " + existing.get("prize", "N/A")}

    prizes = settings.get("prizes", [])
    if not prizes:
        raise HTTPException(status_code=500, detail="No prizes configured")

    weights = [p.get("weight", 1) for p in prizes]
    winner = random.choices(prizes, weights=weights, k=1)[0]

    prize_index = prizes.index(winner)

    entry = {
        "id": str(uuid.uuid4()),
        "name": data.name.strip(),
        "email": email,
        "phone": data.phone.strip() if data.phone else None,
        "prize": winner["label"],
        "prize_index": prize_index,
        "claimed": False,
        "entered_at": datetime.now(timezone.utc).isoformat()
    }
    await db.giveaway_entries.insert_one(entry)

    return {"already_entered": False, "prize": winner["label"], "prize_index": prize_index, "message": f"Congratulations! You won: {winner['label']}!"}


@router.get("/entries")
async def get_giveaway_entries(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    entries = await db.giveaway_entries.find({}, {"_id": 0}).sort("entered_at", -1).to_list(500)
    return {"entries": entries, "total": len(entries)}


@router.put("/entries/{entry_id}/claim")
async def mark_entry_claimed(entry_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    result = await db.giveaway_entries.update_one({"id": entry_id}, {"$set": {"claimed": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"message": "Marked as claimed"}


@router.get("/winners")
async def get_giveaway_winners():
    winners = await db.giveaway_entries.find(
        {"prize": {"$ne": "Try Again"}},
        {"_id": 0, "name": 1, "prize": 1, "entered_at": 1}
    ).sort("entered_at", -1).to_list(20)
    return {"winners": winners}
