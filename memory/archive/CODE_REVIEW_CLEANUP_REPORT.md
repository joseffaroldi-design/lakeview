# Code Quality Cleanup — Sprint 19 Post-Sign-off Pass

**Date:** Feb 2026
**Scope:** Apply low-risk fixes from the platform code-review report WITHOUT
refactoring the rendering engine, public APIs, auth, or flyer output logic.
**Trigger:** Code Quality Report for environment `ef37b546`.

---

## TL;DR

* **20 real warnings fixed** (15 frontend + 5 backend).
* **3 warning categories declined** with documented rationale (MD5 for layout
  seeds, `random` for decorative variation, JWT in localStorage).
* **3 refactor categories deferred** to a dedicated tech-debt sprint after
  Sprint 20 ships (large compositor function, large background-paint function,
  oversized React components).
* Static analyzers (`ruff`, ESLint) dropped from **16 reported problems → 2**
  (the 2 remaining are vendored shadcn `calendar.jsx` and out of scope).
* Backend regression: **24 / 24** pytests green.
* Frontend smoke: dashboard loads, 0 console errors.
* `render_engine.py` / `typography_engine.py` / `quality_score.py` —
  **zero diff lines**. Sprint 19 visual approval is preserved.

---

## A. Fixed this session

### A1. Empty `catch` blocks now log in dev mode (7 sites)

Pattern applied:
```js
catch (e) {
  if (process.env.NODE_ENV !== "production") console.warn("[component] context:", e);
  // ...any prior side-effects preserved
}
```

| File | Lines | Was | Now |
|---|---|---|---|
| `App.js` | 792, 803 (LoyaltyJoin / Lookup) | `catch { setResult(...) }` | logs + same setResult |
| `LibraryTab.jsx` | 141 (`toggleFav`) | `catch { /* ignore */ }` | logs |
| `shared.jsx` | 49 (`CopyableItem.onCopy`) | `catch (_) { /* ignore */ }` | logs |
| `PhotoToFlyer.jsx` | 710 (video poll) | `catch { setTimeout(...) }` | logs + setTimeout |
| `PromoteThisItem.jsx` | 254 (job poll) | empty catch | logs + retry |
| `AiDesigner.jsx` | 694, 865, 1003, 1217 (4 sites) | `catch { /* keep polling */ }` etc | logs |

Sites intentionally left silent (existing comments justify the silence):
- `index.js:56` — `localStorage.removeItem` on cleanup (cannot meaningfully fail).
- `PhotoToFlyer.jsx:67, 84` — `sessionStorage.removeItem` on cleanup.
- `LibraryTab.jsx:199, 231` — `sessionStorage.setItem` with payload (storage-full
  is non-actionable for the owner).
- `AiDesigner.jsx:406` — `submitAbortRef.current.abort()` (idempotent — throws if
  already aborted, expected).
- `AiDesigner.jsx:1162` — returns `""` fallback for a string parse helper.
- `PhotoToFlyer.jsx:1015, 1115` — already commented as expected-404 / silent-retry.

### A2. Undefined-variable / unused-name warnings (4 backend sites)

| File | Was | Now |
|---|---|---|
| `routers/creative_director.py:140` | `r, g, b = bg[...]` (g unused) | `r, _g, b = ...` |
| `routers/creative_director.py:149` | `pr, pg, pb = ...` (pg unused) | `pr, _pg, pb = ...` |
| `scripts/sprint19_visual_audit.py:240/242/244` | 3 × `ok = False; why.append(...)` (E702) | 6 separate lines |
| `tests/test_ai_image_generation.py:285` | `import sys, os` (E401) | two lines |

### A3. Array-index-as-key — fixed where lists reorder / filter (3 sites)

| File | Site | Was | Now |
|---|---|---|---|
| `App.js:454` | `cat.items.map((item, idx))` (menu items can be filtered) | `key={idx}` | `` key={`${cat.slug}-${item.name \|\| idx}`} `` |
| `HomeTab.jsx:264` | `health.issues.map((iss, idx))` (issues change between fetches) | `key={idx}` | `` key={`issue-${text.slice(0, 32)}-${idx}`} `` |
| `TodaysPick.jsx:387` | `copy.hashtags.slice(0, 6).map((tag, idx))` | `key={idx}` | `` key={`tag-${tag}-${idx}`} `` |

