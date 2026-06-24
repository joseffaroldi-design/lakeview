# Phase 2 — Production Smoke-Test Runbook

**Use AFTER**: Emergent Support confirms env-var propagation is fixed and
production responds 200 to the new `ADMIN_PASSWORD` (`83CeLOZJQbOcopK0yYmNtdRQg4VPii8o`).

**Audience**: You (running curl/browser from your local terminal). E1 has no
network path to production from inside the preview pod.

Set these once at the top of your shell:

```bash
PROD="https://lakeview-grill.emergent.host"
NEW_PW="83CeLOZJQbOcopK0yYmNtdRQg4VPii8o"
OLD_PW="<the password that's currently still working in prod>"
```

---

## Gate 0 — Auth (must pass before continuing)

### G0.1 — Old password rejected
```bash
curl -s -o /dev/null -w "old_pw=%{http_code}\n" \
  -X POST "$PROD/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"password\":\"$OLD_PW\"}"
```
**Pass**: `old_pw=401`
**Fail**: `old_pw=200` (env still not propagated — return to Support)

### G0.2 — New password accepted, returns token
```bash
TOKEN=$(curl -s -X POST "$PROD/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"password\":\"$NEW_PW\"}" | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
echo "TOKEN length: ${#TOKEN}"
```
**Pass**: TOKEN length ≥ 30
**Fail**: empty / shell error

### G0.3 — Token verifies
```bash
curl -s -o /dev/null -w "verify=%{http_code}\n" \
  "$PROD/api/auth/verify" -H "Authorization: Bearer $TOKEN"
```
**Pass**: `verify=200`

### G0.4 — Invalid token rejected
```bash
curl -s -o /dev/null -w "bad=%{http_code}\n" \
  "$PROD/api/auth/verify" -H "Authorization: Bearer not-a-token"
```
**Pass**: `bad=401`

---

## Gate 1 — Platform Health

### G1.1 — Public homepage
```bash
curl -s -o /dev/null -w "home=%{http_code}\n" "$PROD/"
```
**Pass**: `home=200`

### G1.2 — Public menu API
```bash
curl -s -o /dev/null -w "menu=%{http_code}\n" "$PROD/api/menu"
```
**Pass**: `menu=200`

### G1.3 — Media health probe
```bash
curl -s "$PROD/api/media/health" -H "Authorization: Bearer $TOKEN" | python -m json.tool
```
**Pass**:
- `"healthy": true`
- `storage.reachable: true`
- `storage.backend: "emergent_object_storage"`
- `ai_image_queue.failed_recent` is 0 or low

### G1.4 — Home dashboard health
```bash
curl -s "$PROD/api/home/health" -H "Authorization: Bearer $TOKEN" | python -m json.tool
```
**Pass**: 200 with non-empty body

---

## Gate 2 — AI Designer

### G2.1 — Estimate endpoint responds (no LLM call needed)
```bash
curl -s -X POST "$PROD/api/ai-designer/estimate" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"variations":1}' | python -m json.tool
```
**Pass**: 200 with cost estimate fields

### G2.2 — Manual flyer generation through the dashboard UI
1. Open browser → `$PROD/dashboard`
2. Login with `$NEW_PW`
3. Go to "AI Ads" tab → AI Designer
4. Upload one of `/app/memory/launch/assets/<dish>.jpg` (or any food photo)
5. Item name: "SMASH BURGER", features: "American Cheese, Pickled Onions, House Sauce, Comes with Fries", price: "$13.95"
6. Pick theme: `comic_pop` (flyer-grade)
7. Generate
8. **Screenshot the result** → save to `/tmp/prod_designer.png`

**Pass criteria**:
- Job reaches `completed` within 90s
- Output flyer shows ingredient icons (burger/cheese/onion/fries/sauce glyphs visible)
- Typography is Bebas Neue / Bungee (not generic sans-serif)
- Price tag is visible in the corner
- Image is downloadable from the review screen

