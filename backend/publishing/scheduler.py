"""Scheduler — schedule / cancel / reschedule + due-poll runner.

Collections:
  scheduled_posts  — one document per scheduled publish
  publish_jobs     — short-lived job records (one per publish attempt)
  publish_logs     — append-only audit trail

Status flow:
  draft → scheduled → publishing → published
                                 → failed
                  → cancelled (terminal)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import publish_now


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _log(db, *, scheduled_post_id: Optional[str], action: str, actor: str, detail: Dict[str, Any]) -> None:
    await db.publish_logs.insert_one({
        "id": str(uuid.uuid4()),
        "scheduled_post_id": scheduled_post_id,
        "action": action,
        "actor": actor,
        "detail": detail,
        "created_at": _now(),
    })


async def schedule_publish(
    db,
    *,
    asset_id: str,
    provider: str,
    scheduled_at: str,
    actor: str = "admin",
    campaign_id: Optional[str] = None,
    business_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a scheduled_post document and flip the asset status to scheduled."""
    asset = await db.ai_assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise ValueError(f"Asset {asset_id} not found")

    sp_id = str(uuid.uuid4())
    doc = {
        "id": sp_id,
        "asset_id": asset_id,
        "campaign_id": campaign_id,
        "business_id": business_id,
        "platform": provider,
        "provider": provider,
        "scheduled_at": scheduled_at,
        "published_at": None,
        "status": "scheduled",
        "error_message": None,
        "external_id": None,
        "notes": notes,
        "created_at": _now(),
        "updated_at": _now(),
        # Denormalised for fast calendar render — avoid asset lookup per cell.
        "title": asset.get("title"),
        "kind": asset.get("kind"),
    }
    await db.scheduled_posts.insert_one(doc)
    await db.ai_assets.update_one(
        {"id": asset_id},
        {"$set": {"status": "scheduled", "updated_at": _now()}},
    )
    await _log(db, scheduled_post_id=sp_id, action="schedule.created", actor=actor,
               detail={"provider": provider, "scheduled_at": scheduled_at, "asset_id": asset_id})
    return {k: v for k, v in doc.items() if k != "_id"}


async def cancel_publish(db, scheduled_post_id: str, actor: str = "admin") -> Dict[str, Any]:
    sp = await db.scheduled_posts.find_one({"id": scheduled_post_id}, {"_id": 0})
    if not sp:
        raise ValueError("Scheduled post not found")
    if sp["status"] in ("published", "cancelled"):
        return sp
    await db.scheduled_posts.update_one(
        {"id": scheduled_post_id},
        {"$set": {"status": "cancelled", "updated_at": _now()}},
    )
    await _log(db, scheduled_post_id=scheduled_post_id, action="schedule.cancelled", actor=actor,
               detail={"prior_status": sp["status"]})
    sp["status"] = "cancelled"
    return sp


async def reschedule_publish(db, scheduled_post_id: str, new_at: str, actor: str = "admin") -> Dict[str, Any]:
    sp = await db.scheduled_posts.find_one({"id": scheduled_post_id}, {"_id": 0})
    if not sp:
        raise ValueError("Scheduled post not found")
    if sp["status"] not in ("scheduled", "failed", "draft"):
        raise ValueError(f"Cannot reschedule a post in '{sp['status']}' state")
    await db.scheduled_posts.update_one(
        {"id": scheduled_post_id},
        {"$set": {
            "scheduled_at": new_at,
            "status": "scheduled",
            "error_message": None,
            "updated_at": _now(),
        }},
    )
    await _log(db, scheduled_post_id=scheduled_post_id, action="schedule.rescheduled", actor=actor,
               detail={"from": sp.get("scheduled_at"), "to": new_at})
    sp["scheduled_at"] = new_at
    sp["status"] = "scheduled"
    return sp


