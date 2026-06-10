"""AI image generation — async job + polling, orphan cleanup."""
from __future__ import annotations

import asyncio
import io
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Header, HTTPException
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, constr

from auth import verify_session
import storage as objstore
from .shared import _now, _spawn_ai_image_task, db

router = APIRouter()


class AiImageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    prompt: constr(min_length=3, max_length=2000)
    style: Optional[constr(max_length=200)] = "Food photography, natural light, appetizing, restaurant menu hero shot"
    count: int = Field(default=1, ge=1, le=4)
    quality: constr(pattern=r"^(low|medium|high)$") = "medium"
    folder: Optional[constr(max_length=60)] = "Promotions"
    headline: Optional[constr(max_length=200)] = None
    tags: Optional[List[str]] = None


# ---- Async job architecture ------------------------------------------------
# AI image generation takes ~60-85s end-to-end, which exceeds Cloudflare's 60s
# idle-connection limit in production. We therefore enqueue a background job,
# return 202 + job_id immediately, and let the frontend poll until done.
# State lives in the `ai_image_jobs` collection.


async def _run_ai_image_job(job_id: str, body: AiImageRequest) -> None:
    """Background worker — does the actual generation and updates job state."""
    import logging
    img_log = logging.getLogger("uvicorn.error")

    async def _update(**fields: Any) -> None:
        fields["updated_at"] = _now()
        await db.ai_image_jobs.update_one({"id": job_id}, {"$set": fields})

    async def _fail(err) -> None:
        await _update(status="failed", error=err.to_payload(), progress=0)

    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        from errors import StructuredError, report_failure
        err = StructuredError(
            code="key_missing", status=500, retryable=False,
            user_message="AI image generation isn't configured on this server. Ask your admin to set EMERGENT_LLM_KEY.",
            technical="EMERGENT_LLM_KEY env var is empty",
        )
        await report_failure(db, surface="ai_image", err=err)
        await _fail(err)
        return

    from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration

    full_prompt = body.prompt
    if body.style:
        full_prompt += f". Style: {body.style}"
    if body.headline:
        full_prompt += f". Include headline: '{body.headline}' tastefully overlaid in restaurant typography."

    await _update(status="processing", progress=10)

    client = OpenAIImageGeneration(api_key=key)
    try:
        # Background path — no Cloudflare in the loop, so we can afford a generous
        # ceiling. 180s comfortably covers worst-case 4×high-quality runs.
        image_bytes_list = await asyncio.wait_for(
            client.generate_images(
                prompt=full_prompt, model="gpt-image-1",
                number_of_images=body.count, quality=body.quality,
            ),
            timeout=180.0,
        )
    except asyncio.TimeoutError:
        from errors import StructuredError, report_failure
        err = StructuredError(
            code="timeout", status=504, retryable=True, retry_action="retry",
            user_message="Image generation took too long (over 3 minutes). Try a shorter prompt, lower quality, or fewer images.",
            technical="client.generate_images timed out after 180s",
        )
        await report_failure(db, surface="ai_image", err=err,
                             prompt=full_prompt[:120], quality=body.quality, count=body.count)
        await _fail(err)
        return
    except Exception as e:  # noqa: BLE001
        from errors import classify_llm_error, report_failure
        err = classify_llm_error(e, surface="image generation")
        img_log.exception("[ai-image] job=%s generation raised — code=%s", job_id, err.code)
        await report_failure(db, surface="ai_image", err=err,
                             prompt=full_prompt[:120], quality=body.quality, count=body.count)
        await _fail(err)
        return

    if not image_bytes_list:
        from errors import StructuredError, report_failure
        err = StructuredError(
            code="provider_empty", status=502, retryable=True, retry_action="retry",
            user_message="The AI provider returned no images. Please try again.",
            technical="empty image_bytes_list from provider",
        )
        await report_failure(db, surface="ai_image", err=err, prompt=full_prompt[:120])
        await _fail(err)
        return

    await _update(progress=80)

    saved = []
    for img_bytes in image_bytes_list:
        aid = str(uuid.uuid4())
        storage_path = objstore.make_path("ai_images", aid, "png")
        objstore.put_bytes(storage_path, img_bytes, "image/png")
        try:
            with Image.open(io.BytesIO(img_bytes)) as im:
                w, h = im.size
        except Exception:  # noqa: BLE001
            w = h = None
        doc = {
            "id": aid,
            "filename": f"ai-{(body.headline or body.prompt)[:40].replace(' ', '-')}-{aid[:6]}.png",
            "kind": "image",
            "mime": "image/png",
            "size_bytes": len(img_bytes),
            "width": w, "height": h, "duration_seconds": None,
            "folder": body.folder or "Promotions",
            "tags": (body.tags or []) + ["ai-generated"],
            "storage_path": storage_path,
            "is_favorite": False, "status": "active",
            "source": "ai_image",
            "ai_prompt": full_prompt,
            "uploaded_at": _now(), "updated_at": _now(),
        }
        await db.media_assets.insert_one(doc)
        saved.append({k: v for k, v in doc.items() if k != "_id"})

    img_log.info("[ai-image] job=%s generated %s image(s)", job_id, len(saved))
    await _update(
        status="completed",
        progress=100,
        result={"assets": saved, "count": len(saved)},
    )


