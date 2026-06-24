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

---

## Gate 3 — Marketing Pack (Video Generation)

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
| G3.1 | Upload 200 | ☐ | |
| G3.2 | Pack generate 202 | ☐ | |
| G3.3 | Pack completes in 90s | ☐ | |
| G3.4 | Video downloadable, no copy fields | ☐ | |
| G3.5 | Video plays | ☐ | |
| G4   | Media audit clean | ☐ | |
| G5   | No 5xx in 5-min soak | ☐ | |

**Launch decision**: All ☑ → `Ready for production`. Any ☐ → halt, document.
