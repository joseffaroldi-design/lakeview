"""Image editor — crop/resize/rotate/flip/adjustments/text+logo overlay/bg-removal."""
from __future__ import annotations

import asyncio
import io
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Cookie, Header, HTTPException
from PIL import Image, ImageDraw, ImageEnhance, ImageOps
from pydantic import BaseModel, ConfigDict, Field, constr

from auth import verify_session
import storage as objstore
from .shared import TMP_DIR, _hex_to_rgb, _load_font, _now, db

router = APIRouter()


class CropBox(BaseModel):
    model_config = ConfigDict(extra="ignore")
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(gt=0)
    h: int = Field(gt=0)


class TextOverlay(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: constr(min_length=1, max_length=200)
    x_pct: float = Field(default=0.5, ge=0.0, le=1.0)  # 0..1, anchor center
    y_pct: float = Field(default=0.85, ge=0.0, le=1.0)
    size_pct: float = Field(default=0.06, ge=0.02, le=0.25)  # of image height
    color: constr(pattern=r"^#?[0-9a-fA-F]{3,8}$") = "#FFFFFF"
    background: Optional[constr(pattern=r"^#?[0-9a-fA-F]{3,8}$")] = None  # box bg
    background_opacity: float = Field(default=0.55, ge=0.0, le=1.0)
    align: constr(pattern=r"^(left|center|right)$") = "center"


class LogoOverlay(BaseModel):
    model_config = ConfigDict(extra="ignore")
    logo_asset_id: str
    x_pct: float = Field(default=0.05, ge=0.0, le=1.0)  # anchor: top-left of logo
    y_pct: float = Field(default=0.05, ge=0.0, le=1.0)
    width_pct: float = Field(default=0.18, ge=0.05, le=0.6)  # of image width
    opacity: float = Field(default=1.0, ge=0.2, le=1.0)


class EditImageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_asset_id: str
    crop: Optional[CropBox] = None
    resize_w: Optional[int] = Field(default=None, gt=0, le=5000)
    resize_h: Optional[int] = Field(default=None, gt=0, le=5000)
    rotate: int = Field(default=0)  # 0/90/180/270
    flip_horizontal: bool = False
    brightness: float = Field(default=1.0, ge=0.3, le=2.0)
    contrast: float = Field(default=1.0, ge=0.3, le=2.0)
    saturation: float = Field(default=1.0, ge=0.0, le=2.0)
    sharpness: float = Field(default=1.0, ge=0.0, le=3.0)
    remove_background: bool = False
    bg_color: Optional[constr(pattern=r"^#?[0-9a-fA-F]{3,8}$")] = None  # fill after bg removal
    text_overlay: Optional[TextOverlay] = None
    logo_overlay: Optional[LogoOverlay] = None
    folder: Optional[constr(max_length=60)] = None
    filename: Optional[constr(max_length=160)] = None
    tags: Optional[List[str]] = None


def _apply_edits(img: Image.Image, body: EditImageRequest, logo_path: Optional[Path]) -> Image.Image:
    """Pure-PIL pipeline. Returns RGB(A) image. Background removal handled by caller."""
    # Crop
    if body.crop:
        c = body.crop
        x2 = min(img.width, c.x + c.w)
        y2 = min(img.height, c.y + c.h)
        img = img.crop((c.x, c.y, x2, y2))

    # Rotate (0/90/180/270)
    if body.rotate in (90, 180, 270):
        img = img.rotate(-body.rotate, expand=True)

    # Flip
    if body.flip_horizontal:
        img = ImageOps.mirror(img)

    # Resize
    if body.resize_w or body.resize_h:
        target_w = body.resize_w or int(img.width * (body.resize_h / img.height))
        target_h = body.resize_h or int(img.height * (body.resize_w / img.width))
        img = img.resize((target_w, target_h), Image.LANCZOS)

    # Adjustments — must be RGB for ImageEnhance.Color
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    if body.brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(body.brightness)
    if body.contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(body.contrast)
    if body.saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(body.saturation)
    if body.sharpness != 1.0:
        img = ImageEnhance.Sharpness(img).enhance(body.sharpness)

    # Logo overlay
    if body.logo_overlay and logo_path and logo_path.exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            target_w = int(img.width * body.logo_overlay.width_pct)
            ratio = target_w / max(1, logo.width)
            target_h = max(1, int(logo.height * ratio))
            logo = logo.resize((target_w, target_h), Image.LANCZOS)
            if body.logo_overlay.opacity < 1.0:
                alpha = logo.split()[3].point(lambda p: int(p * body.logo_overlay.opacity))
                logo.putalpha(alpha)
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            x = int(img.width * body.logo_overlay.x_pct)
            y = int(img.height * body.logo_overlay.y_pct)
            img.paste(logo, (x, y), logo)
        except Exception:  # noqa: BLE001
            pass

    # Text overlay
    if body.text_overlay:
        t = body.text_overlay
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font_size = max(10, int(img.height * t.size_pct))
        font = _load_font(font_size)
        # Measure
        try:
            bbox = draw.textbbox((0, 0), t.text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:  # noqa: BLE001
            tw, th = font_size * len(t.text) // 2, font_size
        cx = int(img.width * t.x_pct)
        cy = int(img.height * t.y_pct)
        if t.align == "left":
            tx = cx
        elif t.align == "right":
            tx = cx - tw
        else:
            tx = cx - tw // 2
        ty = cy - th // 2
        # Box background
        if t.background:
            pad = max(8, font_size // 4)
            r, g, b = _hex_to_rgb(t.background, (0, 0, 0))
            a = int(255 * t.background_opacity)
            draw.rectangle([tx - pad, ty - pad, tx + tw + pad, ty + th + pad], fill=(r, g, b, a))
        # Text — black stroke for readability
        fill = _hex_to_rgb(t.color, (255, 255, 255))
        try:
            draw.text((tx, ty), t.text, font=font, fill=fill + (255,),
                      stroke_width=max(1, font_size // 24), stroke_fill=(0, 0, 0, 220))
        except TypeError:  # very old PIL
            draw.text((tx, ty), t.text, font=font, fill=fill + (255,))
        img = Image.alpha_composite(img, overlay)

    return img


def _remove_background(src: Path) -> bytes:
    """Run rembg in a thread (CPU bound, downloads model on first call)."""
    from rembg import remove
    with open(src, "rb") as f:
        return remove(f.read())


@router.post("/edit")
async def edit_image(
    body: EditImageRequest,
    authorization: str = Header(None),
    session_token: str = Cookie(None),
):
    """Apply crop/rotate/resize/adjustments/text/logo/background-removal. Saves a NEW asset."""
    await verify_session(authorization, session_token)
    from errors import StructuredError, report_failure
    src_asset = await db.media_assets.find_one({"id": body.source_asset_id}, {"_id": 0})
    if not src_asset or src_asset.get("kind") != "image":
        err = await report_failure(db, surface="image_edit", err=StructuredError(
            code="asset_missing", status=404, retryable=False, retry_action="pick_assets",
            user_message="The image you tried to edit was deleted or isn't an image. Pick a different source from the Asset Library.",
            technical=f"media_assets({body.source_asset_id}) not found or wrong kind",
        ), source_asset_id=body.source_asset_id)
        raise HTTPException(status_code=err.status, detail=err.to_payload())
    # Download source to /tmp scratch for PIL/rembg
    src_scratch = TMP_DIR / f"src_{uuid.uuid4().hex}.{src_asset['storage_path'].rsplit('.', 1)[-1]}"
    try:
        objstore.download_to_tmp(src_asset["storage_path"], src_scratch)
    except FileNotFoundError:
        err = await report_failure(db, surface="image_edit", err=StructuredError(
            code="asset_missing", status=404, retryable=False, retry_action="pick_assets",
            user_message="The image file is missing in storage. Re-upload it and try again.",
            technical=f"object missing: {src_asset['storage_path']}",
        ), source_asset_id=body.source_asset_id)
        raise HTTPException(status_code=err.status, detail=err.to_payload())

    logo_scratch: Optional[Path] = None
    if body.logo_overlay:
        logo_asset = await db.media_assets.find_one({"id": body.logo_overlay.logo_asset_id}, {"_id": 0})
        if logo_asset and logo_asset.get("kind") == "image":
            logo_scratch = TMP_DIR / f"logo_{uuid.uuid4().hex}.{logo_asset['storage_path'].rsplit('.', 1)[-1]}"
            try:
                objstore.download_to_tmp(logo_asset["storage_path"], logo_scratch)
            except FileNotFoundError:
                logo_scratch = None

    try:
        # Background removal first (separate thread — slow)
        if body.remove_background:
            try:
                png_bytes = await asyncio.to_thread(_remove_background, src_scratch)
                base = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
            except Exception as e:  # noqa: BLE001
                err = await report_failure(db, surface="image_edit", err=StructuredError(
                    code="provider_unavailable", status=502, retryable=True, retry_action="retry",
                    user_message="Background removal failed. The AI model may still be downloading — wait 30 seconds and try again. (First-ever run can take 60s.)",
                    technical=str(e)[:400],
                ), source_asset_id=body.source_asset_id)
                raise HTTPException(status_code=err.status, detail=err.to_payload())
            if body.bg_color:
                bg = Image.new("RGBA", base.size, _hex_to_rgb(body.bg_color, (255, 255, 255)) + (255,))
                base = Image.alpha_composite(bg, base)
        else:
            base = Image.open(src_scratch)
            base.load()

        edited = None
        try:
            edited = await asyncio.to_thread(_apply_edits, base, body, logo_scratch)
        except Exception as e:  # noqa: BLE001
            err = await report_failure(db, surface="image_edit", err=StructuredError(
                code="asset_invalid", status=500, retryable=True, retry_action="retry",
                user_message="The image editor crashed while applying changes. Try simpler adjustments (smaller crop, less text) or use a different source image.",
                technical=str(e)[:400],
            ), source_asset_id=body.source_asset_id)
            raise HTTPException(status_code=err.status, detail=err.to_payload())
        finally:
            if edited is not None and base is not edited:
                try:
                    base.close()
                except Exception:  # noqa: BLE001
                    pass

        # Save — PNG if alpha channel present, otherwise JPEG
        has_alpha = edited.mode == "RGBA" and edited.getextrema()[3][0] < 255
        new_id = str(uuid.uuid4())
        if has_alpha or body.remove_background:
            ext = "png"
            save_kwargs = {"format": "PNG", "optimize": True}
            mime = "image/png"
        else:
            if edited.mode == "RGBA":
                edited = edited.convert("RGB")
            ext = "jpg"
            save_kwargs = {"format": "JPEG", "quality": 90, "optimize": True}
            mime = "image/jpeg"
        storage_path = objstore.make_path("edits", new_id, ext)
        buf = io.BytesIO()
        edited.save(buf, **save_kwargs)
        out_bytes = buf.getvalue()
        objstore.put_bytes(storage_path, out_bytes, mime)

        src_name = src_asset.get("filename", "edited.png").rsplit(".", 1)[0]
        final_filename = body.filename or f"{src_name}-edited-{new_id[:6]}.{ext}"
        tags = (body.tags or []) + ["edited"]
        if body.remove_background:
            tags.append("bg-removed")

        doc = {
            "id": new_id,
            "filename": final_filename,
            "kind": "image",
            "mime": mime,
            "size_bytes": len(out_bytes),
            "width": edited.width, "height": edited.height, "duration_seconds": None,
            "folder": body.folder or src_asset.get("folder", "Custom"),
            "tags": tags,
            "storage_path": storage_path,
            "is_favorite": False, "status": "active",
            "source": "image_edit",
            "source_asset_id": body.source_asset_id,
            "edit_params": body.model_dump(exclude_none=True, exclude={"source_asset_id"}),
            "uploaded_at": _now(), "updated_at": _now(),
        }
        await db.media_assets.insert_one(doc)
        return {k: v for k, v in doc.items() if k != "_id"}
    finally:
        src_scratch.unlink(missing_ok=True)
        if logo_scratch:
            logo_scratch.unlink(missing_ok=True)
