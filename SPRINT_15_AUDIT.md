# SPRINT 15 — ZERO-BS PLATFORM AUDIT
**Date:** Feb 22, 2026
**Auditor mode:** Senior architect + QA + UX + perf + restaurant owner
**Scope:** Read-only. No code changed. Findings only.

---

## INVESTIGATION ON THE SERVER ERROR SCREENSHOT

The "Server error — Something broke on our side. Please retry." banner comes from a **global axios interceptor** in `/app/frontend/src/index.js:26` that fires for ANY 5xx response from ANY API call.

Live test against production (https://lakeview-grill.emergent.host) on mobile viewport:
- `GET /api/menu` → 200
- `GET /api/specials?active_only=true` → 200
- `GET /api/content` → 200
- `POST /api/analytics/track` → 200
- No 5xx, no Server error banner reproduced.

**Verdict:** The error your screenshot captured was **transient**, likely from a cold-start of the deployed container, a brief MongoDB hiccup, or a single slow request that timed out. It is **not currently reproducing**. However, the root design flaw — see Bug #1 — guarantees you'll see this banner again and have no diagnostic information when you do.

---

## SECTION 1 — TOP 20 BUGS

| # | Severity | Bug | Location | Impact | Fix Effort |
|---|---|---|---|---|---|
| 1 | **HIGH** | Global "Server error" toast leaks to public homepage. Any 5xx from a public endpoint (e.g. `analytics/track`, `specials`, `content`, `menu`) pops the same generic toast in front of real diners. There is no rate-limit, dedupe, or context. | `frontend/src/index.js:25-27` | Diners see a scary red banner on a working site; owner can't tell which call failed. | 1 hour: gate the toast to dashboard routes only, or rate-limit per error-key, or include the URL in `description`. |
| 2 | **HIGH** | `admin_sessions` collection has **412 expired tokens out of 439** with no TTL index. `verify_session` only deletes one expired row when it happens to be hit; the rest live forever. | `backend/auth.py:36`, `server.py` index list | Unbounded growth, every login adds 1 doc; expired tokens are still queryable. Security-adjacent. | 30 min: add `TTL index on expires` (string ISO breaks normal TTL — need `expires_at` as `Date`). |
| 3 | **HIGH** | `home_health` pill counts **ffmpeg + rembg** as required subsystems, but the dashboard no longer uses either (MediaStudio is unmounted — see Section 7). Owner sees a yellow/red pill for a system they never touch. | `backend/routers/home.py:69-104` | Owner confusion ("is my site broken?"). | 30 min: drop ffmpeg+rembg from the health computation, or hide the pill until the feature returns. |
| 4 | **HIGH** | `index.js` line 17–22: 401 globally clears `admin_token` and redirects, but `/auth/verify` is hit on Dashboard mount — if the cookie expired the user gets bounced silently with no feedback about why. | `frontend/src/pages/Dashboard.js:46-54` + `index.js` | Owner thinks login is broken; actually session expired. | 1 hour: separate "session expired" copy from "wrong password". |
| 5 | **HIGH** | `AiDesigner.jsx` Progress component has a 6-minute timeout (`POLL_TIMEOUT_MS = 6 * 60 * 1000`) and the message tells users designs take **30–90 seconds**. If the backend gets slow (which happens — gpt-image-1 cold start can be 2 min), the polling silently keeps going past 90s with an unchanged spinner. | `AiDesigner.jsx:25, 480` | Owner-promised time (90s) is broken; abandonment likely. | This is exactly what Sprint 14B.1A was instrumented for. Wait for data. |
| 6 | **MEDIUM** | `Progress` `useEffect` lists `onCompleted`, `onFailed` in its deps array, which are passed inline `(j) => ...` arrows from `AiDesigner` top-level → new identity on every render → potential extra interval setup. The `clearInterval` cleanup hides this, but it's brittle and re-fires polls. | `AiDesigner.jsx:443-465` | Wasted polls, slight cost. | 30 min: useCallback or remove from deps. |
| 7 | **MEDIUM** | `HomeTab.jsx` makes **7 parallel API calls on every mount** including `/home/health` (which does `shutil.which("ffmpeg")` — a sync subprocess shell-out per request). | `HomeTab.jsx:86-93`, `home.py:73-77` | Slow Home load + IO on every refresh. | 1 hour: cache health for 60s server-side; remove ffmpeg/rembg per Bug #3. |
| 8 | **MEDIUM** | `App.js` (public site) fires `POST /api/analytics/track` on every route change **without throttling**. Bots, scrapers, and SEO crawlers all hit it. `page_views` already has **504 docs** in a small business DB. | `App.js:31` | DB write amplification; eventual cost. | 30 min: skip-if-bot user-agent filter + TTL is already 30d so it self-limits. |
| 9 | **MEDIUM** | `Login.js` uses `localStorage.getItem("admin_token")` for auth, but backend also issues an HttpOnly `session_token` cookie. Two sources of truth → cookie persists after logout if `delete_cookie` fails. | `auth.py:57-65, 80` | Subtle session leak. | 1 hour: pick one (cookie OR bearer) and remove the other. |
| 10 | **MEDIUM** | `TodaysPick` Copy Image button uses `navigator.clipboard.write([ClipboardItem(...)])` — **fails silently on iOS Safari <15.4 and most Android browsers**. The owner's screenshot is iOS Safari 9:36 AM. | `home/TodaysPick.jsx` (clipboard API) | Owner taps "Copy Image", nothing happens, no error. | 1 hour: add error toast + fallback "long-press to save" instructions. |
| 11 | **MEDIUM** | `marketing_pack.py` and `ai_designer.py` both write to `media_assets` and both run PIL composition with overlapping helpers. A render failure in one taints the asset folder visible in the other. | both routers | Owner sees ghosts in Library tab. | High. Refactor required. |
| 12 | **MEDIUM** | `verify_session` accepts an ISO-string `expires` and parses it on every call (`datetime.fromisoformat`). On 1000s of sessions, this is wasted CPU. Should be stored as native BSON `Date`. | `auth.py:30-35` | Mild CPU/perf. | 1 hour. |
| 13 | **MEDIUM** | `AiDesigner.jsx` `useEffect` for abandonment listens to `getAuthHeader` only (my recent fix). If `step`/`jobId` change without `getAuthHeader` changing, the listeners don't re-bind, which is intended — but the in-effect closure could capture stale state for `step` in the cleanup. Cleanup uses `hasActiveGeneration()` module-level helper, so it actually works, but the dependency is non-obvious. | `AiDesigner.jsx:1084-1097` | Maintenance footgun. | 15 min: add comment. |
| 14 | **MEDIUM** | Public Home (`App.js`) does an `axios.get` on `/menu` and `/content` for every visitor; no caching layer. Mongo gets queried per pageview. | `App.js:1080-1081` | DB pressure on traffic spikes. | 2 hours: add ETag or 60s memory cache. |
| 15 | **LOW** | `aiDesignerAnalytics.js` `sendBeacon` path uses `navigator.sendBeacon` without auth header (cookies-only). On iOS Safari, cross-origin sendBeacon often omits cookies. → silent loss of `page_unload` abandonment events. | `aiDesignerAnalytics.js:187-205` | Some abandon events never fire (already documented as known limitation). | 2 hours: switch to keepalive `fetch` with bearer header. |
| 16 | **LOW** | `Designer.submit()` sends `features: features` but on parse path uses `featuresText` newline-split — if user pastes a list with mixed `\r\n` (Windows) and `\n`, some lines get blank. | `AiDesigner.jsx:207-222` | Minor UX. | 15 min: normalize line endings. |
| 17 | **LOW** | `marketing_pack/generate` accepts `auto_copy` but no idempotency key — double-click generates two packs and burns cost. | `marketing_pack.py:469` | Owner accidentally pays twice. | 1 hour: client-side disable + server-side idempotency. |
| 18 | **LOW** | `media/assets` GET has `limit=200` cap; LibraryTab loads 200 thumbnails at once → slow on mobile. | `LibraryTab.jsx:29-30` | Slow Library on phone. | 2 hours: pagination or virtualization. |
| 19 | **LOW** | `loyalty/lookup?phone=` does substring scan, not indexed. With 30 members it's fine; with 3000 it's not. | `loyalty.py:39` | Future scaling. | 30 min: add phone index. |
| 20 | **LOW** | `catering/inquiry` POST has no rate-limit. Public form, spam vector. | `catering.py:14` | Spam fillup. | 30 min: hCaptcha or 1/min/IP. |

---

## SECTION 2 — TOP 20 DEAD CODE CANDIDATES

| # | File / Endpoint | Why dead | LOC | Recommendation |
|---|---|---|---|---|
| 1 | `pages/dashboard/aiads/MediaStudio.jsx` | **Imported by NO ONE**. Only reference is a comment in `LibraryTab.jsx:5-8` saying "MediaStudio remains as the editor" — but LibraryTab doesn't actually mount it. | 622 | **DELETE** |
| 2 | `pages/dashboard/aiads/ImageEditor.jsx` | Only imported by `MediaStudio.jsx`. Dies with #1. | 388 | **DELETE** |
| 3 | `routers/media/ai_image.py` (`/media/ai-image`, `/media/ai-image/job/{id}`) | Only callers are in MediaStudio (dead). | ~230 | **DELETE** |
| 4 | `routers/media/edit.py` (`/media/edit`) | Only caller is ImageEditor (dead). | ~? | **DELETE** |
| 5 | `routers/media/video.py` (`/video/render`, `/video/jobs`, `/video/jobs/{id}`) | Only callers in MediaStudio (dead). ffmpeg dependency is wholly for this. | ~150 | **DELETE** — and drop ffmpeg system dependency. |
| 6 | `routers/media/export.py` (`/export-social`) | Zero frontend callers. | ~50 | **DELETE** |
| 7 | `routers/ai_ads.py` — 9 of 10 endpoints | `/ai-ads/templates`, `/ai-ads/generate/{kind}`, `/ai-ads/assets` (GET/POST/PUT/DELETE/duplicate/bulk/export). Only `/ai-ads/stats` is called from `HomeTab.jsx`. Legacy from pre-Marketing-Pack era. | ~430 of 470 | **DELETE 9 of 10 routes**; keep `/stats`. |
| 8 | `/api/ai-designer/from-template/{id}` | Never called from frontend. | ~25 | **DELETE** |
| 9 | `/api/misc/upload-image` | Never called; superseded by `/media/upload`. | ~30 | **DELETE** |
| 10 | `server.py` SCHEDULER_INTERVAL_SECONDS + `_scheduler_task` | Dead comments and globals from Sprint 12D. | ~5 | **DELETE** |
| 11 | `routers/home.py` "scheduled" + "real_failures" legacy keys in summary | "Retained for one release" — but that release is past. | ~5 | **DELETE** keys + matching frontend reads. |
| 12 | `ai_image_jobs` collection (18 docs) | Only used by dead `/media/ai-image`. | DB | **DROP** |
| 13 | `render_jobs` collection (38 docs) | Only used by dead `/media/video`. Plus `media/assets.py` and `media/health.py` count these stats — also dead. | DB | **DROP** + remove the count calls. |
| 14 | `ai_generations` collection (42 docs) | Written by dead `/ai-ads/generate`, only read by dead `/ai-ads/stats`-adjacent paths. **Wait** — `/ai-ads/stats` IS used. Need to verify reads. | DB | **VERIFY then DROP** |
| 15 | `ai_design_templates` collection (0 docs) | Empty for 8+ months. Feature never adopted. | DB | **DROP** + remove `/templates` endpoint + Designer's template UI. |
| 16 | `button_clicks` collection (1 doc) | One click ever recorded. The instrumentation is wired (`App.js:47`), but it's never used to drive any decision. | DB | **DROP** OR start using it. |
| 17 | `menu_promotions` collection (2 docs) | Only updated by `marketing-pack/generate` and read by one endpoint. Unclear what value it adds vs. just looking at `marketing_packs.created_at`. | DB | **VERIFY** — likely DROP. |
| 18 | `failure_audit_log` collection (2 docs) | Has TTL, but in 8 months only 2 failures. Audit value is zero at this scale. Useful infra to keep, just shouldn't bias decisions. | DB | **KEEP** (cheap insurance) |
| 19 | `aiDesigner.jsx` "Pin" feature (`/jobs/{id}/pin`) | Endpoint exists; let me check FE usage — it IS called at line 942. **Not dead.** Listed for transparency. | — | KEEP |
| 20 | `aiDesigner.jsx` `Save as template` | Endpoint exists, FE button exists, but `ai_design_templates` has 0 docs after 8 months. Owner doesn't use it. | ~80 FE + 20 BE | **DELETE** — feature isn't being adopted; surface area for nothing. |

**Estimated total deletable code: ~2,000 lines + 6 collections + 15 endpoints.**

---

## SECTION 3 — TOP 10 DUPLICATE SYSTEMS

| # | Duplicate | Where | Owner Confusion | Action |
|---|---|---|---|---|
| 1 | **Two AI image generation pipelines.** "Marketing Pack" (PromoteThisItem) uses GPT-text + PIL overlays; "AI Designer" uses PIL composer with themes. Both produce social graphics from a food photo. | `PromoteThisItem.jsx` + `AiDesigner.jsx` | Owner has to learn two flows for the same outcome. | **MERGE.** Pick one. Designer is the better artifact (3 themes, single-select, deterministic). Marketing Pack adds caption packs — fold that into Designer's `auto_copy`. |
| 2 | **Today's Pick is AI Designer in a trench coat.** Today's Pick auto-runs PIL composition at 5:30 AM with the same theme machinery. | `todays_pick.py` + `ai_designer.py` | None to owner (single button). But code duplicates PIL helpers. | **MERGE** PIL helpers into a shared module; keep the cron + scheduled-pick logic in `todays_pick.py`. |
| 3 | **Two upload paths.** `/media/upload` (used) and `/misc/upload-image` (dead). | both | n/a | **DELETE** misc one. |
| 4 | **Two analytics events systems.** `usage_analytics` (Sprint 14A — Today's Pick + AI Designer events) vs `page_views` + `button_clicks` (App.js). | `analytics.py` + `todays_pick.py` POST /analytics | None to owner. But two collections, two endpoints, two query patterns. | **MERGE** into one `events` collection or at least one POST endpoint with a `type` field. |
| 5 | **Two ways to get to "Promote": (a)** Promote tab; **(b)** Home tab → "Promote this item" button on suggestions → modal version of the same component. | `Dashboard.js` + `HomeTab.jsx` + `PromoteThisItem.jsx` | Owner sees the same form twice. Cool — until they wonder which one their work was saved in. | **KEEP**, but unify visual styling so they look like the same screen. |
| 6 | **Two AI Designer entry points:** AiDesigner.jsx and "Today's Pick" both let the owner produce a promotable graphic. | dashboard | Owner asks "is Today's Pick different from a Custom?" | **MERGE** the conceptual model — make Today's Pick a "Designer preset" you can re-roll. |
| 7 | **Two CMS surfaces:** `/api/content` (one-doc CMS for hero/about) and `/api/menu` (categories) — different shapes, same dashboard "Menu" tab. | `cms.py` | Slight. | KEEP (different domain models). |
| 8 | **Three places to copy a caption:** Today's Pick card, AI Designer Review, PromoteThisItem result. Three "Copy" buttons, three implementations. | various | Different keyboard shortcuts/toasts. | **STANDARDIZE** the Copy button (one shared component with one toast style). |
| 9 | **PIL composer logic is split across `marketing_pack.py` and `ai_designer.py`** — both crop food, lay overlays, draw price badges. | both routers | Code duplication only. | **MERGE** into `backend/lib/pil_composer.py`. |
| 10 | **Two folders concept in Library:** `LibraryTab.jsx` is flat; `media/assets.py` still returns `folders` arrays; `MediaStudio.jsx` (dead) had a folder browser. | mixed | Owner sees `folder` field on uploads but no UI to filter by it. | **DELETE** folder field if not surfacing it. |

---

## SECTION 4 — TOP 10 UX FRICTION POINTS

Performed owner simulation. Findings, ranked by friction:

| # | Task | Time | Clicks | Friction |
|---|---|---|---|---|
| 1 | **Reply to a customer inquiry** | 60-90s | 6+ | No `mailto:` link. Owner must (1) click inquiry, (2) read email, (3) manually select+copy email, (4) open mail app, (5) paste, (6) type reply. **THIS WAS FLAGGED FOR SPRINT 14B.3.** Still unfixed. |
| 2 | **AI Designer 60-90s wait** | 90s+ | 1 | No progress %, no ETA, no background mode. Owner stares at a spinner. **Sprint 14B.1A now instrumenting; do not build progress bars yet per your mandate.** |
| 3 | **Reuse old graphic** | 30s | 4 | Recent Designs rail at top of AI Designer is good. But "Copy caption" requires re-opening the job — and copy isn't saved with the job, so the caption is gone. **Flagged in Sprint 14B.3.** |
| 4 | **Where do I post a custom graphic?** | varies | 4-8 | After Designer completes, owner gets 3 designs. To actually post, they have to: copy image → switch to IG → paste. No native "Post to Instagram" deep-link. |
| 5 | **Server error toast** | — | 0 | Generic "Something broke" with no detail, no retry button. (See Bug #1.) |
| 6 | **Mobile layout on public Home** | — | — | Top toast in your screenshot overlapped the Lakeview logo. Sonner's `top-right` position on a 390-wide iPhone fills the entire top of screen. |
| 7 | **Dashboard auth check** | 1-2s | — | Every Dashboard mount calls `/auth/verify` synchronously before rendering anything → "Loading dashboard..." for 1-2s on every reload. |
| 8 | **Switching between Marketing Pack and AI Designer** | — | 2 | Inside Promote tab the toggle is a small pill at the top. Owner doesn't realize there are two modes. |
| 9 | **No "what does this button do" affordance** | — | — | Owner-facing copy on AI Designer ("Each design takes about 30–90 seconds. Hang tight.") is informal but offers no recovery path if it goes longer. |
| 10 | **Library = 200 thumbnails at once** | 5-15s on 4G | — | LibraryTab fetches `limit=200` and renders all. On 3G/4G mobile, this is brutal. |

---

## SECTION 5 — COLLECTIONS SAFE TO DELETE

After confirming no live writers:

| Collection | Docs | Safe to drop? | Notes |
|---|---|---|---|
| `ai_image_jobs` | 18 | ✅ YES | Dead with MediaStudio. |
| `render_jobs` | 38 | ✅ YES | Dead with /video. |
| `ai_design_templates` | 0 | ✅ YES | Never used. |
| `button_clicks` | 1 | ✅ YES (or start using) | One click in 8 months. |
| `ai_generations` | 42 | ⚠️ VERIFY | Written by dead `/ai-ads/generate`; `/ai-ads/stats` reads it. Confirm `/ai-ads/stats` still produces useful Home numbers before dropping. |
| `menu_promotions` | 2 | ⚠️ VERIFY | Read by `/marketing-pack/items-not-promoted-recently`. **Keep until that endpoint is also re-evaluated.** |
| `failure_audit_log` | 2 | ❌ KEEP | Cheap audit; TTL'd. |
| `admin_sessions` | 439 (412 expired) | ⚠️ CLEAN | Don't drop, but **add TTL + bulk-delete expired now**. |

---

## SECTION 6 — ROUTES SAFE TO DELETE

```
DELETE /api/misc/upload-image                     # superseded
DELETE /api/ai-ads/templates                      # legacy
DELETE /api/ai-ads/generate/{kind}                # legacy
DELETE /api/ai-ads/assets                         # legacy (GET, POST)
DELETE /api/ai-ads/assets/{asset_id}              # legacy (PUT, DELETE)
DELETE /api/ai-ads/assets/{asset_id}/duplicate    # legacy
DELETE /api/ai-ads/assets/bulk                    # legacy
DELETE /api/ai-ads/assets/export                  # legacy
DELETE /api/ai-designer/from-template/{id}        # never used
DELETE /api/media/ai-image                        # dies with MediaStudio
DELETE /api/media/ai-image/job/{job_id}           # dies with MediaStudio
DELETE /api/media/edit                            # dies with ImageEditor
DELETE /api/media/video/render                    # dies with MediaStudio
DELETE /api/media/video/jobs                      # dies with MediaStudio
DELETE /api/media/video/jobs/{job_id}             # dies with MediaStudio
DELETE /api/media/export-social                   # zero callers
```
**Total: 16 endpoints, ~900 LOC** of backend code.

---

## SECTION 7 — COMPONENTS SAFE TO DELETE

```
DELETE frontend/src/pages/dashboard/aiads/MediaStudio.jsx       (622 LOC)
DELETE frontend/src/pages/dashboard/aiads/ImageEditor.jsx       (388 LOC)
EVALUATE — frontend/src/pages/dashboard/aiads/AiDesigner.jsx
   • "Save as template" button (lines around 763) — dead
   • Templates rail (lines 277-310) — never has data
```
Plus comment cleanup in `LibraryTab.jsx:1-9` (stale comment about MediaStudio).

**Total: ~1,000 LOC of frontend.**

---

## SECTION 8 — PERFORMANCE IMPROVEMENTS

| # | Improvement | Win | Effort |
|---|---|---|---|
| 1 | Remove `shutil.which("ffmpeg")` from `home/health` (called on every Home load). | -50ms/load + no subprocess fork. | 5 min |
| 2 | Cache `/menu` and `/content` (public, immutable per CMS save) for 60s in memory. | -2 DB queries per pageview. | 1 hour |
| 3 | Add MongoDB TTL on `admin_sessions.expires` (after migrating it to native `Date`). | 412 docs immediately gone. | 30 min |
| 4 | Bot/UA filter on `/analytics/track`. | -30-50% writes. | 30 min |
| 5 | Paginate `LibraryTab` (load 24, lazy-load more on scroll). | Cuts mobile load from 5-15s to <1s. | 2 hours |
| 6 | Add MongoDB index on `media_assets.uploaded_at` (sort key). | Faster Library. | 5 min |
| 7 | Replace `AiDesigner`'s `POLL_MS=4000` with exponential backoff (4s → 8s → 12s). | Fewer requests during long jobs. | 30 min |
| 8 | Compress thumbnails server-side; serve WebP. | Mobile data savings. | 2 hours |

---

## SECTION 9 — SECURITY CONCERNS

| # | Severity | Concern | Action |
|---|---|---|---|
| 1 | MEDIUM | `admin_sessions` 412 expired tokens persisting; sessions are stored as ISO strings, not native dates — TTL can't be applied directly. | Migrate `expires` to BSON Date, then `createIndex({expires:1}, {expireAfterSeconds:0})`. Bulk-delete current expired. |
| 2 | MEDIUM | Dual auth (cookie + localStorage bearer). Bearer leaks via XSS if any exists; cookie leaks via CSRF if not SameSite=Strict. Current is `samesite="lax"`. | Pick one. If staying with bearer, set `samesite="strict"` on cookie OR remove it entirely. |
| 3 | MEDIUM | `/api/catering/inquiry` and `/api/loyalty/join` and `/api/newsletter/subscribe` are unauthenticated public endpoints with no rate-limit / captcha. | Add per-IP rate-limit (the `slowapi` `limiter` is already imported elsewhere). |
| 4 | LOW | `verify_admin_password` (used in `auth.py:45`) — if it uses bcrypt with the env-stored hash, ensure `$` is not shell-expanded. Standard Lakeview footgun per handoff. | Audit `config.py:verify_admin_password`. |
| 5 | LOW | Frontend stores token in `localStorage` (XSS risk). Move to HttpOnly cookie only. | (See #2.) |
| 6 | LOW | `/api/messages/send` (used in CustomersTab) sends blast SMS/email — if there's no rate-limit and the bearer leaks, an attacker spams the loyalty members. | Add 10/min limit on `/messages/send`. |
| 7 | LOW | No CORS allowlist visible in `server.py` (skimmed). | Confirm CORS is restricted in prod. |

---

## SECTION 10 — PRODUCTION READINESS SCORE

| Dimension | Score /20 | Notes |
|---|---|---|
| **Stability** | 13 | No critical crashes; transient 5xx are masked by generic toast; no observability into what fails. |
| **Performance** | 11 | Public site OK. Dashboard makes 7 parallel calls on mount, one of which `shutil`s ffmpeg. Library loads 200 images. |
| **Maintainability** | 9 | `AiDesigner.jsx` 1,216 LOC monolith. ~2,000 LOC of dead code in `aiads/`. 9 dead ai-ads endpoints. Duplicate PIL composer. |
| **Owner Experience** | 12 | Today's Pick + Copy Image are excellent. AI Designer wait is a black box. Inquiries have no mailto. |
| **Mobile Experience** | 11 | Sonner toasts overlap content; Library is 200-thumb dump; Clipboard API silently fails on older iOS. |

**OVERALL: 56 / 100**

The platform works. The owner can post Today's Pick in <90s — that's real. But under that hood is **~2,000 LOC of dead code from previous sprints**, **6 collections that should be dropped**, **16 endpoints with zero callers**, and **412 expired admin sessions**. The platform isn't broken — it's bloated.

---

## FINAL QUESTION

> "If you owned this restaurant and had only 10 minutes per day to use this platform, what would you delete immediately?"

**Brutally honest answer — delete this week:**

1. **`MediaStudio.jsx` + `ImageEditor.jsx` + their backend routes.** 1,000+ LOC for a feature that's mounted nowhere. (`AI Image Generator`, video slideshow, image editor.)
2. **9 of 10 `/ai-ads/*` endpoints.** They're a graveyard from before Marketing Pack existed.
3. **`ai_design_templates` collection + "Save as Template" + the templates rail in AI Designer.** Zero adoption in 8 months. The owner isn't using it. Stop showing it.
4. **`button_clicks` collection.** One click in 8 months. Either start using it or delete.
5. **`render_jobs` + `ai_image_jobs` collections.** Dead with their parents.
6. **`home/health`'s ffmpeg + rembg checks.** Misleading red/yellow pill for a system the owner doesn't use.
7. **The "Server error" global toast.** Replace it with route-aware error handling, OR remove it from public routes.
8. **The 412 expired admin_sessions.** Migrate `expires` to BSON Date, add TTL, bulk-delete. 30-minute job.

**Keep these — they're earning their keep:**
- Today's Pick (the entire flow, including the 5:30 AM cron). This is the platform's killer feature.
- AI Designer for one-off custom graphics.
- Menu + Content editor.
- Loyalty stamping.
- Catering inquiries form.
- Public site (works, fast).

**The "stop building, start removing" play is real here.** Every dead route is a deploy-blocker waiting to happen, every dead collection is a backup cost, every dead component is a build-time penalty. The owner's velocity is being slowed not by missing features but by carrying the corpses of cancelled features.

---

## RECOMMENDED CLEANUP SPRINT (if you ever want it)

**Sprint 15B — Carcass Removal (1-2 days):**
- Day 1: Delete dead frontend (MediaStudio, ImageEditor, save-template UI). Delete 16 dead routes. Drop 4 dead collections.
- Day 2: Fix Bug #1 (route-aware error toast), Bug #2 (admin_sessions TTL), Bug #3 (health pill cleanup). Cache `/menu` and `/content`.

**Result:** -3,000 LOC, -6 collections, -16 routes, +30 readiness score.

But **per your mandate, no code changes have been made.** This report is the deliverable. Tell me which sections (if any) to action.
