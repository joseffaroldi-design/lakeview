"""Phase 3 — Marketing Engine launch validation.

Generates real Lakeview promotions on preview, end-to-end:
  Smash Burger, Café Fries, Wings, Shrimp Po-Boy, Oyster Plate.

For each item:
  1. Build a synthetic food photo (PIL) — preview has no menu item images
  2. Upload via /api/media/upload
  3. AI Designer generate (auto_copy=True) → flyer + copy_pack
  4. Marketing Pack generate → 15-second promo video
  5. Verify thumbnails + downloads
  6. Record full result row

Writes a JSON report to /app/memory/launch/PHASE_3_RESULTS.json and downloads
all artifacts to /app/memory/launch/assets/.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import uuid
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

BASE = "https://food-graphics-lab.preview.emergentagent.com"
PW = os.environ.get("ADMIN_PASSWORD", "83CeLOZJQbOcopK0yYmNtdRQg4VPii8o")
OUT = Path("/app/memory/launch/assets")
OUT.mkdir(parents=True, exist_ok=True)


PROMOS = [
    {
        "slug": "smash-burger",
        "name": "Smash Burger",
        "features": ["2 Burger Patties", "American Cheese", "Pickled Onions",
                     "House Aioli", "Comes With Fries"],
        "price": "$13.95",
        "headline": "WEEKEND SMASH",
        "cta": "Order Now",
        "theme": "comic_pop",
        "color": (210, 90, 55),       # burger brown
        "menu_item_key": None,
    },
    {
        "slug": "cafe-fries",
        "name": "Café Fries",
        "features": ["Hand-Cut Fries", "Cajun Seasoning",
                     "Garlic Aioli", "Topped With Cheese"],
        "price": "$8.50",
        "headline": "CAJUN GOLD",
        "cta": "Try Today",
        "theme": "vintage_diner",
        "color": (230, 175, 60),      # fries yellow
        "menu_item_key": None,
    },
    {
        "slug": "wings",
        "name": "Chicken Wings",
        "features": ["6 Wings", "House Buffalo Sauce", "Blue Cheese Dip",
                     "Celery & Carrots"],
        "price": "$10.95",
        "headline": "WING NIGHT",
        "cta": "Order Now",
        "theme": "bold_purple_pop",
        "color": (200, 70, 50),       # wing red
        "menu_item_key": None,
    },
    {
        "slug": "shrimp-poboy",
        "name": "Shrimp Po-Boy",
        "features": ["Fried Gulf Shrimp", "Lettuce", "Tomato", "Remoulade Sauce",
                     "On New Orleans French Bread"],
        "price": "$14.95",
        "headline": "NOLA CLASSIC",
        "cta": "Get Yours",
        "theme": "casual_teal",
        "color": (235, 195, 130),     # shrimp golden
        "menu_item_key": None,
    },
    {
        "slug": "oyster-plate",
        "name": "Fried Oyster Plate",
        "features": ["Gulf Oysters", "Cornmeal Crust", "Garlic Aioli",
                     "Comes With Fries"],
        "price": "$18.95",
        "headline": "GULF FRESH",
        "cta": "Order Now",
        "theme": "distressed_orange",
        "color": (180, 130, 70),      # oyster brown
        "menu_item_key": None,
    },
]


def fresh_ip() -> str:
    return f"198.51.100.{uuid.uuid4().int % 250 + 1}"


def login() -> str:
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"password": PW},
        headers={"X-Forwarded-For": fresh_ip()},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["token"]


def make_food_photo(promo: dict, w: int = 1200, h: int = 1200) -> bytes:
    """Synthetic food photo — a saturated swatch with the dish name baked in.
    Looks like a stylized 'top-down' food shot; good enough for a code-side
    end-to-end test of the flyer + video pipeline."""
    base_color = promo["color"]
    img = Image.new("RGB", (w, h), base_color)
    d = ImageDraw.Draw(img)
    # Center dark plate
    plate_r = int(min(w, h) * 0.42)
    cx, cy = w // 2, h // 2
    plate_color = (max(0, base_color[0] - 60),
                   max(0, base_color[1] - 60),
                   max(0, base_color[2] - 60))
    d.ellipse((cx - plate_r, cy - plate_r, cx + plate_r, cy + plate_r),
              fill=plate_color)
    # Highlight ring
    d.ellipse((cx - plate_r, cy - plate_r, cx + plate_r, cy + plate_r),
              outline=(255, 255, 255, 120), width=8)
    # Inner garnish blobs
    for i, dx in enumerate(range(-3, 4)):
        ox = cx + dx * 60 + (i * 7)
        oy = cy + ((i * 31) % 80) - 40
        c = (min(255, base_color[0] + 30),
             min(255, base_color[1] + 30),
             min(255, base_color[2] + 30))
        d.ellipse((ox - 40, oy - 40, ox + 40, oy + 40), fill=c)
    # Label band at bottom
    try:
        font = ImageFont.truetype("/app/backend/fonts/BebasNeue-Regular.ttf", 80)
    except Exception:
        font = ImageFont.load_default()
    label = promo["name"].upper()
    bbox = d.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    d.rectangle((0, h - 140, w, h), fill=(20, 20, 28))
    d.text(((w - tw) // 2, h - 110), label,
           fill=(255, 245, 220), font=font)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def upload(token: str, promo: dict) -> dict:
    photo_bytes = make_food_photo(promo)
    (OUT / f"{promo['slug']}-source.jpg").write_bytes(photo_bytes)
    r = requests.post(
        f"{BASE}/api/media/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (f"{promo['slug']}.jpg", photo_bytes, "image/jpeg")},
        data={"folder": "Launch Validation", "tags": f"launch,{promo['slug']}"},
        timeout=45,
    )
    r.raise_for_status()
    return r.json()


def designer_generate(token: str, asset_id: str, promo: dict) -> str:
    r = requests.post(
        f"{BASE}/api/ai-designer/generate",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json={
            "source_asset_id": asset_id,
            "item_name": promo["name"],
            "features": promo["features"],
            "price": promo["price"],
            "theme": promo["theme"],
            "auto_copy": True,
            "remove_background": False,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["job_id"]


def marketing_pack_generate(token: str, asset_id: str, promo: dict) -> str:
    r = requests.post(
        f"{BASE}/api/marketing-pack/generate",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json={
            "source_asset_id": asset_id,
            "menu_item_key": promo.get("menu_item_key"),
            "name": promo["name"],
            "price": promo["price"],
            "headline": promo["headline"],
            "cta": promo["cta"],
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["job_id"]


def wait_designer(token: str, job_id: str, timeout: int = 180) -> dict:
    """Poll AI Designer job to completion."""
    deadline = time.time() + timeout
    H = {"Authorization": f"Bearer {token}"}
    last = {}
    while time.time() < deadline:
        r = requests.get(f"{BASE}/api/ai-designer/job/{job_id}",
                         headers=H, timeout=15)
        try:
            last = r.json()
        except Exception:
            last = {"status": "?", "raw": r.text[:200]}
        if last.get("status") == "completed":
            return last
        if last.get("status") == "failed":
            raise RuntimeError(f"Designer job {job_id} failed: {last.get('error')}")
        time.sleep(5)
    raise TimeoutError(f"Designer job {job_id} did not complete in {timeout}s: {last}")


def wait_pack(token: str, job_id: str, timeout: int = 180) -> dict:
    deadline = time.time() + timeout
    H = {"Authorization": f"Bearer {token}"}
    last = {}
    while time.time() < deadline:
        r = requests.get(f"{BASE}/api/marketing-pack/job/{job_id}",
                         headers=H, timeout=15)
        try:
            last = r.json()
        except Exception:
            last = {"status": "?", "raw": r.text[:200]}
        if last.get("status") == "completed":
            return last
        if last.get("status") == "failed":
            raise RuntimeError(f"Pack {job_id} failed: {last.get('error')}")
        time.sleep(5)
    raise TimeoutError(f"Pack {job_id} did not complete in {timeout}s: {last}")


def download(token: str, asset_id: str, slug: str, kind: str, ext: str) -> dict:
    """Download both the file and its thumbnail. Returns size info."""
    H = {"Authorization": f"Bearer {token}"}
    info = {"asset_id": asset_id, "kind": kind}
    try:
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
    except Exception as e:  # noqa: BLE001
        info["file_ok"] = False
        info["file_error"] = str(e)
    try:
        tr = requests.get(f"{BASE}/api/media/thumb/{asset_id}", headers=H, timeout=30)
        info["thumb_ok"] = tr.status_code == 200 and len(tr.content) > 200
        info["thumb_status"] = tr.status_code
        info["thumb_size"] = len(tr.content)
    except Exception as e:  # noqa: BLE001
        info["thumb_ok"] = False
        info["thumb_error"] = str(e)
    return info


def main():
    print("\n" + "=" * 60)
    print("PHASE 3 — MARKETING ENGINE VALIDATION")
    print("=" * 60)
    token = login()
    print(f"[login] OK (token len {len(token)})")

    report = {"started_at": time.time(), "base_url": BASE, "promotions": []}
    for promo in PROMOS:
        slug = promo["slug"]
        print(f"\n── {slug.upper()} ────────────────────────────────")
        row = {"slug": slug, "name": promo["name"], "theme": promo["theme"]}
        try:
            t0 = time.time()
            asset = upload(token, promo)
            row["source_asset_id"] = asset["id"]
            row["source_size"] = asset["size_bytes"]
            print(f"  upload         OK  asset={asset['id'][:8]}  {asset['size_bytes']/1024:.0f}KB")

            # Kick off both pipelines in parallel — they're independent
            designer_job = designer_generate(token, asset["id"], promo)
            print(f"  designer_kick  OK  job={designer_job[:8]}")
            pack_job = marketing_pack_generate(token, asset["id"], promo)
            print(f"  pack_kick      OK  job={pack_job[:8]}")
            row["designer_job_id"] = designer_job
            row["pack_job_id"] = pack_job

            # Wait designer first (it's typically faster)
            d_result = wait_designer(token, designer_job)
            row["designer_ms"] = int((time.time() - t0) * 1000)
            print(f"  designer       OK  {row['designer_ms']}ms")
            # Job rows store the first variation's flyer
            variations = d_result.get("variations") or []
            flyer_asset_id = (variations[0].get("asset_id")
                              if variations else None)
            row["flyer_asset_id"] = flyer_asset_id
            row["variations_count"] = len(variations)
            row["copy_pack"] = d_result.get("copy_pack") or {}
            row["has_copy"] = bool(row["copy_pack"])

            # Now wait pack (takes longer due to video render)
            p_result = wait_pack(token, pack_job, timeout=240)
            row["pack_ms"] = int((time.time() - t0) * 1000)
            result_dict = p_result.get("result") or {}
            row["video_asset_id"] = result_dict.get("video_asset_id")
            row["video_skipped"] = row["video_asset_id"] is None
            print(f"  pack           OK  total {row['pack_ms']}ms  "
                  f"video={'yes' if row['video_asset_id'] else 'skipped'}")

            # Sprint 16B.4 regression — no copy fields in pack result
            row["pack_clean"] = all(
                k not in result_dict
                for k in ("caption", "hashtags", "sms", "email", "gbp")
            )

            # Download artifacts
            if flyer_asset_id:
                row["flyer"] = download(token, flyer_asset_id, slug, "flyer", "png")
                print(f"  flyer dl       {'OK' if row['flyer']['file_ok'] else 'FAIL'}  "
                      f"{row['flyer'].get('file_size', 0)/1024:.0f}KB  "
                      f"thumb={row['flyer'].get('thumb_ok')}")
            if row["video_asset_id"]:
                row["video"] = download(token, row["video_asset_id"], slug, "video", "mp4")
                print(f"  video dl       {'OK' if row['video']['file_ok'] else 'FAIL'}  "
                      f"{row['video'].get('file_size', 0)/1024:.0f}KB  "
                      f"thumb={row['video'].get('thumb_ok')}")

            row["status"] = "ok"
        except Exception as e:  # noqa: BLE001
            row["status"] = "fail"
            row["error"] = str(e)
            print(f"  *** ERROR: {e}")
        report["promotions"].append(row)

    report["finished_at"] = time.time()
    report["duration_s"] = int(report["finished_at"] - report["started_at"])
    report["pass_count"] = sum(1 for p in report["promotions"] if p.get("status") == "ok")
    report["fail_count"] = len(report["promotions"]) - report["pass_count"]

    out_path = Path("/app/memory/launch/PHASE_3_RESULTS.json")
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print("\n" + "=" * 60)
    print(f"RESULTS  pass={report['pass_count']}  fail={report['fail_count']}  "
          f"duration={report['duration_s']}s")
    print(f"Report → {out_path}")
    print("=" * 60)
    return 0 if report["fail_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