async def execute_publish(db, scheduled_post_id: str, actor: str = "system") -> Dict[str, Any]:
    """Run one publish attempt; updates scheduled_post + logs + creates publish_job."""
    sp = await db.scheduled_posts.find_one({"id": scheduled_post_id}, {"_id": 0})
    if not sp:
        raise ValueError("Scheduled post not found")
    if sp["status"] in ("published", "cancelled"):
        return sp

    asset = await db.ai_assets.find_one({"id": sp["asset_id"]}, {"_id": 0})
    if not asset:
        from errors import StructuredError, audit_log
        err = StructuredError(
            code="asset_missing", status=404, retryable=False, retry_action="pick_assets",
            user_message="The asset attached to this scheduled post was deleted. Pick a new asset and reschedule.",
            technical=f"ai_assets({sp['asset_id']}) not found",
        )
        await audit_log(db, surface="publishing", err=err,
                        scheduled_post_id=scheduled_post_id, provider=sp["provider"])
        await db.scheduled_posts.update_one(
            {"id": scheduled_post_id},
            {"$set": {"status": "failed",
                      "error_message": err.user_message,
                      "error": err.to_payload(),
                      "updated_at": _now()}},
        )
        await _log(db, scheduled_post_id=scheduled_post_id, action="publish.failed", actor=actor,
                   detail={"code": err.code, "reason": "asset_missing"})
        return {**sp, "status": "failed", "error_message": err.user_message, "error": err.to_payload()}

    # Pull connection if exists (may be None — provider stubs simulate)
    conn = await db.provider_connections.find_one({"provider": sp["provider"]}, {"_id": 0})

    # Mark publishing + create job
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "scheduled_post_id": scheduled_post_id,
        "provider": sp["provider"],
        "status": "running",
        "attempt": (sp.get("attempts") or 0) + 1,
        "created_at": _now(),
    }
    await db.publish_jobs.insert_one(job)
    await db.scheduled_posts.update_one(
        {"id": scheduled_post_id},
        {"$set": {"status": "publishing", "updated_at": _now()},
         "$inc": {"attempts": 1}},
    )
    await _log(db, scheduled_post_id=scheduled_post_id, action="publish.started", actor=actor,
               detail={"job_id": job_id, "provider": sp["provider"]})

    # Run the publish
    result = await publish_now(provider_id=sp["provider"], asset=asset, connection=conn)

    final_status = "published" if result.success else "failed"
    update = {
        "status": final_status,
        "updated_at": _now(),
        "error_message": result.error,
        "error": result.structured_error,  # structured payload for the UI
        "external_id": result.external_id,
    }
    if result.success:
        update["published_at"] = result.published_at or _now()

    await db.scheduled_posts.update_one({"id": scheduled_post_id}, {"$set": update})
    await db.publish_jobs.update_one(
        {"id": job_id},
        {"$set": {
            "status": final_status,
            "result": result.raw,
            "error": result.error,
            "structured_error": result.structured_error,
            "finished_at": _now(),
        }},
    )
    await _log(
        db,
        scheduled_post_id=scheduled_post_id,
        action=f"publish.{final_status}",
        actor=actor,
        detail={
            "job_id": job_id,
            "external_id": result.external_id,
            "error": result.error,
            "error_code": (result.structured_error or {}).get("code"),
        },
    )

    # Audit log every failure so the operator can see patterns across providers
    if not result.success and result.structured_error:
        from errors import StructuredError, audit_log
        err_obj = StructuredError(**{k: v for k, v in result.structured_error.items() if k != "context"})
        await audit_log(db, surface="publishing", err=err_obj,
                        scheduled_post_id=scheduled_post_id,
                        provider=sp["provider"], asset_id=sp["asset_id"])

    # Update parent asset to mirror state
    if result.success:
        await db.ai_assets.update_one(
            {"id": sp["asset_id"]},
            {"$set": {"status": "active", "updated_at": _now()}},
        )

    return {**sp, **update}


async def fetch_due_posts(db, *, limit: int = 50) -> List[Dict[str, Any]]:
    """Return scheduled_posts whose scheduled_at <= now AND status == 'scheduled'."""
    cursor = db.scheduled_posts.find(
        {
            "status": "scheduled",
            "scheduled_at": {"$lte": _now()},
        },
        {"_id": 0},
    ).sort("scheduled_at", 1).limit(limit)
    return await cursor.to_list(limit)


async def run_due_publishes(db, *, limit: int = 25) -> List[Dict[str, Any]]:
    """Single tick of the background worker — publish anything that's due."""
    due = await fetch_due_posts(db, limit=limit)
    out: List[Dict[str, Any]] = []
    for sp in due:
        try:
            out.append(await execute_publish(db, sp["id"]))
        except Exception as e:  # noqa: BLE001
            from errors import StructuredError, audit_log
            err = StructuredError(
                code="unknown", status=500, retryable=True, retry_action="retry_publish",
                user_message="The publishing worker crashed while processing this post. It will retry on the next scheduler tick.",
                technical=str(e)[:400],
            )
            await audit_log(db, surface="publishing", err=err,
                            scheduled_post_id=sp["id"], provider=sp.get("provider"))
            await _log(db, scheduled_post_id=sp["id"], action="publish.crash", actor="system",
                       detail={"error": str(e), "code": err.code})
    return out
