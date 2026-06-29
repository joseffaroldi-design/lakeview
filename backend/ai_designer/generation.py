"""
Generation Orchestration

Background worker that processes a single AI Designer job:
  1. Loads the source food photo from object storage.
  2. Pre-processes the food cutout ONCE (rembg opt-in).
  3. Iterates over the requested variant count, composing each variant
     through the router-provided `compose_design` callable.
  4. Persists each variant via the router-provided `save_design_asset`
     callable.
  5. Updates the `ai_design_jobs` row with progress + final state.
  6. Optionally generates marketing copy via `write_designer_copy`.

Tech Debt Sprint Step 5 — Extracted from routers/ai_designer.py.
Composition, rendering, schemas, route handlers, and DB writer all
remain in the router. This module only owns the orchestration loop.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import HTTPException

from ai_designer.copy_generation import write_designer_copy
from ai_designer.registries.layouts import LAYOUTS
from ai_designer.registries.themes import THEME_STYLES

logger = logging.getLogger("uvicorn.error")

VARIATION_LABELS = ["A", "B", "C", "D", "E"]  # Support up to 5 variants

# Sprint 22B — Production stability hardening.
# Heavy PIL composition is CPU-bound and synchronous. Two failure modes
# were observed on the production container:
#   1. Event loop starvation — the running job blocks `/api/ai-designer/jobs/{id}`
#      polling requests long enough for the ingress to return 502/504.
#   2. Concurrent compositions — multiple jobs in flight simultaneously can
#      blow past the production memory ceiling, triggering container restarts
#      and 520 errors.
# Fix: route every sync PIL call through `asyncio.to_thread` so the event loop
# stays responsive, and gate composition behind a module-level semaphore so
# at most `AI_DESIGNER_MAX_CONCURRENCY` heavy renders run at once across the
# whole process. Default is intentionally conservative (2) — overridable via
# env so we can tune without a redeploy.
_MAX_CONCURRENCY = max(1, int(os.environ.get("AI_DESIGNER_MAX_CONCURRENCY", "2")))
_compose_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    # Lazy-init so we bind to the running event loop, not import-time loop.
    global _compose_semaphore
    if _compose_semaphore is None:
        _compose_semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
    return _compose_semaphore


async def run_design_job(
    job_id: str,
    body: Any,
    *,
    db: Any,
    now: Callable[[], Any],
    objstore: Any,
    canvas_max: int,
    get_active_asset: Callable[[str], Awaitable[Dict[str, Any]]],
    prepare_food_cutout: Callable[..., Any],
    compose_design: Callable[..., Any],
    save_design_asset: Callable[..., Awaitable[Dict[str, Any]]],
    pil_background: Callable[[str, int], bytes],
) -> None:
    """Process a single AI Designer job end-to-end.

    All composition, persistence, and rendering primitives are injected
    by the router so this module stays free of FastAPI / storage / PIL
    dependencies beyond the orchestration glue.
    """

    async def update(**fields: Any) -> None:
        fields["updated_at"] = now()
        await db.ai_design_jobs.update_one({"id": job_id}, {"$set": fields})

    async def fail(user_msg: str, technical: str = "", code: str = "generation_failed") -> None:
        await update(
            status="failed",
            progress=0,
            error={
                "code": code,
                "status": 500,
                "retryable": True,
                "retry_action": "retry",
                "user_message": user_msg,
                "technical": technical,
            },
        )

    # Load source food photo
    try:
        asset = await get_active_asset(body.source_asset_id)
        # Production hotfix — objstore.get_bytes is blocking; offload to a
        # worker thread so concurrent jobs don't serialize on this fetch.
        food_bytes, _ = await asyncio.to_thread(
            objstore.get_bytes, asset["storage_path"],
        )
    except HTTPException as e:
        await fail(e.detail if isinstance(e.detail, str) else "Source asset not found")
        return
    except Exception as e:  # noqa: BLE001
        await fail("Couldn't load your source photo from storage. Try again.", str(e))
        return

    # Pre-process food cutout ONCE — same cutout used in all variants.
    # Sprint 15B.3: only run rembg if the user explicitly opted in.
    # Sprint 22B: offload to thread — `prepare_food_cutout` is sync PIL +
    # optional rembg (very heavy). Running it inline blocks the event loop.
    try:
        food_rgba = await asyncio.to_thread(
            prepare_food_cutout,
            food_bytes,
            target_max=int(canvas_max * 0.65),
            use_rembg=bool(getattr(body, "remove_background", False)),
        )
    except Exception as e:  # noqa: BLE001
        await fail("Couldn't read your source photo. Try a different image.", str(e))
        return

    await update(status="processing", progress=5)

    # Sprint 22F → 22G — variation diversity via RenderContext.
    # `job_nonce` is generated once per JOB so two regenerations of the
    # same dish/theme/variant produce visibly different design choices
    # (photo offset, badge corner, feature order, overlay subset, bg
    # tint, title alignment, halftone overlay placement). Variation
    # within a job (A vs B vs C) is preserved via `variant_index`.
    import random as _r
    from ai_designer.render_context import RenderContext
    from ai_designer.registries.theme_packs._overlays import set_job_nonce
    job_nonce = _r.SystemRandom().randint(1, 2**31 - 1)
    logger.info(f"[ai-designer 22G] job_nonce={job_nonce} theme={body.theme} variations={body.variations}")

    variations: List[Dict[str, Any]] = []
    variant_count = min(5, max(1, body.variations))  # Clamp to 1-5
    total = variant_count
    sem = _get_semaphore()
    for idx in range(variant_count):
        variant = VARIATION_LABELS[idx]
        layout = LAYOUTS[idx % len(LAYOUTS)]  # Cycle through layouts if more than 3
        # Distinct nonce per variant so A/B/C don't share design choices
        # within a single job either. Also seeds the overlay TLS for
        # `_overlays._rng()` callers (procedural fallback path).
        variant_nonce = (job_nonce ^ (idx * 2654435761)) & 0xFFFFFFFF
        ctx = RenderContext(
            job_nonce=job_nonce,
            variant_index=idx,
            theme_id=body.theme,
            layout=layout,
            platform=body.platform or "instagram_post",
            item_name=body.item_name,
            features=tuple(body.features or ()),
            price=body.price or "",
            cta=body.cta or "",
            brand=os.environ.get("AI_DESIGNER_BRAND", "LAKEVIEW BURGERS & SEAFOOD"),
        )
        try:
            # Sprint 22B: gate heavy PIL work behind a process-wide semaphore
            # so at most _MAX_CONCURRENCY variants render at once across all
            # in-flight jobs. Offload to a worker thread so the event loop
            # keeps serving `/jobs/{id}` polling requests in the meantime.
            async with sem:
                # Sprint 22F/G — bind the overlay TLS nonce + pass ctx
                # explicitly on the worker thread that actually runs
                # compose_design.
                def _render() -> Any:  # noqa: ANN401
                    set_job_nonce(variant_nonce)
                    bg = pil_background(body.theme, idx)
                    return bg, compose_design(
                        bg,
                        food_rgba,
                        body.item_name,
                        body.features,
                        body.price,
                        body.theme,
                        layout,
                        variant_idx=idx,
                        cta=body.cta,
                        include_price=body.include_price,
                        include_description=body.include_description,
                        platform=body.platform or "instagram_post",
                        tone=body.tone,
                        logo_url=body.logo_url,
                        logo_placement=body.logo_placement,
                        logo_size=body.logo_size,
                        ctx=ctx,
                    )

                _bg_bytes, compose_out = await asyncio.to_thread(_render)
                graphic_bytes, score_info = compose_out
                del _bg_bytes  # bg is consumed inside compose_design; we don't need to retain it
        except Exception as e:  # noqa: BLE001
            variations.append(
                {
                    "theme": body.theme,
                    "variant": variant,
                    "layout": layout,
                    "status": "failed",
                    "error": "Composition failed",
                    "error_code": "compose_error",
                }
            )
            logger.exception(
                "[ai-designer] job=%s variant=%s composition failed: %s", job_id, variant, e
            )
            await update(progress=int(100 * (idx + 1) / total), variations=variations)
            continue

        saved = await save_design_asset(
            graphic_bytes,
            body.item_name,
            body.theme,
            variant,
            item_key=body.item_key,
            source_asset_id=body.source_asset_id,
            score_info=score_info,
        )
        variations.append(
            {
                "theme": body.theme,
                "theme_label": THEME_STYLES[body.theme]["label"],
                "variant": variant,
                "layout": layout,
                "status": "completed",
                "asset_id": saved["id"],
                "asset": saved,
                "cost_usd": 0.0,
                # Sprint 18 — surface the design quality on the response so
                # the FE dev panel can show "Excellent / Very Good / Needs
                # Attention" without an extra fetch.
                "quality_score": score_info.get("score"),
                "quality_label": score_info.get("label"),
            }
        )
        await update(progress=int(100 * (idx + 1) / total), variations=variations)

    successes = [v for v in variations if v.get("status") == "completed"]
    if not successes:
        await update(
            status="failed",
            error={
                "code": "all_variations_failed",
                "status": 500,
                "retryable": True,
                "retry_action": "retry",
                "user_message": (
                    f"All {variant_count} variations failed. "
                    f"Try again or pick a different theme."
                ),
                "technical": "all variations failed",
            },
        )
        return

    await update(status="completed", progress=100, variations=variations)
    logger.info(
        "[ai-designer] job=%s completed %d/%d variations", job_id, len(successes), total
    )

    if getattr(body, "auto_copy", False):
        try:
            label = THEME_STYLES[body.theme]["label"]
            copy_pack = await write_designer_copy(
                body.item_name,
                body.features,
                body.price,
                label,
                tone=body.tone,
                marketing_goal=body.marketing_goal,
                caption_length=body.caption_length,
            )
            await db.ai_design_jobs.update_one(
                {"id": job_id}, {"$set": {"copy_pack": copy_pack, "updated_at": now()}}
            )
            logger.info("[ai-designer] job=%s auto-copy completed", job_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("[ai-designer] job=%s auto-copy failed: %s", job_id, e)
            await db.ai_design_jobs.update_one(
                {"id": job_id},
                {"$set": {"copy_error": str(e)[:300], "updated_at": now()}},
            )


__all__ = ["run_design_job", "VARIATION_LABELS"]
