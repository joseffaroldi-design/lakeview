"""All Pydantic models for Lakeview API."""
import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, EmailStr, constr


# Field type aliases with sensible caps to block abuse (10MB payloads, etc.)
ShortStr = constr(strip_whitespace=True, min_length=1, max_length=200)
LongStr = constr(strip_whitespace=True, min_length=1, max_length=2000)
OptShortStr = constr(strip_whitespace=True, max_length=200)
PhoneStr = constr(strip_whitespace=True, min_length=7, max_length=30)
PasswordStr = constr(min_length=1, max_length=200)


class Special(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    price: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SpecialCreate(BaseModel):
    title: ShortStr
    description: LongStr
    price: Optional[OptShortStr] = None
    image_url: Optional[constr(max_length=2_000_000)] = None  # allow base64 data URLs


class SpecialUpdate(BaseModel):
    title: Optional[ShortStr] = None
    description: Optional[LongStr] = None
    price: Optional[OptShortStr] = None
    image_url: Optional[constr(max_length=2_000_000)] = None
    is_active: Optional[bool] = None


class PageView(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    page: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_agent: Optional[str] = None
    device_type: Optional[str] = None
    browser: Optional[str] = None
    referrer: Optional[str] = None
    session_id: Optional[str] = None
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None


class TrackingData(BaseModel):
    page: constr(max_length=500)
    user_agent: Optional[constr(max_length=500)] = None
    referrer: Optional[constr(max_length=500)] = None
    session_id: Optional[constr(max_length=100)] = None
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None


class ButtonClick(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    button_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = None


class ButtonClickData(BaseModel):
    button_name: constr(max_length=100)
    session_id: Optional[constr(max_length=100)] = None


class NewsletterSubscribe(BaseModel):
    email: EmailStr


class CateringInquiry(BaseModel):
    name: ShortStr
    email: EmailStr
    phone: Optional[PhoneStr] = None
    event_date: Optional[OptShortStr] = None
    guest_count: Optional[OptShortStr] = None
    message: LongStr


class SpinRequest(BaseModel):
    name: ShortStr
    email: EmailStr
    phone: Optional[PhoneStr] = None


class LoyaltyJoinRequest(BaseModel):
    name: ShortStr
    phone: PhoneStr


class MessageBlastRequest(BaseModel):
    subject: OptShortStr = ""
    body: constr(strip_whitespace=True, min_length=1, max_length=10000)
    channel: constr(pattern=r"^(email|sms|both)$")
    recipient_group: constr(pattern=r"^(all|newsletter|giveaway|loyalty)$")


class LoginRequest(BaseModel):
    password: PasswordStr
