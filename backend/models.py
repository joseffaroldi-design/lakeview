"""All Pydantic models for Lakeview API."""
import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


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
    title: str
    description: str
    price: Optional[str] = None
    image_url: Optional[str] = None


class SpecialUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[str] = None
    image_url: Optional[str] = None
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
    page: str
    user_agent: Optional[str] = None
    referrer: Optional[str] = None
    session_id: Optional[str] = None
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None


class ButtonClick(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    button_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = None


class ButtonClickData(BaseModel):
    button_name: str
    session_id: Optional[str] = None


class NewsletterSubscribe(BaseModel):
    email: str


class CateringInquiry(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    event_date: Optional[str] = None
    guest_count: Optional[str] = None
    message: str


class SpinRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None


class LoyaltyJoinRequest(BaseModel):
    name: str
    phone: str


class MessageBlastRequest(BaseModel):
    subject: str
    body: str
    channel: str  # email, sms, both
    recipient_group: str  # all, newsletter, giveaway, loyalty


class LoginRequest(BaseModel):
    password: str
