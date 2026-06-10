"""Media Studio router — image/video uploads, AI image generation, video rendering.

This package was split out of a 1,431-line monolith. The public surface is
preserved 1:1: every endpoint keeps the same path under `/api/media/*`, the
same method signature, the same auth behaviour, and the same background-task
plumbing.

Submodules:
  - `shared`   — utilities reused across submodules + by `routers.marketing_pack`
  - `upload`   — POST   /upload
  - `assets`   — GET    /assets, /file/{id}, /thumb/{id}; PATCH /assets/{id};
                  DELETE /assets/{id}; POST /assets/{id}/duplicate;
                  GET    /folders, /stats
  - `ai_image` — POST   /ai-image (202 + job_id), GET /ai-image/job/{id};
                  startup janitor `cleanup_orphan_ai_image_jobs`
  - `video`    — POST   /video/render, GET /video/jobs, GET /video/jobs/{id};
                  startup janitor `cleanup_orphan_render_jobs`
  - `edit`     — POST   /edit
  - `export`   — POST   /export-social, GET /social-formats
  - `health`   — GET    /health, GET /audit
"""
from __future__ import annotations

from fastapi import APIRouter

from . import ai_image, assets, edit, export, health, upload, video

# Re-exports for back-compat with callers that import from `routers.media`:
#   - `routers.marketing_pack` imports TMP_DIR, _fit_to, _hex_to_rgb, _now,
#     _render_sync, _spawn_ai_image_task
#   - `server.py` imports cleanup_orphan_render_jobs, cleanup_orphan_ai_image_jobs
from .shared import (  # noqa: F401
    TMP_DIR,
    _fit_to,
    _hex_to_rgb,
    _now,
    _render_sync,
    _spawn_ai_image_task,
)
from .ai_image import cleanup_orphan_ai_image_jobs  # noqa: F401
from .video import cleanup_orphan_render_jobs  # noqa: F401

router = APIRouter(prefix="/media", tags=["media"])

# Order matters only insofar as health/audit and folders/stats don't collide
# with parametric paths; FastAPI resolves by exact match first, so include order
# is non-significant here.
router.include_router(upload.router)
router.include_router(assets.router)
router.include_router(ai_image.router)
router.include_router(video.router)
router.include_router(edit.router)
router.include_router(export.router)
router.include_router(health.router)
