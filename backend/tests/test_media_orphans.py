"""Tests for /app/backend/scripts/media_orphans.py.

Covers classification, scanning, archiving, and CLI wiring using a tiny
in-memory fake db (mongomock-style) so the tests run offline with no live
storage or MongoDB dependency.

Uses plain `asyncio.run()` to drive async helpers — keeps the suite free
of `pytest-asyncio` / `anyio` plugin requirements.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from scripts.media_orphans import (  # noqa: E402
    CATEGORIES,
    archive_missing_files,
    classify_asset,
    derive_thumb_path,
    scan_local_storage_for_orphans,
    scan_media_assets,
)


def run(coro):
    """Drive an awaitable to completion. Replaces pytest-asyncio."""
    return asyncio.run(coro)


# ---------- Fake async Mongo collection -------------------------------------

class _FakeCursor:
    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    def limit(self, n: int) -> "_FakeCursor":
        return _FakeCursor(self._rows[:n])

    def __aiter__(self):
        self._iter = iter(self._rows)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


def _matches(row: Dict[str, Any], query: Dict[str, Any]) -> bool:
    for k, v in query.items():
        if isinstance(v, dict):
            if "$in" in v and row.get(k) not in v["$in"]:
                return False
            if "$ne" in v and row.get(k) == v["$ne"]:
                return False
        elif row.get(k) != v:
            return False
    return True


class _FakeCollection:
    def __init__(self, rows: Optional[List[Dict[str, Any]]] = None):
        self.rows: List[Dict[str, Any]] = list(rows or [])

    def find(self, query: Optional[Dict[str, Any]] = None,
             projection: Optional[Dict[str, Any]] = None) -> _FakeCursor:
        q = query or {}
        out = [dict(r) for r in self.rows if _matches(r, q)]
        return _FakeCursor(out)

    async def update_many(self, query: Dict[str, Any],
                          update: Dict[str, Any]):
        modified = 0
        for r in self.rows:
            if _matches(r, query):
                r.update(update.get("$set", {}))
                modified += 1

        class _Result:
            pass
        res = _Result()
        res.modified_count = modified
        return res


class _FakeDB:
    def __init__(self, rows: Optional[List[Dict[str, Any]]] = None):
        self.media_assets = _FakeCollection(rows)


# ---------- Tests: pure classifier ------------------------------------------

class TestClassifier:
    def test_healthy_asset(self):
        """Source + thumb both resolve => healthy."""
        asset = {"id": "a1", "storage_path": "lakeview/uploads/a1.png"}
        existing = {"lakeview/uploads/a1.png", "lakeview/thumbs/a1.jpg"}
        assert classify_asset(asset, lambda p: p in existing) == "healthy"

    def test_missing_file(self):
        """storage_path doesn't exist => missing_file."""
        asset = {"id": "a2", "storage_path": "lakeview/uploads/a2.png"}
        assert classify_asset(asset, lambda p: False) == "missing_file"

    def test_missing_thumbnail(self):
        """Source exists, thumb doesn't => missing_thumbnail."""
        asset = {"id": "a3", "storage_path": "lakeview/uploads/a3.png"}
        existing = {"lakeview/uploads/a3.png"}
        assert classify_asset(asset, lambda p: p in existing) == "missing_thumbnail"

    def test_orphaned_record_blank_path(self):
        """Empty storage_path => orphaned_record."""
        assert classify_asset({"id": "x", "storage_path": ""},
                              lambda p: True) == "orphaned_record"
        assert classify_asset({"id": "x"},
                              lambda p: True) == "orphaned_record"

    def test_orphaned_record_missing_id(self):
        """Row with no id can't even check a thumb => orphaned_record."""
        asset = {"storage_path": "lakeview/uploads/nope.png"}
        assert classify_asset(asset, lambda p: True) == "orphaned_record"

    def test_derive_thumb_path_shape(self):
        assert derive_thumb_path("abc") == "lakeview/thumbs/abc.jpg"
        assert derive_thumb_path("xyz", app_name="other") == "other/thumbs/xyz.jpg"


# ---------- Tests: scanner --------------------------------------------------

@pytest.fixture
def mixed_db():
    """3 healthy + 2 missing_file + 1 missing_thumb + 1 orphan_record."""
    rows = [
        {"id": "h1", "storage_path": "lakeview/uploads/h1.png", "status": "active",
         "kind": "image", "filename": "h1.png", "source": "upload"},
        {"id": "h2", "storage_path": "lakeview/uploads/h2.png", "status": "active",
         "kind": "image", "filename": "h2.png", "source": "upload"},
        {"id": "h3", "storage_path": "lakeview/uploads/h3.png", "status": "active",
         "kind": "image", "filename": "h3.png", "source": "upload"},
        {"id": "m1", "storage_path": "lakeview/uploads/m1.png", "status": "active",
         "kind": "image", "filename": "m1.png", "source": "ai_designer"},
        {"id": "m2", "storage_path": "lakeview/uploads/m2.png", "status": "active",
         "kind": "image", "filename": "m2.png", "source": "ai_designer"},
        {"id": "t1", "storage_path": "lakeview/uploads/t1.png", "status": "active",
         "kind": "image", "filename": "t1.png", "source": "upload"},
        {"id": "o1", "storage_path": "", "status": "active",
         "kind": "image", "filename": "broken.png", "source": "upload"},
        # archived — should be excluded by default status filter
        {"id": "skip", "storage_path": "lakeview/uploads/skip.png",
         "status": "archived", "kind": "image", "filename": "skip.png"},
    ]
    db = _FakeDB(rows)
    existing = {
        "lakeview/uploads/h1.png", "lakeview/thumbs/h1.jpg",
        "lakeview/uploads/h2.png", "lakeview/thumbs/h2.jpg",
        "lakeview/uploads/h3.png", "lakeview/thumbs/h3.jpg",
        "lakeview/uploads/t1.png",  # NO thumb cached
    }
    return db, existing


