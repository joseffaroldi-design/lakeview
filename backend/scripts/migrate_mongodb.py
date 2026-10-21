#!/usr/bin/env python3
"""Inventory, compare, and non-destructively sync MongoDB databases.

The tool never drops collections or deletes documents. ``sync`` is a dry-run
unless ``--apply`` is supplied; applied runs use ``replace_one(..., upsert=True)``
by ``_id``, making repeat runs safe and useful for a final delta sync.

Connection strings are read from named environment variables so credentials do
not land in shell history or reports.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from bson import BSON, json_util
from pymongo import IndexModel, MongoClient, ReplaceOne


def _secret_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise SystemExit(f"Required environment variable {name} is not set")
    return value


def _db(uri_env: str, db_name_env: str):
    client = MongoClient(_secret_env(uri_env), serverSelectionTimeoutMS=10_000)
    client.admin.command("ping")
    return client, client[_secret_env(db_name_env)]


def _collections(db, selected: list[str] | None = None) -> list[str]:
    names = sorted(name for name in db.list_collection_names() if not name.startswith("system."))
    if selected:
        requested = set(selected)
        missing = requested.difference(names)
        if missing:
            raise SystemExit(f"Source collections not found: {', '.join(sorted(missing))}")
        names = [name for name in names if name in requested]
    return names


def _collection_checksum(collection) -> str:
    digest = hashlib.sha256()
    for document in collection.find({}).sort("_id", 1):
        payload = BSON.encode(document)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def inventory(db, selected: list[str] | None = None, checksums: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "database": db.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "collections": {},
    }
    for name in _collections(db, selected):
        collection = db[name]
        entry: dict[str, Any] = {
            "documents": collection.count_documents({}),
            "indexes": sorted(collection.index_information().keys()),
        }
        if checksums:
            entry["sha256"] = _collection_checksum(collection)
        result["collections"][name] = entry
    result["totals"] = {
        "collections": len(result["collections"]),
        "documents": sum(item["documents"] for item in result["collections"].values()),
    }
    return result


def _write_report(report: dict[str, Any], output: str | None) -> None:
    encoded = json.dumps(report, indent=2, default=json_util.default, sort_keys=True)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded + "\n")
    print(encoded)


def _index_models(source_collection) -> Iterable[IndexModel]:
    for name, spec in source_collection.index_information().items():
        if name == "_id_":
            continue
        options = {"name": name}
        for key in (
            "unique", "sparse", "expireAfterSeconds", "partialFilterExpression",
            "hidden", "collation", "weights", "default_language", "language_override",
        ):
            if key in spec:
                options[key] = spec[key]
        yield IndexModel(spec["key"], **options)


def sync_databases(source, target, selected: list[str] | None, apply: bool, batch_size: int) -> dict[str, Any]:
    report: dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "source_database": source.name,
        "target_database": target.name,
        "deletes_performed": 0,
        "collections": {},
    }
    for name in _collections(source, selected):
        src = source[name]
        planned = src.count_documents({})
        entry = {"source_documents": planned, "upserts_planned": planned, "batches": 0}
        report["collections"][name] = entry
        if not apply:
            continue

        dst = target[name]
        models = list(_index_models(src))
        if models:
            dst.create_indexes(models)

        operations = []
        for document in src.find({}).sort("_id", 1):
            operations.append(ReplaceOne({"_id": document["_id"]}, document, upsert=True))
            if len(operations) >= batch_size:
                dst.bulk_write(operations, ordered=True)
                entry["batches"] += 1
                operations = []
        if operations:
            dst.bulk_write(operations, ordered=True)
            entry["batches"] += 1
        entry["target_documents_after"] = dst.count_documents({})
        entry["source_sha256"] = _collection_checksum(src)
        entry["target_sha256"] = _collection_checksum(dst)
        entry["verified_equal"] = (
            entry["source_documents"] == entry["target_documents_after"]
            and entry["source_sha256"] == entry["target_sha256"]
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inventory", "compare", "sync"))
    parser.add_argument("--source-uri-env", default="SOURCE_MONGO_URL")
    parser.add_argument("--source-db-env", default="SOURCE_DB_NAME")
    parser.add_argument("--target-uri-env", default="TARGET_MONGO_URL")
    parser.add_argument("--target-db-env", default="TARGET_DB_NAME")
    parser.add_argument("--collection", action="append", dest="collections")
    parser.add_argument("--skip-checksums", action="store_true")
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    source_client, source = _db(args.source_uri_env, args.source_db_env)
    target_client = None
    try:
        if args.command == "inventory":
            report = inventory(source, args.collections, not args.skip_checksums)
        else:
            target_client, target = _db(args.target_uri_env, args.target_db_env)
            if args.command == "compare":
                report = {
                    "source": inventory(source, args.collections, not args.skip_checksums),
                    "target": inventory(target, args.collections, not args.skip_checksums),
                }
                report["equal"] = report["source"]["collections"] == report["target"]["collections"]
            else:
                if args.batch_size < 1 or args.batch_size > 1000:
                    raise SystemExit("--batch-size must be between 1 and 1000")
                report = sync_databases(source, target, args.collections, args.apply, args.batch_size)
        _write_report(report, args.output)
        return 0
    finally:
        source_client.close()
        if target_client:
            target_client.close()


if __name__ == "__main__":
    raise SystemExit(main())
