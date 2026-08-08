"""Restaurant settings — normal business changes belong here, not in code."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Cookie, Header
from pydantic import BaseModel, ConfigDict, Field

from auth import verify_session
from config import db

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULT_SETTINGS = {
    "business_name": "Lakeview Burgers & Seafood",
    "phone": "",
    "email": "",
    "address": "",
    "hours": {
        "monday": "11:30 AM – 11:00 PM",
        "tuesday": "11:30 AM – 11:00 PM",
        "wednesday": "11:30 AM – 11:00 PM",
        "thursday": "11:30 AM – 11:00 PM",
        "friday": "11:30 AM – 11:00 PM",
        "saturday": "11:30 AM – 11:00 PM",
        "sunday": "Closed",
    },
    "social": {"facebook": "", "instagram": ""},
    "branding": {"logo_url": "", "primary_color": "#0A2540", "accent_color": "#C9A227"},
    "homepage": {"announcement": "", "default_cta": "Order Now"},
    "marketing": {"default_template": "luxury", "default_platform": "instagram_square"},
    "loyalty": {"enabled": True, "visits_required": 10, "reward_label": "Free meal"},
}


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    business_name: str = Field(default=DEFAULT_SETTINGS["business_name"], max_length=120)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=160)
    address: str = Field(default="", max_length=240)
    hours: Dict[str, str] = Field(default_factory=dict)
    social: Dict[str, str] = Field(default_factory=dict)
    branding: Dict[str, str] = Field(default_factory=dict)
    homepage: Dict[str, str] = Field(default_factory=dict)
    marketing: Dict[str, str] = Field(default_factory=dict)
    loyalty: Dict[str, object] = Field(default_factory=dict)


def _merge(base: dict, override: Optional[dict]) -> dict:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = {**out[key], **value}
        else:
            out[key] = value
    return out


async def get_settings_document() -> dict:
    doc = await db.business_settings.find_one({"id": "main"}, {"_id": 0})
    return _merge(DEFAULT_SETTINGS, doc)


@router.get("")
async def get_settings(
    authorization: str = Header(None), session_token: str = Cookie(None)
):
    await verify_session(authorization, session_token)
    return await get_settings_document()


@router.get("/public")
async def get_public_settings():
    settings = await get_settings_document()
    return {
        "business_name": settings["business_name"],
        "phone": settings["phone"],
        "email": settings["email"],
        "address": settings["address"],
        "hours": settings["hours"],
        "social": settings["social"],
        "branding": settings["branding"],
        "homepage": settings["homepage"],
        "loyalty": {
            "enabled": bool(settings.get("loyalty", {}).get("enabled", True)),
            "visits_required": int(settings.get("loyalty", {}).get("visits_required", 10)),
            "reward_label": str(settings.get("loyalty", {}).get("reward_label", "Free meal")),
        },
    }


@router.put("")
async def update_settings(
    body: SettingsIn,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    payload = body.model_dump()
    visits_required = int(payload.get("loyalty", {}).get("visits_required", 10) or 10)
    payload["loyalty"]["visits_required"] = max(1, min(visits_required, 100))
    payload.update({"id": "main", "updated_at": datetime.now(timezone.utc).isoformat()})
    await db.business_settings.update_one({"id": "main"}, {"$set": payload}, upsert=True)

    # Keep the existing public website contract in sync while Settings becomes
    # the owner-facing source of truth. This avoids a risky public-site rewrite.
    hours = payload.get("hours") or {}
    weekday_values = [hours.get(day, "") for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday")]
    same_weekday = bool(weekday_values[0]) and all(v == weekday_values[0] for v in weekday_values)
    hours_weekday = (
        f"Monday - Saturday: {weekday_values[0]}"
        if same_weekday
        else " · ".join(f"{day[:3].title()}: {hours.get(day, '')}" for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday") if hours.get(day))
    )
    await db.site_content.update_one(
        {},
        {"$set": {
            "contact.phone": payload.get("phone", ""),
            "contact.email": payload.get("email", ""),
            "contact.address_line1": payload.get("address", ""),
            "contact.hours_weekday": hours_weekday,
            "contact.hours_weekend": f"Sunday: {hours.get('sunday', 'Closed')}",
            "hero.announcement": (payload.get("homepage") or {}).get("announcement", ""),
        }},
        upsert=True,
    )
    return payload
