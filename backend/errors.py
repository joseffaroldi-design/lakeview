"""Structured error architecture — single source of truth for owner-facing failures.

All long-running surfaces (AI image gen, video render, social export, publishing,
provider API calls) classify their exceptions into a `StructuredError` so the
frontend can render category icons, retry actions, and plain-English messages.

Three things every failure produces:

  1. `StructuredError` JSON payload returned to clients / stored in jobs / posts
  2. `logger.exception(...)` line with surface + code + context
  3. `failure_audit_log` collection entry — append-only audit trail

Categories — kept stable across versions so the frontend can map them to UX:

  budget_exhausted    AI provider out of credit
  key_invalid         Auth rejected by provider
  key_missing         Server config missing
  safety_reject       Content moderation
  rate_limited        Provider 429
  prompt_invalid      Provider 400 (bad input)
  provider_unavailable Network / provider 5xx
  provider_empty      Provider returned nothing
  timeout             Our outer timeout fired
  ffmpeg_missing      Render: ffmpeg binary not installed
  ffmpeg_failed       Render: ffmpeg exited non-zero
  asset_missing       Source asset deleted / file missing
  asset_invalid       Source asset unreadable / wrong type
  provider_unregistered Publishing provider not in registry
  not_connected       Publishing provider lacks credentials
  permission_denied   Provider returned 403
  payload_too_large   Provider rejected payload size
  unknown             Catch-all (still surfaces technical detail)
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger("uvicorn.error")


@dataclass
class StructuredError:
    code: str
    user_message: str
    technical: str = ""
    status: int = 502
    retryable: bool = True
    retry_action: Optional[str] = None  # e.g. "retry_render", "add_balance", "reconnect_provider"
    context: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Classifier — LLM/Image providers (litellm, openai, gemini)
# ---------------------------------------------------------------------------
def classify_llm_error(exc: Exception, *, surface: str = "ai") -> StructuredError:
    msg = str(exc).lower()
    tech = str(exc)[:400]

    if any(k in msg for k in ("insufficient", "budget", "balance", "quota", "billing", "payment required", "402")):
        return StructuredError(
            code="budget_exhausted", status=402,
            user_message="Your AI credit balance is empty. Open your Profile → Universal Key → Add Balance to top up, then try again.",
            technical=tech, retryable=True, retry_action="add_balance",
        )
    if any(k in msg for k in ("unauthorized", "401", "invalid api key", "authentication")):
        return StructuredError(
            code="key_invalid", status=401,
            user_message="The AI provider rejected the API key. Ask your admin to verify EMERGENT_LLM_KEY.",
            technical=tech, retryable=False,
        )
    if any(k in msg for k in ("content_policy", "safety", "moderation", "rejected", "harmful", "violation")):
        return StructuredError(
            code="safety_reject", status=422,
            user_message="Your prompt was rejected by the AI safety filter. Reword it without anything that could be read as violent, sexual, or political — or remove brand/celebrity names.",
            technical=tech, retryable=True, retry_action="edit_prompt",
        )
    if any(k in msg for k in ("rate limit", "ratelimit", "too many requests", "429")):
        return StructuredError(
            code="rate_limited", status=429,
            user_message="AI provider rate limit hit. Wait 30-60 seconds and try again.",
            technical=tech, retryable=True, retry_action="wait_and_retry",
        )
    if any(k in msg for k in ("invalid prompt", "prompt too long", "bad request", "400", "validation")):
        return StructuredError(
            code="prompt_invalid", status=400,
            user_message="The prompt was rejected as invalid (probably too long or empty). Shorten it and retry.",
            technical=tech, retryable=True, retry_action="edit_prompt",
        )
    if any(k in msg for k in ("timeout", "timed out", "connection", "network", "504", "503", "service unavailable")):
        return StructuredError(
            code="provider_unavailable", status=503,
            user_message="Couldn't reach the AI provider. Check your internet connection and try again in a minute.",
            technical=tech, retryable=True, retry_action="retry",
        )
    return StructuredError(
        code="unknown", status=502,
        user_message=f"{surface.capitalize()} failed for an unexpected reason. Try again, or check the technical details below.",
        technical=tech, retryable=True, retry_action="retry",
    )


# ---------------------------------------------------------------------------
# Classifier — FFmpeg / video render
# ---------------------------------------------------------------------------
def classify_render_error(
    exc: Optional[Exception] = None,
    *,
    returncode: Optional[int] = None,
    stderr: str = "",
) -> StructuredError:
    """Render worker — `exc` is the python-level exception; `returncode` and
    `stderr` are from the ffmpeg subprocess if it ran but exited non-zero."""
    if isinstance(exc, FileNotFoundError) or (exc and "no such file" in str(exc).lower() and "ffmpeg" in str(exc).lower()):
        return StructuredError(
            code="ffmpeg_missing", status=503,
            user_message="Video rendering is unavailable: ffmpeg isn't installed on the server. Ask your admin to run `apt-get install -y ffmpeg`. (The server will normally auto-install on restart.)",
            technical=str(exc) or "ffmpeg binary missing",
            retryable=True, retry_action="restart_backend",
        )
    if exc and "no usable source" in str(exc).lower():
        return StructuredError(
            code="asset_missing", status=404, retryable=True, retry_action="pick_assets",
            user_message="None of the selected media files were readable. They may have been deleted or are in an unsupported format. Pick different assets and try again.",
            technical=str(exc),
        )
    if returncode is not None:
        tail = (stderr or "")[-400:] if stderr else ""
        tail_low = tail.lower()
        if "no such file" in tail_low or "no such file or directory" in tail_low:
            return StructuredError(
                code="asset_missing", status=404,
                user_message="One of the selected media files was deleted before rendering could finish. Pick the source images again and re-render.",
                technical=f"ffmpeg exit {returncode}: {tail}",
                retryable=True, retry_action="pick_assets",
            )
        if "invalid data" in tail_low or "moov atom not found" in tail_low or "decoder.*not found" in tail_low:
            return StructuredError(
                code="asset_invalid", status=422,
                user_message="One of your media files is corrupted or in an unsupported format. Try removing it from the selection and rendering again.",
                technical=f"ffmpeg exit {returncode}: {tail}",
                retryable=True, retry_action="pick_assets",
            )
        return StructuredError(
            code="ffmpeg_failed", status=500,
            user_message="The video renderer crashed. This usually means a bad asset or a memory limit. Try fewer clips, a shorter duration, or a different aspect ratio.",
            technical=f"ffmpeg exit {returncode}: {tail}",
            retryable=True, retry_action="retry_render",
        )
    if exc and isinstance(exc, MemoryError):
        return StructuredError(
            code="ffmpeg_failed", status=507,
            user_message="The server ran out of memory while rendering. Try fewer clips or a shorter duration.",
            technical=str(exc), retryable=True, retry_action="retry_render",
        )
    return StructuredError(
        code="unknown", status=500,
        user_message="Video render failed for an unexpected reason. Try again with fewer or smaller assets.",
        technical=str(exc) if exc else "", retryable=True, retry_action="retry_render",
    )


# ---------------------------------------------------------------------------
# Classifier — Provider publishing (Meta / SendGrid / Twilio / Mailchimp)
# ---------------------------------------------------------------------------
def classify_publish_error(provider: str, raw_error: str, *, http_status: Optional[int] = None) -> StructuredError:
    msg = (raw_error or "").lower()
    if not raw_error:
        return StructuredError(
            code="unknown", status=500,
            user_message=f"Publishing to {provider} failed without an error message. Try again or check the Provider Connections tab.",
            technical="provider returned no error string",
            retryable=True, retry_action="retry_publish",
        )
    if any(k in msg for k in ("not connected", "no credentials", "missing", "not configured")):
        return StructuredError(
            code="not_connected", status=400,
            user_message=f"{provider} isn't connected yet. Open Provider Connections, sign in, and re-schedule this post.",
            technical=raw_error, retryable=False, retry_action="open_provider_connections",
        )
    if any(k in msg for k in ("expired", "invalid token", "revoked", "401", "unauthorized", "needs reauthentication")):
        return StructuredError(
            code="key_invalid", status=401,
            user_message=f"Your {provider} login expired. Open Provider Connections and reconnect to keep publishing.",
            technical=raw_error, retryable=False, retry_action="reconnect_provider",
        )
    if any(k in msg for k in ("permission", "forbidden", "403", "scope", "insufficient")):
        return StructuredError(
            code="permission_denied", status=403,
            user_message=f"{provider} blocked the publish — the connected account is missing a permission scope. Reconnect with full Page/Profile permissions.",
            technical=raw_error, retryable=False, retry_action="reconnect_provider",
        )
    if any(k in msg for k in ("rate limit", "ratelimit", "too many", "429")):
        return StructuredError(
            code="rate_limited", status=429,
            user_message=f"{provider} rate-limited your account. Wait a few minutes and retry — or reduce how many posts you publish per hour.",
            technical=raw_error, retryable=True, retry_action="wait_and_retry",
        )
    if any(k in msg for k in ("payload too large", "request entity too large", "413", "file too big")):
        return StructuredError(
            code="payload_too_large", status=413,
            user_message=f"The asset is too large for {provider}. Try exporting a smaller version via Social Exports.",
            technical=raw_error, retryable=True, retry_action="export_smaller",
        )
    if any(k in msg for k in ("safety", "policy", "violat", "rejected", "spam")):
        return StructuredError(
            code="safety_reject", status=422,
            user_message=f"{provider} rejected the content under its policy. Edit the caption/image and retry.",
            technical=raw_error, retryable=True, retry_action="edit_post",
        )
    if any(k in msg for k in ("timeout", "timed out", "connection", "network", "504", "503", "unreachable")):
        return StructuredError(
            code="provider_unavailable", status=503,
            user_message=f"Can't reach {provider} right now. We'll auto-retry on the next scheduler tick.",
            technical=raw_error, retryable=True, retry_action="retry_publish",
        )
    if any(k in msg for k in ("not registered", "unknown provider")):
        return StructuredError(
            code="provider_unregistered", status=400,
            user_message=f"The provider '{provider}' isn't installed on this server. Contact support.",
            technical=raw_error, retryable=False,
        )
    return StructuredError(
        code="unknown", status=502,
        user_message=f"Publishing to {provider} failed unexpectedly. Try again — if it keeps failing, check Provider Connections.",
        technical=raw_error, retryable=True, retry_action="retry_publish",
    )


# ---------------------------------------------------------------------------
# Logging + audit log
# ---------------------------------------------------------------------------
def log_failure(surface: str, err: StructuredError, **context: Any) -> None:
    """Standard backend log line for every classified failure."""
    ctx = " ".join(f"{k}={v!r}" for k, v in context.items())
    logger.error("[%s] FAIL code=%s status=%s %s — %s",
                 surface, err.code, err.status, ctx, err.technical[:200])


async def audit_log(db, *, surface: str, err: StructuredError, **context: Any) -> None:
    """Append to failure_audit_log collection. Best-effort — never raises."""
    try:
        now = datetime.now(timezone.utc)
        await db.failure_audit_log.insert_one({
            "id": str(uuid.uuid4()),
            "surface": surface,
            "code": err.code,
            "status": err.status,
            "user_message": err.user_message,
            "technical": err.technical,
            "context": context,
            "created_at": now.isoformat(),
            # Sprint 12C — TTL: drop after 30 days (BSON Date for the TTL monitor)
            "expires_at": now + timedelta(days=30),
        })
    except Exception as e:  # noqa: BLE001
        logger.warning("[audit_log] could not record failure: %s", e)


async def report_failure(
    db,
    *,
    surface: str,
    err: StructuredError,
    **context: Any,
) -> StructuredError:
    """One-call helper: log + audit + return the error so the caller can raise/return it."""
    log_failure(surface, err, **context)
    if db is not None:
        await audit_log(db, surface=surface, err=err, **context)
    return err
