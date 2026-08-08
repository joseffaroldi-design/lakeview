"""Lakeview Burgers & Seafood — FastAPI app entry point.

Route registration lives here; business logic is split across /routers/*.
"""
import asyncio
import logging
import os
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from config import db, client, ALLOWED_ORIGINS
from seed_data import seed_defaults
from rate_limit import limiter

import auth
from routers import (
    cms, specials, analytics, loyalty, messaging,
    catering, newsletter, misc, media, home,
    billing, todays_pick,
    photo_flyer,
    html_template, settings, marketing,
)

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
api_router.include_router(loyalty.router)
api_router.include_router(messaging.router)
api_router.include_router(catering.router)
api_router.include_router(newsletter.router)
api_router.include_router(media.router)
api_router.include_router(home.router)
api_router.include_router(billing.router)
api_router.include_router(photo_flyer.router)
api_router.include_router(todays_pick.router)
api_router.include_router(html_template.router)
api_router.include_router(settings.router)
api_router.include_router(marketing.router)
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


SCHEDULER_INTERVAL_SECONDS = 30  # Retained constant; scheduler loop removed in Sprint 12D
_scheduler_task = None  # always None — publishing pipeline retired

# Sprint 13A: APScheduler for Today's Pick daily cron
from apscheduler.schedulers.asyncio import AsyncIOScheduler
_daily_scheduler = None


