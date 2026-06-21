"""AI Designer — themed marketing graphic variations via gpt-image-1 image-edit.

User uploads a food photo + item details (name, bullet features, price), picks 1–5
themes, and receives one redesigned marketing graphic per theme. The food photo is
passed as the reference image so the model keeps the actual dish intact.

Architecture mirrors `routers/media/ai_image.py`:
  - POST  /ai-designer/estimate                 — cost preview (no spend)
  - POST  /ai-designer/generate (202)           — enqueue background job
  - GET   /ai-designer/job/{id}                 — poll status
  - GET   /ai-designer/templates                — list saved winners
  - POST  /ai-designer/jobs/{id}/save-template  — mark a variation a "winner"
  - POST  /ai-designer/from-template/{tpl_id}   — re-run a saved theme on a new photo

State lives in `ai_design_jobs` and `ai_design_templates`. Generated graphics are
saved to `media_assets` so they show up in the Library like any other image.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Header, HTTPException
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, constr

from auth import verify_session
import billing
import storage as objstore
from routers.media.shared import _now, _spawn_ai_image_task, db

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/ai-designer", tags=["ai-designer"])


# ---------------------------------------------------------------- Themes

THEMES: Dict[str, Dict[str, str]] = {
    "luxury": {
        "label": "Luxury Black & Gold",
        "style": (
            "Premium restaurant advertisement. Deep matte black background with rich gold "
            "metallic accents, subtle gold filigree borders, and warm rim lighting on the food. "
            "Item name in elegant serif typography at the top in gold. Feature bullets along "
            "the right side in clean cream-colored sans-serif with small gold dot markers. "
            "Large bold gold price badge in the bottom-right corner with a thin gold ring around it."
        ),
    },
    "vintage": {
        "label": "Vintage Diner",
        "style": (
            "Classic American diner advertisement, 1950s aesthetic. Cream and burgundy color palette "
            "with checkerboard accents along the borders. Item name in a chunky retro slab-serif at the "
            "top. Feature bullets on the left in a handwritten-style script font. Big rounded badge for "
            "the price in the bottom-right with a starburst behind it."
        ),
    },
    "modern": {
        "label": "Modern Restaurant",
        "style": (
            "Clean modern restaurant marketing. Off-white background with subtle paper texture. "
            "Item name at the top in a sophisticated modern serif (think New York fine-dining menu). "
            "Feature bullets in a clean minimalist sans-serif on the right side with small line dividers. "
            "Bold dark navy circular price badge in the bottom-right. Generous whitespace."
        ),
    },
    "social": {
        "label": "Bright Social",
        "style": (
            "Eye-catching Instagram-ready food ad. Bright, saturated colors — warm orange and "
            "yellow gradient background with a soft halo behind the food. Item name in a bold "
            "playful display typeface at the top with a slight tilt. Feature bullets on the right "
            "with small emoji-style icons. Huge red price badge bottom-right with a slight rotation."
        ),
    },
    "cajun": {
        "label": "Cajun / Bayou",
        "style": (
            "Louisiana-inspired Cajun restaurant ad. Deep burnt-orange and forest-green palette "
            "with subtle bayou-leaf and paprika-dust textures around the edges. Item name at the "
            "top in a rustic hand-lettered serif. Feature bullets on the left with small pepper "
            "icons. Hand-painted-looking yellow price badge in the bottom-right corner with rough edges."
        ),
    },
}

THEME_IDS = list(THEMES.keys())


# ---------------------------------------------------------------- Schemas

class EstimateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    themes: List[constr(min_length=2, max_length=20)] = Field(default_factory=lambda: ["luxury", "modern"])
    quality: constr(pattern=r"^(low|medium|high)$") = "medium"


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_asset_id: constr(min_length=1, max_length=64)
    item_name: constr(min_length=1, max_length=120)
    features: List[constr(max_length=80)] = Field(default_factory=list)
    price: Optional[constr(max_length=40)] = None
    themes: List[constr(min_length=2, max_length=20)] = Field(default_factory=lambda: ["luxury", "modern"])
    quality: constr(pattern=r"^(low|medium|high)$") = "medium"
    auto_copy: bool = False


class SaveTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    variation_index: int = Field(ge=0, le=4)
    note: Optional[constr(max_length=200)] = None


# ---------------------------------------------------------------- Helpers

async def _get_active_asset(asset_id: str) -> Dict[str, Any]:
    asset = await db.media_assets.find_one({"id": asset_id, "status": "active"}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Source image not found")
    if asset.get("kind") != "image":
        raise HTTPException(status_code=400, detail="Source asset must be an image")
    return asset


def _normalize_themes(themes: List[str]) -> List[str]:
    valid = [t for t in (themes or []) if t in THEMES]
    # Dedupe while preserving order
    seen, out = set(), []
    for t in valid:
        if t not in seen:
            out.append(t)
            seen.add(t)
    if not out:
        raise HTTPException(status_code=400, detail=f"No valid themes. Pick from: {THEME_IDS}")
    if len(out) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 themes per run")
    return out


def _build_prompt(item_name: str, features: List[str], price: Optional[str], theme_id: str) -> str:
    theme = THEMES[theme_id]
    feat_lines = "\n".join(f"  • {f}" for f in features[:5]) if features else "  • (no features)"
    price_str = (price or "").strip()
    price_clause = f"Display the price '{price_str}' as a large badge in the bottom corner." if price_str else ""
    return (
        f"Redesign this image as a polished restaurant marketing graphic. "
        f"KEEP THE FOOD ITEM IN THE REFERENCE IMAGE EXACTLY AS SHOWN — do not change its colors, "
        f"ingredients, plating, or proportions. Only redesign the background, typography, and "
        f"decorative elements around the food.\n\n"
        f"STYLE: {theme['style']}\n\n"
        f"COMPOSITION:\n"
        f"  - Top: large item name '{item_name}'\n"
        f"  - Center: the original food photo as the hero (unchanged)\n"
        f"  - Side: feature bullets list:\n{feat_lines}\n"
        f"  - Bottom corner: {price_clause if price_clause else 'no price badge.'}\n\n"
        f"All text must be perfectly spelled and clearly readable on mobile. "
        f"This is a finished social-media-ready advertisement, not a menu."
    )


async def _call_image_edit(image_bytes: bytes, prompt: str, quality: str) -> bytes:
    """Single-image edit via litellm. Returns PNG bytes of the generated graphic.

    Uses the Emergent LLM proxy so cost is debited from EMERGENT_LLM_KEY balance.
    """
    import litellm

    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY not configured")

    # litellm.aimage_edit accepts a file-like or tuple (name, fileobj, mimetype)
    file_tuple = ("input.png", io.BytesIO(image_bytes), "image/png")

    resp = await litellm.aimage_edit(
        image=file_tuple,
        prompt=prompt,
        model="gpt-image-1",
        n=1,
        size="1024x1024",
        quality=quality,
        api_key=key,
        api_base="https://integrations.emergentagent.com/llm",
    )

    # ImageResponse.data is a list of objects with b64_json (preferred) or url.
    import base64
    data = getattr(resp, "data", None) or (resp.get("data") if isinstance(resp, dict) else None)
    if not data:
        raise RuntimeError("Provider returned no image data")
    item = data[0]
    b64 = getattr(item, "b64_json", None) or (item.get("b64_json") if isinstance(item, dict) else None)
    if b64:
        return base64.b64decode(b64)
    url = getattr(item, "url", None) or (item.get("url") if isinstance(item, dict) else None)
    if url:
        import requests
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        return r.content
    raise RuntimeError("Provider response had neither b64_json nor url")


async def _write_designer_copy(item_name: str, features: List[str], price: Optional[str], theme_label: str) -> Dict[str, Any]:
    """Generate the marketing copy pack for a finished design.

    Returns a dict with: fb_post, ig_post, gbp, sms, email{subject,body}, hashtags.
    Single structured LLM call to keep the tone consistent across channels.
    """
    from ai_engine.client import generate_structured

    feat_text = "\n".join(f"- {f}" for f in features) if features else "(none)"
    price_str = (price or "").strip() or "(omit)"
    sys_prompt = (
        "You are a New Orleans restaurant marketing copywriter for Lakeview "
        "Burgers & Seafood. Write warm, mouth-watering, locally flavored copy. "
        "Output ONLY a valid JSON object — no markdown."
    )
    usr_prompt = (
        f"Item: {item_name}\n"
        f"Features:\n{feat_text}\n"
        f"Price: {price_str}\n"
        f"Visual theme: {theme_label}\n\n"
        "Generate a complete marketing pack:\n"
        " - fb_post: 60-100 words, Facebook-style conversational, 1 emoji max, "
        "ends with a clear CTA on its own line.\n"
        " - ig_post: 30-50 words, punchy and Instagram-native, 2-3 emojis sprinkled "
        "naturally, ends with a hook question or CTA.\n"
        " - gbp: 80-180 words for Google Business Profile, leads with the offer, "
        "ends with a clear next step.\n"
        " - sms: under 140 chars, includes the item name + price, ends with CTA.\n"
        " - email_subject: 4-7 words, attention-grabbing, no clickbait punctuation.\n"
        " - email_body: 60-120 words, friendly, includes the features + price + CTA. "
        "Plain text only (no HTML).\n"
        " - hashtags: 8-12 relevant hashtags as strings (no '#' prefix)."
    )
    schema = (
        '{"fb_post":"string","ig_post":"string","gbp":"string","sms":"string",'
        '"email_subject":"string","email_body":"string","hashtags":["string"]}'
    )
    wrapped = await generate_structured(db, system_prompt=sys_prompt, user_prompt=usr_prompt, schema_hint=schema)
    out = wrapped.get("data") or {}
    return {
        "fb_post": (out.get("fb_post") or "").strip()[:2000],
        "ig_post": (out.get("ig_post") or "").strip()[:2000],
        "gbp": (out.get("gbp") or "").strip()[:1500],
        "sms": (out.get("sms") or "").strip()[:160],
        "email": {
            "subject": (out.get("email_subject") or "").strip()[:120],
            "body": (out.get("email_body") or "").strip()[:2000],
        },
        "hashtags": [h.lstrip("#").strip() for h in (out.get("hashtags") or [])][:15],
        "generated_at": _now(),
    }


async def _save_design_asset(img_bytes: bytes, item_name: str, theme_id: str, ai_prompt: str) -> Dict[str, Any]:
    """Persist a generated design to media_assets so it shows in the Library."""
    aid = str(uuid.uuid4())
    storage_path = objstore.make_path("ai_designs", aid, "png")
    objstore.put_bytes(storage_path, img_bytes, "image/png")
    try:
        with Image.open(io.BytesIO(img_bytes)) as im:
            w, h = im.size
    except Exception:  # noqa: BLE001
        w = h = None
    doc = {
        "id": aid,
        "filename": f"design-{theme_id}-{item_name[:30].replace(' ', '-').lower()}-{aid[:6]}.png",
        "kind": "image",
        "mime": "image/png",
        "size_bytes": len(img_bytes),
        "width": w, "height": h, "duration_seconds": None,
        "folder": "AI Designer",
        "tags": ["ai-designer", f"theme:{theme_id}"],
        "storage_path": storage_path,
        "is_favorite": False, "status": "active",
        "source": "ai_designer",
        "ai_prompt": ai_prompt,
        "uploaded_at": _now(), "updated_at": _now(),
    }
    await db.media_assets.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


# ---------------------------------------------------------------- Background worker

async def _run_design_job(job_id: str, body: GenerateRequest, themes: List[str]) -> None:
    async def update(**fields: Any) -> None:
        fields["updated_at"] = _now()
        await db.ai_design_jobs.update_one({"id": job_id}, {"$set": fields})

    async def fail(user_msg: str, technical: str = "") -> None:
        await update(status="failed", progress=0, error={
            "code": "generation_failed",
            "status": 500,
            "retryable": True,
            "retry_action": "retry",
            "user_message": user_msg,
            "technical": technical,
        })

    try:
        asset = await _get_active_asset(body.source_asset_id)
    except HTTPException as e:
        await fail(e.detail if isinstance(e.detail, str) else "Source asset not found")
        return

    try:
        src_bytes, _ = objstore.get_bytes(asset["storage_path"])
    except Exception as e:  # noqa: BLE001
        await fail("Couldn't load your source photo from storage. Try again.", str(e))
        return

    # gpt-image-1 edit expects PNG/WebP <4 MB, square. Force-square-pad + convert to PNG.
    try:
        prepared = _prepare_for_edit(src_bytes)
    except Exception as e:  # noqa: BLE001
        await fail("Couldn't read your source photo. Try a different image.", str(e))
        return

    await update(status="processing", progress=5)

    variations: List[Dict[str, Any]] = []
    total = len(themes)
    for idx, theme_id in enumerate(themes):
        prompt = _build_prompt(body.item_name, body.features, body.price, theme_id)
        try:
            out_bytes = await asyncio.wait_for(
                _call_image_edit(prepared, prompt, body.quality),
                timeout=180.0,
            )
        except asyncio.TimeoutError:
            variations.append({"theme": theme_id, "status": "failed", "error": "timeout"})
            logger.warning("[ai-designer] job=%s theme=%s timeout", job_id, theme_id)
            continue
        except Exception as e:  # noqa: BLE001
            from errors import classify_llm_error
            err = classify_llm_error(e, surface="ai_designer")
            variations.append({
                "theme": theme_id, "status": "failed",
                "error": err.user_message or "Generation failed",
                "error_code": err.code,
            })
            logger.exception("[ai-designer] job=%s theme=%s failed code=%s", job_id, theme_id, err.code)
            # If budget exhausted, abort the whole job — no point continuing.
            if err.code in ("budget_exhausted", "key_invalid", "key_missing"):
                await update(progress=int(100 * (idx + 1) / total), variations=variations)
                await update(status="failed", error=err.to_payload())
                return
            continue

        # Record cost (per successful image)
        cost = billing.estimate_image_cost("gpt-image-1", body.quality, count=1)
        await billing.record_usage(
            db,
            surface="ai_designer",
            model="gpt-image-1",
            operation=f"image_edit:{theme_id}",
            cost_usd=cost,
            image_count=1,
            pipeline_id=job_id,
        )

        saved = await _save_design_asset(out_bytes, body.item_name, theme_id, prompt)
        variations.append({
            "theme": theme_id,
            "theme_label": THEMES[theme_id]["label"],
            "status": "completed",
            "asset_id": saved["id"],
            "asset": saved,
            "prompt": prompt,
            "cost_usd": round(cost, 4),
        })
        await update(progress=int(100 * (idx + 1) / total), variations=variations)

    successes = [v for v in variations if v.get("status") == "completed"]
    if not successes:
        await update(status="failed", error={
            "code": "all_variations_failed",
            "status": 500,
            "retryable": True,
            "retry_action": "retry",
            "user_message": "None of the design variations completed. Try fewer themes or a different photo.",
            "technical": "all variations failed",
        })
        return

    await update(status="completed", progress=100, variations=variations)
    logger.info("[ai-designer] job=%s completed %d/%d variations", job_id, len(successes), total)

    # Optional auto-copy: kick off marketing copy generation immediately. Failures here
    # don't fail the design job — owner can retry from the Review screen.
    if body.auto_copy:
        try:
            primary_theme = THEMES.get(successes[0]["theme"], {}).get("label", successes[0]["theme"])
            copy_pack = await _write_designer_copy(body.item_name, body.features, body.price, primary_theme)
            await db.ai_design_jobs.update_one(
                {"id": job_id},
                {"$set": {"copy_pack": copy_pack, "updated_at": _now()}},
            )
            logger.info("[ai-designer] job=%s auto-copy completed", job_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("[ai-designer] job=%s auto-copy failed: %s", job_id, e)
            await db.ai_design_jobs.update_one(
                {"id": job_id},
                {"$set": {"copy_error": str(e)[:300], "updated_at": _now()}},
            )


def _prepare_for_edit(src_bytes: bytes) -> bytes:
    """Pad the source image to a square 1024×1024 PNG so gpt-image-1's edit endpoint
    accepts it. Keep the food centered; pad with the average edge color so the model
    has a neutral canvas to redesign around.
    """
    with Image.open(io.BytesIO(src_bytes)) as im:
        im = im.convert("RGB")
        max_side = 1024
        # Scale so longest side = 1024
        scale = min(max_side / im.width, max_side / im.height)
        new_w = max(1, int(im.width * scale))
        new_h = max(1, int(im.height * scale))
        im = im.resize((new_w, new_h), Image.LANCZOS)
        # Sample edge average for pad color
        try:
            edge_pixels = list(im.crop((0, 0, im.width, 1)).getdata())
            r = sum(p[0] for p in edge_pixels) // len(edge_pixels)
            g = sum(p[1] for p in edge_pixels) // len(edge_pixels)
            b = sum(p[2] for p in edge_pixels) // len(edge_pixels)
            pad = (r, g, b)
        except Exception:  # noqa: BLE001
            pad = (245, 240, 230)
        canvas = Image.new("RGB", (max_side, max_side), pad)
        canvas.paste(im, ((max_side - new_w) // 2, (max_side - new_h) // 2))
        buf = io.BytesIO()
        canvas.save(buf, "PNG", optimize=True)
        return buf.getvalue()


# ---------------------------------------------------------------- Routes

@router.get("/themes")
async def list_themes(authorization: str = Header(None), session_token: str = Cookie(None)):
    """Return the catalog of theme presets — id, label, and short description."""
    await verify_session(authorization, session_token)
    return {
        "themes": [
            {"id": tid, "label": t["label"], "style": t["style"][:140] + ("…" if len(t["style"]) > 140 else "")}
            for tid, t in THEMES.items()
        ]
    }


@router.post("/estimate")
async def estimate(
    body: EstimateRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Cost preview — does not spend or call the LLM."""
    await verify_session(authorization, session_token)
    themes = _normalize_themes(body.themes)
    per_image = billing.estimate_image_cost("gpt-image-1", body.quality, count=1)
    total = per_image * len(themes)
    status = await billing.get_status(db)
    return {
        "themes": themes,
        "count": len(themes),
        "quality": body.quality,
        "per_image_cost_usd": round(per_image, 4),
        "total_cost_usd": round(total, 4),
        "current_balance_usd": status["current_balance_usd"],
        "would_exceed_balance": total > status["current_balance_usd"],
        "tier": status["tier"],
    }