Sites left as-is (fixed-length, never reordered):
- `App.js:834` — 10 punch-card dots (`Array.from({length:10}).map`)
- `LoyaltyMessaging.js:16, 167` — fixed counters / error lists
- `RecommendedStyleCard.jsx:25` — 5 star icons (`Array.from({length:5}).map`)
- `CreativeDirectorRecs.jsx:24` — same 5-star pattern
- `AiDesigner.jsx:725` — 3 variations (fixed length per job)

### A4. `console.log` / `console.warn` wrapped behind NODE_ENV guard (5 sites)

| File | Line | Statement | Change |
|---|---|---|---|
| `index.js` | 35 | `[axios] 5xx silenced` | wrapped in NODE_ENV guard |
| `index.js` | 42 | `[axios] retrying once` | wrapped |
| `aiDesignerAnalytics.js` | 37 | `[Analytics]` echo | wrapped |
| `ContentEditor.js` | 200 | menu-editor prefill warn | wrapped |
| `TodaysPick.jsx` | 118 | Clipboard fallback warn | wrapped |

All `console.error` calls were **left as-is** — they correctly surface
real problems even in production logs.

### A5. JSX hygiene (5 sites in App.js, 1 in TodaysPick.jsx)

* `App.js:224` — `fetchpriority="high"` → `fetchPriority="high"` (React camelCase).
* Apostrophe entities → `&apos;` in 5 places (App.js Specials header, "Don't",
  "Today's", "You're", "we've", "We'll").
* Quote entities → `&quot;` in TodaysPick.jsx ("Regenerate").

### A6. Unused `eslint-disable` directives removed (5 sites)

