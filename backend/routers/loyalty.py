"""Loyalty punch card: join, lookup, stamp, claim."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header, Cookie, Request

from config import db
from auth import verify_session
from models import LoyaltyJoinRequest
from routers.settings import get_settings_document
from rate_limit import limiter

router = APIRouter(prefix="/loyalty")


async def _loyalty_config():
    settings = await get_settings_document()
    cfg = settings.get("loyalty") or {}
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "visits_required": max(1, int(cfg.get("visits_required", 10) or 10)),
        "reward_label": str(cfg.get("reward_label") or "Free meal"),
    }


async def _record_event(member_id: str, event_type: str, delta: int, reason: str, balance: int):
    await db.loyalty_events.insert_one({
        "id": str(uuid.uuid4()),
        "member_id": member_id,
        "event_type": event_type,
        "delta": delta,
        "reason": reason,
        "balance": balance,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


@router.post("/join")
@limiter.limit("5/minute")
async def join_loyalty(request: Request, data: LoyaltyJoinRequest):
    phone = data.phone.strip()
    name = data.name.strip()
    if not phone or not name:
        raise HTTPException(status_code=400, detail="Name and phone are required")

    cfg = await _loyalty_config()
    if not cfg["enabled"]:
        raise HTTPException(status_code=503, detail="Loyalty program is currently paused")

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

    cfg = await _loyalty_config()
    new_visits = member.get("visits", 0) + 1
    reward_earned = new_visits >= cfg["visits_required"]
    await db.loyalty_members.update_one({"id": member_id}, {"$set": {"visits": new_visits, "reward_earned": reward_earned}})
    await _record_event(member_id, "stamp", 1, "Visit stamped", new_visits)
    return {
        "visits": new_visits,
        "reward_earned": reward_earned,
        "visits_required": cfg["visits_required"],
        "message": f"{cfg['reward_label']} earned!" if reward_earned and not member.get("reward_earned") else "Visit stamped!",
    }


@router.put("/members/{member_id}/claim")
async def claim_loyalty_reward(member_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    member = await db.loyalty_members.find_one({"id": member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if not member.get("reward_earned"):
        raise HTTPException(status_code=400, detail="Reward not yet earned")
    prior_visits = int(member.get("visits", 0) or 0)
    await db.loyalty_members.update_one({"id": member_id}, {"$set": {"reward_claimed": True, "visits": 0, "reward_earned": False}})
    await _record_event(member_id, "redeem", -prior_visits, "Reward claimed", 0)
    return {"message": "Reward claimed! Punch card reset."}


@router.get("/members/{member_id}/activity")
async def loyalty_activity(member_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    rows = await db.loyalty_events.find({"member_id": member_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"events": rows}


@router.put("/members/{member_id}/adjust")
async def adjust_loyalty(member_id: str, data: dict, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    member = await db.loyalty_members.find_one({"id": member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    try:
        delta = int(data.get("delta"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="delta must be an integer")
    reason = str(data.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Adjustment reason is required")
    cfg = await _loyalty_config()
    new_visits = max(0, int(member.get("visits", 0) or 0) + delta)
    reward_earned = new_visits >= cfg["visits_required"]
    await db.loyalty_members.update_one({"id": member_id}, {"$set": {"visits": new_visits, "reward_earned": reward_earned}})
    await _record_event(member_id, "adjustment", delta, reason, new_visits)
    return {"visits": new_visits, "reward_earned": reward_earned, "visits_required": cfg["visits_required"]}