## Gate 2.5 — Photo → Flyer Fusion (Sprint 16D)

This gate group exercises the new entry point: a single photo upload that
produces an enhanced asset, an AI vision analysis, a fuzzy menu match,
and (via the existing AI Designer + Marketing Pack reuse) a finished
flyer + captions + opt-in video.

Save a real food photo locally (any JPG/PNG of a dish — e.g. one taken
in-house at Lakeview). Set:
```bash
PHOTO=/path/to/lakeview-burger.jpg
```

### G2.5.1 — Analyze endpoint reachable + multipart upload accepted
```bash
ANALYZE=$(curl -s -X POST "$PROD/api/photo-flyer/analyze" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$PHOTO" \
  -F "folder=Custom")
echo "$ANALYZE" | python -m json.tool | head -30
```
**Pass**:
- HTTP 200
- Response contains `original_asset_id`, `enhanced_asset_id`, `vision_ok`,
  `food_type`, `features`, `suggested_theme`, `menu_match`

### G2.5.2 — Both source and enhanced assets are downloadable
```bash
ORIG=$(echo "$ANALYZE" | python -c "import sys,json;print(json.load(sys.stdin)['original_asset_id'])")
ENHANCED=$(echo "$ANALYZE" | python -c "import sys,json;print(json.load(sys.stdin)['enhanced_asset_id'])")
echo "orig=$ORIG"
echo "enhanced=$ENHANCED"

curl -s -o /tmp/prod_orig.jpg -w "orig_http=%{http_code} size=%{size_download}\n" \
  "$PROD/api/media/file/$ORIG" -H "Authorization: Bearer $TOKEN"

curl -s -o /tmp/prod_enhanced.jpg -w "enhanced_http=%{http_code} size=%{size_download}\n" \
  "$PROD/api/media/file/$ENHANCED" -H "Authorization: Bearer $TOKEN"
```
**Pass**:
- Both `*_http=200`
- Both `size > 10000` bytes
- Enhanced bytes ≠ original bytes (PIL pipeline actually applied)
- Thumbnails also retrievable:
  ```bash
  curl -s -o /dev/null -w "thumb=%{http_code}\n" \
    "$PROD/api/media/thumb/$ENHANCED" -H "Authorization: Bearer $TOKEN"   # → 200
  ```

### G2.5.3 — Vision analysis returns useful data OR gracefully degrades
```bash
echo "$ANALYZE" | python -c "
import sys, json
d = json.load(sys.stdin)
print('vision_ok    =', d['vision_ok'])
print('food_type    =', d.get('food_type'))
print('confidence   =', d.get('confidence'))
print('features     =', d.get('features'))
print('theme        =', d.get('suggested_theme'))
print('menu_matched =', (d.get('menu_match') or {}).get('matched'))
print('vision_error =', d.get('vision_error'))
"
```
**Pass — happy path** (LLM budget healthy):
- `vision_ok = True`
- `food_type` is non-empty and contextually correct
- `confidence ≥ 0.5`
- `features` has 1+ entries
- `suggested_theme ∈ {comic_pop, vintage_diner, bold_purple_pop, casual_teal, distressed_orange}`

**Pass — degraded path** (LLM budget capped):
- `vision_ok = False`
- `vision_error` contains "budget" (or "timeout"/"json")
- `suggested_theme = 'comic_pop'` (safe default)
- `features = []`
- **Critical**: response is still 200, not 500 — the UI must be able to render

### G2.5.4 — Menu match returns editable shape
```bash
echo "$ANALYZE" | python -c "
import sys, json
mm = json.load(sys.stdin).get('menu_match') or {}
print('matched =', mm.get('matched'))
print('name    =', mm.get('name'))
print('price   =', mm.get('price'))
print('confidence =', mm.get('confidence'))
print('tried   =', mm.get('tried'))
"
```
**Pass**:
- `tried > 0` (menu collection was queryable in prod)
- If matched: `name`, `price`, `confidence ≥ 0.55` all present
- If not matched: `matched=False`, `price=None` — the UI shows a manual
  price field (this is the documented conservative behaviour, not a bug)