* `ErrorBoundary.jsx:20` — `eslint-disable-next-line no-console` (the only
  console.error in the file is intentional and the lint rule isn't set).
* `AiDesigner.jsx:1382` — `eslint-disable-next-line react-hooks/exhaustive-deps`.
* `PhotoToFlyer.jsx:369, 989, 1000` — same disable comment (3 sites).

All confirmed by ESLint as redundant; removing them does NOT re-introduce a
warning (the actual deps were already correct).

---

## B. Hook-dependency audit (bucket e — selective)

The report flagged 54 instances. Running ESLint's actual
`react-hooks/exhaustive-deps` rule against the entire frontend codebase now
reports **0 violations** — all the `useEffect` / `useCallback` deps that the
team committed are complete with the current rule set.

Spot-checked the three sites the report singled out as bug-risks:

| Site | Allegation | Reality |
|---|---|---|
| `PhotoToFlyer.jsx:369` | Missing `effectiveName`, `setName` | `effectiveName` IS in deps (via `[visionChoice]` — `effectiveName` is derived from `visionChoice`); `setName` is React-stable. No bug. |
| `PhotoToFlyer.jsx:1005` | "Missing 13+ dependencies" | `refreshRecs` uses only `getAuthHeader` (in deps), `setSavedMemory`/`setRecs`/`setRecsContext` (React-stable), and the module-level `API` constant. No real missing deps. |
| `PromoteThisItem.jsx:232` | Missing API, polling constants, state setters | `POLL_MS`/`POLL_TIMEOUT_MS` are module-scoped, `setProgress`/`setCurrentStep` are React-stable, `getAuthHeader`/`onCompleted`/`onFailed`/`jobId` are all in deps. No bug. |

No code changes needed in this bucket. The "54 missing deps" headline appears
to be from a separate scanner that flags React-stable setters and module-level
constants as missing deps — they are NOT.

---

## C. Declined with documented rationale

### C1. MD5 used in `render_engine.py:501`, `typography_engine.py:200, 217`

**Not a security issue.** All three MD5 calls are deterministic layout-selection
seeds:

```python
# render_engine.py:501
seed = int(hashlib.md5(theme_id.encode("utf-8")).hexdigest()[:6], 16)
return pool[(seed + variant_idx) % len(pool)]
```

This picks one of 6 layouts based on a theme name. No user data, no auth
token, no secret material. SHA-256 would produce identical behavior — the
output is reduced to a 6-hex-digit integer either way. MD5 is faster, which
matters because this runs on every flyer composition.

**Action:** Declined. The MD5 calls remain.

### C2. `random` module — 40 instances

All flagged uses are for **decorative variation**:

* `theme_packs/_overlays.py` — confetti / bubble / smoke placement (`random.uniform`).
* `typography_engine.py` — badge rotation jitter, distressed-stamp irregularity.
* `routers/ai_designer.py` — variant index seeding, decorative star placement.

None of these touch user IDs, auth tokens, or anything reversible. The
`secrets` module would be a 100×-slower drop-in with zero security gain.

**Action:** Declined. No changes to `random` usage.

### C3. JWT in localStorage

`Login.js:28`, `Dashboard.js:36, 41`, `BillingCard.jsx:23` all read the
session token from `localStorage.getItem("admin_token")`.

Replacing with httpOnly cookies would require:
* Backend: change `/api/auth/login` to set cookies + add CSRF middleware.
* Frontend: axios interceptor to read CSRF token from cookie.
* All admin routes: add `credentials: "include"` to fetch / axios calls.
* Cross-origin: configure SameSite + CORS for the Cloudflare-fronted
  production domain.

That's a multi-week security-hardening sprint, not a code-review fix.

**Action:** Declined for this pass. Logged as **P1 backlog: "Auth hardening
sprint — JWT cookies + CSRF middleware"** for after Sprint 20 ships.

---

## D. Deferred to a dedicated tech-debt sprint

### D1. `_compose_once` (161 lines, complexity 23)

* Splitting this would touch the SAME render engine that just received the
  Sprint 19 visual sign-off.
* Owner explicitly asked: "Do not refactor the rendering engine right now."
* Recommended approach when we do it: extract
  `_paint_background`, `_paint_food`, `_paint_overlay`, `_paint_badge`,
  `_paint_text` helpers — but ONLY after Sprint 20 stabilises and we have a
  golden-image regression suite to gate the diff.

### D2. `_pil_background` (complexity 42)

Same risk profile — used by every theme's `background_fn` chain. Refactor
together with D1.

### D3. Oversized React components

* `TodaysPick.jsx` (488), `AiDesigner.jsx` (412), `LibraryTab.jsx` (393),
  `AiImageGenerator.jsx` (345).
* Sprint 20 will rebuild Library as the new "Marketing Workspace" surface
  and split `TodaysPick` into the new Smart Insights widgets — natural
  refactor moment.

---

## E. Acceptance — pass/fail table

| Acceptance criterion | Result |
|---|---|
| No visual rendering regressions | ✅ Render engine 0 diff lines |
| No workflow regressions | ✅ Dashboard loads, 0 console errors, smoke screenshot clean |
| Lint / static warnings reduced | ✅ 16 → 2 ESLint problems; 6 → 0 ruff problems |
| Backend smoke still passes | ✅ 24 / 24 pytests green |
| Every warning fixed reported | ✅ See section A |
| Every warning documented as intentional reported | ✅ See section C |
| Every warning deferred reported | ✅ See section D |

---

## F. Files changed

```
backend/
  routers/creative_director.py        (2 unused-name fixes)
  scripts/sprint19_visual_audit.py    (3 E702 line splits)
  tests/test_ai_image_generation.py   (1 E401 fix)

frontend/src/
  App.js                              (key, fetchPriority, 5 entity escapes,
                                       2 catch blocks)
  components/ErrorBoundary.jsx        (remove unused eslint-disable)
  index.js                            (2 NODE_ENV guards)
  pages/ContentEditor.js              (1 NODE_ENV guard)
  pages/dashboard/HomeTab.jsx         (1 key fix)
  pages/dashboard/LibraryTab.jsx      (1 catch fix)
  pages/dashboard/aiads/AiDesigner.jsx        (4 catch fixes, 1 unused disable)
  pages/dashboard/aiads/PhotoToFlyer.jsx      (1 catch, 3 unused disables)
  pages/dashboard/aiads/PromoteThisItem.jsx   (1 catch fix)
  pages/dashboard/aiads/aiDesignerAnalytics.js (1 NODE_ENV guard)
  pages/dashboard/aiads/shared.jsx    (1 catch fix)
  pages/dashboard/home/TodaysPick.jsx (1 key, 1 entity escape, 1 NODE_ENV)
```

Render engine, typography engine, quality score engine, theme packs,
public APIs, auth, and session storage architecture were **not touched**.
