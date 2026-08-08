"""Simple deterministic marketing flyer renderer.

This is the V1 target path for Photo-to-Flyer. It deliberately avoids agent
orchestration and AI-controlled layout. Inputs are explicit; templates are
explicit; rendering is deterministic for the same job/variant.
"""
from __future__ import annotations

import asyncio
import hashlib
import random
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import html_renderer
import storage as objstore
from config import db

TEMPLATES: List[Dict[str, str]] = [
    {"id": "cajun", "name": "Cajun", "description": "Warm Louisiana red and cream."},
    {"id": "cajun_blackened", "name": "Blackened Cajun", "description": "Darker Cajun treatment for grilled dishes."},
    {"id": "luxury", "name": "Luxury", "description": "Black and gold premium restaurant look."},
    {"id": "luxury_dark", "name": "Luxury Dark", "description": "High-contrast black and gold."},
    {"id": "seafood", "name": "Seafood", "description": "Clean Gulf seafood presentation."},
    {"id": "seafood_coastal", "name": "Coastal Seafood", "description": "Navy, sea-foam, and citrus."},
    {"id": "seafood_lagoon", "name": "Seafood Lagoon", "description": "Cool coastal treatment."},
]
TEMPLATE_IDS = {t["id"] for t in TEMPLATES}

PLATFORM_SIZES: Dict[str, Tuple[int, int]] = {
    "facebook_post": (1200, 630),
    "instagram_square": (1080, 1080),
    "instagram_story": (1080, 1920),
}


@dataclass(frozen=True)
class _RenderContext:
    job_nonce: str
    variant_index: int

    def rng(self, salt: str) -> random.Random:
        seed_material = f"{self.job_nonce}:{self.variant_index}:{salt}".encode("utf-8")
        seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
        return random.Random(seed)


def normalize_template(template_id: str) -> str:
    value = (template_id or "").strip().lower()
    if value in TEMPLATE_IDS:
        return value
    # Keep old saved theme ids usable without exposing the old theme registry.
    if "cajun" in value:
        return "cajun"
    if "seafood" in value or "lagoon" in value or "dock" in value:
        return "seafood_coastal"
    if "lux" in value:
        return "luxury"
    return "luxury"


def dimensions_for(platform: str) -> Tuple[int, int]:
    return PLATFORM_SIZES.get(platform or "", PLATFORM_SIZES["instagram_square"])


def build_copy(item_name: str, features: Iterable[str], price: str, cta: str) -> Dict[str, str]:
    feature_text = ", ".join([f.strip() for f in features if f and f.strip()][:3])
    price_text = f" — {price}" if price else ""
    detail = f" {feature_text}." if feature_text else ""
    action = (cta or "Order today").strip()
    fb = f"{item_name}{price_text}.{detail} {action} at Lakeview Burgers & Seafood."
    ig = f"{item_name}{price_text} 🍔{detail} {action}. #LakeviewNOLA #NewOrleansFood"
    return {"fb_post": fb.strip(), "ig_post": ig.strip()}


async def render_marketing_job(job_id: str) -> None:
    job = await db.marketing_flyer_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        return

    async def update(**fields: Any) -> None:
        await db.marketing_flyer_jobs.update_one({"id": job_id}, {"$set": fields})

    try:
        await update(status="processing", progress=10, current_step="loading_photo")
        asset = await db.media_assets.find_one(
            {"id": job["source_asset_id"], "status": "active"}, {"_id": 0}
        )
        if not asset or asset.get("kind") != "image":
            raise ValueError("Source image not found")

        image_bytes, _ = await asyncio.to_thread(objstore.get_bytes, asset["storage_path"])
        suffix = Path(asset.get("filename") or "photo.jpg").suffix or ".jpg"
        template_id = normalize_template(job.get("template_id") or "luxury")
        width, height = dimensions_for(job.get("platform") or "instagram_square")
        variant_count = max(1, min(int(job.get("variations") or 1), 3))
        variations: List[Dict[str, Any]] = []

        await update(progress=25, current_step="rendering")
        with tempfile.TemporaryDirectory(prefix="lakeview-flyer-") as td:
            photo_path = Path(td) / f"source{suffix}"
            photo_path.write_bytes(image_bytes)
            for idx in range(variant_count):
                ctx = _RenderContext(job_nonce=job_id, variant_index=idx)
                png = await asyncio.to_thread(
                    html_renderer.render_flyer,
                    template_id,
                    item_name=job.get("item_name") or "Featured Dish",
                    features=job.get("features") or [],
                    price=job.get("price") or "",
                    brand=job.get("brand") or "Lakeview Burgers & Seafood",
                    cta=job.get("cta") or "Order Now",
                    food_image_path=str(photo_path),
                    output_width=width,
                    output_height=height,
                    render_width=max(width, 1600),
                    render_height=max(height, 1600),
                    ctx=ctx,
                )
                asset_id = str(uuid.uuid4())
                storage_path = objstore.make_path("marketing_flyers", asset_id, "png")
                await asyncio.to_thread(objstore.put_bytes, storage_path, png, "image/png")
                now = job.get("created_at")
                await db.media_assets.insert_one({
                    "id": asset_id,
                    "filename": f"{job.get('item_name') or 'flyer'}-{idx + 1}.png",
                    "kind": "image",
                    "mime": "image/png",
                    "size_bytes": len(png),
                    "width": width,
                    "height": height,
                    "folder": "Marketing · Flyers",
                    "tags": ["flyer", "marketing-template", f"template:{template_id}"],
                    "storage_path": storage_path,
                    "is_favorite": False,
                    "status": "active",
                    "source": "marketing_template",
                    "theme": template_id,
                    "template_id": template_id,
                    "item_key": job.get("item_key"),
                    "item_name": job.get("item_name"),
                    "source_asset_id": job.get("source_asset_id"),
                    "uploaded_at": now,
                    "updated_at": now,
                })
                variations.append({
                    "variant": chr(65 + idx),
                    "asset_id": asset_id,
                    "template_id": template_id,
                    "headline": job.get("headline") or job.get("item_name") or "Featured Dish",
                    "quality_label": "Template",
                })
                await update(progress=25 + int(((idx + 1) / variant_count) * 60))

        copy_pack = build_copy(
            job.get("item_name") or "Featured Dish",
            job.get("features") or [],
            job.get("price") or "",
            job.get("cta") or "Order Now",
        )
        await update(
            status="completed",
            progress=100,
            current_step="done",
            variations=variations,
            copy_pack=copy_pack,
            template_id=template_id,
        )
    except Exception as exc:  # noqa: BLE001
        await update(
            status="failed",
            progress=100,
            current_step="failed",
            error={"code": "template_render_failed", "user_message": str(exc)[:240]},
        )
