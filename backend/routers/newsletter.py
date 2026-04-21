"""Newsletter email subscription."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header, Cookie

from config import db
from auth import verify_session
from models import NewsletterSubscribe

router = APIRouter(prefix="/newsletter")


@router.post("/subscribe")
async def subscribe_newsletter(data: NewsletterSubscribe):
    email = data.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")

    existing = await db.newsletter_subscribers.find_one({"email": email})
    if existing:
        return {"message": "You're already on our list!", "already_subscribed": True}

    doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "subscribed_at": datetime.now(timezone.utc).isoformat(),
        "source": "website"
    }
    await db.newsletter_subscribers.insert_one(doc)
    return {"message": "Welcome to the Lakeview family!", "already_subscribed": False}


@router.get("/subscribers")
async def get_newsletter_subscribers(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    subscribers = await db.newsletter_subscribers.find({}, {"_id": 0}).to_list(1000)
    return {"subscribers": subscribers, "total": len(subscribers)}
