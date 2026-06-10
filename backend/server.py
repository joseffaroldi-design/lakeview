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
    cms, specials, analytics, giveaway, loyalty, messaging,
    catering, newsletter, misc, ai_ads, publishing, media, home,
    marketing_pack,
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
api_router.include_router(media.router)
api_router.include_router(home.router)
api_router.include_router(marketing_pack.router)
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
    # ---- 1. MongoDB indexes on hot collections (idempotent — create_index is a no-op if it exists)
    try:
        # ai_assets: Library search/filter
        await db.ai_assets.create_index([("status", 1), ("kind", 1), ("created_at", -1)], name="assets_status_kind_created")
        await db.ai_assets.create_index([("platform", 1), ("created_at", -1)], name="assets_platform_created")
        await db.ai_assets.create_index([("is_favorite", 1), ("created_at", -1)], name="assets_fav_created")
        await db.ai_assets.create_index("id", name="assets_id", unique=True, sparse=True)
        # scheduled_posts: Calendar + Queue + scheduler poll
        await db.scheduled_posts.create_index([("status", 1), ("scheduled_at", 1)], name="sp_status_at")
        await db.scheduled_posts.create_index([("provider", 1), ("scheduled_at", 1)], name="sp_provider_at")
        await db.scheduled_posts.create_index("id", name="sp_id", unique=True, sparse=True)
        # publish_logs: audit trail lookups
        await db.publish_logs.create_index([("scheduled_post_id", 1), ("created_at", -1)], name="logs_sp_created")
        await db.publish_logs.create_index([("created_at", -1)], name="logs_created")
        # ai_generations: analytics aggregations
        await db.ai_generations.create_index([("created_at", -1)], name="gens_created")
        await db.ai_generations.create_index([("brief.platform", 1)], name="gens_platform")
        # provider_connections: lookup by provider + business
        await db.provider_connections.create_index([("provider", 1), ("business_id", 1)], name="conn_provider_biz", unique=True)
        # media_assets: Library lookups by kind/folder/tags
        await db.media_assets.create_index([("status", 1), ("kind", 1), ("uploaded_at", -1)], name="media_status_kind_uploaded")
        await db.media_assets.create_index([("folder", 1), ("uploaded_at", -1)], name="media_folder_uploaded")
        await db.media_assets.create_index("id", name="media_id", unique=True, sparse=True)
        await db.render_jobs.create_index([("status", 1), ("created_at", -1)], name="render_status_created")
        await db.render_jobs.create_index("id", name="render_id", unique=True, sparse=True)
        # ai_image_jobs: AI image generation polling (Cloudflare bypass)
        await db.ai_image_jobs.create_index([("status", 1), ("created_at", -1)], name="aij_status_created")
        await db.ai_image_jobs.create_index("id", name="aij_id", unique=True, sparse=True)
        # marketing_packs: Promote This Item 2.0
        await db.marketing_packs.create_index([("status", 1), ("created_at", -1)], name="mpk_status_created")
        await db.marketing_packs.create_index("id", name="mpk_id", unique=True, sparse=True)
        await db.menu_promotions.create_index("item_key", name="mp_item_key", unique=True)
        logger.info("MongoDB indexes ensured on hot collections")
    except Exception as e:  # noqa: BLE001
        logger.warning("Index creation skipped: %s", e)

    # ---- 6. Pre-warm the plugin catalog (static — avoids cold-cache latency on first Automation Center mount)
    try:
        from ai_engine.plugins import list_plugins, get_plugin
        list_plugins()
        get_plugin("restaurant")
    except Exception:  # noqa: BLE001
        pass

    # ---- 7. Clean up orphan media jobs left behind by a previous worker
    try:
        from routers.media import cleanup_orphan_render_jobs, cleanup_orphan_ai_image_jobs
        from routers.marketing_pack import cleanup_orphan_marketing_packs
        await cleanup_orphan_render_jobs()
        await cleanup_orphan_ai_image_jobs()
        await cleanup_orphan_marketing_packs()
    except Exception as e:  # noqa: BLE001
        logger.warning("Orphan job cleanup skipped: %s", e)

    # ---- 7b. Initialize Emergent Object Storage (off the event loop)
    try:
        import storage as objstore
        await asyncio.to_thread(objstore.init_storage)
    except Exception as e:  # noqa: BLE001
        logger.warning("Object storage init skipped: %s", e)

    # ---- 8. Media Studio infra: ensure ffmpeg + pre-warm rembg model in background
    try:
        from bootstrap import ensure_ffmpeg, prewarm_rembg
        await asyncio.to_thread(ensure_ffmpeg)
        # Run model warmup off the main loop so backend stays responsive
        asyncio.create_task(prewarm_rembg())
    except Exception as e:  # noqa: BLE001
        logger.warning("Media bootstrap skipped: %s", e)

    global _scheduler_task
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("Publishing scheduler started (interval=%ss)", SCHEDULER_INTERVAL_SECONDS)


@app.on_event("shutdown")
async def on_shutdown():
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
    client.close()
