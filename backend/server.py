from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Response, Cookie, Header
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
import random

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Admin credentials - load from environment (required, no fallback)
ADMIN_PASSWORD = os.environ['ADMIN_PASSWORD']
ADMIN_PASSWORD_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()

# Default site content
DEFAULT_SITE_CONTENT = {
    "hero": {
        "tagline": "Lakeview",
        "subtitle": "Serving the finest burgers and fresh Gulf seafood in the heart of New Orleans since 2015"
    },
    "about": {
        "accent_text": "Our Story",
        "heading": "A New Orleans Tradition",
        "paragraph1": "Founded by Chef Joseph Faroldi in 2015, Lakeview Burgers & Seafood has become a beloved fixture in the charming Lakeview neighborhood. What started as a dream to bring quality burgers and fresh Gulf seafood to the community has grown into a true family affair.",
        "paragraph2": "Today, Chef Joseph works alongside his son Josef, passing down culinary traditions and a passion for great food to the next generation. Together, they take pride in sourcing the freshest Gulf seafood daily and crafting each dish with care and expertise.",
        "paragraph3": "Whether you're craving a perfectly charred burger or authentic Louisiana seafood, the Faroldi family invites you to experience the taste of the Crescent City at Lakeview Burgers & Seafood.",
        "established_text": "Est. 2015 \u2022 New Orleans, LA"
    },
    "contact": {
        "address_line1": "872 Harrison Ave",
        "address_line2": "New Orleans, LA 70124",
        "hours_weekday": "Monday - Saturday: 11:30am - 11pm",
        "hours_weekend": "Sunday: Closed",
        "phone": "(504) 289-1032",
        "email": "info@lakeviewburgers.com",
        "catering_text": "Catering available for private events and parties"
    }
}

