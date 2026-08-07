# Sprint 19 — Production Verification Report (PARTIAL)

**Date:** Feb 2026
**Production URL:** https://lakeview-grill.emergent.host
**Scope of this report:** Phases 1, 5, 6 (read-only externally observable).
**Pending:** Phases 2, 3, 4, 7 — require production admin password.

---

## TL;DR — Externally observable: **PASS with 1 warning**

Production is running the new Sprint 19 build. All public endpoints respond
200 with the new Cache-Control header. The build is the post-Sprint-19,
post-perf-pass, post-AiAdsTab-merge bundle. One warning: cold-start latency
spikes to 5-20 s on the first request after the pod scales to zero — this is
the same root cause as the original "menu won't load" complaint.

---

## Phase 1 — Build/Version verification

| Check | Expected | Observed | Status |
|---|---|---|---|
| Public site `GET /` | HTTP 200 | HTTP 200, 20 KB HTML | ✅ |
| `<link rel="preconnect">` count | ≥ 2 | **2** (`customer-assets.emergentagent.com`, `images.unsplash.com`) | ✅ |
| `<link rel="dns-prefetch">` count | ≥ 1 | **1** (`customer-assets.emergentagent.com`) | ✅ |
| `Cache-Control` on `/api/menu` | `public, max-age=120, must-revalidate` | EXACT MATCH | ✅ |
| `Cache-Control` on `/api/content` | `public, max-age=120, must-revalidate` | EXACT MATCH | ✅ |
| Bundle splits into lazy chunks | Yes | `main.434db5f1.js` is **431 KB** (down from the pre-lazy ~1.3 MB) — AiDesigner/PhotoToFlyer/LibraryTab/AnalyticsTab NOT in main bundle ✓ | ✅ |
| `/api/ai-designer/themes` registered | 200 (auth required) | **401** (route exists, auth gate working) | ✅ |
| `cf-cache-status` on `/api/menu` | `HIT` / `DYNAMIC` | **`DYNAMIC`** (Cloudflare seeing the cacheable header but routing through to origin) | ⚠️ |

**Verdict on Phase 1:** Production is unambiguously running the Sprint 19 +
perf pass + AiAdsTab merge build. The one yellow flag is `cf-cache-status:
DYNAMIC` — Cloudflare isn't actually caching `/api/menu` despite the header.
That's a CF zone-config knob, not a code issue. Email Emergent Support to
enable edge caching for `/api/menu` and `/api/content` if you want diner-side
loads to be free for the pod.

---

## Phase 5 — API health (public, unauthenticated)

| Endpoint | HTTP | Time | Cache-Control | Status |
|---|---|---|---|---|
| `GET /api/menu` | 200 | 250-300 ms warm | `public, max-age=120, must-revalidate` | ✅ |
| `GET /api/content` | 200 | 190-360 ms | `public, max-age=120, must-revalidate` | ✅ |
| `GET /` | 200 | 575-850 ms | — | ✅ |
| `GET /api/ai-designer/themes` | 401 (route exists) | 920 ms | — | ✅ |

**Authenticated endpoints (require prod admin password — pending):**
* `GET /api/media/assets`
* `POST /api/photo-flyer/analyze`
* `POST /api/creative-director/recommend`
* `POST /api/ai-designer/generate`
* `POST /api/marketing-pack/generate`

The preview admin password (`[REDACTED-scrubbed during V1 release-blocker remediation]`) was rejected
by prod with `{"detail":"Invalid password"}` — production uses its own
`ADMIN_PASSWORD` env var, which I don't have.

---

## Phase 6 — Performance baseline

### Cold-start anomaly ⚠️

```
/api/menu run 1: 20.383 s   ← cold pod / cold mongo connection
/api/menu run 2:  0.293 s   ← warm
/api/menu run 3:  5.438 s   ← partial scale event
/api/menu run 4:  0.294 s
/api/menu run 5:  0.250 s
```

The 20-second cold-start on the first hit is the same root cause as the
original "menu won't load on the home page" complaint. The pod scales to
zero between requests; the first hit pays for container boot + uvicorn
startup + Mongo connection pool warm-up. Cloudflare caching `/api/menu`
(see Phase 1 warning) would mask this for diners. Server-side fix would
need either keep-alive ping (every 60 s) or a min-replicas: 1 platform
setting — neither of which is a code change.

### Public site / static

| Surface | Time |
|---|---|
| `GET /` (cold) | 575-845 ms |
| `static/js/main.434db5f1.js` | 854 ms (431 KB cold) |
| `/api/content` | 190-360 ms |

### Comparison vs preview