### G2.5.5 — Flyer + caption generation completes under 90 seconds
This step exercises the **existing** AI Designer route reused by the new
flow — proves the fusion does not slow down the underlying pipeline.

```bash
DESIGNER_JOB=$(curl -s -X POST "$PROD/api/ai-designer/generate" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "$(echo "$ANALYZE" | python -c "
import sys, json
d = json.load(sys.stdin)
mm = d.get('menu_match') or {}
print(json.dumps({
  'source_asset_id': d['enhanced_asset_id'],
  'item_name': d.get('food_type') or 'Featured Dish',
  'features': d.get('features') or [],
  'price': mm.get('price') or '\$13.95',
  'theme': d.get('suggested_theme') or 'comic_pop',
  'variations': 1,
  'auto_copy': True,
}))")" | python -c "import sys,json;print(json.load(sys.stdin)['job_id'])")
echo "DESIGNER_JOB=$DESIGNER_JOB"

START=$(date +%s)
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18; do
  STATE=$(curl -s "$PROD/api/ai-designer/job/$DESIGNER_JOB" \
    -H "Authorization: Bearer $TOKEN" | \
    python -c "import sys,json;d=json.load(sys.stdin);print(d.get('status'),d.get('progress'))")
  ELAPSED=$(($(date +%s) - START))
  echo "t=${ELAPSED}s  $STATE"
  if echo "$STATE" | grep -q completed; then break; fi
  sleep 5
done
ELAPSED=$(($(date +%s) - START))
echo "Designer wall time: ${ELAPSED}s"

# Pull the result and confirm copy_pack
curl -s "$PROD/api/ai-designer/job/$DESIGNER_JOB" \
  -H "Authorization: Bearer $TOKEN" | python -c "
import sys, json
j = json.load(sys.stdin)
vs = j.get('variations') or []
cp = j.get('copy_pack') or {}
print('variations =', len(vs))
print('flyer_asset_id =', vs[0].get('asset_id') if vs else None)
print('fb_post_len =', len(cp.get('fb_post', '')))
print('ig_post_len =', len(cp.get('ig_post', '')))
print('copy_error =', j.get('copy_error'))
"
```
**Pass**:
- Reaches `completed 100` in **≤ 90 s**
- `variations ≥ 1` and `flyer_asset_id` is non-empty
- If LLM budget healthy: `fb_post_len ≥ 60` and `ig_post_len ≥ 60`
- If LLM budget capped: `fb_post_len = 0` AND `copy_error` is set; this
  is acceptable — owner can paste their own caption (graceful degradation)

### G2.5.6 — Flyer + thumbnail downloadable
```bash
FLYER=$(curl -s "$PROD/api/ai-designer/job/$DESIGNER_JOB" \
  -H "Authorization: Bearer $TOKEN" | \
  python -c "import sys,json;print(json.load(sys.stdin)['variations'][0]['asset_id'])")

curl -s -o /tmp/prod_flyer.png -w "flyer_http=%{http_code} size=%{size_download}\n" \
  "$PROD/api/media/file/$FLYER" -H "Authorization: Bearer $TOKEN"
curl -s -o /dev/null -w "flyer_thumb=%{http_code}\n" \
  "$PROD/api/media/thumb/$FLYER" -H "Authorization: Bearer $TOKEN"
```
**Pass**:
- `flyer_http = 200`, `size > 50000`
- `flyer_thumb = 200`
- Open `/tmp/prod_flyer.png` and visually confirm:
  - Title typography rendered (Bebas Neue / Bungee / Permanent Marker)
  - Price badge visible
  - Ingredient icons rendered next to feature lines (Sprint 16A.2)
  - Lakeview branding present