@router.post("/generate", status_code=202)
async def enqueue_generate(
    body: GenerateRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Enqueue an AI design job. Returns 202 + job_id. Frontend polls /job/{id}."""
    await verify_session(authorization, session_token)

    if not os.environ.get("EMERGENT_LLM_KEY"):
        raise HTTPException(status_code=500, detail={
            "code": "key_missing", "status": 500, "retryable": False,
            "user_message": "AI image generation isn't configured on this server. Ask your admin to set EMERGENT_LLM_KEY.",
            "technical": "EMERGENT_LLM_KEY env var is empty",
        })

    themes = _normalize_themes(body.themes)
    await _get_active_asset(body.source_asset_id)  # validate up-front

    # Pre-flight budget check
    total_cost = billing.estimate_image_cost("gpt-image-1", body.quality, count=1) * len(themes)
    can, status = await billing.check_can_afford(db, total_cost, surface="ai_designer")
    if not can:
        raise HTTPException(status_code=402, detail={
            "code": "budget_exhausted",
            "status": 402,
            "retryable": False,
            "user_message": (
                f"Not enough virtual balance for this run. Need ${total_cost:.2f}, "
                f"balance ${status['current_balance_usd']:.2f}. Top up Emergent and tap 'I topped up' on the Home billing card."
            ),
            "technical": f"budget_check_failed required={total_cost} balance={status['current_balance_usd']}",
        })

    job_id = str(uuid.uuid4())
    now = _now()
    await db.ai_design_jobs.insert_one({
        "id": job_id,
        "status": "pending",
        "source_asset_id": body.source_asset_id,
        "item_name": body.item_name,
        "features": body.features,
        "price": body.price,
        "themes": themes,
        "quality": body.quality,
        "progress": 0,
        "variations": [],
        "estimated_cost_usd": round(total_cost, 4),
        "created_at": now,
        "updated_at": now,
        "error": None,
    })
    # Build a fresh request body that includes the normalized themes
    body_normalized = GenerateRequest(**{**body.model_dump(), "themes": themes})
    _spawn_ai_image_task(_run_design_job(job_id, body_normalized, themes))
    return {"job_id": job_id, "status": "pending", "estimated_cost_usd": round(total_cost, 4)}


@router.get("/job/{job_id}")
async def get_job(
    job_id: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    await verify_session(authorization, session_token)
    job = await db.ai_design_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/templates")
async def list_templates(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """List saved 'winner' templates the owner can reuse on new photos."""
    await verify_session(authorization, session_token)
    cur = db.ai_design_templates.find({}, {"_id": 0}).sort("created_at", -1).limit(20)
    items = await cur.to_list(length=20)
    return {"templates": items}


@router.post("/jobs/{job_id}/save-template")
async def save_template(
    job_id: str,
    body: SaveTemplateRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Mark one variation from a completed job as a reusable template."""
    await verify_session(authorization, session_token)
    job = await db.ai_design_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    variations = job.get("variations") or []
    if body.variation_index >= len(variations):
        raise HTTPException(status_code=400, detail="variation_index out of range")
    v = variations[body.variation_index]
    if v.get("status") != "completed":
        raise HTTPException(status_code=400, detail="That variation didn't complete")

    tpl = {
        "id": str(uuid.uuid4()),
        "theme": v["theme"],
        "theme_label": v.get("theme_label") or THEMES.get(v["theme"], {}).get("label", v["theme"]),
        "item_name": job["item_name"],
        "features": job.get("features") or [],
        "price": job.get("price"),
        "quality": job.get("quality", "medium"),
        "source_job_id": job_id,
        "preview_asset_id": v["asset_id"],
        "note": body.note,
        "created_at": _now(),
        "last_used_at": _now(),
        "uses": 1,
    }
    await db.ai_design_templates.insert_one(tpl)
    return {k: val for k, val in tpl.items() if k != "_id"}


@router.post("/from-template/{template_id}", status_code=202)
async def generate_from_template(
    template_id: str,
    source_asset_id: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Re-run a saved theme on a fresh photo. Keeps the template's name/features/price.

    Pass `?source_asset_id=...` query param.
    """
    await verify_session(authorization, session_token)
    tpl = await db.ai_design_templates.find_one({"id": template_id}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    body = GenerateRequest(
        source_asset_id=source_asset_id,
        item_name=tpl["item_name"],
        features=tpl.get("features") or [],
        price=tpl.get("price"),
        themes=[tpl["theme"]],
        quality=tpl.get("quality", "medium"),
    )
    resp = await enqueue_generate(body, authorization=authorization, session_token=session_token)
    # Bump template stats
    await db.ai_design_templates.update_one(
        {"id": template_id},
        {"$set": {"last_used_at": _now()}, "$inc": {"uses": 1}},
    )
    return resp


@router.get("/jobs/{job_id}/copy")
async def get_copy(
    job_id: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Return the marketing copy pack saved alongside a finished design (if any)."""
    await verify_session(authorization, session_token)
    job = await db.ai_design_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "has_copy": bool(job.get("copy_pack")),
        "copy_pack": job.get("copy_pack"),
        "copy_error": job.get("copy_error"),
    }


@router.post("/jobs/{job_id}/copy")
async def write_copy(
    job_id: str,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Generate (or re-generate) the marketing copy pack for a completed design job.

    Reuses the job's item_name / features / price / first-completed-theme so the owner
    doesn't have to fill out another form. Idempotent: if a copy_pack already exists,
    returns it unchanged unless `?force=1` is passed.
    """
    await verify_session(authorization, session_token)
    job = await db.ai_design_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job hasn't completed yet")

    if job.get("copy_pack"):
        return {"copy_pack": job["copy_pack"], "regenerated": False}

    successes = [v for v in (job.get("variations") or []) if v.get("status") == "completed"]
    if not successes:
        raise HTTPException(status_code=400, detail="No completed designs to write copy for")

    primary_theme = THEMES.get(successes[0]["theme"], {}).get("label", successes[0]["theme"])
    try:
        copy_pack = await _write_designer_copy(
            job["item_name"], job.get("features") or [], job.get("price"), primary_theme,
        )
    except Exception as e:  # noqa: BLE001
        from errors import classify_llm_error
        err = classify_llm_error(e, surface="ai_designer")
        await db.ai_design_jobs.update_one(
            {"id": job_id}, {"$set": {"copy_error": err.user_message or str(e)[:300], "updated_at": _now()}},
        )
        raise HTTPException(status_code=err.status or 500, detail=err.to_payload())

    await db.ai_design_jobs.update_one(
        {"id": job_id},
        {"$set": {"copy_pack": copy_pack, "copy_error": None, "updated_at": _now()}},
    )
    return {"copy_pack": copy_pack, "regenerated": True}


async def cleanup_orphan_ai_design_jobs() -> None:
    """Mark in-flight jobs as failed at startup (their asyncio tasks died with the prev process)."""
    orphan_err = {
        "code": "unknown", "status": 500, "retryable": True, "retry_action": "retry",
        "user_message": "This design run was interrupted by a server restart. Tap Try again.",
        "technical": "backend restarted with job in pending/processing state",
    }
    r = await db.ai_design_jobs.update_many(
        {"status": {"$in": ["pending", "processing"]}},
        {"$set": {"status": "failed", "error": orphan_err, "progress": 0, "updated_at": _now()}},
    )
    if r.modified_count > 0:
        logger.info("[ai-designer] Marked %d orphan job(s) as failed at startup", r.modified_count)
