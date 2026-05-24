"""Loyalty punch card: join, lookup, stamp, claim."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header, Cookie, Request

from config import db
from auth import verify_session
from models import LoyaltyJoinRequest
from rate_limit import limiter

router = APIRouter(prefix="/loyalty")


@router.post("/join")
@limiter.limit("5/minute")
async def join_loyalty(request: Request, data: LoyaltyJoinRequest):
    phone = data.phone.strip()
    name = data.name.strip()
    if not phone or not name:
        raise HTTPException(status_code=400, detail="Name and phone are required")

    existing = await db.loyalty_members.find_one({"phone": phone})
    if existing:
        return {"already_member": True, "visits": existing.get("visits", 0), "reward_earned": existing.get("reward_earned", False), "message": "Welcome back! You have " + str(existing.get("visits", 0)) + " visits."}

    member = {
        "id": str(uuid.uuid4()),
        "name": name,
        "phone": phone,
        "visits": 0,
        "reward_earned": False,
        "reward_claimed": False,
        "joined_at": datetime.now(timezone.utc).isoformat()
    }
    await db.loyalty_members.insert_one(member)
    return {"already_member": False, "visits": 0, "reward_earned": False, "message": "Welcome to the Lakeview Loyalty Club!"}


@router.get("/lookup")
async def lookup_loyalty(phone: str):
    member = await db.loyalty_members.find_one({"phone": phone.strip()}, {"_id": 0})
    if not member:
        raise HTTPException(status_code=404, detail="Not a loyalty member")
    return member


@router.get("/members")
async def get_loyalty_members(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    members = await db.loyalty_members.find({}, {"_id": 0}).sort("joined_at", -1).to_list(500)
    return {"members": members, "total": len(members)}


@router.put("/members/{member_id}/stamp")
async def stamp_loyalty(member_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    member = await db.loyalty_members.find_one({"id": member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    new_visits = member.get("visits", 0) + 1
    reward_earned = new_visits >= 10
    await db.loyalty_members.update_one({"id": member_id}, {"$set": {"visits": new_visits, "reward_earned": reward_earned}})
    return {"visits": new_visits, "reward_earned": reward_earned, "message": "Free meal earned!" if reward_earned and not member.get("reward_earned") else "Visit stamped!"}


@router.put("/members/{member_id}/claim")
async def claim_loyalty_reward(member_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    member = await db.loyalty_members.find_one({"id": member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if not member.get("reward_earned"):
        raise HTTPException(status_code=400, detail="Reward not yet earned")
    await db.loyalty_members.update_one({"id": member_id}, {"$set": {"reward_claimed": True, "visits": 0, "reward_earned": False}})
    return {"message": "Reward claimed! Punch card reset."}
