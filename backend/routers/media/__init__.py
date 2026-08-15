"""Media router — image uploads, asset library, health.

Sprint 15B carcass removal: ai_image, video, edit, export submodules deleted
along with MediaStudio.jsx (zero remaining callers). The shared module remains
because `_render_sync` / `_spawn_ai_image_task` are still used by
`routers.marketing_pack` (slideshow video + background pipelines).

Live submodules:
  - `shared`   — utilities reused by `routers.marketing_pack` + `routers.ai_designer`
  - `upload`   — POST   /upload
  - `assets`   — GET    /assets, /file/{id}, /thumb/{id}; PATCH /assets/{id};
                  DELETE /assets/{id}; POST /assets/{id}/duplicate;
                  GET    /folders, /stats
  - `health`   — GET    /health, GET /audit
"""
from __future__ import annotations

from fastapi import APIRouter

from . import assets, health, upload, library_manage

# Re-exports for back-compat with callers that import from `routers.media`:
from .shared import (  # noqa: F401
    TMP_DIR,
    _fit_to,
    _hex_to_rgb,
    _now,
    _render_sync,
    _spawn_ai_image_task,
)

router = APIRouter(prefix="/media", tags=["media"])

router.include_router(upload.router)
router.include_router(assets.router)
router.include_router(health.router)
router.include_router(library_manage.router)
