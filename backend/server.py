from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Depends, Response, Cookie, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import base64
import hashlib
import secrets

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Admin credentials - load from environment
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Lakeview872')
ADMIN_PASSWORD_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()

# Session storage (in production, use Redis or database)
active_sessions = {}

app = FastAPI()
api_router = APIRouter(prefix="/api")
security = HTTPBasic()

# Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

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

class LoginRequest(BaseModel):
    password: str

class AnalyticsResponse(BaseModel):
    total_views: int
    views_today: int
    views_this_week: int
    views_this_month: int
    unique_sessions: int
    unique_sessions_today: int
    page_breakdown: dict
    device_breakdown: dict
    browser_breakdown: dict
    hourly_views_today: dict
    daily_views_week: dict
    top_referrers: dict
    avg_pages_per_session: float
    button_clicks: dict
    button_clicks_today: dict

# Helper functions
def parse_user_agent(user_agent: str) -> tuple:
    """Parse user agent to extract device type and browser"""
    if not user_agent:
        return "unknown", "unknown"
    
    ua_lower = user_agent.lower()
    
    # Device type
    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        device = "mobile"
    elif "tablet" in ua_lower or "ipad" in ua_lower:
        device = "tablet"
    else:
        device = "desktop"
    
    # Browser
    if "chrome" in ua_lower and "edg" not in ua_lower:
        browser = "Chrome"
    elif "firefox" in ua_lower:
        browser = "Firefox"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        browser = "Safari"
    elif "edg" in ua_lower:
        browser = "Edge"
    elif "opera" in ua_lower or "opr" in ua_lower:
        browser = "Opera"
    else:
        browser = "Other"
    
    return device, browser

def verify_session(authorization: str = None, session_token: str = Cookie(None)):
    """Verify admin session via header or cookie"""
    token = None
    
    # Try header first (Bearer token)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    # Fall back to cookie
    elif session_token:
        token = session_token
    
    if not token or token not in active_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session = active_sessions[token]
    if datetime.now(timezone.utc) > session["expires"]:
        del active_sessions[token]
        raise HTTPException(status_code=401, detail="Session expired")
    
    return True

# Auth routes
@api_router.post("/auth/login")
async def login(request: LoginRequest, response: Response):
    password_hash = hashlib.sha256(request.password.encode()).hexdigest()
    
    if password_hash != ADMIN_PASSWORD_HASH:
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Create session token
    session_token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=24)
    
    active_sessions[session_token] = {
        "created": datetime.now(timezone.utc),
        "expires": expires
    }
    
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        max_age=86400,
        samesite="lax"
    )
    
    return {"message": "Login successful", "token": session_token}

@api_router.post("/auth/logout")
async def logout(response: Response, session_token: str = Cookie(None)):
    if session_token and session_token in active_sessions:
        del active_sessions[session_token]
    
    response.delete_cookie("session_token")
    return {"message": "Logged out"}

