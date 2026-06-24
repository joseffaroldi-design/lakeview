"""Media asset orphan & health scanner — preview maintenance script.

Scans the `media_assets` collection and the storage layer to classify every
row into one of:

    healthy             — DB row + source file + cached thumb all present
    missing_file        — DB row references a storage_path that doesn't exist
    missing_thumbnail   — Source file present, but no cached thumbnail
    orphaned_record     — DB row has no/empty storage_path (cannot resolve)
    orphaned_storage_file — File on local-disk fallback with no DB row

The script is READ-ONLY by default. It NEVER hard-deletes anything. Only with
the explicit `--archive` flag does it mutate rows, and even then it only
sets `status="archived"` (reversible) on rows in the `missing_file` bucket.

USAGE
    # Dry-run scan (default), pretty-print to stdout:
    python -m scripts.media_orphans

    # Scan and write a JSON report:
    python -m scripts.media_orphans --report /tmp/media_health.json

    # Archive every `missing_file` row (still no hard delete):
    python -m scripts.media_orphans --archive

    # Limit scan to first N rows (safety for huge collections):
    python -m scripts.media_orphans --limit 500

PRODUCTION
    This script is intended for PREVIEW. The production env-var propagation
    bug (escalated to Emergent Support) makes prod runs unsafe until fixed.
    A `--allow-prod` safety flag is required to run outside of the preview
    deployment.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

# Make `backend` package imports work when invoked as a script.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

CATEGORIES = (
    "healthy",
    "missing_file",
    "missing_thumbnail",
    "orphaned_record",
    "orphaned_storage_file",
)


# --------------------------------------------------------------- Classification

def derive_thumb_path(asset_id: str, app_name: str = "lakeview") -> str:
    """Mirror of `storage.make_path('thumbs', asset_id, 'jpg')` — kept local
    so the classifier can be unit-tested without importing the storage
    module (which makes a network call on import in some envs)."""
    return f"{app_name}/thumbs/{asset_id}.jpg"


def classify_asset(asset: Dict[str, Any],
                   exists: Callable[[str], bool],
                   app_name: str = "lakeview") -> str:
    """Classify a single asset row. Pure function — easy to unit test.

    Args:
        asset: a `media_assets` row dict.
        exists: callable returning True if a storage path resolves to bytes.
        app_name: object-storage app namespace (only used for thumb path).
    """
    sp = (asset.get("storage_path") or "").strip()
    aid = asset.get("id")
    if not sp or not aid:
        return "orphaned_record"
    if not exists(sp):
        return "missing_file"
    thumb = derive_thumb_path(aid, app_name=app_name)
    if not exists(thumb):
        return "missing_thumbnail"
    return "healthy"


# ---------------------------------------------------------------- Scanner

async def scan_media_assets(
    database,
    exists: Callable[[str], bool],
    *,
    status_filter: Optional[str] = "active",
    limit: Optional[int] = None,
    app_name: str = "lakeview",
) -> Dict[str, List[Dict[str, Any]]]:
    """Walk `media_assets`, classify each row, and bucket them.

    Returns:
        {category: [{id, filename, storage_path, kind, source, uploaded_at}]}
    """
    query: Dict[str, Any] = {}
    if status_filter:
        query["status"] = status_filter

    cursor = database.media_assets.find(query, {"_id": 0})
    if limit:
        cursor = cursor.limit(limit)

    buckets: Dict[str, List[Dict[str, Any]]] = {c: [] for c in CATEGORIES}
    async for asset in cursor:
        category = classify_asset(asset, exists, app_name=app_name)
        buckets[category].append({
            "id": asset.get("id"),
            "filename": asset.get("filename"),
            "kind": asset.get("kind"),
            "source": asset.get("source"),
            "storage_path": asset.get("storage_path"),
            "uploaded_at": asset.get("uploaded_at"),
        })
    return buckets


async def scan_local_storage_for_orphans(
    database,
    local_dir: Path,
) -> List[Dict[str, Any]]:
    """Walk the legacy local-disk fallback dir and flag files that have no
    matching `media_assets.storage_path` (bare filename) anywhere in the DB.

    Object storage doesn't expose a list endpoint, so we can only do this
    detection for legacy local files. Anything detected here is genuinely
    orphan disk weight — safe to delete in a future sprint.
    """
    if not local_dir.exists():
        return []

    # Collect every bare-filename storage_path in the DB (legacy fallback).
    known: set[str] = set()
    async for row in database.media_assets.find(
        {}, {"storage_path": 1, "_id": 0},
    ):
        sp = (row.get("storage_path") or "").strip()
        if sp and "/" not in sp:
            known.add(sp)

    orphans: List[Dict[str, Any]] = []
    for f in sorted(local_dir.iterdir()):
        if not f.is_file():
            continue
        if f.name in known:
            continue
        orphans.append({
            "path": str(f),
            "filename": f.name,
            "size_bytes": f.stat().st_size,
        })
    return orphans


# ---------------------------------------------------------------- Archive

async def archive_missing_files(database, asset_ids: List[str]) -> int:
    """Set `status="archived"` on the given rows.

    NEVER hard-deletes. Records an `archived_at` + `archived_reason` so the
    operation can be audited / reversed later by a one-line `update_many`.
    """
    if not asset_ids:
        return 0
    result = await database.media_assets.update_many(
        {"id": {"$in": asset_ids}, "status": {"$ne": "archived"}},
        {"$set": {
            "status": "archived",
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "archived_reason": "orphan_cleanup: storage_path file missing",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return result.modified_count


# ---------------------------------------------------------------- Report shape

def summarise(buckets: Dict[str, List[Dict[str, Any]]],
              storage_orphans: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            **{c: len(buckets.get(c, [])) for c in CATEGORIES if c != "orphaned_storage_file"},
            "orphaned_storage_file": len(storage_orphans),
            "scanned_rows": sum(len(buckets.get(c, [])) for c in CATEGORIES),
        },
        "details": {
            **buckets,
            "orphaned_storage_file": storage_orphans,
        },
    }


def render_console(report: Dict[str, Any]) -> str:
    """Compact human-readable summary."""
    t = report["totals"]
    lines = [
        "=" * 60,
        "MEDIA HEALTH REPORT",
        f"generated_at: {report['generated_at']}",
        "-" * 60,
        f"  healthy:               {t['healthy']:>6}",
        f"  missing_file:          {t['missing_file']:>6}",
        f"  missing_thumbnail:     {t['missing_thumbnail']:>6}",
        f"  orphaned_record:       {t['orphaned_record']:>6}",
        f"  orphaned_storage_file: {t['orphaned_storage_file']:>6}",
        "  ──────────────────────────────",
        f"  scanned_rows:          {t['scanned_rows']:>6}",
        "=" * 60,
    ]
    # Show first few broken records for quick visual triage.
    for cat in ("missing_file", "orphaned_record"):
        items = report["details"][cat][:5]
        if items:
            lines.append(f"\nSample [{cat}] (first 5):")
            for it in items:
                lines.append(f"  - id={it.get('id')}  file={it.get('filename')}"
                             f"  path={it.get('storage_path')!r}")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI driver

async def _run_cli(args: argparse.Namespace) -> int:
    """Wire scanner + classifier to the live storage layer."""
    import storage as objstore
    from config import client as mongo_client, db

    env = os.environ.get("ENVIRONMENT", "preview").lower()
    if env == "production" and not args.allow_prod:
        print(
            "[media-orphans] REFUSING to run in production without --allow-prod.\n"
            "                Production env-var propagation is currently broken\n"
            "                (escalated to Emergent Support). Re-run in preview\n"
            "                or wait for env-var fix before forcing.",
            file=sys.stderr,
        )
        return 2

    try:
        buckets = await scan_media_assets(
            db,
            exists=objstore.exists,
            status_filter=args.status,
            limit=args.limit,
            app_name=getattr(objstore, "APP_NAME", "lakeview"),
        )
        storage_orphans = await scan_local_storage_for_orphans(
            db,
            local_dir=Path(os.environ.get("MEDIA_STORAGE_DIR", "/app/backend/media_storage")),
        )
        report = summarise(buckets, storage_orphans)
        print(render_console(report))

        if args.report:
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report).write_text(json.dumps(report, indent=2, default=str))
            print(f"\n[media-orphans] Wrote JSON report → {args.report}")

        if args.archive:
            ids = [r["id"] for r in buckets["missing_file"] if r.get("id")]
            n = await archive_missing_files(db, ids)
            print(f"\n[media-orphans] Archived {n} 'missing_file' rows "
                  f"(out of {len(ids)} candidates). No hard deletes performed.")
        else:
            print("\n[media-orphans] Dry-run only — pass --archive to soft-archive "
                  "'missing_file' rows.")
        return 0
    finally:
        # Close the Motor client so the script doesn't hang on event-loop
        # teardown (the default driver keeps pooled connections open).
        try:
            mongo_client.close()
        except Exception:  # noqa: BLE001
            pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Scan media_assets for orphans and broken file references "
                    "(preview maintenance, read-only by default).",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Explicit dry-run (this is the default behaviour).")
    p.add_argument("--archive", action="store_true",
                   help="Soft-archive 'missing_file' rows (status=archived). "
                        "No hard deletes.")
    p.add_argument("--report", metavar="PATH",
                   help="Write full JSON report to this path.")
    p.add_argument("--limit", type=int, default=None,
                   help="Cap on the number of media_assets rows scanned.")
    p.add_argument("--status", default="active",
                   help="status filter for media_assets (default: active). "
                        "Pass empty string to scan all.")
    p.add_argument("--allow-prod", action="store_true",
                   help="Required to run in production. Refuses otherwise "
                        "while the env-var propagation bug is open.")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_run_cli(args))


if __name__ == "__main__":
    sys.exit(main())