@router.post("/ai-image", status_code=202)
async def enqueue_ai_image(
    body: AiImageRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Enqueue an AI image generation job and return immediately.

    Returns 202 with `{job_id, status: "pending"}` in under 1 second so Cloudflare
    never times out. The frontend polls `GET /ai-image/job/{job_id}` until the
    job reaches `completed` or `failed`.
    """
    await verify_session(authorization, session_token)

    # Fail fast if the key is missing — surface a structured error synchronously
    # so the form shows it immediately instead of via a polled job.
    if not os.environ.get("EMERGENT_LLM_KEY"):
        from errors import StructuredError, report_failure
        err = StructuredError(
            code="key_missing", status=500, retryable=False,
            user_message="AI image generation isn't configured on this server. Ask your admin to set EMERGENT_LLM_KEY.",
            technical="EMERGENT_LLM_KEY env var is empty",
        )
        await report_failure(db, surface="ai_image", err=err)
        raise HTTPException(status_code=err.status, detail=err.to_payload())

    job_id = str(uuid.uuid4())
    now = _now()
    await db.ai_image_jobs.insert_one({
        "id": job_id,
        "status": "pending",
        "prompt": body.prompt,
        "headline": body.headline,
        "style": body.style,
        "count": body.count,
        "quality": body.quality,
        "folder": body.folder,
        "tags": body.tags or [],
        "progress": 0,
        "created_at": now,
        "updated_at": now,
        "result": None,
        "error": None,
    })

    _spawn_ai_image_task(_run_ai_image_job(job_id, body))

    return {"job_id": job_id, "status": "pending"}


@router.get("/ai-image/job/{job_id}")
async def get_ai_image_job(
    job_id: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Poll endpoint — returns full job state, including `result` once complete
    or `error` (structured) on failure."""
    await verify_session(authorization, session_token)
    job = await db.ai_image_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _classify_image_error(exc: Exception) -> Dict[str, Any]:
    """Deprecated — kept only for the test fixture in test_phase8_media_studio.py.
    All production code paths now use errors.classify_llm_error directly."""
    from errors import classify_llm_error
    err = classify_llm_error(exc, surface="image generation")
    return {"code": err.code, "status": err.status, "user_message": err.user_message}


async def cleanup_orphan_ai_image_jobs():
    """Mark pending/processing AI image jobs as failed at startup. The background
    `asyncio.create_task` lives only in the previous process; once we restart,
    those tasks are gone forever. Without this sweep the UI polls indefinitely.

    Threshold: any job currently in pending/processing is orphaned by definition
    when the server (re)starts — no live process is driving it. We don't filter
    by age because the new process starts with an empty task set."""
    orphan_err = {
        "code": "unknown",
        "status": 500,
        "retryable": True,
        "retry_action": "retry",
        "user_message": "This image generation was interrupted by a server restart. Click Try again to regenerate.",
        "technical": "backend restarted with job in pending/processing state",
        "context": {},
    }
    r = await db.ai_image_jobs.update_many(
        {"status": {"$in": ["pending", "processing"]}},
        {"$set": {"status": "failed", "error": orphan_err, "progress": 0, "updated_at": _now()}},
    )
    if r.modified_count > 0:
        import logging
        logging.getLogger("uvicorn.error").info(
            f"[media] Marked {r.modified_count} orphan ai_image_job(s) as failed at startup"
        )
