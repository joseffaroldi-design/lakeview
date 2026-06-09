"""Lakeview Burgers & Seafood — FastAPI app entry point.

Route registration lives here; business logic is split across /routers/*.
"""
import asyncio
import logging
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from config import db, client, ALLOWED_ORIGINS
from seed_data import seed_defaults
from rate_limit import limiter

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
    ai_ads,
    publishing,
)
from publishing import run_due_publishes

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
api_router.include_router(ai_ads.router)
api_router.include_router(publishing.router)
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


SCHEDULER_INTERVAL_SECONDS = 30
_scheduler_task: asyncio.Task | None = None


async def _scheduler_loop():
    """Background worker — polls scheduled_posts every SCHEDULER_INTERVAL_SECONDS
    and publishes anything due. Crashes are logged but don't kill the loop."""
    while True:
        try:
            executed = await run_due_publishes(db, limit=25)
            if executed:
                logger.info("Scheduler tick — executed %d publishes", len(executed))
        except Exception as e:  # noqa: BLE001
            logger.exception("Scheduler tick failed: %s", e)
        await asyncio.sleep(SCHEDULER_INTERVAL_SECONDS)


@app.on_event("startup")
async def on_startup():
    await seed_defaults(db)
    global _scheduler_task
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("Publishing scheduler started (interval=%ss)", SCHEDULER_INTERVAL_SECONDS)


@app.on_event("shutdown")
async def on_shutdown():
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
    client.close()