@app.on_event("startup")
async def on_startup():
    await seed_defaults(db)
    # ---- 1. MongoDB indexes on hot collections (idempotent — create_index is a no-op if it exists)
    try:
        # Sprint 12D: scheduled_posts / publish_logs / provider_connections indexes
        # removed with the publishing pipeline (collections to be dropped).
        # ai_generations: analytics aggregations
        await db.ai_generations.create_index([("created_at", -1)], name="gens_created")
        await db.ai_generations.create_index([("brief.platform", 1)], name="gens_platform")
        # media_assets: Library lookups by kind/folder/tags
        await db.media_assets.create_index([("status", 1), ("kind", 1), ("uploaded_at", -1)], name="media_status_kind_uploaded")
        await db.media_assets.create_index([("folder", 1), ("uploaded_at", -1)], name="media_folder_uploaded")
        await db.media_assets.create_index("id", name="media_id", unique=True, sparse=True)
        # Sprint 12C: route /api/ai-ads/assets to media_assets via source filter
        await db.media_assets.create_index([("source", 1), ("created_at", -1)], name="media_source_created")
        # Sprint 15B: render_jobs and ai_image_jobs indexes removed (collections dropped).
        # marketing_packs: Promote This Item 2.0
        await db.marketing_packs.create_index([("status", 1), ("created_at", -1)], name="mpk_status_created")
        await db.marketing_packs.create_index("id", name="mpk_id", unique=True, sparse=True)
        await db.menu_promotions.create_index("item_key", name="mp_item_key", unique=True)
        # V1 simplification: owner settings + deterministic flyer jobs + auditable loyalty.
        await db.business_settings.create_index("id", name="business_settings_id", unique=True, sparse=True)
        await db.marketing_flyer_jobs.create_index("id", name="marketing_flyer_job_id", unique=True, sparse=True)
        await db.marketing_flyer_jobs.create_index([("status", 1), ("created_at", -1)], name="marketing_flyer_status_created")
        await db.loyalty_events.create_index([("member_id", 1), ("created_at", -1)], name="loyalty_events_member_created")
        # Sprint 12C — Task 3: TTL indexes prevent unbounded growth on append-only
        # audit / log / analytics collections. Mongo's TTL monitor deletes any doc
        # whose `expires_at` (BSON Date) is in the past, checked roughly every 60s.
        await db.failure_audit_log.create_index("expires_at", name="fal_ttl", expireAfterSeconds=0)
        await db.page_views.create_index("expires_at", name="pv_ttl", expireAfterSeconds=0)
        # Sprint 12C — Task 5: ai_generations retained 90 days for /api/ai-ads/stats analytics
        await db.ai_generations.create_index("expires_at", name="gens_ttl", expireAfterSeconds=0)
        # Sprint 15B: admin_sessions TTL. New rows write native BSON `expires_at`;
        # legacy ISO-string `expires` rows are bulk-cleaned below.
        await db.admin_sessions.create_index("expires_at", name="as_ttl", expireAfterSeconds=0)
        logger.info("MongoDB indexes ensured on hot collections")
    except Exception as e:  # noqa: BLE001
        logger.warning("Index creation skipped: %s", e)

    # Sprint 12D: ai_engine.plugins pre-warm removed (plugins package deleted).

    # ---- 7. Legacy generation job cleanup retired.
    # Historical rows and render implementations remain read-compatible until
    # their data is migrated, but the old generation APIs no longer create jobs.

    # ---- 7a. Sprint 12C — Backfill TTL `expires_at` on legacy rows.
    try:
        from migrations.ttl_backfill import backfill_ttl_expiries
        await backfill_ttl_expiries(db)
    except Exception as e:  # noqa: BLE001
        logger.warning("TTL backfill skipped: %s", e)

    # ---- 7b. Sprint 15B: bulk-delete expired admin_sessions (legacy ISO-string `expires`).
    try:
        deleted = await auth.cleanup_expired_sessions()
        if deleted:
            logger.info("Cleaned up %d expired admin_sessions", deleted)
    except Exception as e:  # noqa: BLE001
        logger.warning("Session cleanup skipped: %s", e)

    # ---- 7c. Initialize Emergent Object Storage (off the event loop)
    try:
        import storage as objstore
        await asyncio.to_thread(objstore.init_storage)
    except Exception as e:  # noqa: BLE001
        logger.warning("Object storage init skipped: %s", e)

    # ---- 8. Media Studio infra: ensure ffmpeg + (optionally) pre-warm rembg model.
    # Sprint 15B.3: BOTH ffmpeg-ensure and rembg-prewarm are now fully off the
    # critical startup path. ffmpeg-install runs as a background task (was
    # blocking startup up to 120s if apt-get had to install the binary).
    # rembg is opt-in via REMBG_PREWARM=1; default skips and loads lazily on
    # the first user-triggered "Remove background" call.
    try:
        from bootstrap import ensure_ffmpeg, prewarm_rembg
        asyncio.create_task(asyncio.to_thread(ensure_ffmpeg))
        if os.environ.get("REMBG_PREWARM", "").lower() in ("1", "true", "yes"):
            asyncio.create_task(prewarm_rembg())
        else:
            logger.info("[bootstrap] rembg pre-warm skipped (set REMBG_PREWARM=1 to enable). Model loads on first explicit Remove-Background request.")
    except Exception as e:  # noqa: BLE001
        logger.warning("Media bootstrap skipped: %s", e)

    # Sprint 12D: scheduler loop removed (publishing pipeline retired)
    logger.info("Backend startup complete — Sprint 12D demolition active")
    
    # ---- 9. Start APScheduler for Today's Pick (Sprint 13A → 14A) ----
    global _daily_scheduler
    try:
        _daily_scheduler = AsyncIOScheduler()
        # Sprint 14A: Run at 5:30 AM UTC (generate graphics + copy before owner wakes up)
        _daily_scheduler.add_job(
            todays_pick.generate_todays_pick_job,
            'cron',
            hour=5,
            minute=30,
            id='todays_pick_daily',
            replace_existing=True,
        )
        _daily_scheduler.start()
        logger.info("Today's Pick scheduler started (runs daily at 5:30 AM UTC with graphics)")
    except Exception as e:
        logger.error(f"Failed to start Today's Pick scheduler: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
    if _daily_scheduler:
        _daily_scheduler.shutdown(wait=False)
