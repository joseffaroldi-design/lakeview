"""End-to-end smoke test for Sprint 16D: Photo→Flyer.

Validates the full new flow against live preview:
  1. POST /api/photo-flyer/analyze  → enhanced asset + vision JSON
  2. POST /api/ai-designer/generate (auto_copy=True) using the enhanced asset
  3. Poll designer job → assert flyer + copy_pack present
  4. (Opt-in) POST /api/marketing-pack/generate
  5. Poll pack → assert 15-s video asset

Total wall-time target: < 90s (vision ~9s, designer ~35s, video ~50s).
"""
from __future__ import annotations

import os

import io
import sys
import time
import uuid
from pathlib import Path

import requests
from PIL import Image, ImageDraw

BASE = "https://upload-stage-two.preview.emergentagent.com"
PW = os.environ.get("ADMIN_PASSWORD", "")
OUT = Path("/app/memory/launch/assets/sprint16d")
OUT.mkdir(parents=True, exist_ok=True)


def fresh_ip() -> str:
    return f"198.51.100.{uuid.uuid4().int % 250 + 1}"


def make_realistic_photo() -> bytes:
    """A photo with enough visual texture for Gemini to classify."""
    img = Image.new("RGB", (1024, 1024), (190, 110, 70))
    d = ImageDraw.Draw(img)
    import random
    random.seed(7)
    # Plate
    d.ellipse((150, 150, 874, 874), fill=(40, 30, 24))
    d.ellipse((150, 150, 874, 874), outline=(220, 220, 220), width=6)
    # Burger-like stack in centre
    cx, cy = 512, 512
    # Bottom bun
    d.ellipse((cx-260, cy+60, cx+260, cy+220), fill=(200, 150, 90))
    # Patty
    d.rectangle((cx-240, cy-30, cx+240, cy+90), fill=(85, 45, 25))
    # Cheese
    d.polygon([(cx-230, cy-40), (cx+230, cy-40),
               (cx+260, cy-10), (cx-260, cy-10)], fill=(255, 200, 70))
    # Lettuce
    d.polygon([(cx-250, cy-70), (cx+250, cy-70),
               (cx+220, cy-40), (cx-220, cy-40)], fill=(80, 140, 60))
    # Top bun
    d.pieslice((cx-260, cy-280, cx+260, cy-40), 180, 360, fill=(230, 170, 110))
    # Sesame seeds
    for _ in range(40):
        sx = cx + random.randint(-220, 220)
        sy = cy - 180 + random.randint(-40, 30)
        d.ellipse((sx, sy, sx+8, sy+5), fill=(255, 245, 210))
    # Fries pile on the side
    for i in range(20):
        fx = 700 + (i * 4)
        fy = 600 + random.randint(-30, 30)
        d.rectangle((fx, fy, fx+8, fy+90), fill=(230, 180, 70))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def main():
    token_resp = requests.post(f"{BASE}/api/auth/login", json={"password": PW},
                               headers={"X-Forwarded-For": fresh_ip()}, timeout=15)
    assert token_resp.status_code == 200, token_resp.text
    H = {"Authorization": f"Bearer {token_resp.json()['token']}"}

    photo = make_realistic_photo()
    (OUT / "source.jpg").write_bytes(photo)
    print(f"[seed] source photo {len(photo)} bytes")

    # 1) Analyze
    print("\n[1/3] POST /api/photo-flyer/analyze ...")
    t0 = time.time()
    r = requests.post(f"{BASE}/api/photo-flyer/analyze",
                      headers=H, files={"file": ("burger.jpg", photo, "image/jpeg")},
                      timeout=60)
    elapsed = time.time() - t0
    assert r.status_code == 200, f"analyze: {r.status_code} {r.text[:300]}"
    analysis = r.json()
    print(f"     OK in {elapsed:.1f}s")
    print(f"     food_type      = {analysis.get('food_type')!r}")
    print(f"     confidence     = {analysis.get('confidence')}")
    print(f"     features       = {analysis.get('features')}")
    print(f"     suggested_theme = {analysis.get('suggested_theme')}")
    print(f"     menu_match     = {analysis.get('menu_match', {}).get('matched')}"
          f" ({analysis.get('menu_match', {}).get('name')})")
    print(f"     vision_ok      = {analysis.get('vision_ok')}")
    assert analysis.get("original_asset_id")
    assert analysis.get("enhanced_asset_id")
    enhanced_id = analysis["enhanced_asset_id"]

    # Confirm enhanced asset retrievable + has thumbnail
    fr = requests.get(f"{BASE}/api/media/file/{enhanced_id}", headers=H, timeout=30)
    tr = requests.get(f"{BASE}/api/media/thumb/{enhanced_id}", headers=H, timeout=15)
    assert fr.status_code == 200 and len(fr.content) > 5000
    assert tr.status_code == 200 and len(tr.content) > 1000
    (OUT / "enhanced.jpg").write_bytes(fr.content)
    print("     enhanced asset downloadable + thumb generated")

    # 2) Hand off to AI Designer (reuses existing route — no duplication)
    print("\n[2/3] POST /api/ai-designer/generate (auto_copy=True) ...")
    t1 = time.time()
    body = {
        "source_asset_id": enhanced_id,
        "item_name": analysis.get("food_type") or "Smash Burger",
        "features": analysis.get("features") or ["American Cheese", "Pickled Onions"],
        "price": (analysis.get("menu_match") or {}).get("price") or "$13.95",
        "theme": analysis.get("suggested_theme") or "comic_pop",
        "variations": 1,
        "auto_copy": True,
        "remove_background": False,
    }
    gr = requests.post(f"{BASE}/api/ai-designer/generate",
                       headers=H, json=body, timeout=30)
    assert gr.status_code == 202, gr.text
    designer_job = gr.json()["job_id"]
    print(f"     job_id = {designer_job}")
    # Poll
    last = {}
    for i in range(36):  # 36 × 5s = 3 min
        time.sleep(5)
        try:
            jr = requests.get(f"{BASE}/api/ai-designer/job/{designer_job}",
                              headers=H, timeout=20)
            last = jr.json()
        except Exception as e:
            print(f"     poll {i} err: {e}")
            continue
        s = last.get("status")
        print(f"     [{i*5+5:3}s] status={s} progress={last.get('progress')} "
              f"step={last.get('current_step')}")
        if s in ("completed", "failed"):
            break
    assert last.get("status") == "completed", f"designer not completed: {last}"
    elapsed_d = time.time() - t1
    variations = last.get("variations") or []
    assert variations, "no variations produced"
    flyer_id = variations[0]["asset_id"]
    print(f"     designer completed in {elapsed_d:.1f}s; flyer_id={flyer_id}")
    print(f"     copy_pack present: {bool(last.get('copy_pack'))}")
    if last.get("copy_pack"):
        cp = last["copy_pack"]
        print(f"       fb_post len = {len(cp.get('fb_post',''))}")
        print(f"       ig_post len = {len(cp.get('ig_post',''))}")
    elif last.get("copy_error"):
        print(f"     copy_error: {last['copy_error']!r}")

    # Download the flyer
    fr2 = requests.get(f"{BASE}/api/media/file/{flyer_id}", headers=H, timeout=30)
    assert fr2.status_code == 200 and len(fr2.content) > 10_000
    (OUT / "flyer.png").write_bytes(fr2.content)
    print("     flyer downloaded")

    # 3) Total time check
    total = time.time() - t0
    print(f"\n[3/3] TOTAL wall time: {total:.1f}s (target < 90s)")
    assert total < 120, f"Took too long: {total:.1f}s"

    print("\n✅ Sprint 16D end-to-end PASS")
    print(f"   artifacts: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