### G2.5.7 — "Turn this into a 15s video" — opt-in trigger works
```bash
PACK=$(curl -s -X POST "$PROD/api/marketing-pack/generate" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "$(echo "$ANALYZE" | python -c "
import sys, json
d = json.load(sys.stdin)
mm = d.get('menu_match') or {}
print(json.dumps({
  'source_asset_id': d['enhanced_asset_id'],
  'name': d.get('food_type') or 'Featured Dish',
  'price': mm.get('price') or '',
  'cta': 'Order Now',
}))")")
PACK_ID=$(echo "$PACK" | python -c "import sys,json;print(json.load(sys.stdin)['job_id'])")
echo "PACK_ID=$PACK_ID"

START=$(date +%s)
for i in $(seq 1 24); do
  STATE=$(curl -s "$PROD/api/marketing-pack/job/$PACK_ID" \
    -H "Authorization: Bearer $TOKEN" | \
    python -c "import sys,json;d=json.load(sys.stdin);print(d.get('status'),d.get('progress'))")
  ELAPSED=$(($(date +%s) - START))
  echo "t=${ELAPSED}s  $STATE"
  if echo "$STATE" | grep -q completed; then break; fi
  sleep 5
done
ELAPSED=$(($(date +%s) - START))
echo "Pack wall time: ${ELAPSED}s"

VID=$(curl -s "$PROD/api/marketing-pack/$PACK_ID" \
  -H "Authorization: Bearer $TOKEN" | \
  python -c "import sys,json;print(json.load(sys.stdin)['result']['video_asset_id'])")
echo "VIDEO_ASSET_ID=$VID"
```
**Pass**:
- Pack reaches `completed` in ≤ 120 s
- `VIDEO_ASSET_ID` is non-empty

### G2.5.8 — Video playable MP4
```bash
curl -s -o /tmp/prod_fusion_video.mp4 -w "vid_http=%{http_code} size=%{size_download}\n" \
  "$PROD/api/media/file/$VID" -H "Authorization: Bearer $TOKEN"
ffprobe -v error -show_entries stream=codec_type,width,height,duration \
  /tmp/prod_fusion_video.mp4 2>&1 | head -10
```
**Pass**:
- `vid_http = 200`, `size > 50000`
- `codec_type = video`
- `width=720 height=1280`
- `duration ≈ 15 ± 1` seconds
- Optional: `xdg-open /tmp/prod_fusion_video.mp4` plays the slideshow

---

## Gate 3 — Marketing Pack (Video Generation, standalone path)

### G3.1 — Upload a source image
```bash
curl -s -X POST "$PROD/api/media/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/burger.jpg" \
  -F "folder=Marketing Packs" \
  -F "tags=smoke-test"
```
**Pass**: 200 with `id` and `storage_path`. Capture `ASSET_ID=$(echo $response | jq -r .id)`

### G3.2 — Generate 15-s video
```bash
PACK=$(curl -s -X POST "$PROD/api/marketing-pack/generate" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d "{\"source_asset_id\":\"$ASSET_ID\",\"name\":\"Smash Burger\",\"price\":\"\$13.95\",\"cta\":\"Order Now\"}")
PACK_ID=$(echo "$PACK" | python -c "import sys,json;print(json.load(sys.stdin)['job_id'])")
echo "PACK_ID=$PACK_ID"
```
**Pass**: 202 with `job_id`

### G3.3 — Poll pipeline to completion
```bash
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  STATE=$(curl -s "$PROD/api/marketing-pack/job/$PACK_ID" \
    -H "Authorization: Bearer $TOKEN" | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('status'),d.get('progress'),d.get('current_step'))")
  echo "t=${i}x5s  $STATE"
  if echo "$STATE" | grep -q completed; then break; fi
  if echo "$STATE" | grep -q failed; then echo "FAILED"; break; fi
  sleep 5
done
```
**Pass**: reaches `completed 100 done` within 90s

