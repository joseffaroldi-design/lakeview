"""Shared utilities for the media router subpackage.

All code in this module is intentionally framework-agnostic (no `APIRouter`
declarations) and reused by every submodule under `routers/media/`.
"""
from __future__ import annotations

import asyncio
import io
import os
import shutil
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image, ImageFont

import storage as objstore

# ---------------------------------------------------------------- DB

mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]

# /tmp scratch space — only for ffmpeg pipelines that require filesystem inputs.
# All canonical media is stored in Emergent Object Storage.
TMP_DIR = Path(tempfile.gettempdir()) / "media_scratch"
TMP_DIR.mkdir(parents=True, exist_ok=True)

# Sanity check at import — warn loudly if ffmpeg is missing so operators see it in logs.
if shutil.which("ffmpeg") is None:
    import logging
    logging.getLogger("uvicorn.error").warning(
        "[media] ffmpeg binary not found on PATH — video rendering and video thumbnails will fail. "
        "Install with: apt-get install -y ffmpeg"
    )

ALLOWED_IMAGE = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_VIDEO = {"video/mp4", "video/quicktime", "video/webm"}
MAX_IMAGE_BYTES = 15 * 1024 * 1024     # 15 MB
MAX_VIDEO_BYTES = 100 * 1024 * 1024    # 100 MB
DEFAULT_FOLDERS = ["Menu Items", "Promotions", "Catering", "Events", "Logos", "Social Media", "Custom"]


SOCIAL_FORMATS: Dict[str, tuple] = {
    "ig_post_1_1":      (1080, 1080),
    "ig_portrait_4_5":  (1080, 1350),
    "ig_reel_9_16":     (1080, 1920),
    "fb_post":          (1200, 630),
    "fb_story":         (1080, 1920),
    "tiktok_9_16":      (1080, 1920),
    "gbp_image":        (1200, 900),
    "flyer_8_5_11":     (2550, 3300),
}

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ext_from_mime(mime: str) -> str:
    return {
        "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp",
        "video/mp4": "mp4", "video/quicktime": "mov", "video/webm": "webm",
    }.get(mime, "bin")


@contextmanager
def _local_copy(storage_path: str, suffix: str = ""):
    """Yield a local tmp file path for an asset. Downloads from object storage
    or copies from legacy local disk. Cleans up on exit."""
    tmp = TMP_DIR / f"{uuid.uuid4().hex}{suffix or '.' + storage_path.rsplit('.', 1)[-1] if '.' in storage_path else ''}"
    try:
        objstore.download_to_tmp(storage_path, tmp)
        yield tmp
    finally:
        tmp.unlink(missing_ok=True)


async def _ensure_thumb_bytes(asset: Dict[str, Any]) -> Optional[bytes]:
    """Return JPEG thumbnail bytes for an asset. Generates lazily from the
    canonical asset bytes and caches in object storage at
    `lakeview/thumbs/{asset_id}.jpg` so subsequent fetches are O(1)."""
    thumb_path = objstore.make_path("thumbs", asset["id"], "jpg")
    # Cached?
    # Production hotfix — objstore.get_bytes / put_bytes are blocking
    # (synchronous requests calls). Run them in worker threads so a
    # thumbnail fetch can't starve the event loop.
    try:
        data, _ = await asyncio.to_thread(objstore.get_bytes, thumb_path)
        return data
    except FileNotFoundError:
        pass
    except Exception:  # noqa: BLE001
        pass
    # Generate
    try:
        src_bytes, _ = await asyncio.to_thread(objstore.get_bytes, asset["storage_path"])
    except FileNotFoundError:
        return None
    out = io.BytesIO()
    try:
        if asset["kind"] == "image":
            with Image.open(io.BytesIO(src_bytes)) as img:
                img = img.convert("RGB")
                w, h = img.size
                if w > 360:
                    h = int(h * 360 / w)
                    w = 360
                img.thumbnail((w, h), Image.LANCZOS)
                img.save(out, "JPEG", quality=82, optimize=True)
        else:  # video — extract frame at 1s via ffmpeg
            with _local_copy(asset["storage_path"]) as src_tmp:
                thumb_tmp = TMP_DIR / f"{uuid.uuid4().hex}.jpg"
                try:
                    subprocess.run(
                        ["ffmpeg", "-y", "-loglevel", "error", "-ss", "1",
                         "-i", str(src_tmp), "-vframes", "1", "-vf", "scale=360:-2",
                         str(thumb_tmp)],
                        check=False, timeout=20,
                    )
                    if thumb_tmp.exists():
                        out.write(thumb_tmp.read_bytes())
                finally:
                    thumb_tmp.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        return None
    data = out.getvalue()
    if not data:
        return None
    try:
        await asyncio.to_thread(objstore.put_bytes, thumb_path, data, "image/jpeg")
    except Exception:  # noqa: BLE001
        pass  # Cache write is best-effort
    return data


