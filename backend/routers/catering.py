"""Catering inquiries."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header, Cookie

from config import db
from auth import verify_session
from models import CateringInquiry

router = APIRouter(prefix="/catering")


@router.post("/inquiry")
async def submit_catering_inquiry(data: CateringInquiry):
    if not data.name.strip() or not data.email.strip() or not data.message.strip():
        raise HTTPException(status_code=400, detail="Name, email, and message are required")

    doc = {
        "id": str(uuid.uuid4()),
        "name": data.name.strip(),
        "email": data.email.strip().lower(),
        "phone": data.phone.strip() if data.phone else None,
        "event_date": data.event_date.strip() if data.event_date else None,
        "guest_count": data.guest_count.strip() if data.guest_count else None,
        "message": data.message.strip(),
        "status": "new",
        "submitted_at": datetime.now(timezone.utc).isoformat()
    }
    await db.catering_inquiries.insert_one(doc)
    return {"message": "Thank you! We'll be in touch within 24 hours.", "id": doc["id"]}


@router.get("/inquiries")
async def get_catering_inquiries(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    inquiries = await db.catering_inquiries.find({}, {"_id": 0}).sort("submitted_at", -1).to_list(100)
    return {"inquiries": inquiries, "total": len(inquiries)}


@router.put("/inquiries/{inquiry_id}/status")
async def update_catering_status(inquiry_id: str, status: dict, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    new_status = status.get("status", "").strip()
    if new_status not in ["new", "contacted", "confirmed", "completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    result = await db.catering_inquiries.update_one({"id": inquiry_id}, {"$set": {"status": new_status}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    return {"message": "Status updated"}