### G3.4 — Verify result and download video
```bash
RESULT=$(curl -s "$PROD/api/marketing-pack/$PACK_ID" -H "Authorization: Bearer $TOKEN")
VID=$(echo "$RESULT" | python -c "import sys,json;print(json.load(sys.stdin)['result']['video_asset_id'])")
echo "VIDEO_ASSET_ID=$VID"

# Result must NOT carry copy fields (Sprint 16B.4)
echo "$RESULT" | python -c "
import sys, json
r = json.load(sys.stdin)['result']
for f in ('caption','hashtags','sms','email','gbp'):
    assert f not in r, f'FAIL — {f} should have been removed in Sprint 16B.4'
print('OK — no copy fields in video-only result')
"

# Download the video
curl -s -o /tmp/prod_video.mp4 "$PROD/api/media/file/$VID" \
  -H "Authorization: Bearer $TOKEN"
ls -la /tmp/prod_video.mp4
file /tmp/prod_video.mp4
```
**Pass**:
- VIDEO_ASSET_ID is non-empty
- "no copy fields in video-only result" prints
- File size > 100KB
- `file` reports `ISO Media, MP4`

### G3.5 — Open the video in a player
```bash
xdg-open /tmp/prod_video.mp4   # or VLC, QuickTime
```
**Pass**: plays for ~15 s, shows the source image + title overlay + CTA

---

## Gate 4 — Media Orphan Scan

Since the script can't run from inside production directly (the pod doesn't
have the script), this is informational. Instead, hit the audit endpoint:

```bash
curl -s "$PROD/api/media/audit" -H "Authorization: Bearer $TOKEN" | python -m json.tool
```
**Pass**:
- `total` ≥ 1
- `missing_storage` = 0
- `orphans` is empty array

---

## Gate 5 — Platform Stability

After running G0 → G4, leave the dashboard open in a browser for 5 minutes
and refresh a few times. Then check Emergent platform logs for the prod pod:

**Pass**:
- Zero `5xx` responses in nginx/ingress logs
- No `python` traceback lines in stdout
- No `gunicorn worker exited` / `supervisorctl restart` events
- No `OOMKilled` or memory-pressure pod events

---

## Pass/Fail Summary Template

| Gate | Test | Result | Notes |
|------|------|--------|-------|
| G0.1 | Old password 401 | ☐ | |
| G0.2 | New password 200 + token | ☐ | |
| G0.3 | Token verifies | ☐ | |
| G0.4 | Bad token 401 | ☐ | |
| G1.1 | Home 200 | ☐ | |
| G1.2 | Menu 200 | ☐ | |
| G1.3 | Media health: reachable | ☐ | |
| G1.4 | Home health 200 | ☐ | |
| G2.1 | AI Designer estimate 200 | ☐ | |
| G2.2 | Flyer generates + icons + fonts visible | ☐ | screenshot attached |
| G2.5.1 | Photo→Flyer analyze endpoint reachable | ☐ | |
| G2.5.2 | Original + enhanced assets downloadable, thumbs OK | ☐ | |
| G2.5.3 | Vision returns useful data OR gracefully degrades | ☐ | budget state: ___ |
| G2.5.4 | Menu match returns editable shape | ☐ | tried=___ matched=___ |
| G2.5.5 | Flyer + caption generation ≤ 90 s | ☐ | wall time: ___s |
| G2.5.6 | Flyer + thumbnail downloadable, visual review passes | ☐ | |
| G2.5.7 | Opt-in video kick succeeds, pack completes | ☐ | wall time: ___s |
| G2.5.8 | Video playable MP4 (720×1280, ~15s) | ☐ | |
| G3.1 | Upload 200 | ☐ | |
| G3.2 | Pack generate 202 | ☐ | |
| G3.3 | Pack completes in 90s | ☐ | |
| G3.4 | Video downloadable, no copy fields | ☐ | |
| G3.5 | Video plays | ☐ | |
| G4   | Media audit clean | ☐ | |
| G5   | No 5xx in 5-min soak | ☐ | |

**Launch decision**: All ☑ → `Ready for production`. Any ☐ → halt, document.