@api_router.get("/auth/verify")
async def verify_auth(authorization: str = Header(None), session_token: str = Cookie(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif session_token:
        token = session_token
    
    if not token or token not in active_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session = active_sessions[token]
    if datetime.now(timezone.utc) > session["expires"]:
        del active_sessions[token]
        raise HTTPException(status_code=401, detail="Session expired")
    
    return {"authenticated": True}

# Basic routes
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    return status_checks

# Specials CRUD (protected)
@api_router.post("/specials", response_model=Special)
async def create_special(special: SpecialCreate, authorization: str = Header(None), session_token: str = Cookie(None)):
    verify_session(authorization, session_token)
    special_obj = Special(**special.model_dump())
    doc = special_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.specials.insert_one(doc)
    return special_obj

@api_router.get("/specials", response_model=List[Special])
async def get_specials(active_only: bool = False):
    query = {"is_active": True} if active_only else {}
    specials = await db.specials.find(query, {"_id": 0}).to_list(100)
    for special in specials:
        if isinstance(special.get('created_at'), str):
            special['created_at'] = datetime.fromisoformat(special['created_at'])
    return specials

@api_router.get("/specials/{special_id}", response_model=Special)
async def get_special(special_id: str):
    special = await db.specials.find_one({"id": special_id}, {"_id": 0})
    if not special:
        raise HTTPException(status_code=404, detail="Special not found")
    if isinstance(special.get('created_at'), str):
        special['created_at'] = datetime.fromisoformat(special['created_at'])
    return special

@api_router.put("/specials/{special_id}", response_model=Special)
async def update_special(special_id: str, update: SpecialUpdate, authorization: str = Header(None), session_token: str = Cookie(None)):
    verify_session(authorization, session_token)
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    result = await db.specials.update_one({"id": special_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Special not found")
    
    special = await db.specials.find_one({"id": special_id}, {"_id": 0})
    if isinstance(special.get('created_at'), str):
        special['created_at'] = datetime.fromisoformat(special['created_at'])
    return special

@api_router.delete("/specials/{special_id}")
async def delete_special(special_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    verify_session(authorization, session_token)
    result = await db.specials.delete_one({"id": special_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Special not found")
    return {"message": "Special deleted successfully"}

# Analytics (public tracking, protected viewing)
@api_router.post("/analytics/track")
async def track_page_view(data: TrackingData):
    device_type, browser = parse_user_agent(data.user_agent)
    
    page_view = PageView(
        page=data.page,
        user_agent=data.user_agent,
        device_type=device_type,
        browser=browser,
        referrer=data.referrer,
        session_id=data.session_id,
        screen_width=data.screen_width,
        screen_height=data.screen_height
    )
    
    doc = page_view.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.page_views.insert_one(doc)
    return {"message": "Page view tracked"}

@api_router.post("/analytics/button-click")
async def track_button_click(data: ButtonClickData):
    button_click = ButtonClick(
        button_name=data.button_name,
        session_id=data.session_id
    )
    
    doc = button_click.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.button_clicks.insert_one(doc)
    return {"message": "Button click tracked"}

@api_router.get("/analytics")
async def get_analytics(authorization: str = Header(None), session_token: str = Cookie(None)):
    verify_session(authorization, session_token)
    
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    
    # Total views
    total_views = await db.page_views.count_documents({})
    
    # Views today
    views_today = await db.page_views.count_documents({
        "timestamp": {"$gte": today_start.isoformat()}
    })
    
    # Views this week
    views_this_week = await db.page_views.count_documents({
        "timestamp": {"$gte": week_start.isoformat()}
    })
    
    # Views this month
    views_this_month = await db.page_views.count_documents({
        "timestamp": {"$gte": month_start.isoformat()}
    })
    
    # Unique sessions (all time)
    unique_sessions_pipeline = [
        {"$match": {"session_id": {"$ne": None}}},
        {"$group": {"_id": "$session_id"}},
        {"$count": "count"}
    ]
    unique_result = await db.page_views.aggregate(unique_sessions_pipeline).to_list(1)
    unique_sessions = unique_result[0]["count"] if unique_result else 0
    
    # Unique sessions today
    unique_today_pipeline = [
        {"$match": {"session_id": {"$ne": None}, "timestamp": {"$gte": today_start.isoformat()}}},
        {"$group": {"_id": "$session_id"}},
        {"$count": "count"}
    ]
    unique_today_result = await db.page_views.aggregate(unique_today_pipeline).to_list(1)
    unique_sessions_today = unique_today_result[0]["count"] if unique_today_result else 0
    
    # Page breakdown
    page_pipeline = [
        {"$group": {"_id": "$page", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    page_stats = await db.page_views.aggregate(page_pipeline).to_list(100)
    page_breakdown = {stat["_id"]: stat["count"] for stat in page_stats}
    
    # Device breakdown
    device_pipeline = [
        {"$match": {"device_type": {"$ne": None}}},
        {"$group": {"_id": "$device_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    device_stats = await db.page_views.aggregate(device_pipeline).to_list(10)
    device_breakdown = {stat["_id"]: stat["count"] for stat in device_stats}
    
    # Browser breakdown
    browser_pipeline = [
        {"$match": {"browser": {"$ne": None}}},
        {"$group": {"_id": "$browser", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    browser_stats = await db.page_views.aggregate(browser_pipeline).to_list(10)
    browser_breakdown = {stat["_id"]: stat["count"] for stat in browser_stats}
    
    # Hourly views today (0-23)
    hourly_views_today = {str(h): 0 for h in range(24)}
    all_today = await db.page_views.find(
        {"timestamp": {"$gte": today_start.isoformat()}},
        {"_id": 0, "timestamp": 1}
    ).to_list(10000)
    for view in all_today:
        ts = view.get("timestamp")
        if ts:
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            hour = str(ts.hour)
            hourly_views_today[hour] = hourly_views_today.get(hour, 0) + 1
    
    # Daily views this week
    daily_views_week = {}
    for i in range(7):
        day = week_start + timedelta(days=i)
        day_end = day + timedelta(days=1)
        day_name = day.strftime("%a")
        count = await db.page_views.count_documents({
            "timestamp": {"$gte": day.isoformat(), "$lt": day_end.isoformat()}
        })
        daily_views_week[day_name] = count
    
    # Top referrers
    referrer_pipeline = [
        {"$match": {"referrer": {"$ne": None, "$ne": ""}}},
        {"$group": {"_id": "$referrer", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    referrer_stats = await db.page_views.aggregate(referrer_pipeline).to_list(5)
    top_referrers = {stat["_id"]: stat["count"] for stat in referrer_stats}
    
    # Average pages per session
    if unique_sessions > 0:
        avg_pages_per_session = round(total_views / unique_sessions, 2)
    else:
        avg_pages_per_session = 0
    
    # Button clicks (all time)
    button_pipeline = [
        {"$group": {"_id": "$button_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    button_stats = await db.button_clicks.aggregate(button_pipeline).to_list(20)
    button_clicks = {stat["_id"]: stat["count"] for stat in button_stats}
    
    # Button clicks today
    button_today_pipeline = [
        {"$match": {"timestamp": {"$gte": today_start.isoformat()}}},
        {"$group": {"_id": "$button_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    button_today_stats = await db.button_clicks.aggregate(button_today_pipeline).to_list(20)
    button_clicks_today = {stat["_id"]: stat["count"] for stat in button_today_stats}
    
    return {
        "total_views": total_views,
        "views_today": views_today,
        "views_this_week": views_this_week,
        "views_this_month": views_this_month,
        "unique_sessions": unique_sessions,
        "unique_sessions_today": unique_sessions_today,
        "page_breakdown": page_breakdown,
        "device_breakdown": device_breakdown,
        "browser_breakdown": browser_breakdown,
        "hourly_views_today": hourly_views_today,
        "daily_views_week": daily_views_week,
        "top_referrers": top_referrers,
        "avg_pages_per_session": avg_pages_per_session,
        "button_clicks": button_clicks,
        "button_clicks_today": button_clicks_today
    }

@api_router.post("/upload-image")
async def upload_image(file: UploadFile = File(...), authorization: str = Header(None), session_token: str = Cookie(None)):
    verify_session(authorization, session_token)
    contents = await file.read()
    base64_image = base64.b64encode(contents).decode('utf-8')
    content_type = file.content_type or 'image/jpeg'
    data_url = f"data:{content_type};base64,{base64_image}"
    return {"image_url": data_url}

# Include router
app.include_router(api_router)

# CORS configuration - handle credentials properly
cors_origins = os.environ.get('CORS_ORIGINS', '*')
if cors_origins == '*':
    allowed_origins = ["*"]
else:
    allowed_origins = cors_origins.split(',')

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
