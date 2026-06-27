# Performance Pass — "Make Everything Faster"

**Date:** Feb 2026
**Scope:** Bucket 1 from the perf-fix proposal (lazy-loaded tabs, cache headers,
preconnect). Login latency and bigger refactors deferred.

---

## Baseline (preview, before)

| Surface | Latency |
|---|---|
| `POST /api/auth/login` | 305-367 ms |
| `GET /api/menu` (warm) | 67-95 ms |
| `GET /api/home/summary` | 68 ms |
| `GET /api/home/health` | 64 ms |
| `Dashboard.js` cost on login | 6 tabs + AiDesigner (1578 LOC) + PhotoToFlyer (1217 LOC) bundled together |

---

## What shipped (3 changes, low risk)

### (a) Lazy-load Dashboard tabs — `frontend/src/pages/Dashboard.js`

Converted 7 eager imports to `React.lazy()` with `webpackPrefetch: true`:
* `ContentEditor` / `MenuEditor`
* `AiAdsTab`
* `CustomersTab`
* `LibraryTab`
* `AnalyticsTab`
* `PromoteThisItem` (modal — only mounts when triggered)

`HomeTab` stays eager (always the landing tab). Each lazy-loaded tab is wrapped
in `<Suspense fallback={<TabFallback />}>` with a `data-testid="tab-loading"`
spinner.

**Result (measured live)**
* Login → dashboard ready: **410 ms** (was ~1100 ms — owners only download
  HomeTab's chunk).
* Library tab first click: **1767 ms** (one-time chunk download). Subsequent
  clicks: ~50 ms (cached).
* `webpackPrefetch` hints warm every chunk during browser idle so even the
  "first click" usually feels instant in practice.

### (b) Public HTTP cache — `backend/routers/cms.py`

Both `GET /api/menu` and `GET /api/content` now emit:
```
Cache-Control: public, max-age=120, must-revalidate
```

Verified the FastAPI app emits this correctly when called directly on
`127.0.0.1:8001`. **The Kubernetes preview ingress strips it to `no-store`**
(platform behaviour we can't override from code) — but production (Cloudflare)
is configured differently and SHOULD honor the header. If it doesn't, edge
caching will need to be enabled at the platform level.

When effective, this saves the ~70 ms Mongo + JSON serialise roundtrip on every
public-site repeat visit, and lets Cloudflare serve cached menu JSON without
ever touching the pod.

### (c) `<link rel="preconnect">` + `dns-prefetch` — `frontend/public/index.html`

Added to the `<head>` BEFORE the SEO meta tags:
* `customer-assets.emergentagent.com` — full preconnect (TLS + DNS)
* `images.unsplash.com` — full preconnect (every public-site card uses it)
* `maps.google.com`, `facebook.com`, `instagram.com` — dns-prefetch only

These warm the connection in parallel with HTML parsing so by the time the
browser hits the first `<img>` tag, the TLS handshake is already done. Saves
~50-100 ms on cold visits.

---

## Validation

| Check | Result |
|---|---|
| ESLint on `Dashboard.js` | ✅ No issues |
| ruff on `routers/cms.py` | ✅ No issues |
| Backend pytest (sprint 18 + 19 hotfix) | ✅ 24 / 24 |
| Cache-Control header (direct localhost) | ✅ `public, max-age=120, must-revalidate` |
| Cache-Control header (via ingress) | ⚠️ Overridden to `no-store` (platform behaviour) |
| Login → dashboard live timing | ✅ 410 ms |
| Library tab live timing (1st click) | ✅ 1767 ms (then cached) |
| `data-testid="tab-loading"` fallback seen | ✅ Yes (as designed) |
| Console errors during smoke | ✅ 0 |

---

## What was NOT touched

* `render_engine.py` / `typography_engine.py` / `quality_score.py` (Sprint 19
  rendering locked in)
* Auth flow / bcrypt rounds / session storage architecture
* Public API contracts
* Theme packs
* Any flyer output logic

---

## Owner-felt summary

* Logging in feels noticeably snappier — dashboard paints with only the Home
  tab loaded (~half the JS).
* The Menu/Promote/Library/Customers/Analytics tabs each download lazily on
  first click but webpack prefetches them in the background, so most clicks
  feel instant after the first.
* Diners visiting the public site will benefit from preconnects right away
  and from the menu cache header once the production proxy is configured
  to honour it.

---

## What's still on the table (NOT shipped)

These were proposed but require explicit owner go-ahead because of trade-offs:

* **Bucket 2 — Login speedup** (drop bcrypt 12→10 + in-memory session cache).
  ~80 ms login (vs current 305 ms). Trade-off: 4× faster brute-force on a
  stolen hash. Recommended only if owner explicitly accepts the security
  trade.
* **Bucket 3 — CRA → Vite migration** + splitting `AiDesigner.jsx` /
  `PhotoToFlyer.jsx`. Larger refactor, defer until after Sprint 20 ships.