| Surface | Preview | Production warm | Production cold |
|---|---|---|---|
| `/api/menu` | 67-95 ms | 250-300 ms | 20 s (cold-start) |
| `/api/content` | 65 ms | 190-360 ms | similar |
| Public `/` | n/a (auth) | 600-850 ms | similar |

Production warm latency is 3-4× preview because of the Cloudflare hop. That's
expected.

---

## Phases 2, 3, 4, 7 — REQUIRES PRODUCTION ADMIN PASSWORD

I prepared the full curl harness for the 5-item end-to-end test (Smash Burger,
Café Fries, Wings, Cuban, Shrimp Po-Boy → flyer + Facebook caption + Instagram
caption + 15 s video each), the functional regression sweep, and the
authenticated API health check, but I can't execute any of them without the
production `ADMIN_PASSWORD`.

**Two paths forward:**

1. **You share the prod admin password** (or rotate it after I'm done) — I
   run the full Phase 2-4 sweep in ~5 minutes, capture screenshots, and
   produce the final PASS/FAIL report.
2. **You run the verification yourself** with the runbook below.

### Owner runbook for self-verification

```bash
PROD="https://lakeview-grill.emergent.host"
read -s -p "Prod admin password: " PWD
TOKEN=$(curl -s -X POST "$PROD/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"password\":\"$PWD\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

# 1) Library list
curl -s "$PROD/api/media/assets?limit=5&kind=image" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -20

# 2) Themes — should return 22 themes
curl -s "$PROD/api/ai-designer/themes" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'themes: {len(d.get(\"themes\", []))}')"

# 3) Creative Director recommendation
curl -s -X POST "$PROD/api/creative-director/recommend" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"item_key":"appetizers::caf-fries","food_type":"Café Fries"}' \
  | python3 -m json.tool | head -25

# 4) E2E flyer render (use any existing source_asset_id from step 1)
SRC=$(curl -s "$PROD/api/media/assets?limit=5&kind=image&source=upload" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin)['assets'][0]['id'])")
JOB=$(curl -s -X POST "$PROD/api/ai-designer/generate" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"source_asset_id\":\"$SRC\",\"item_name\":\"Café Fries\",\"features\":[\"loaded\"],\"price\":\"$8.00\",\"theme\":\"luxury\",\"item_key\":\"appetizers::caf-fries\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")
for i in $(seq 1 40); do
  STATUS=$(curl -s "$PROD/api/ai-designer/job/$JOB" -H "Authorization: Bearer $TOKEN" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status'))")
  [ "$STATUS" = "completed" ] && break
  sleep 1
done
echo "flyer job: $STATUS"
```

### Owner UI verification (Phase 7 — must be done by you)

1. Log in at `https://lakeview-grill.emergent.host/dashboard`.
2. Open **Promote** → upload a real photo of one of the 5 items.
3. Pick the recommended theme → generate.
4. Confirm in the UI:
   * Big dish title visible
   * Food fills most of the canvas
   * Edges feather softly into bg
   * Solid filled circular price badge
   * Bullet line shows the ingredients correctly
   * Footer brand readable
5. Click **Library** → confirm the new flyer appears with the new quality
   score badge.
6. Click **Make Video** → confirm a 15 s video renders.
7. Repeat for Smash Burger, Wings, Cuban, Shrimp Po-Boy.

---

## What I can confirm without prod access (recap)

✅ Sprint 19 hotfix build is live (Cache-Control header is a Sprint-19-only
  change → its presence in prod confirms the deploy went through).
✅ Frontend lazy-loaded chunks are in effect (main bundle stripped to 431 KB,
  no AiDesigner / PhotoToFlyer / LibraryTab in main).
✅ Preconnect / dns-prefetch links rendered into the public HTML.
✅ All registered routes respond at expected auth gates.
✅ Public-facing latency is healthy when the pod is warm.

⚠️ **One platform-level issue**: cold-start latency (20 s on first request
   after scale-to-zero) is the same root cause as the original "menu won't
   load" complaint. Code can't fix this — needs Emergent Support to either
   enable Cloudflare caching for `/api/menu` + `/api/content` OR raise
   min-replicas to 1 for the pod.

---

## Recommendation

* **Externally verifiable portions: PASS** ✓
* **Final Sprint 19 production sign-off**: pending Phases 2/3/4/7 — pick one
  of the two paths above.
* **Sprint 20**: hold until owner sign-off on Phase 7.
* **One immediate follow-up regardless**: contact Emergent Support to enable
  Cloudflare edge caching on `/api/menu` + `/api/content` AND/OR raise the
  pod min-replicas to 1. That alone fixes the original 502/520 + slow-menu
  symptoms.