def test_scan_buckets_correctly(mixed_db):
    db, existing = mixed_db
    buckets = run(scan_media_assets(db, exists=lambda p: p in existing))
    counts = {c: len(v) for c, v in buckets.items() if c != "orphaned_storage_file"}
    assert counts == {
        "healthy": 3,
        "missing_file": 2,
        "missing_thumbnail": 1,
        "orphaned_record": 1,
    }
    # Archived row should be excluded from active-only scan
    all_ids = {r["id"] for items in buckets.values() for r in items}
    assert "skip" not in all_ids


def test_scan_respects_limit(mixed_db):
    db, existing = mixed_db
    buckets = run(scan_media_assets(db, exists=lambda p: p in existing, limit=2))
    total = sum(len(v) for v in buckets.values())
    assert total == 2


def test_scan_no_status_filter_includes_archived(mixed_db):
    db, existing = mixed_db
    buckets = run(scan_media_assets(db, exists=lambda p: p in existing,
                                    status_filter=None))
    all_ids = {r["id"] for items in buckets.values() for r in items}
    assert "skip" in all_ids


# ---------- Tests: archive behaviour ----------------------------------------

def test_archive_marks_status_and_adds_audit_fields():
    db = _FakeDB([
        {"id": "m1", "storage_path": "x", "status": "active"},
        {"id": "m2", "storage_path": "y", "status": "active"},
        {"id": "keep", "storage_path": "z", "status": "active"},
    ])
    n = run(archive_missing_files(db, ["m1", "m2"]))
    assert n == 2
    rows = {r["id"]: r for r in db.media_assets.rows}
    assert rows["m1"]["status"] == "archived"
    assert rows["m1"]["archived_reason"].startswith("orphan_cleanup")
    assert "archived_at" in rows["m1"]
    assert rows["m2"]["status"] == "archived"
    # Untouched row stays active
    assert rows["keep"]["status"] == "active"
    assert "archived_at" not in rows["keep"]


def test_archive_is_idempotent():
    """Re-running archive on already-archived rows should be a no-op."""
    db = _FakeDB([
        {"id": "m1", "storage_path": "x", "status": "archived",
         "archived_reason": "orphan_cleanup: original"},
    ])
    n = run(archive_missing_files(db, ["m1"]))
    assert n == 0
    assert db.media_assets.rows[0]["archived_reason"] == "orphan_cleanup: original"


def test_archive_empty_list_returns_zero():
    db = _FakeDB([])
    assert run(archive_missing_files(db, [])) == 0


# ---------- Tests: local-storage orphan scan --------------------------------

def test_local_orphan_scan(tmp_path):
    """Files on disk with no DB row are flagged; matched ones are not."""
    (tmp_path / "matched.jpg").write_bytes(b"x" * 100)
    (tmp_path / "orphan-1.jpg").write_bytes(b"x" * 250)
    (tmp_path / "orphan-2.png").write_bytes(b"x" * 80)
    db = _FakeDB([
        {"id": "a", "storage_path": "matched.jpg"},
        {"id": "b", "storage_path": "lakeview/uploads/remote.png"},  # remote, ignored
    ])
    orphans = run(scan_local_storage_for_orphans(db, tmp_path))
    names = {o["filename"] for o in orphans}
    assert names == {"orphan-1.jpg", "orphan-2.png"}
    sizes = {o["filename"]: o["size_bytes"] for o in orphans}
    assert sizes["orphan-1.jpg"] == 250
    assert sizes["orphan-2.png"] == 80


def test_local_orphan_scan_missing_dir(tmp_path):
    db = _FakeDB([])
    out = run(scan_local_storage_for_orphans(db, tmp_path / "nope"))
    assert out == []


# ---------- Tests: CLI ------------------------------------------------------

class TestCli:
    def test_default_is_dry_run(self):
        from scripts.media_orphans import build_parser
        args = build_parser().parse_args([])
        assert args.archive is False
        assert args.report is None
        assert args.status == "active"
        assert args.limit is None

    def test_archive_flag_set(self):
        from scripts.media_orphans import build_parser
        args = build_parser().parse_args(["--archive", "--limit", "10"])
        assert args.archive is True
        assert args.limit == 10

    def test_categories_constant_matches_spec(self):
        assert set(CATEGORIES) == {
            "healthy",
            "missing_file",
            "missing_thumbnail",
            "orphaned_record",
            "orphaned_storage_file",
        }
