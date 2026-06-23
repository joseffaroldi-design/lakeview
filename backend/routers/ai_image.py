"""Sprint 15B.8 — AI Image Generation router.

Adds a second engine alongside the existing Template Designer:

  POST /api/ai-image/generate        → enqueue, returns 202 + job_id
  GET  /api/ai-image/job/{job_id}    → poll status + variations
  GET  /api/ai-image/style-presets   → list of 10 style packs for the UI
  GET  /api/ai-image/providers       → diagnostic (mirrored in /media/health)

Reuses ALL existing infrastructure:
  * `storage.put_bytes()`           — Emergent Object Storage
  * `media_assets` collection       — same library as everything else
  * `/api/media/thumb/{id}`         — thumbnails serve generated images
  * `verify_session` auth           — same admin protection
  * Background-task pattern         — mirrors ai_designer.py polling
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Cookie, Header, HTTPException
from pydantic import BaseModel, Field

from auth import verify_session
from config import db
import storage as objstore
from services.image_generation import (
    ImageGenerationError,
    STYLE_PRESETS,
    available_providers,
    build_prompt,
    get_image_provider,
)
from services.image_generation.style_presets import preset_keys

logger = logging.getLogger("ai-image")

router = APIRouter(prefix="/ai-image", tags=["ai-image"])


# ---------------------------------------------------------------- Schemas

_ALLOWED_RATIOS = {"1:1", "4:5", "9:16", "16:9"}
_PRESET_KEYS = set(preset_keys())
_MAX_PROMPT_LEN = 500
_MIN_PROMPT_LEN = 4

# Sprint 15B.8 production-safety cap.
# Preview environment: 4 variations per Generate (full UX).
# Production environment: 1 variation initially — caps API cost, latency
# spikes, worker blocking, and accidental credit burn while the infra
# upgrade (workers=4, REMBG_PREWARM=1) is being honored by Emergent Support.
# Switch to 4 in production after one week of stable operation by setting
# AI_IMAGE_MAX_VARIATIONS=4 OR ENVIRONMENT=preview in the prod env config.
def _variation_cap() -> int:
    import os  # noqa: PLC0415
    override = os.environ.get("AI_IMAGE_MAX_VARIATIONS")
    if override and override.isdigit():
        return max(1, min(4, int(override)))
    env = (os.environ.get("ENVIRONMENT") or "preview").lower()
    return 1 if env == "production" else 4


class GenerateImageRequest(BaseModel):
    prompt: str = Field(..., min_length=_MIN_PROMPT_LEN, max_length=_MAX_PROMPT_LEN)
    style_pack: str = Field(..., description="One of style_presets keys")
    aspect_ratio: str = Field(default="1:1", description="1:1 | 4:5 | 9:16 | 16:9")
    # Optional override; otherwise factory picks (Flux if FAL_KEY, else OpenAI).
    provider: Optional[str] = Field(default=None, description="'flux' | 'openai' | None")


# ---------------------------------------------------------------- Helpers

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_job_or_404(job_id: str) -> dict:
    job = await db.ai_image_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def _save_generated_asset(
    *,
    img_bytes: bytes,
    mime: str,
    width: int,
    height: int,
    item_name: str,
    style_pack: str,
    provider: str,
) -> dict:
    """Persist one generated image as a `media_assets` row + object-storage blob.

    Mirrors `_save_design_asset` in ai_designer.py so library/thumb/file
    endpoints work without any change.
    """
    import uuid
    aid = str(uuid.uuid4())
    storage_path = objstore.make_path("ai_images", aid, "png")
    await asyncio.to_thread(objstore.put_bytes, storage_path, img_bytes, mime)
    slug = item_name[:30].replace(" ", "-").lower().strip("-") or "ai-image"
    doc = {
        "id": aid,
        "filename": f"ai-image-{provider}-{slug}-{aid[:6]}.png",
        "kind": "image",
        "mime": mime,
        "size_bytes": len(img_bytes),
        "width": width,
        "height": height,
        "duration_seconds": None,
        "folder": "AI Image Generator",
        "tags": ["ai-image", f"provider:{provider}", f"style:{style_pack}"],
        "storage_path": storage_path,
        "is_favorite": False,
        "status": "active",
        "source": "ai_image_generator",
        "uploaded_at": _now(),
        "updated_at": _now(),
    }
    await db.media_assets.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


# ---------------------------------------------------------------- Background worker

async def _run_image_job(
    job_id: str,
    *,
    prompt: str,
    style_pack: str,
    aspect_ratio: str,
    preferred_provider: Optional[str],
    item_name: str,
    n_variations: int,
) -> None:
    async def update(**fields: Any) -> None:
        fields["updated_at"] = _now()
        await db.ai_image_jobs.update_one({"id": job_id}, {"$set": fields})

    async def fail(code: str, user_msg: str, technical: str = "") -> None:
        await update(status="failed", progress=0, error={
            "code": code,
            "status": 500,
            "retryable": code not in ("invalid_prompt", "no_provider"),
            "retry_action": "retry",
            "user_message": user_msg,
            "technical": technical[:300],
        })

    # 1. Pick the provider.
    try:
        provider = get_image_provider(prefer=preferred_provider)
    except ImageGenerationError as e:
        await fail(e.code, e.user_message, e.detail or "")
        return

    await update(status="processing", progress=15, provider=provider.name, model=provider.model)

    # 2. Generate.
    scaffolded, _negative = build_prompt(style_pack, prompt)
    try:
        results = await provider.generate(
            prompt=scaffolded,
            aspect_ratio=aspect_ratio,
            n=n_variations,
        )
    except ImageGenerationError as e:
        # Provider-specific fallback: if Flux fails and OpenAI is configured,
        # do one retry on OpenAI before giving up. Only when caller didn't
        # explicitly pin to Flux.
        if (
            provider.name == "flux"
            and preferred_provider != "flux"
            and e.code in ("provider_timeout", "provider_error", "quota_exceeded", "invalid_api_key")
        ):
            logger.warning("[ai-image] job=%s flux failed (%s); falling back to openai", job_id, e.code)
            try:
                fallback = get_image_provider(prefer="openai")
            except ImageGenerationError:
                await fail(e.code, e.user_message, e.detail or "")
                return
            await update(progress=35, provider=fallback.name, model=fallback.model,
                         fallback_from="flux", fallback_reason=e.code)
            try:
                results = await fallback.generate(
                    prompt=scaffolded, aspect_ratio=aspect_ratio, n=n_variations,
                )
            except ImageGenerationError as e2:
                await fail(e2.code, e2.user_message, e2.detail or "")
                return
        else:
            await fail(e.code, e.user_message, e.detail or "")
            return

    await update(progress=70)

    # 3. Persist each variation.
    variations: List[dict] = []
    for idx, img in enumerate(results):
        try:
            asset = await _save_generated_asset(
                img_bytes=img.data,
                mime=img.mime,
                width=img.width,
                height=img.height,
                item_name=item_name,
                style_pack=style_pack,
                provider=img.provider,
            )
            variations.append({
                "variant": chr(ord("A") + idx),
                "status": "completed",
                "asset_id": asset["id"],
                "asset": asset,
                "provider": img.provider,
                "seed": img.seed,
            })
        except Exception as e:  # noqa: BLE001
            logger.exception("[ai-image] job=%s variant=%d persist failed", job_id, idx)
            variations.append({
                "variant": chr(ord("A") + idx),
                "status": "failed",
                "error": "Could not save the generated image. Try again.",
                "error_code": "storage_error",
                "technical": str(e)[:300],
            })

    successes = [v for v in variations if v.get("status") == "completed"]
    if not successes:
        await fail(
            "all_variations_failed",
            "All variations failed to save. Storage may be temporarily unavailable.",
            "no variations persisted",
        )
        return

    await update(
        status="completed",
        progress=100,
        variations=variations,
        finished_at=_now(),
    )
    logger.info("[ai-image] job=%s completed %d/%d variations via %s",
                job_id, len(successes), n_variations, provider.name)


# ---------------------------------------------------------------- Routes

@router.get("/style-presets")
async def list_style_presets(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    return {"presets": [{"key": p["key"], "label": p["label"]} for p in STYLE_PRESETS]}


@router.get("/providers")
async def list_providers(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    info = available_providers()
    info["variations_per_request"] = _variation_cap()
    return info


@router.post("/generate", status_code=202)
async def enqueue_generate(
    body: GenerateImageRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)

    if body.style_pack not in _PRESET_KEYS:
        raise HTTPException(status_code=400, detail="Unknown style_pack")
    if body.aspect_ratio not in _ALLOWED_RATIOS:
        raise HTTPException(status_code=400, detail="Unsupported aspect_ratio")
    if body.provider is not None and body.provider not in ("flux", "openai"):
        raise HTTPException(status_code=400, detail="Unknown provider")

    # Hard 503 if no provider at all — we never accept a job we cannot run.
    try:
        provider = get_image_provider(prefer=body.provider)
    except ImageGenerationError as e:
        raise HTTPException(status_code=503, detail={
            "code": e.code,
            "user_message": e.user_message,
        }) from e

    import uuid
    job_id = str(uuid.uuid4())
    item_name = body.prompt.split(".")[0][:60].strip() or "AI image"
    n_variations = _variation_cap()
    job_doc = {
        "id": job_id,
        "status": "pending",
        "progress": 0,
        "prompt": body.prompt,
        "style_pack": body.style_pack,
        "aspect_ratio": body.aspect_ratio,
        "provider": provider.name,
        "model": provider.model,
        "variations": [],
        "n_variations": n_variations,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.ai_image_jobs.insert_one(job_doc)

    asyncio.create_task(_run_image_job(
        job_id,
        prompt=body.prompt,
        style_pack=body.style_pack,
        aspect_ratio=body.aspect_ratio,
        preferred_provider=body.provider,
        item_name=item_name,
        n_variations=n_variations,
    ))

    return {
        "job_id": job_id,
        "status": "pending",
        "provider": provider.name,
        "model": provider.model,
        "variations": n_variations,
    }


@router.get("/job/{job_id}")
async def get_job(
    job_id: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    return await _get_job_or_404(job_id)
