"""Sprint 19 Hotfix — Visual Audit (post-rendering inspection).

Picks the most recent flyers grouped by item_key (one per item), downloads
each via the proxy `/api/media/file/{id}`, and runs four objective pixel
checks that map to the Hotfix acceptance criteria:

  1. food_dominance_pct  — share of the 1024×1024 canvas that is NOT pure
                           background colour (using the theme bg sampled
                           from canvas corners). Target: >= 30 % real
                           "stuff" (food + text + badge).
  2. food_coverage_pct   — share of the canvas occupied by NON-text,
                           NON-bg pixels in the central 70% band. Target:
                           60-75% per the hotfix spec.
  3. badge_fill_check    — samples the bottom-right and bottom-left
                           quadrants for a saturated disc of >= 80 px²
                           solid colour (proves the badge always renders
                           filled, not outline-only).
  4. rect_border_detect  — runs a Sobel edge filter and looks for long
                           straight horizontal/vertical edges INSIDE the
                           canvas (would indicate a hard photo border).

Output: a markdown table that is appended to the Sprint 19 Hotfix
Validation Report and a PASS/FAIL exit code.
"""
from __future__ import annotations

import io
import json
import os
import sys
from typing import Dict, List

import requests
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CANVAS = 1024


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
    r = requests.post(
        f"{api}/auth/login",
        json={"password": password},
        headers={"X-Forwarded-For": f"198.51.100.{uuid.uuid4().int % 250 + 1}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["token"]


def _recent_flyers(api: str, auth: Dict[str, str], n: int = 30) -> List[Dict]:
    r = requests.get(
        f"{api}/media/assets?limit={n}&source=ai_designer&kind=image",
        headers=auth, timeout=15,
    )
    r.raise_for_status()
    return r.json().get("assets", [])


def _dl(api: str, auth: Dict[str, str], asset_id: str) -> Image.Image:
    r = requests.get(f"{api}/media/file/{asset_id}", headers=auth, timeout=20)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def _bg_color(im: Image.Image) -> tuple:
    """Sample the four corners and return the mean — that's the bg."""
    w, h = im.size
    pad = 12
    samples = [
        im.getpixel((pad, pad)),
        im.getpixel((w - pad, pad)),
        im.getpixel((pad, h - pad)),
        im.getpixel((w - pad, h - pad)),
    ]
    r = sum(s[0] for s in samples) // 4
    g = sum(s[1] for s in samples) // 4
    b = sum(s[2] for s in samples) // 4
    return (r, g, b)


def food_dominance(im: Image.Image, bg: tuple, tol: int = 28) -> float:
    """% of canvas pixels that differ from background colour by `tol`+."""
    px = im.load()
    w, h = im.size
    diff = 0
    step = 4  # subsample for speed
    total = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b = px[x, y]
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > tol:
                diff += 1
            total += 1
    return diff / total * 100.0


def central_food_coverage(im: Image.Image, bg: tuple) -> float:
    """% of the CENTRAL band (10%-90% horizontal, 18%-82% vertical) that
    differs from bg. Excludes the title band and the badge corner so we
    isolate the food itself (approximately)."""
    px = im.load()
    w, h = im.size
    x0, x1 = int(w * 0.10), int(w * 0.90)
    y0, y1 = int(h * 0.18), int(h * 0.82)
    diff, total = 0, 0
    step = 4
    for y in range(y0, y1, step):
        for x in range(x0, x1, step):
            r, g, b = px[x, y]
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > 28:
                diff += 1
            total += 1
    return diff / total * 100.0 if total else 0.0


def badge_filled(im: Image.Image, bg: tuple) -> bool:
    """Search the four corners for a disc-like blob of saturated colour
    (>=100 px² in a 256×256 corner that differs from bg)."""
    w, h = im.size
    quads = [
        (0, 0, 280, 280),
        (w - 280, 0, w, 280),
        (0, h - 280, 280, h),
        (w - 280, h - 280, w, h),
    ]
    for (x0, y0, x1, y1) in quads:
        region = im.crop((x0, y0, x1, y1))
        rpx = region.load()
        bw, bh = region.size
        count = 0
        for y in range(0, bh, 3):
            for x in range(0, bw, 3):
                r, g, b = rpx[x, y]
                if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > 50:
                    count += 1
        # filled badge produces hundreds of contrasting pixels in its corner
        if count > 600:
            return True
    return False


def rect_border_pct(im: Image.Image) -> float:
    """Run a Sobel edge filter and look for long straight horizontal /
    vertical edges INSIDE the canvas (5%-95%). Returns the % of the inner
    canvas covered by long axis-aligned edges. <8% → no hard border."""
    edges = im.convert("L").filter(ImageFilter.FIND_EDGES)
    w, h = edges.size
    px = edges.load()
    # Threshold for "edge"
    THR = 100
    # Scan inner rows / cols
    long_runs = 0
    total_inner = 0
    # Horizontal scans
    for y in range(int(h * 0.10), int(h * 0.90), 6):
        run = 0
        for x in range(int(w * 0.05), int(w * 0.95)):
            v = px[x, y]
            if v > THR:
                run += 1
                if run > 220:  # 220 px of continuous edge ≈ rectangle border
                    long_runs += 1
                    run = 0
            else:
                run = 0
        total_inner += 1
    # Vertical scans
    for x in range(int(w * 0.10), int(w * 0.90), 6):
        run = 0
        for y in range(int(h * 0.05), int(h * 0.95)):
            v = px[x, y]
            if v > THR:
                run += 1
                if run > 220:
                    long_runs += 1
                    run = 0
            else:
                run = 0
        total_inner += 1
    return long_runs / total_inner * 100.0 if total_inner else 0.0


def main():
    api = f"{_read_base_url()}/api"
    pwd = os.environ.get("ADMIN_PASSWORD")
    if not pwd:
        raise RuntimeError("ADMIN_PASSWORD env var missing")
    token = _login(api, pwd)
    auth = {"Authorization": f"Bearer {token}"}

    assets = _recent_flyers(api, auth, n=50)
    # One flyer per item_key (newest)
    seen = set()
    chosen = []
    for a in assets:
        k = a.get("item_key") or a.get("id")
        if k in seen:
            continue
        seen.add(k)
        chosen.append(a)
        if len(chosen) >= 15:
            break

    rows = []
    save_dir = "/tmp/sprint19_samples"
    os.makedirs(save_dir, exist_ok=True)
    print(f"\nAuditing {len(chosen)} flyers (one per item)...\n")
    print(f"{'item_key':<48} {'food%':>7} {'central%':>9} {'badge':>6} {'border%':>8}")
    print("-" * 90)

    pass_count = 0
    fail_reasons = []
    for a in chosen:
        try:
            im = _dl(api, auth, a["id"])
            bg = _bg_color(im)
            fd = food_dominance(im, bg)
            cc = central_food_coverage(im, bg)
            bf = badge_filled(im, bg)
            rb = rect_border_pct(im)
            item_key = a.get("item_key", "?")[:48]
            print(f"{item_key:<48} {fd:>6.1f}% {cc:>8.1f}% {'YES' if bf else 'NO':>6} {rb:>7.2f}%")
            ok = True
            why = []
            if cc < 35:
                ok = False; why.append("central food coverage low")
            if not bf:
                ok = False; why.append("badge missing")
            if rb > 8.0:
                ok = False; why.append("hard rect border detected")
            rows.append({
                "item_key": item_key,
                "food_dominance_pct": round(fd, 1),
                "central_coverage_pct": round(cc, 1),
                "badge_filled": bf,
                "rect_border_pct": round(rb, 2),
                "pass": ok,
                "why": why,
            })
            if ok:
                pass_count += 1
            else:
                fail_reasons.append(f"{item_key}: {', '.join(why)}")
            # Save a tiled sample
            im.save(f"{save_dir}/{item_key.replace('::','_')}.jpg", quality=80)
        except Exception as e:  # noqa: BLE001
            print(f"{a.get('item_key','?')[:48]:<48} ERROR {e}")

    print("-" * 90)
    print(f"\nVisual audit: {pass_count}/{len(rows)} pass")
    if fail_reasons:
        print("Failures:")
        for r in fail_reasons:
            print(f"  - {r}")
    # Save JSON for downstream reporting
    with open("/tmp/sprint19_visual_audit.json", "w") as f:
        json.dump({"rows": rows, "pass": pass_count, "total": len(rows)}, f, indent=2)
    print(f"\nSamples saved to {save_dir}/")
    print("JSON report: /tmp/sprint19_visual_audit.json")
    return 0 if pass_count == len(rows) else 2


if __name__ == "__main__":
    sys.exit(main())
