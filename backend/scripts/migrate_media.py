#!/usr/bin/env python3
"""Inventory and checksum-copy Lakeview media to S3-compatible storage.

This script never deletes source or target objects and never mutates MongoDB.
It is a dry-run unless ``--apply`` is present. Existing remote object keys are
preserved; bare legacy filenames map to ``<app>/legacy/<filename>``, matching
``storage.py``'s transition fallback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from pymongo import MongoClient

def _env(name: str, *, required: bool = True) -> str | None:
    value = (os.environ.get(name) or "").strip()
    if required and not value:
        raise SystemExit(f"Required environment variable {name} is not set")
    return value or None


def _safe_key(value: str) -> str:
    raw = (value or "").strip().replace("\\", "/")
    path = PurePosixPath(raw)
    if not raw or raw.startswith("/") or ".." in path.parts:
        raise ValueError(f"Unsafe object path: {value!r}")
    return str(path)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _r2_client():
    return boto3.client(
        "s3",
        endpoint_url=_env("S3_ENDPOINT_URL"),
        aws_access_key_id=_env("S3_ACCESS_KEY_ID"),
        aws_secret_access_key=_env("S3_SECRET_ACCESS_KEY"),
        region_name=_env("S3_REGION", required=False) or "auto",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _load_assets() -> tuple[MongoClient, list[dict[str, Any]]]:
    client = MongoClient(_env("SOURCE_MONGO_URL"), serverSelectionTimeoutMS=10_000)
    client.admin.command("ping")
    database = client[_env("SOURCE_DB_NAME")]
    projection = {"_id": 0, "id": 1, "filename": 1, "storage_path": 1, "mime": 1, "size_bytes": 1}
    assets = list(database.media_assets.find({}, projection).sort("storage_path", 1))
    return client, assets


def _local_inventory(local_dir: Path) -> dict[str, Any]:
    files = sorted(path for path in local_dir.rglob("*") if path.is_file())
    aggregate = hashlib.sha256()
    total = 0
    manifest = []
    for path in files:
        data = path.read_bytes()
        relative = path.relative_to(local_dir).as_posix()
        digest = _sha256(data)
        total += len(data)
        aggregate.update(relative.encode())
        aggregate.update(bytes.fromhex(digest))
        manifest.append({"path": relative, "bytes": len(data), "sha256": digest})
    top_level = [item for item in manifest if "/" not in item["path"]]
    nested: dict[str, dict[str, int]] = {}
    for item in manifest:
        if "/" not in item["path"]:
            continue
        group = item["path"].split("/", 1)[0]
        entry = nested.setdefault(group, {"files": 0, "bytes": 0})
        entry["files"] += 1
        entry["bytes"] += item["bytes"]
    return {
        "local_directory": str(local_dir.resolve()),
        "files": len(files),
        "bytes": total,
        "top_level_files": len(top_level),
        "top_level_bytes": sum(item["bytes"] for item in top_level),
        "nested_groups": nested,
        "manifest_sha256": aggregate.hexdigest(),
        "manifest": manifest,
    }


def _source_bytes(asset: dict[str, Any], local_dir: Path, source_root: Path | None):
    storage_path = _safe_key(asset.get("storage_path") or "")
    if "/" not in storage_path:
        path = local_dir / storage_path
        if not path.is_file():
            raise FileNotFoundError(str(path))
        return path.read_bytes(), asset.get("mime") or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if source_root:
        path = source_root / storage_path
        if path.is_file():
            return path.read_bytes(), asset.get("mime") or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    raise FileNotFoundError(
        f"remote object is absent from the repository and neutral export: {storage_path}"
    )


def _repository_assets(local_dir: Path) -> list[dict[str, Any]]:
    """Describe repository-owned top-level media without requiring a database."""
    return [
        {
            "id": None,
            "filename": path.name,
            "storage_path": path.name,
            "mime": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "size_bytes": path.stat().st_size,
            "inventory_source": "repository",
        }
        for path in sorted(local_dir.glob("*"))
        if path.is_file()
    ]


def _target_key(storage_path: str, app_name: str) -> str:
    safe = _safe_key(storage_path)
    return safe if "/" in safe else f"{app_name}/legacy/{safe}"


def _existing_digest(client, bucket: str, key: str, verify_existing: bool) -> tuple[str | None, int | None]:
    try:
        head = client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        code = exc.response.get("Error", {}).get("Code")
        if status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
            return None, None
        raise
    digest = (head.get("Metadata") or {}).get("sha256")
    # Verification mode intentionally hashes the downloaded bytes even when
    # metadata is present. Metadata is useful for fast normal dry-runs, but it
    # is not independent evidence that the stored object is intact.
    if verify_existing:
        digest = _sha256(client.get_object(Bucket=bucket, Key=key)["Body"].read())
    return digest, head.get("ContentLength")


def _sync(args, assets: list[dict[str, Any]]) -> dict[str, Any]:
    client = _r2_client()
    bucket = _env("S3_BUCKET")
    app_name = (_env("STORAGE_APP_NAME", required=False) or "lakeview").strip("/")
    source_root = Path(args.source_root) if args.source_root else None
    local_dir = Path(args.local_dir)
    selected_assets = assets[: args.limit or None]
    stats = {"planned": len(selected_assets), "uploaded": 0, "verified": 0, "skipped": 0, "conflicts": 0, "missing_source": 0}
    items = []

    for asset in selected_assets:
        source_path = asset.get("storage_path") or ""
        key = _target_key(source_path, app_name)
        item = {"asset_id": asset.get("id"), "source_path": source_path, "target_key": key}
        try:
            data, content_type = _source_bytes(asset, local_dir, source_root)
        except FileNotFoundError as exc:
            item.update(status="missing_source", error=str(exc)[:200])
            stats["missing_source"] += 1
            items.append(item)
            continue
        digest = _sha256(data)
        item.update(bytes=len(data), sha256=digest)
        existing_digest, existing_size = _existing_digest(client, bucket, key, args.verify_existing)
        if existing_digest == digest and existing_size == len(data):
            item["status"] = "already_verified"
            stats["verified"] += 1
        elif existing_size is not None and not args.overwrite_mismatch:
            item.update(status="conflict_not_overwritten", existing_bytes=existing_size, existing_sha256=existing_digest)
            stats["conflicts"] += 1
        elif not args.apply:
            item["status"] = "would_upload"
            stats["skipped"] += 1
        else:
            client.put_object(
                Bucket=bucket, Key=key, Body=data, ContentType=content_type,
                Metadata={
                    "sha256": digest,
                    # S3 user metadata is transported as HTTP headers, so keep
                    # the diagnostic source path ASCII-safe.
                    "source-path": urllib.parse.quote(source_path, safe="/._-")[:1024],
                },
            )
            downloaded = client.get_object(Bucket=bucket, Key=key)["Body"].read()
            if _sha256(downloaded) != digest:
                raise RuntimeError(f"post-upload checksum mismatch for {key}")
            item["status"] = "uploaded_and_verified"
            stats["uploaded"] += 1
            stats["verified"] += 1
        items.append(item)
    stats["unverified"] = stats["planned"] - stats["verified"]
    return {
        "mode": "apply" if args.apply else "dry-run",
        "deletes_performed": 0,
        "verification_complete": stats["verified"] == stats["planned"],
        "stats": stats,
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("local-inventory", "local-sync", "inventory", "sync")
    )
    parser.add_argument("--local-dir", default=str(Path(__file__).resolve().parents[1] / "media_storage"))
    parser.add_argument("--source-root", help="Optional export directory containing full object keys")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--overwrite-mismatch", action="store_true")
    parser.add_argument(
        "--database-records-only",
        action="store_true",
        help="Do not preserve repository-local files that lack a media_assets record",
    )
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.overwrite_mismatch and not args.apply:
        raise SystemExit("--overwrite-mismatch requires --apply")

    source_client = None
    try:
        if args.command == "local-inventory":
            report = _local_inventory(Path(args.local_dir))
        elif args.command == "local-sync":
            report = _sync(args, _repository_assets(Path(args.local_dir)))
        else:
            source_client, assets = _load_assets()
            local_files = sorted(path for path in Path(args.local_dir).glob("*") if path.is_file())
            referenced_bare = {
                asset.get("storage_path") for asset in assets
                if "/" not in (asset.get("storage_path") or "")
            }
            unreferenced_local = [path for path in local_files if path.name not in referenced_bare]
            if args.command == "inventory":
                local_names = {path.name for path in local_files}
                bare = [a for a in assets if "/" not in (a.get("storage_path") or "")]
                remote = [a for a in assets if "/" in (a.get("storage_path") or "")]
                report = {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "database_assets": len(assets),
                    "bare_filename_records": len(bare),
                    "remote_object_records": len(remote),
                    "bare_files_present": sum(1 for a in bare if a.get("storage_path") in local_names),
                    "bare_files_missing": sorted(a.get("storage_path") for a in bare if a.get("storage_path") not in local_names),
                    "unreferenced_local_files": [path.name for path in unreferenced_local],
                    "local": _local_inventory(Path(args.local_dir)),
                    "remote_objects_verified": False,
                    "note": "Remote object existence requires a sync dry-run with source access.",
                }
            else:
                if not args.database_records_only:
                    assets.extend({
                        "id": None,
                        "filename": path.name,
                        "storage_path": path.name,
                        "mime": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                        "size_bytes": path.stat().st_size,
                        "inventory_source": "repository_unreferenced",
                    } for path in unreferenced_local)
                report = _sync(args, assets)

        encoded = json.dumps(report, indent=2, sort_keys=True)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(encoded + "\n")
        print(encoded)
        if args.command in {"local-sync", "sync"} and (
            report["stats"]["missing_source"] or report["stats"]["conflicts"]
        ):
            return 2
        return 0
    finally:
        if source_client:
            source_client.close()


if __name__ == "__main__":
    raise SystemExit(main())
