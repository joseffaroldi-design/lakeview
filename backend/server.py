"""Lakeview Burgers & Seafood — FastAPI app entry point.

Route registration lives here; business logic is split across /routers/*.
"""
import logging
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from config import db, client, ALLOWED_ORIGINS
from seed_data import seed_defaults

import auth
from routers import (
    cms,
    specials,
    analytics,
    giveaway,
    loyalty,
    messaging,
    catering,
    newsletter,
    misc,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# All routes mount under /api
api_router = APIRouter(prefix="/api")
api_router.include_router(misc.router)
api_router.include_router(auth.router)
api_router.include_router(cms.router)
api_router.include_router(specials.router)
api_router.include_router(analytics.router)
api_router.include_router(giveaway.router)
api_router.include_router(loyalty.router)
api_router.include_router(messaging.router)
api_router.include_router(catering.router)
api_router.include_router(newsletter.router)
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await seed_defaults(db)


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
