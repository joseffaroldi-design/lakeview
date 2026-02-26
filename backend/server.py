from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Define Models
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

class AnalyticsResponse(BaseModel):
    total_views: int
    views_today: int
    views_this_week: int
    views_this_month: int
    page_breakdown: dict

# Routes
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    return status_checks

# Specials CRUD
@api_router.post("/specials", response_model=Special)
async def create_special(special: SpecialCreate):
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
async def update_special(special_id: str, update: SpecialUpdate):
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    result = await db.specials.update_one(
        {"id": special_id},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Special not found")
    
    special = await db.specials.find_one({"id": special_id}, {"_id": 0})
    if isinstance(special.get('created_at'), str):
        special['created_at'] = datetime.fromisoformat(special['created_at'])
    return special

@api_router.delete("/specials/{special_id}")
async def delete_special(special_id: str):
    result = await db.specials.delete_one({"id": special_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Special not found")
    return {"message": "Special deleted successfully"}

# Analytics
@api_router.post("/analytics/track")
async def track_page_view(page: str, user_agent: Optional[str] = None):
    page_view = PageView(page=page, user_agent=user_agent)
    doc = page_view.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.page_views.insert_one(doc)
    return {"message": "Page view tracked"}

@api_router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics():
    from datetime import timedelta
    
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
    
    # Page breakdown
    pipeline = [
        {"$group": {"_id": "$page", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    page_stats = await db.page_views.aggregate(pipeline).to_list(100)
    page_breakdown = {stat["_id"]: stat["count"] for stat in page_stats}
    
    return AnalyticsResponse(
        total_views=total_views,
        views_today=views_today,
        views_this_week=views_this_week,
        views_this_month=views_this_month,
        page_breakdown=page_breakdown
    )

@api_router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    contents = await file.read()
    base64_image = base64.b64encode(contents).decode('utf-8')
    content_type = file.content_type or 'image/jpeg'
    data_url = f"data:{content_type};base64,{base64_image}"
    return {"image_url": data_url}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
