"""Lakeview Burgers & Seafood — FastAPI app entry point.

The public restaurant website and the small owner dashboard share this API.
Only routes required by those two surfaces are mounted here. Historical AI,
designer, flyer, billing, workspace, and experimental admin routers are kept
out of the live application.
"""
import asyncio
import logging
import os

from fastapi import APIRouter, FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware

import auth
from config import ALLOWED_ORIGINS, client, db
from rate_limit import limiter
from seed_data import seed_defaults
from routers import (
    analytics,
    catering,
    cms,
    home,
    loyalty,
    media,
    messaging,
    misc,
    newsletter,
    specials,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Public restaurant + essential owner-dashboard API only.
api_router = APIRouter(prefix="/api")
api_router.include_router(misc.router)
api_router.include_router(auth.router)
api_router.include_router(cms.router)
api_router.include_router(specials.router)
api_router.include_router(analytics.router)
api_router.include_router(loyalty.router)
api_router.include_router(messaging.router)
api_router.include_router(catering.router)
api_router.include_router(newsletter.router)
api_router.include_router(media.router)
api_router.include_router(home.router)
app.include_router(api_router)

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

    # Index only collections used by the live public/admin surfaces.
    try:
        await db.media_assets.create_index(
            [("status", 1), ("kind", 1), ("uploaded_at", -1)],
            name="media_status_kind_uploaded",
        )
        await db.media_assets.create_index(
            [("folder", 1), ("uploaded_at", -1)],
            name="media_folder_uploaded",
        )
        await db.media_assets.create_index("id", name="media_id", unique=True, sparse=True)
        await db.failure_audit_log.create_index(
            "expires_at", name="fal_ttl", expireAfterSeconds=0
        )
        await db.page_views.create_index(
            "expires_at", name="pv_ttl", expireAfterSeconds=0
        )
        await db.admin_sessions.create_index(
            "expires_at", name="as_ttl", expireAfterSeconds=0
        )
        logger.info("Live Lakeview indexes ensured")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Index creation skipped: %s", exc)

    # Retain TTL compatibility for existing public analytics/session rows.
    try:
        from migrations.ttl_backfill import backfill_ttl_expiries

        await backfill_ttl_expiries(db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("TTL backfill skipped: %s", exc)

    try:
        deleted = await auth.cleanup_expired_sessions()
        if deleted:
            logger.info("Cleaned up %d expired admin sessions", deleted)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Session cleanup skipped: %s", exc)

    # Library uploads continue to use Emergent object storage.
    try:
        import storage as objstore

        await asyncio.to_thread(objstore.init_storage)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Object storage init skipped: %s", exc)

    # Keep media helpers lazy/background-only for Library operations.
    try:
        from bootstrap import ensure_ffmpeg, prewarm_rembg

        asyncio.create_task(asyncio.to_thread(ensure_ffmpeg))
        if os.environ.get("REMBG_PREWARM", "").lower() in ("1", "true", "yes"):
            asyncio.create_task(prewarm_rembg())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Media bootstrap skipped: %s", exc)

    logger.info("Lakeview backend started with public + essential admin routes only")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
