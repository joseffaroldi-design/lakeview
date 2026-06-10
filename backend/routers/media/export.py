"""Bulk social-format export — resize one source image to N social presets."""
from __future__ import annotations

import asyncio
import io
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Header, HTTPException
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, constr

from auth import verify_session
import storage as objstore
from .shared import SOCIAL_FORMATS, TMP_DIR, _fit_to, _hex_to_rgb, _now, db

router = APIRouter()


class SocialExportRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_asset_id: str
    formats: List[constr(min_length=2, max_length=40)] = Field(min_length=1, max_length=12)
    fit: constr(pattern=r"^(cover|contain)$") = "cover"
    bg_color: constr(pattern=r"^#?[0-9a-fA-F]{3,8}$") = "#FFFFFF"
    folder: Optional[constr(max_length=60)] = "Social Media"


@router.post("/export-social")
async def export_social(
    body: SocialExportRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Generate sized copies of one image for IG/FB/TikTok/GBP/Flyer."""
    await verify_session(authorization, session_token)
    from errors import StructuredError, report_failure
    src_asset = await db.media_assets.find_one({"id": body.source_asset_id}, {"_id": 0})
    if not src_asset or src_asset.get("kind") != "image":
        err = await report_failure(db, surface="social_export", err=StructuredError(
            code="asset_missing", status=404, retryable=False, retry_action="pick_assets",
            user_message="The source image was deleted or isn't an image. Pick a different one from the Asset Library.",
            technical=f"media_assets({body.source_asset_id}) not found or wrong kind",
        ), source_asset_id=body.source_asset_id)
        raise HTTPException(status_code=err.status, detail=err.to_payload())
    src_scratch = TMP_DIR / f"src_{uuid.uuid4().hex}.{src_asset['storage_path'].rsplit('.', 1)[-1]}"
    try:
        try:
            objstore.download_to_tmp(src_asset["storage_path"], src_scratch)
        except FileNotFoundError:
            err = await report_failure(db, surface="social_export", err=StructuredError(
                code="asset_missing", status=404, retryable=False, retry_action="pick_assets",
                user_message="The image file is missing in storage. Re-upload it and try again.",
                technical=f"object missing: {src_asset['storage_path']}",
            ), source_asset_id=body.source_asset_id)
            raise HTTPException(status_code=err.status, detail=err.to_payload())

        bg = _hex_to_rgb(body.bg_color, (255, 255, 255))
        unknown = [f for f in body.formats if f not in SOCIAL_FORMATS]
        if unknown:
            err = await report_failure(db, surface="social_export", err=StructuredError(
                code="prompt_invalid", status=400, retryable=False,
                user_message=f"These social format names aren't supported: {', '.join(unknown)}. Use the preset chips in the UI.",
                technical=f"unknown formats requested: {unknown}",
            ), formats=body.formats)
            raise HTTPException(status_code=err.status, detail=err.to_payload())

        saved: List[Dict[str, Any]] = []
        try:
            base = Image.open(src_scratch).convert("RGB")
            base.load()
        except Exception as e:  # noqa: BLE001
            err = await report_failure(db, surface="social_export", err=StructuredError(
                code="asset_invalid", status=422, retryable=False, retry_action="pick_assets",
                user_message="The source image is corrupted or in an unsupported format. Re-upload it or pick a different one.",
                technical=str(e)[:300],
            ), source_asset_id=body.source_asset_id)
            raise HTTPException(status_code=err.status, detail=err.to_payload())

        for fmt in body.formats:
            tw, th = SOCIAL_FORMATS[fmt]
            out = await asyncio.to_thread(_fit_to, base, tw, th, body.fit, bg)
            aid = str(uuid.uuid4())
            storage_path = objstore.make_path("exports", aid, "jpg")
            buf = io.BytesIO()
            out.save(buf, format="JPEG", quality=90, optimize=True)
            out_bytes = buf.getvalue()
            objstore.put_bytes(storage_path, out_bytes, "image/jpeg")
            src_name = src_asset.get("filename", "image").rsplit(".", 1)[0]
            doc = {
                "id": aid,
                "filename": f"{src_name}-{fmt}-{aid[:6]}.jpg",
                "kind": "image", "mime": "image/jpeg",
                "size_bytes": len(out_bytes),
                "width": tw, "height": th, "duration_seconds": None,
                "folder": body.folder or "Social Media",
                "tags": [fmt, "social-export", body.fit],
                "storage_path": storage_path,
                "is_favorite": False, "status": "active",
                "source": "social_export",
                "source_asset_id": body.source_asset_id,
                "uploaded_at": _now(), "updated_at": _now(),
            }
            await db.media_assets.insert_one(doc)
            saved.append({k: v for k, v in doc.items() if k != "_id"})
    finally:
        src_scratch.unlink(missing_ok=True)

    return {"assets": saved, "count": len(saved)}


# Sprint 12D: /social-formats endpoint deleted — formats are static; ship as JS constant on the frontend.
