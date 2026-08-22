"""Lakeview Burgers & Seafood — FastAPI app entry point.

Only public-site and core admin routes are mounted here. Historical AI/design
routers remain in source for compatibility/archive purposes but are intentionally
not mounted or started.
"""
import asyncio
import logging

from fastapi import APIRouter, FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware

import auth
from config import ALLOWED_ORIGINS, client, db
from rate_limit import limiter
from routers import (
    analytics,
    catering,
    cms,
    home,
    html_template,
    loyalty,
    media,
    misc,
    newsletter,
    site_images,
    specials,
)
from seed_data import seed_defaults

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Public restaurant site + simplified admin allowlist.
api_router = APIRouter(prefix="/api")
api_router.include_router(misc.router)          # health / misc public helpers
api_router.include_router(auth.router)          # admin login/session
api_router.include_router(cms.router)           # public content + menu editing
api_router.include_router(specials.router)      # public specials
api_router.include_router(analytics.router)     # lightweight public analytics
api_router.include_router(loyalty.router)       # public/admin loyalty
api_router.include_router(catering.router)      # public inquiry + admin follow-up
api_router.include_router(newsletter.router)    # public signup + admin subscribers
api_router.include_router(media.router)         # library files/images
api_router.include_router(site_images.router)   # slot→asset mapping for public-site photos
api_router.include_router(home.router)          # public homepage layout
api_router.include_router(html_template.router) # public featured-special image endpoint
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
    """Start only the infrastructure still used by the public site/admin."""
    await seed_defaults(db)

    try:
        # Library / public featured-special lookups.
        await db.media_assets.create_index(
            [("status", 1), ("kind", 1), ("uploaded_at", -1)],
            name="media_status_kind_uploaded",
        )
        await db.media_assets.create_index(
            [("folder", 1), ("uploaded_at", -1)],
            name="media_folder_uploaded",
        )
        await db.media_assets.create_index("id", name="media_id", unique=True, sparse=True)
        await db.media_assets.create_index(
            [("source", 1), ("uploaded_at", -1)],
            name="media_source_uploaded",
        )

        # Public analytics + admin authentication retention.
        await db.failure_audit_log.create_index(
            "expires_at", name="fal_ttl", expireAfterSeconds=0
        )
        await db.page_views.create_index(
            "expires_at", name="pv_ttl", expireAfterSeconds=0
        )
        await db.admin_sessions.create_index(
            "expires_at", name="as_ttl", expireAfterSeconds=0
        )
        logger.info("Core Lakeview indexes ensured")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Index creation skipped: %s", exc)

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

    try:
        import storage as objstore

        await asyncio.to_thread(objstore.init_storage)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Object storage init skipped: %s", exc)

    logger.info("Lakeview core backend startup complete")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
