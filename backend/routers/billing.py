"""Billing routes — virtual budget visibility + reset.

Surfaces:
  GET  /api/billing/status         — current balance + tier + estimated packs remaining
  GET  /api/billing/usage          — recent llm_usage events (admin debug)
  POST /api/billing/reset          — "I just topped up Emergent" — resets virtual balance to cap
  POST /api/billing/cap            — Admin: set new monthly cap
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Cookie, Header

from auth import verify_session
from config import db
import billing

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/status")
async def get_status(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    return await billing.get_status(db)


@router.get("/usage")
async def get_usage(
    limit: int = 50,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    cursor = db.llm_usage.find({}, {"_id": 0}).sort("created_at", -1).limit(min(limit, 200))
    events = await cursor.to_list(min(limit, 200))
    total_spent = sum(e.get("cost_usd", 0) for e in events)
    return {"events": events, "count": len(events), "spent_in_window_usd": round(total_spent, 4)}


@router.post("/reset")
async def reset_balance(authorization: str = Header(None), session_token: str = Cookie(None)):
    """Owner clicks this AFTER they actually added balance in Emergent."""
    await verify_session(authorization, session_token)
    return await billing.reset_balance(db)


@router.post("/cap")
async def set_cap(
    payload: dict = Body(...),
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    return await billing.set_cap(db, float(payload.get("monthly_cap_usd", 0)))
