"""Admin authentication: login, logout, verify, and verify_session dependency."""
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Response, Cookie, Header, Request

from config import db, verify_admin_password
from models import LoginRequest
from rate_limit import limiter

router = APIRouter(prefix="/auth")


async def verify_session(authorization: str = None, session_token: str = Cookie(None)):
    """Verify admin session via Bearer header or cookie (MongoDB-backed). Raises 401 if invalid."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif session_token:
        token = session_token

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = await db.admin_sessions.find_one({"token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Sprint 15B: prefer native BSON `expires_at`; fall back to legacy ISO-string `expires`.
    expires_at = session.get("expires_at") or session.get("expires")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if not expires_at or datetime.now(timezone.utc) > expires_at:
        await db.admin_sessions.delete_one({"token": token})
        raise HTTPException(status_code=401, detail="Session expired")

    return True


async def cleanup_expired_sessions() -> int:
    """Sprint 15B: Bulk-delete expired admin_sessions. Handles both native Date
    `expires_at` and legacy ISO-string `expires`. Returns number deleted.
    Called once on startup; the TTL index handles future expirations.
    """
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    r = await db.admin_sessions.delete_many({
        "$or": [
            {"expires_at": {"$lt": now}},
            {"expires": {"$lt": now_iso}},   # legacy string compare (ISO-8601 sorts lexically)
        ]
    })
    return r.deleted_count


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, data: LoginRequest, response: Response):
    if not verify_admin_password(data.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    session_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=24)

    # Sprint 15B: Store expires_at as native BSON Date so the TTL index can reap it.
    await db.admin_sessions.insert_one({
        "token": session_token,
        "created_at": now,
        "expires_at": expires,
    })

    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        max_age=86400,
        samesite="lax"
    )

    return {"message": "Login successful", "token": session_token}


@router.post("/logout")
async def logout(response: Response, authorization: str = Header(None), session_token: str = Cookie(None)):
    # Resolve token from Bearer header first, then cookie — mirrors verify_session
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif session_token:
        token = session_token

    if token:
        await db.admin_sessions.delete_one({"token": token})

    response.delete_cookie("session_token")
    return {"message": "Logged out"}


@router.get("/verify")
async def verify_auth(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    return {"authenticated": True}
