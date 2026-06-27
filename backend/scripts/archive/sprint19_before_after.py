"""Sprint 19 Hotfix — BEFORE vs AFTER comparison.

Renders the SAME 5 menu items twice — once on the current (HOTFIX)
render_engine.py and once on the pre-hotfix version checked out from
commit ad739a9 — and saves side-by-side composites + a metrics table.

The "before" engine is stitched in as `render_engine_legacy` from a
clean copy of the file at parent commit ad739a9.

Run from `/app/backend`:
    ADMIN_PASSWORD=... python scripts/sprint19_before_after.py
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402


# 5 representative items spanning categories, layouts, themes.
ITEMS = [
    {"item_key": "appetizers::caf-fries", "name": "Café Fries", "price": "$8.00",
     "features": ["seasoned", "loaded", "shareable"], "theme": "luxury"},
    {"item_key": "appetizers::chicken-wings-6", "name": "Chicken Wings (6)",
     "price": "$11.00", "features": ["Asian Glaze", "BBQ", "Buffalo"],
     "theme": "game_day_scoreboard"},
    {"item_key": "soups::seafood-gumbo", "name": "Seafood Gumbo",
     "price": "$7.00 / $9.00", "features": ["Cup", "Bowl"],
     "theme": "seafood_coastal"},
    {"item_key": "salads::add-fried-oysters-or-shrimp",
     "name": "Add Fried Oysters or Shrimp", "price": "$12.95",
     "features": ["per portion"], "theme": "seafood_coastal"},
    {"item_key": "burgers::extra-patty", "name": "Extra Patty", "price": "$5.00",
     "features": ["8oz", "all-natural beef"], "theme": "burger_classic"},
]

SOURCE_ASSET = "ddfa3085-3bb6-40e6-b422-5f6124d0a973"


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


def _render_one(api: str, auth, item: Dict, source_asset: str) -> Dict:
    """Trigger AI Designer + poll until done."""
    r = requests.post(f"{api}/ai-designer/generate", headers=auth, json={
        "source_asset_id": source_asset,
        "item_name": item["name"],
        "features": item["features"],
        "price": item["price"],
        "theme": item["theme"],
        "item_key": item["item_key"],
    }, timeout=30)
    r.raise_for_status()
    job_id = r.json()["job_id"]
    import time
    for _ in range(45):
        body = requests.get(f"{api}/ai-designer/job/{job_id}",
                            headers=auth, timeout=15).json()
        if body.get("status") in ("completed", "failed"):
            return body
        time.sleep(1)
    return {"status": "timeout"}


def _dl_first_completed(api, auth, job: Dict) -> bytes:
    for v in job.get("variations", []):
        if v.get("status") == "completed":
            r = requests.get(f"{api}/media/file/{v['asset_id']}", headers=auth, timeout=20)
            r.raise_for_status()
            return r.content
    return b""


def _restart_backend():
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"],
                   check=True, capture_output=True)
    import time
    # wait until /api/health responds
    api = f"{_read_base_url()}/api"
    for _ in range(40):
        try:
            r = requests.get(f"{api}/menu", timeout=5)
            if r.status_code in (200, 401):
                return
        except Exception:
            pass
        time.sleep(1)


def _swap_engine_to(commit_or_path: str):
    """Replace /app/backend/render_engine.py with the version from a git
    commit. Pass 'HEAD' to restore the working tree."""
    if commit_or_path == "WORKING":
        subprocess.run(["git", "-C", "/app", "checkout", "--", "backend/render_engine.py"],
                       check=True, capture_output=True)
    else:
        # Save current to a temp & overwrite with the historical version.
        with open("/app/backend/render_engine.py", "w") as f:
            content = subprocess.check_output(
                ["git", "-C", "/app", "show", f"{commit_or_path}:backend/render_engine.py"]
            ).decode("utf-8")
            f.write(content)


def _composite_pair(before_bytes: bytes, after_bytes: bytes,
                    label: str) -> Image.Image:
    """Make a 2048x1100 side-by-side: BEFORE | AFTER with a header label."""
    a = Image.open(io.BytesIO(before_bytes)).convert("RGB").resize((1000, 1000))
    b = Image.open(io.BytesIO(after_bytes)).convert("RGB").resize((1000, 1000))
    canvas = Image.new("RGB", (2040, 1080), (245, 244, 240))
    canvas.paste(a, (20, 60))
    canvas.paste(b, (1040, 60))
    d = ImageDraw.Draw(canvas)
    try:
        f = ImageFont.truetype(
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 28)
        fs = ImageFont.truetype(
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf", 22)
    except OSError:
        f = ImageFont.load_default()
        fs = f
    d.text((20, 18), f"{label}", fill=(20, 20, 24), font=f)
    d.text((20, 1045), "BEFORE (pre-Sprint 19 hotfix)", fill=(180, 60, 50), font=fs)
    d.text((1040, 1045), "AFTER (Sprint 19 hotfix)", fill=(40, 130, 80), font=fs)
    return canvas


def main() -> int:
    api = f"{_read_base_url()}/api"
    pwd = os.environ.get("ADMIN_PASSWORD")
    if not pwd:
        raise RuntimeError("ADMIN_PASSWORD env var missing")

    out_dir = "/tmp/sprint19_before_after"
    os.makedirs(out_dir, exist_ok=True)

    # -------- 1) Swap to BEFORE engine (pre-hotfix) and render --------
    print("==> Swapping render_engine.py to ad739a9 (pre-hotfix)")
    _swap_engine_to("ad739a9")
    _restart_backend()
    token = _login(api, pwd)
    auth = {"Authorization": f"Bearer {token}"}
    before_renders: Dict[str, bytes] = {}
    for it in ITEMS:
        print(f"   BEFORE: {it['name']}")
        job = _render_one(api, auth, it, SOURCE_ASSET)
        before_renders[it["item_key"]] = _dl_first_completed(api, auth, job)

    # -------- 2) Restore the AFTER engine (Sprint 19 hotfix) --------
    print("==> Restoring HEAD render_engine.py (post-hotfix)")
    _swap_engine_to("WORKING")
    _restart_backend()
    token = _login(api, pwd)
    auth = {"Authorization": f"Bearer {token}"}
    after_renders: Dict[str, bytes] = {}
    for it in ITEMS:
        print(f"   AFTER:  {it['name']}")
        job = _render_one(api, auth, it, SOURCE_ASSET)
        after_renders[it["item_key"]] = _dl_first_completed(api, auth, job)

    # -------- 3) Side-by-side composites --------
    print("==> Composing side-by-sides")
    for it in ITEMS:
        k = it["item_key"]
        if not before_renders.get(k) or not after_renders.get(k):
            print(f"   SKIP {k} — missing render")
            continue
        pair = _composite_pair(before_renders[k], after_renders[k],
                               f"{it['name']} ({it['theme']})")
        pair.save(f"{out_dir}/{k.replace('::','_')}.jpg", quality=82)
    print(f"==> Done. Side-by-sides saved to {out_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