def _load_font(size: int) -> ImageFont.ImageFont:
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size=size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def _hex_to_rgb(s: str, default=(255, 255, 255)) -> tuple:
    try:
        s = s.lstrip("#")
        if len(s) == 3:
            s = "".join(c * 2 for c in s)
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:  # noqa: BLE001
        return default


def _aspect_dims(aspect: str) -> tuple:
    return {
        "1:1": (1080, 1080), "4:5": (1080, 1350),
        "9:16": (1080, 1920), "16:9": (1920, 1080),
    }[aspect]


def _fit_to(img: Image.Image, target_w: int, target_h: int, mode: str, bg: tuple) -> Image.Image:
    """`cover` = scale+crop to fill; `contain` = scale+pad with bg."""
    src_ratio = img.width / img.height
    tgt_ratio = target_w / target_h
    if mode == "cover":
        if src_ratio > tgt_ratio:
            new_h = target_h
            new_w = int(target_h * src_ratio)
        else:
            new_w = target_w
            new_h = int(target_w / src_ratio)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        x = (new_w - target_w) // 2
        y = (new_h - target_h) // 2
        return resized.crop((x, y, x + target_w, y + target_h))
    # contain
    if src_ratio > tgt_ratio:
        new_w = target_w
        new_h = int(target_w / src_ratio)
    else:
        new_h = target_h
        new_w = int(target_h * src_ratio)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), bg)
    canvas.paste(resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
    return canvas


def _render_sync(job: Dict[str, Any], ordered: list, W: int, H: int, work_dir: Path) -> Path:
    """Blocking ffmpeg pipeline — runs inside asyncio.to_thread. All file paths
    live under `work_dir` (a /tmp subdir) for the duration of the render."""
    per = max(2.0, job["duration_seconds"] / max(1, len(ordered)))
    src_paths: List[Path] = []
    # Download each source asset to the work dir
    for i, asset in enumerate(ordered):
        ext = asset["storage_path"].rsplit(".", 1)[-1] if "." in asset["storage_path"] else "bin"
        local = work_dir / f"src_{i}.{ext}"
        objstore.download_to_tmp(asset["storage_path"], local)
        src_paths.append(local)

    clip_paths = []
    for i, (asset, src) in enumerate(zip(ordered, src_paths)):
        clip = work_dir / f"clip_{i}.mp4"
        if asset["kind"] == "image":
            cmd = ["ffmpeg", "-y", "-loglevel", "error",
                   "-loop", "1", "-i", str(src),
                   "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=yuv420p",
                   "-t", f"{per:.2f}", "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                   str(clip)]
        else:
            cmd = ["ffmpeg", "-y", "-loglevel", "error",
                   "-i", str(src),
                   "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=yuv420p",
                   "-t", f"{per:.2f}", "-r", "30", "-an", "-c:v", "libx264",
                   str(clip)]
        subprocess.run(cmd, check=True, timeout=60, capture_output=True)
        clip_paths.append(clip)

    concat_file = work_dir / "concat.txt"
    concat_file.write_text("\n".join(f"file '{p}'" for p in clip_paths))
    out_path = work_dir / "final.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(concat_file), "-c", "copy", str(out_path)],
        check=True, timeout=120, capture_output=True,
    )

    if job.get("title"):
        titled = work_dir / "titled.mp4"
        txt = (job.get("title") or "").replace(":", r"\:").replace("'", r"\'")
        cta = (job.get("cta") or "").replace(":", r"\:").replace("'", r"\'")
        vf = (
            f"drawtext=text='{txt}':fontcolor=white:fontsize=60:"
            f"x=(w-text_w)/2:y=h*0.08:box=1:boxcolor=black@0.5:boxborderw=20:enable='lte(t,3.0)'"
        )
        if cta:
            vf += (
                f",drawtext=text='{cta}':fontcolor=white:fontsize=44:"
                f"x=(w-text_w)/2:y=h*0.88:box=1:boxcolor=#C8A95E@0.85:boxborderw=15"
            )
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(out_path),
                 "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(titled)],
                check=True, timeout=120,
            )
            if titled.exists() and titled.stat().st_size > 1000:
                out_path = titled
        except subprocess.CalledProcessError:
            pass  # drawtext is best-effort

    return out_path


# ---------------------------------------------------------------- AI image task tracking
# Strong-reference registry so `asyncio.create_task` results aren't GC'd before
# they finish. Used by both AI image and marketing-pack background pipelines.

_ai_image_tasks: set = set()


def _spawn_ai_image_task(coro):
    """Fire-and-forget background task with a strong reference so it isn't GC'd."""
    task = asyncio.create_task(coro)
    _ai_image_tasks.add(task)
    task.add_done_callback(_ai_image_tasks.discard)
    return task
