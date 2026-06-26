"""Sprint 19 — Real Menu Validation harness.

Generates one Creative-Director-recommended flyer per real Lakeview menu
item and prints a table: item · category · recommended theme · score ·
label. Helps identify rendering problems WITHOUT modifying the engine.

USAGE:
    cd /app/backend
    python scripts/menu_validation.py
      [--limit N]              # cap how many items to process
      [--source-asset <id>]    # use this photo for every item (default: pick first food image)

The script intentionally does NOT write a markdown report — per Sprint 19
scope ("no more documentation"). It outputs to STDOUT and exits with
non-zero if any generation failed, so it can also gate CI.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

# Make backend importable when running this script directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402


def _read_base_url() -> str:
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                return ln.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL missing")


def _login(api: str, password: str) -> str:
    import uuid
    fresh_ip = f"198.51.100.{uuid.uuid4().int % 250 + 1}"
    r = requests.post(f"{api}/auth/login", json={"password": password},
                      headers={"X-Forwarded-For": fresh_ip}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def _menu_items(api: str, auth: Dict[str, str]) -> List[Dict]:
    r = requests.get(f"{api}/menu", headers=auth, timeout=15)
    r.raise_for_status()
    out: List[Dict] = []
    import re
    slug = lambda s: re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")  # noqa: E731
    for cat in r.json():
        cat_label = cat.get("display_name") or cat.get("name") or "Menu"
        for it in cat.get("items", []) or []:
            if not it.get("name"):
                continue
            features = it.get("features") or []
            if not features and it.get("description"):
                features = [s.strip() for s in str(it["description"]).split(",") if s.strip()][:4]
            out.append({
                "item_key": it.get("item_key") or f"{slug(cat_label)}::{slug(it['name'])}",
                "name": it["name"],
                "price": it.get("price", ""),
                "features": features,
                "category": cat_label,
            })
    return out


def _pick_default_photo(api: str, auth: Dict[str, str]) -> str:
    r = requests.get(f"{api}/media/assets?limit=20&kind=image",
                     headers=auth, timeout=15)
    r.raise_for_status()
    for a in r.json().get("assets", []):
        # Skip generated flyers — we want a clean food photo.
        if a.get("source") == "ai_designer":
            continue
        if a.get("width", 0) >= 256:
            return a["id"]
    raise RuntimeError("No usable photo asset found")


def _recommend_theme(api: str, auth: Dict[str, str], item: Dict) -> Tuple[str, str]:
    r = requests.post(f"{api}/creative-director/recommend", headers=auth,
                      json={"item_key": item["item_key"],
                            "food_type": item["name"],
                            "features": item["features"]}, timeout=15)
    r.raise_for_status()
    rec = (r.json().get("recommendations") or [{}])[0]
    return rec.get("id", ""), rec.get("label", "")


def _generate(api: str, auth: Dict[str, str], item: Dict,
              theme: str, source_asset: str) -> Optional[Dict]:
    r = requests.post(f"{api}/ai-designer/generate", headers=auth, json={
        "source_asset_id": source_asset,
        "item_name": item["name"],
        "features": item["features"],
        "price": (f"${item['price']}" if item.get("price") and
                  not str(item["price"]).startswith("$") else item.get("price", "")),
        "theme": theme,
        "item_key": item["item_key"],
    }, timeout=30)
    r.raise_for_status()
    job_id = r.json().get("job_id")
    if not job_id:
        return None
    # Poll
    for _ in range(40):
        rr = requests.get(f"{api}/ai-designer/job/{job_id}",
                          headers=auth, timeout=15)
        rr.raise_for_status()
        body = rr.json()
        if body.get("status") in ("completed", "failed"):
            return body
        time.sleep(1)
    return None


def _scores(job: Dict) -> Tuple[List[float], List[str]]:
    scores, labels = [], []
    for v in job.get("variations", []):
        if v.get("status") == "completed":
            if v.get("quality_score") is not None:
                scores.append(float(v["quality_score"]))
            if v.get("quality_label"):
                labels.append(v["quality_label"])
    return scores, labels


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="Limit number of menu items processed (0 = all)")
    ap.add_argument("--source-asset", default=None,
                    help="Asset ID to use as the source photo for every item")
    args = ap.parse_args()

    api = f"{_read_base_url()}/api"
    pwd = os.environ.get("ADMIN_PASSWORD")
    if not pwd:
        raise RuntimeError("ADMIN_PASSWORD env var missing")
    token = _login(api, pwd)
    auth = {"Authorization": f"Bearer {token}"}

    items = _menu_items(api, auth)
    if args.limit and args.limit > 0:
        items = items[: args.limit]
    if not items:
        print("No menu items found.")
        return 1

    source_asset = args.source_asset or _pick_default_photo(api, auth)
    print(f"Source photo: {source_asset}")
    print(f"Running {len(items)} menu items...\n")
    print(f"{'#':>3}  {'item':<28} {'category':<14} {'theme':<22} {'rank':<14} "
          f"{'avg':>6}  scores                  labels")
    print("-" * 130)

    failures = 0
    rows = []
    t_start = time.perf_counter()
    for i, item in enumerate(items, 1):
        try:
            theme, rank = _recommend_theme(api, auth, item)
            if not theme:
                print(f"{i:>3}  {item['name'][:28]:<28} {item['category'][:14]:<14} "
                      f"{'NO_REC':<22} -")
                failures += 1
                continue
            job = _generate(api, auth, item, theme, source_asset)
            if not job or job.get("status") != "completed":
                print(f"{i:>3}  {item['name'][:28]:<28} {item['category'][:14]:<14} "
                      f"{theme[:22]:<22} {rank[:14]:<14} GENERATE_FAILED")
                failures += 1
                continue
            scores, labels = _scores(job)
            avg = (sum(scores) / len(scores)) if scores else 0.0
            print(f"{i:>3}  {item['name'][:28]:<28} {item['category'][:14]:<14} "
                  f"{theme[:22]:<22} {rank[:14]:<14} {avg:>6.1f}  "
                  f"{str([round(s, 1) for s in scores]):<22}  {','.join(labels)}")
            rows.append((item, theme, avg, scores, labels))
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"{i:>3}  {item['name'][:28]:<28} ERROR {e}")

    dt = time.perf_counter() - t_start
    print("-" * 130)
    if rows:
        rows.sort(key=lambda r: r[2])
        worst = rows[0]
        best = rows[-1]
        all_scores = [r[2] for r in rows]
        print(f"\nSummary: ran {len(rows)} OK, {failures} failed in {dt:.1f}s")
        print(f"  avg quality:  {sum(all_scores) / len(all_scores):.1f}")
        print(f"  worst:        {worst[0]['name']:<28} ({worst[1]:<22}) avg={worst[2]:.1f}")
        print(f"  best:         {best[0]['name']:<28} ({best[1]:<22}) avg={best[2]:.1f}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
