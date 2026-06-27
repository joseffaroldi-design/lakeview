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

import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import HTTPException

from ai_designer.copy_generation import write_designer_copy
from ai_designer.registries.layouts import LAYOUTS
from ai_designer.registries.themes import THEME_STYLES

logger = logging.getLogger("uvicorn.error")

VARIATION_LABELS = ["A", "B", "C", "D", "E"]  # Support up to 5 variants


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
        food_bytes, _ = objstore.get_bytes(asset["storage_path"])
    except HTTPException as e:
        await fail(e.detail if isinstance(e.detail, str) else "Source asset not found")
        return
    except Exception as e:  # noqa: BLE001
        await fail("Couldn't load your source photo from storage. Try again.", str(e))
        return

    # Pre-process food cutout ONCE — same cutout used in all variants.
    # Sprint 15B.3: only run rembg if the user explicitly opted in.
    try:
        food_rgba = prepare_food_cutout(
            food_bytes,
            target_max=int(canvas_max * 0.65),
            use_rembg=bool(getattr(body, "remove_background", False)),
        )
    except Exception as e:  # noqa: BLE001
        await fail("Couldn't read your source photo. Try a different image.", str(e))
        return

    await update(status="processing", progress=5)

    variations: List[Dict[str, Any]] = []
    variant_count = min(5, max(1, body.variations))  # Clamp to 1-5
    total = variant_count
    for idx in range(variant_count):
        variant = VARIATION_LABELS[idx]
        layout = LAYOUTS[idx % len(LAYOUTS)]  # Cycle through layouts if more than 3
        try:
            bg_bytes = pil_background(body.theme, idx)
            graphic_bytes, score_info = compose_design(
                bg_bytes,
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
            )
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