DEFAULT_MENU_CATEGORIES = [
    {
        "id": str(uuid.uuid4()), "slug": "appetizers", "display_name": "Appetizers",
        "subtitle": None, "columns": 2, "sort_order": 1,
        "items": [
            {"name": "Caf\u00e9 Fries", "description": "With Roast Beef Gravy, Cheddar Cheese, Sour Cream & Jalape\u00f1os", "price": "13.25"},
            {"name": "Chicken Wings (6)", "description": "Asian Glaze, BBQ or Buffalo", "price": "11.00"},
            {"name": "Chicken Wings (12)", "description": "Asian Glaze, BBQ or Buffalo", "price": "17.25"},
            {"name": "Fresh Mozzarella Cheese Sticks", "description": "With Marinara Sauce", "price": "10.00"},
            {"name": "Fried Louisiana Okra", "description": "With Ranch", "price": "9.00"},
            {"name": "Fried Onion Rings", "description": "", "price": "9.00"},
            {"name": "Fried Pickles", "description": "With Ranch", "price": "8.00"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "soups", "display_name": "Soups",
        "subtitle": None, "columns": 3, "sort_order": 2,
        "items": [
            {"name": "Chicken Andouille Gumbo", "description": "Cup / Bowl", "price": "7.00 / 9.00"},
            {"name": "Corn & Crab Bisque", "description": "Cup / Bowl", "price": "7.00 / 9.00"},
            {"name": "Seafood Gumbo", "description": "Cup / Bowl", "price": "7.00 / 9.00"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "salads", "display_name": "Salads",
        "subtitle": None, "columns": 2, "sort_order": 3,
        "items": [
            {"name": "Caesar Salad", "description": "", "price": "10.00"},
            {"name": "Garden Salad", "description": "Mixed Greens, Tomato, Red Onion & Cucumber", "price": "10.00"},
            {"name": "Spinach Salad", "description": "Red Onions, Pecans, Hot Bacon & Honey Mustard Dressing", "price": "10.00"},
            {"name": "Add Grilled/Blackened Tuna or Shrimp", "description": "", "price": "10.95"},
            {"name": "Add Fried Oysters or Shrimp", "description": "", "price": "12.95"},
            {"name": "Add Grilled/Blackened Chicken", "description": "", "price": "7.50"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "burgers", "display_name": "Burgers",
        "subtitle": None, "columns": 2, "sort_order": 4,
        "items": [
            {"name": "Classic Burger (8oz)", "description": "Served on a fresh bun with your choice of toppings", "price": "13.50"},
            {"name": "Extra Patty", "description": "Add another 8oz patty", "price": "5.75"},
            {"name": "Add Bacon", "description": "", "price": "0.50"},
            {"name": "Add Cheese", "description": "American, Blue Cheese, Cheddar, Pepper Jack, Provolone or Swiss", "price": "0.50"},
            {"name": "Add Fried Egg", "description": "", "price": "1.75"},
            {"name": "Add Mushroom", "description": "", "price": "0.50"},
            {"name": "Add Onion", "description": "Grilled or Raw", "price": "0.50"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "sandwiches", "display_name": "Sandwiches & Po'Boys",
        "subtitle": None, "columns": 2, "sort_order": 5,
        "items": [
            {"name": "Chicken Sandwich", "description": "Grilled, Blackened, or Paneed - Bun or Po'Boy, Dressed", "price": "12.00"},
            {"name": "Chicken Parmesan", "description": "Mozzarella/Provolone", "price": "12.00"},
            {"name": "Cuban", "description": "Ham, Salami & Pork", "price": "12.00"},
            {"name": "French Fry Po'Boy", "description": "Cheddar Cheese & Gravy", "price": "9.00"},
            {"name": "Fried Fish Po'Boy", "description": "Dressed", "price": "12.00"},
            {"name": "Fried Oyster Po'Boy", "description": "Dressed", "price": "17.50"},
            {"name": "Fried Shrimp Po'Boy", "description": "Dressed", "price": "13.25"},
            {"name": "Grilled Shrimp Po'Boy", "description": "Blackened", "price": "13.25"},
            {"name": "Grilled Ham", "description": "", "price": "9.00"},
            {"name": "Ham/Roast/Swiss", "description": "", "price": "12.00"},
            {"name": "Hot Sausage", "description": "", "price": "10.50"},
            {"name": "Meatball Sub", "description": "Mozzarella/Provolone", "price": "12.00"},
            {"name": "Pulled Pork", "description": "BBQ or Plain", "price": "11.00"},
            {"name": "Roast Beef", "description": "New Orleans Debris Style", "price": "14.50"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "tacos", "display_name": "Tacos",
        "subtitle": None, "columns": 2, "sort_order": 6,
        "items": [
            {"name": "Chicken Tacos", "description": "Blackened or Grilled, topped with Cheddar Cheese, Lettuce, Pico de Gallo & Sour Cream", "price": "12.00"},
            {"name": "Fish Tacos", "description": "Blackened, Fried or Grilled, topped with Cheddar Cheese, Lettuce, Pico de Gallo & Sour Cream", "price": "13.25"},
            {"name": "Pork Tacos", "description": "Topped with Cheddar Cheese, Lettuce, Pico de Gallo & Sour Cream", "price": "12.50"},
            {"name": "Shrimp Tacos", "description": "Blackened, Fried or Grilled, topped with Cheddar Cheese, Lettuce, Pico de Gallo & Sour Cream", "price": "13.25"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "fried-plates", "display_name": "Fried Plates",
        "subtitle": None, "columns": 2, "sort_order": 7,
        "items": [
            {"name": "Fried Fish Plate", "description": "Your Choice of 2 Sides", "price": "16.25"},
            {"name": "Chicken Tenders Plate", "description": "Your Choice of 2 Sides", "price": "13.25"},
            {"name": "Fried Oyster Plate", "description": "Your Choice of 2 Sides", "price": "23.00"},
            {"name": "Fried Shrimp Plate", "description": "Your Choice of 2 Sides", "price": "17.25"},
            {"name": "Seafood Platter", "description": "Fish, Oyster, Shrimp & Your Choice of 2 Sides", "price": "23.50"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "family-dinners", "display_name": "Family Dinners",
        "subtitle": "Served with Bed of Fries & Garlic Bread", "columns": 2, "sort_order": 8,
        "items": [
            {"name": "Catfish Pirogue", "description": "Served with French Fries & Garlic Bread", "price": "29.00"},
            {"name": "Oyster Pirogue", "description": "Served with French Fries & Garlic Bread", "price": "33.95"},
            {"name": "Shrimp Pirogue", "description": "Served with French Fries & Garlic Bread", "price": "31.00"},
            {"name": "Seafood Pirogue", "description": "Fish, Oyster & Shrimp with French Fries & Garlic Bread", "price": "33.50"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "sides", "display_name": "Sides",
        "subtitle": None, "columns": 3, "sort_order": 9,
        "items": [
            {"name": "Corn on the Cob (3)", "description": "", "price": "3.00"},
            {"name": "Green Beans", "description": "", "price": "3.00"},
            {"name": "Coleslaw", "description": "", "price": "2.50"},
            {"name": "French Fries", "description": "", "price": "4.50"},
            {"name": "Cajun Potatoes", "description": "", "price": "3.00"},
            {"name": "Side Salad", "description": "Garden or Caesar", "price": "4.75"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "kids", "display_name": "Kids Menu",
        "subtitle": None, "columns": 4, "sort_order": 10,
        "items": [
            {"name": "Fish Plate", "description": "With French Fries", "price": "8.00"},
            {"name": "Chicken Tenders", "description": "With French Fries", "price": "8.00"},
            {"name": "Shrimp Plate", "description": "With French Fries", "price": "8.00"},
            {"name": "Sliders (2)", "description": "With French Fries", "price": "9.00"},
        ]
    },
]

DEFAULT_GIVEAWAY_SETTINGS = {
    "id": "main",
    "is_active": False,
    "title": "Summer Spin & Win!",
    "subtitle": "Spin the wheel for a chance to win free food, discounts, and more!",
    "start_date": "2026-06-01",
    "end_date": "2026-08-31",
    "prizes": [
        {"label": "Free Appetizer", "weight": 15, "color": "#366343"},
        {"label": "10% Off", "weight": 25, "color": "#a5935b"},
        {"label": "Free Side", "weight": 20, "color": "#1d2a3b"},
        {"label": "15% Off", "weight": 15, "color": "#366343"},
        {"label": "Free Drink", "weight": 15, "color": "#a5935b"},
        {"label": "Free Dessert", "weight": 5, "color": "#1d2a3b"},
        {"label": "Dinner for 4", "weight": 2, "color": "#8B0000"},
        {"label": "Try Again", "weight": 3, "color": "#555555"}
    ]
}

app = FastAPI()
api_router = APIRouter(prefix="/api")

# Models
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

async def verify_session(authorization: str = None, session_token: str = Cookie(None)):
    """Verify admin session via header or cookie (MongoDB-backed)"""
    token = None

    # Try header first (Bearer token)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    # Fall back to cookie
    elif session_token:
        token = session_token

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = await db.admin_sessions.find_one({"token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    expires_at = session.get("expires")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if not expires_at or datetime.now(timezone.utc) > expires_at:
        await db.admin_sessions.delete_one({"token": token})
        raise HTTPException(status_code=401, detail="Session expired")

    return True

# Seed default content on startup
@app.on_event("startup")
async def seed_default_content():
    existing = await db.site_content.find_one({}, {"_id": 0})
    if not existing:
        await db.site_content.insert_one({**DEFAULT_SITE_CONTENT, "id": "main"})
        logger.info("Seeded default site content")
    
    existing_menu = await db.menu_categories.count_documents({})
    if existing_menu == 0:
        await db.menu_categories.insert_many(DEFAULT_MENU_CATEGORIES)
        logger.info("Seeded default menu categories")
    
    existing_giveaway = await db.giveaway_settings.find_one({}, {"_id": 0})
    if not existing_giveaway:
        await db.giveaway_settings.insert_one(DEFAULT_GIVEAWAY_SETTINGS)
        logger.info("Seeded default giveaway settings")

# CMS - Site Content
@api_router.get("/content")
async def get_site_content():
    content = await db.site_content.find_one({}, {"_id": 0})
    if not content:
        return DEFAULT_SITE_CONTENT
    return content

@api_router.put("/content/{section}")
async def update_site_content(section: str, data: dict, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    if section not in ["hero", "about", "contact"]:
        raise HTTPException(status_code=400, detail="Invalid section")
    result = await db.site_content.update_one({}, {"$set": {section: data}})
    if result.matched_count == 0:
        await db.site_content.insert_one({**DEFAULT_SITE_CONTENT, "id": "main", section: data})
    updated = await db.site_content.find_one({}, {"_id": 0})
    return updated

# CMS - Menu
@api_router.get("/menu")
async def get_menu():
    categories = await db.menu_categories.find({}, {"_id": 0}).sort("sort_order", 1).to_list(50)
    if not categories:
        return DEFAULT_MENU_CATEGORIES
    return categories

@api_router.put("/menu/{category_id}")
async def update_menu_category(category_id: str, data: dict, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    update_fields = {}
    for key in ["display_name", "subtitle", "columns", "sort_order", "items"]:
        if key in data:
            update_fields[key] = data[key]
    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    result = await db.menu_categories.update_one({"id": category_id}, {"$set": update_fields})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    updated = await db.menu_categories.find_one({"id": category_id}, {"_id": 0})
    return updated

@api_router.post("/menu")
async def add_menu_category(data: dict, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    if not data.get("display_name"):
        raise HTTPException(status_code=400, detail="display_name is required")
    max_order = await db.menu_categories.find_one(sort=[("sort_order", -1)])
    new_cat = {
        "id": str(uuid.uuid4()),
        "slug": data.get("slug", data["display_name"].lower().replace(" ", "-").replace("'", "")),
        "display_name": data["display_name"],
        "subtitle": data.get("subtitle"),
        "columns": data.get("columns", 2),
        "sort_order": (max_order["sort_order"] + 1) if max_order else 1,
        "items": data.get("items", [])
    }
    await db.menu_categories.insert_one(new_cat)
    return {k: v for k, v in new_cat.items() if k != "_id"}

@api_router.delete("/menu/{category_id}")
async def delete_menu_category(category_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    result = await db.menu_categories.delete_one({"id": category_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"message": "Category deleted"}

# Auth routes
@api_router.post("/auth/login")
async def login(request: LoginRequest, response: Response):
    password_hash = hashlib.sha256(request.password.encode()).hexdigest()

    if password_hash != ADMIN_PASSWORD_HASH:
        raise HTTPException(status_code=401, detail="Invalid password")

    # Create session token (persisted in MongoDB)
    session_token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=24)

    await db.admin_sessions.insert_one({
        "token": session_token,
        "created": datetime.now(timezone.utc).isoformat(),
        "expires": expires.isoformat()
    })

    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        max_age=86400,
        samesite="lax"
    )

    return {"message": "Login successful", "token": session_token}

@api_router.post("/auth/logout")
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

@api_router.get("/auth/verify")
async def verify_auth(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    return {"authenticated": True}

# Basic routes
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

# Specials CRUD (protected)
@api_router.post("/specials", response_model=Special)
async def create_special(special: SpecialCreate, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
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
    await verify_session(authorization, session_token)
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
    await verify_session(authorization, session_token)
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
    await verify_session(authorization, session_token)
    
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
    
    # Hourly views today (0-23) - use aggregation pipeline for efficiency
    hourly_views_today = {str(h): 0 for h in range(24)}
    hourly_pipeline = [
        {"$match": {"timestamp": {"$gte": today_start.isoformat()}}},
        {"$addFields": {
            "parsed_timestamp": {
                "$cond": {
                    "if": {"$eq": [{"$type": "$timestamp"}, "string"]},
                    "then": {"$dateFromString": {"dateString": "$timestamp"}},
                    "else": "$timestamp"
                }
            }
        }},
        {"$group": {
            "_id": {"$hour": "$parsed_timestamp"},
            "count": {"$sum": 1}
        }}
    ]
    hourly_stats = await db.page_views.aggregate(hourly_pipeline).to_list(24)
    for stat in hourly_stats:
        if stat["_id"] is not None:
            hourly_views_today[str(stat["_id"])] = stat["count"]
    
    # Daily views this week - optimized with single aggregation query
    daily_views_week = {}
    daily_pipeline = [
        {"$match": {"timestamp": {"$gte": week_start.isoformat()}}},
        {"$addFields": {
            "parsed_timestamp": {
                "$cond": {
                    "if": {"$eq": [{"$type": "$timestamp"}, "string"]},
                    "then": {"$dateFromString": {"dateString": "$timestamp"}},
                    "else": "$timestamp"
                }
            }
        }},
        {"$group": {
            "_id": {"$dayOfWeek": "$parsed_timestamp"},
            "count": {"$sum": 1}
        }}
    ]
    daily_stats = await db.page_views.aggregate(daily_pipeline).to_list(7)
    day_map = {1: "Sun", 2: "Mon", 3: "Tue", 4: "Wed", 5: "Thu", 6: "Fri", 7: "Sat"}
    for stat in daily_stats:
        if stat["_id"] is not None:
            daily_views_week[day_map.get(stat["_id"], "Unknown")] = stat["count"]
    # Ensure all days are represented
    for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        if day not in daily_views_week:
            daily_views_week[day] = 0
    
    # Top referrers
    referrer_pipeline = [
        {"$match": {"referrer": {"$nin": [None, "", "null"]}}},
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

# Giveaway
@api_router.get("/giveaway/settings")
async def get_giveaway_settings():
    settings = await db.giveaway_settings.find_one({}, {"_id": 0})
    if not settings:
        return DEFAULT_GIVEAWAY_SETTINGS
    return settings

@api_router.put("/giveaway/settings")
async def update_giveaway_settings(data: dict, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    allowed = ["is_active", "title", "subtitle", "start_date", "end_date", "prizes"]
    update_fields = {k: v for k, v in data.items() if k in allowed}
    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields")
    result = await db.giveaway_settings.update_one({}, {"$set": update_fields})
    if result.matched_count == 0:
        await db.giveaway_settings.insert_one({**DEFAULT_GIVEAWAY_SETTINGS, **update_fields})
    updated = await db.giveaway_settings.find_one({}, {"_id": 0})
    return updated

@api_router.post("/giveaway/spin")
async def spin_wheel(data: SpinRequest):
    settings = await db.giveaway_settings.find_one({}, {"_id": 0})
    if not settings or not settings.get("is_active"):
        raise HTTPException(status_code=400, detail="Giveaway is not active")
    
    email = data.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    
    existing = await db.giveaway_entries.find_one({"email": email})
    if existing:
        return {"already_entered": True, "prize": existing.get("prize"), "message": "You've already spun! Your prize: " + existing.get("prize", "N/A")}
    
    prizes = settings.get("prizes", [])
    if not prizes:
        raise HTTPException(status_code=500, detail="No prizes configured")
    
    weights = [p.get("weight", 1) for p in prizes]
    winner = random.choices(prizes, weights=weights, k=1)[0]
    
    prize_index = prizes.index(winner)
    
    entry = {
        "id": str(uuid.uuid4()),
        "name": data.name.strip(),
        "email": email,
        "phone": data.phone.strip() if data.phone else None,
        "prize": winner["label"],
        "prize_index": prize_index,
        "claimed": False,
        "entered_at": datetime.now(timezone.utc).isoformat()
    }
    await db.giveaway_entries.insert_one(entry)
    
    return {"already_entered": False, "prize": winner["label"], "prize_index": prize_index, "message": f"Congratulations! You won: {winner['label']}!"}

@api_router.get("/giveaway/entries")
async def get_giveaway_entries(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    entries = await db.giveaway_entries.find({}, {"_id": 0}).sort("entered_at", -1).to_list(500)
    return {"entries": entries, "total": len(entries)}

@api_router.put("/giveaway/entries/{entry_id}/claim")
async def mark_entry_claimed(entry_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    result = await db.giveaway_entries.update_one({"id": entry_id}, {"$set": {"claimed": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"message": "Marked as claimed"}

@api_router.get("/giveaway/winners")
async def get_giveaway_winners():
    winners = await db.giveaway_entries.find(
        {"prize": {"$ne": "Try Again"}},
        {"_id": 0, "name": 1, "prize": 1, "entered_at": 1}
    ).sort("entered_at", -1).to_list(20)
    return {"winners": winners}

# Loyalty Punch Card
@api_router.post("/loyalty/join")
async def join_loyalty(data: LoyaltyJoinRequest):
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

@api_router.get("/loyalty/lookup")
async def lookup_loyalty(phone: str):
    member = await db.loyalty_members.find_one({"phone": phone.strip()}, {"_id": 0})
    if not member:
        raise HTTPException(status_code=404, detail="Not a loyalty member")
    return member

@api_router.get("/loyalty/members")
async def get_loyalty_members(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    members = await db.loyalty_members.find({}, {"_id": 0}).sort("joined_at", -1).to_list(500)
    return {"members": members, "total": len(members)}

@api_router.put("/loyalty/members/{member_id}/stamp")
async def stamp_loyalty(member_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    member = await db.loyalty_members.find_one({"id": member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    new_visits = member.get("visits", 0) + 1
    reward_earned = new_visits >= 10
    await db.loyalty_members.update_one({"id": member_id}, {"$set": {"visits": new_visits, "reward_earned": reward_earned}})
    return {"visits": new_visits, "reward_earned": reward_earned, "message": "Free meal earned!" if reward_earned and not member.get("reward_earned") else "Visit stamped!"}

@api_router.put("/loyalty/members/{member_id}/claim")
async def claim_loyalty_reward(member_id: str, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    member = await db.loyalty_members.find_one({"id": member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if not member.get("reward_earned"):
        raise HTTPException(status_code=400, detail="Reward not yet earned")
    await db.loyalty_members.update_one({"id": member_id}, {"$set": {"reward_claimed": True, "visits": 0, "reward_earned": False}})
    return {"message": "Reward claimed! Punch card reset."}

# Messaging Blast
@api_router.post("/messages/send")
async def send_message_blast(data: MessageBlastRequest, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    
    recipients_emails = []
    recipients_phones = []
    
    if data.recipient_group in ["all", "newsletter"]:
        subs = await db.newsletter_subscribers.find({}, {"_id": 0, "email": 1}).to_list(1000)
        recipients_emails.extend([s["email"] for s in subs])
    
    if data.recipient_group in ["all", "giveaway"]:
        entries = await db.giveaway_entries.find({}, {"_id": 0, "email": 1, "phone": 1}).to_list(1000)
        recipients_emails.extend([e["email"] for e in entries if e.get("email")])
        recipients_phones.extend([e["phone"] for e in entries if e.get("phone")])
    
    if data.recipient_group in ["all", "loyalty"]:
        members = await db.loyalty_members.find({}, {"_id": 0, "phone": 1}).to_list(1000)
        recipients_phones.extend([m["phone"] for m in members if m.get("phone")])
    
    recipients_emails = list(set(recipients_emails))
    recipients_phones = list(set([p for p in recipients_phones if p]))
    
    email_sent = 0
    sms_sent = 0
    errors = []
    
    if data.channel in ["email", "both"] and recipients_emails:
        sendgrid_key = os.environ.get("SENDGRID_API_KEY")
        sender_email = os.environ.get("SENDER_EMAIL")
        if sendgrid_key and sender_email:
            try:
                from sendgrid import SendGridAPIClient
                from sendgrid.helpers.mail import Mail
                sg = SendGridAPIClient(sendgrid_key)
                for email_addr in recipients_emails:
                    try:
                        message = Mail(from_email=sender_email, to_emails=email_addr, subject=data.subject, html_content=data.body)
                        sg.send(message)
                        email_sent += 1
                    except Exception as e:
                        errors.append(f"Email to {email_addr}: {str(e)}")
            except Exception as e:
                errors.append(f"SendGrid init error: {str(e)}")
        else:
            errors.append("SendGrid not configured (missing SENDGRID_API_KEY or SENDER_EMAIL)")
    
    if data.channel in ["sms", "both"] and recipients_phones:
        twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
        twilio_phone = os.environ.get("TWILIO_PHONE_NUMBER")
        if twilio_sid and twilio_token and twilio_phone:
            try:
                from twilio.rest import Client as TwilioClient
                twilio_client = TwilioClient(twilio_sid, twilio_token)
                for phone in recipients_phones:
                    try:
                        twilio_client.messages.create(body=data.body, from_=twilio_phone, to=phone)
                        sms_sent += 1
                    except Exception as e:
                        errors.append(f"SMS to {phone}: {str(e)}")
            except Exception as e:
                errors.append(f"Twilio init error: {str(e)}")
        else:
            errors.append("Twilio not configured (missing TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, or TWILIO_PHONE_NUMBER)")
    
    blast_record = {
        "id": str(uuid.uuid4()),
        "subject": data.subject,
        "body": data.body,
        "channel": data.channel,
        "recipient_group": data.recipient_group,
        "email_count": email_sent,
        "sms_count": sms_sent,
        "total_emails": len(recipients_emails),
        "total_phones": len(recipients_phones),
        "errors": errors,
        "sent_at": datetime.now(timezone.utc).isoformat()
    }
    await db.message_blasts.insert_one(blast_record)
    
    return {
        "email_sent": email_sent,
        "sms_sent": sms_sent,
        "total_emails": len(recipients_emails),
        "total_phones": len(recipients_phones),
        "errors": errors,
        "message": f"Sent {email_sent} emails and {sms_sent} SMS messages"
    }

@api_router.get("/messages/history")
async def get_message_history(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    blasts = await db.message_blasts.find({}, {"_id": 0}).sort("sent_at", -1).to_list(50)
    return {"blasts": blasts, "total": len(blasts)}

# Catering inquiries
@api_router.post("/catering/inquiry")
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

@api_router.get("/catering/inquiries")
async def get_catering_inquiries(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    inquiries = await db.catering_inquiries.find({}, {"_id": 0}).sort("submitted_at", -1).to_list(100)
    return {"inquiries": inquiries, "total": len(inquiries)}

@api_router.put("/catering/inquiries/{inquiry_id}/status")
async def update_catering_status(inquiry_id: str, status: dict, authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    new_status = status.get("status", "").strip()
    if new_status not in ["new", "contacted", "confirmed", "completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    result = await db.catering_inquiries.update_one({"id": inquiry_id}, {"$set": {"status": new_status}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    return {"message": "Status updated"}

# Newsletter subscription
@api_router.post("/newsletter/subscribe")
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

@api_router.get("/newsletter/subscribers")
async def get_newsletter_subscribers(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    subscribers = await db.newsletter_subscribers.find({}, {"_id": 0}).to_list(1000)
    return {"subscribers": subscribers, "total": len(subscribers)}

@api_router.post("/upload-image")
async def upload_image(file: UploadFile = File(...), authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
