"""Sprint 12C — Task 3: backfill `expires_at` BSON Date on collections that
just received TTL indexes. Runs once on startup; idempotent.

  - failure_audit_log → 30-day retention (TTL key built from `created_at`)
  - publish_logs      → 90-day retention
  - page_views        → 180-day retention

For each collection we walk rows that don't yet have `expires_at`, parse the
existing ISO string timestamp, and set `expires_at = ts + retention_days`. Rows
with no parseable timestamp get `expires_at = now + retention_days` so they
still get garbage-collected eventually.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple

logger = logging.getLogger(__name__)


def _parse_iso(s: str | None) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    try:
        # Handle both `Z` suffix and `+00:00`.
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


async def _backfill_one(db, collection: str, ts_field: str, retention_days: int) -> Tuple[int, int]:
    """Returns (scanned, set_count). Idempotent — only writes if `expires_at` missing."""
    now = datetime.now(timezone.utc)
    retention = timedelta(days=retention_days)
    coll = db[collection]
    cursor = coll.find({"expires_at": {"$exists": False}}, {"_id": 1, ts_field: 1})
    scanned = 0
    set_count = 0
    async for doc in cursor:
        scanned += 1
        parsed = _parse_iso(doc.get(ts_field)) or now
        expires_at = parsed + retention
        # If the doc is already older than its retention, give it a 1-minute
        # grace so the TTL monitor reaps it on its next sweep without surprise.
        if expires_at < now:
            expires_at = now + timedelta(minutes=1)
        await coll.update_one({"_id": doc["_id"]}, {"$set": {"expires_at": expires_at}})
        set_count += 1
    return scanned, set_count


async def backfill_ttl_expiries(db) -> None:
    """Run once at startup. Logs how many rows were stamped per collection."""
    plan = [
        ("failure_audit_log", "created_at", 30),
        ("publish_logs", "created_at", 90),
        ("page_views", "timestamp", 180),
        ("ai_generations", "created_at", 90),
    ]
    for coll, ts_field, days in plan:
        try:
            scanned, set_count = await _backfill_one(db, coll, ts_field, days)
            if set_count:
                logger.info(
                    "[ttl-backfill] %s: stamped expires_at on %d/%d rows (retention=%dd)",
                    coll, set_count, scanned, days,
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("[ttl-backfill] %s skipped: %s", coll, e)
