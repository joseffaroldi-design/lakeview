"""Bootstrap helpers — runtime self-healing for binaries the container may strip.

Two responsibilities:

1. `ensure_ffmpeg()` — verify ffmpeg is on PATH; reinstall via apt if missing.
   This is here because the preview/runtime container occasionally loses
   /usr/bin/ffmpeg between rebuilds. Calling apt-get from the backend startup
   is idempotent and survives container restarts as long as the apt cache is
   reachable.

2. `prewarm_rembg()` — eagerly create a u2net session in a background thread so
   the first user-triggered "Remove background" doesn't pay the 30-90s model
   download. Safe to call multiple times.

Both helpers fail soft — they log and continue so the backend always boots even
when network is offline.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger("uvicorn.error")

# Module-level state so /api/media/health can introspect without re-running checks
_rembg_state = {"available": False, "model_ready": False, "error": None}


def ensure_ffmpeg(timeout: int = 120) -> bool:
    """Install ffmpeg via apt if it isn't on PATH. Returns True if available afterward."""
    if shutil.which("ffmpeg") is not None:
        return True
    logger.warning("[bootstrap] ffmpeg missing — running `apt-get install -y ffmpeg`")
    try:
        subprocess.run(
            ["apt-get", "update", "-qq"],
            check=False, capture_output=True, timeout=timeout,
        )
        result = subprocess.run(
            ["apt-get", "install", "-y", "--no-install-recommends", "ffmpeg"],
            check=False, capture_output=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.error(
                "[bootstrap] apt-get install ffmpeg failed (rc=%s): %s",
                result.returncode, result.stderr.decode("utf-8", "replace")[-500:],
            )
            return False
    except subprocess.TimeoutExpired:
        logger.error("[bootstrap] ffmpeg install timed out after %ss", timeout)
        return False
    except Exception as e:  # noqa: BLE001
        logger.exception("[bootstrap] ffmpeg install raised: %s", e)
        return False
    installed = shutil.which("ffmpeg") is not None
    logger.info("[bootstrap] ffmpeg installed: %s", installed)
    return installed


def _load_rembg_session_sync(model: str = "u2net"):
    """Blocking — runs in a worker thread. Imports rembg lazily so the backend
    can boot even if onnxruntime is missing."""
    from rembg import new_session
    session = new_session(model)
    # Touch the inner sessions to force model download / load
    _ = session.inner_session
    return session


def rembg_state() -> dict:
    """Return the current rembg readiness so /api/media/health can include it."""
    return dict(_rembg_state)


async def prewarm_rembg(model: str = "u2net") -> None:
    """Fire-and-forget warmup. Run from a startup hook via asyncio.create_task."""
    try:
        await asyncio.to_thread(_load_rembg_session_sync, model)
        _rembg_state.update({"available": True, "model_ready": True, "error": None})
        logger.info("[bootstrap] rembg model '%s' pre-warmed", model)
    except ImportError as e:
        _rembg_state.update({"available": False, "model_ready": False, "error": f"import: {e}"})
        logger.warning("[bootstrap] rembg not importable: %s", e)
    except Exception as e:  # noqa: BLE001
        _rembg_state.update({"available": True, "model_ready": False, "error": str(e)[:300]})
        logger.warning("[bootstrap] rembg model warmup failed (will retry on first call): %s", e)
