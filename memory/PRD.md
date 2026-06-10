# Lakeview Burgers & Seafood - Website PRD

## Original Problem Statement
Build a website for restaurant "Lakeview Burgers & Seafood" featuring menu, ordering, admin dashboard, SEO, CMS, summer giveaway, loyalty program, and messaging system.

## Architecture
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Auth**: JWT Bearer token
- **Integrations**: SendGrid (email), Twilio (SMS) — keys pending

## Implemented Features

### Public Site
- Hero, About, Menu, Contact (all CMS-editable)
- Specials (auto-displayed from dashboard)
- Email newsletter signup
- Loyalty Punch Card (join + lookup visits)
- Catering inquiry form
- Google Maps embed
- Sticky order bar (Uber Eats + Square)
- Spin & Win giveaway (admin-activated)

### Admin Dashboard (9 tabs)
1. Analytics, 2. Specials, 3. Site Content, 4. Menu Editor, 5. Giveaway, 6. Loyalty, 7. Messages, 8. Inquiries, 9. Subscribers

### Key Systems
- **CMS**: Edit all site text + full menu from dashboard
- **Giveaway**: Spin wheel with 8 prizes, admin activate/deactivate
- **Loyalty**: 10 visits = free meal, stamp from dashboard
- **Messaging**: Blast emails/SMS to subscribers, giveaway entries, loyalty members
- **SEO**: 4 JSON-LD schemas, robots.txt, sitemap.xml, geo tags

## Testing: 122/123 backend (99%), full frontend coverage

## Changelog
- **Feb 2026 — AI Ad Builder (Phase 1)**:
  - New `AI Ads` tab in dashboard. Industry-agnostic reusable engine.
  - Backend: `/app/backend/ai_engine/` (client, prompts, templates, industries/restaurant) + `/app/backend/routers/ai_ads.py` (8 endpoints).
  - 3 MongoDB collections: `ai_campaigns`, `ai_generations`, `ai_config`.
  - GPT-5 via Emergent LLM key with `emergentintegrations`. Model is DB-configurable via Settings panel (provider+model stored in `ai_config`).
  - 11 campaign templates: 8 restaurant (Promotion / Daily Special / Happy Hour / Catering / Seafood Special / Burger Special / Event Promotion / Customer Loyalty) + 3 generic (Lead Gen / Event / Loyalty).
  - Master generation = 5 headlines + 3 primary text + 3 CTAs + 8-12 hashtags + 3 image concepts + 2 video concepts + 3 video hooks.
  - "Generate More Variations" button increments `variation_seed` to force fresh outputs.
  - Save/Load/Delete saved campaigns with status (draft/active/archived).
  - Audit trail: every generation persisted with full brief + output + model + timestamp.
  - Rate-limited (10/min per IP via slowapi).
  - All `verify_session` protected. Input validation on every field.
  - Worked around Emergent visual-edits Babel plugin recursion bug by precomputing JSX arrays (no inline `.map(c => c.x)` patterns in main file).
- **Feb 2026 — Part 2: Security Hardening**:
  - **bcrypt password storage**: replaced unsalted SHA-256 with bcrypt (12 rounds + per-process salt). `verify_admin_password` uses `bcrypt.checkpw` (timing-safe). Verified hash format `$2b$12$...`.
  - **Rate limiting via slowapi**: per-IP limits using `X-Forwarded-For` (ingress-aware). Login 10/min, public submissions (newsletter/catering/loyalty) 5/min, spin 3/min, analytics 60/min. Verified 6th rapid call returns 429.
  - **Upload validation**: `/api/upload-image` now rejects non-image MIME types (only jpeg/png/webp/gif) and files >5 MB.
  - **Input length caps**: All Pydantic models gained `constr(max_length=...)` + `EmailStr` validation. Forms now block 5000-char emails, oversized messages, invalid recipient/channel enums.
- **Feb 2026 — Part 1: Performance & SEO Foundation**:
  - Added proper SEO `<h1>` to home page (visually hidden), favicon `<link rel="icon">` + `apple-touch-icon`, removed unused Inter font.
  - Lazy-loaded all non-hero images (`loading="lazy"` + `decoding="async"` on about, footer, specials, install prompt).
  - Optimized hero BG URL with Unsplash `w=1600&q=75` params (≈80% smaller).
  - Added `fetchpriority="high"` to hero logo. FCP measured 104 ms, full load 1.24 s.
- **Feb 2026 — Dashboard JSX Cleanup**:
  - Converted `GiveawayManager.js` (134L) and `LoyaltyMessaging.js` (228L) from legacy `React.createElement(...)` to modern JSX.
  - Worked around an Emergent `visual-edits/babel-metadata-plugin` recursion bug (`getArrayIterationContext` ↔ `analyzeMemberExpression`) by extracting sub-components (`PunchDots`, `LoyaltyMemberRow`, `ResultBanner`, `BlastHistoryRow`, `PrizeRow`, `EntryRow`) — breaks the plugin's recursive scan boundary.
- **Feb 2026 — Dashboard.js Refactor + Lazy-Loading**:
  - Split `Dashboard.js` (918L → 179L) into orchestrator + per-tab components (`AnalyticsTab`, `SpecialsTab`, `CateringTab`, `SubscribersTab` under `/pages/dashboard/`).
  - Each tab lazy-fetches its own data on mount instead of all tabs loading on dashboard open. Verified via Playwright network trace.
- **Feb 2026 — Backend Modularization**:
  - Split monolithic `server.py` (1085 lines) into modular structure: `server.py` (69L entry), `config.py`, `models.py`, `seed_data.py`, `auth.py`, and 9 routers under `/routers/` (cms, specials, analytics, giveaway, loyalty, messaging, catering, newsletter, misc). Zero behavioral changes — 123/123 backend tests pass.
- **Feb 2026 — PWA Install Prompt + Analytics**:
  - New `InstallPrompt` component fires after 30s engagement or 60% scroll; Android native install + iOS instructions; 7-day dismissal cooldown.
  - New "PWA Installs" KPI card on Dashboard Analytics tab tracking accepted/dismissed/completed funnel via `appinstalled` event.
  - New Catering nav link on desktop + mobile drawer.
- **Feb 2026 — P0 Cleanup + P1 Session Persistence**:
  - Removed dead code: `frontend/src/data/menu.js`, unused `/api/status` routes + `StatusCheck` model, unused FastAPI imports (`HTTPBasic`, `Depends`, `Any`).
  - Removed hardcoded `ADMIN_PASSWORD='Lakeview872'` fallback in `server.py` — now loaded from `.env` only (fails fast if missing).
  - Fixed missing mobile hamburger menu in `App.js` Navbar (new `mobile-menu-toggle` + `mobile-menu-drawer` testids).
  - Added missing CSS classes to `index.css`: `section-divider`, `decorative-border`, `img-zoom`, `btn-vintage`, `hero-bg`.
  - Fixed stale JSON-LD menu prices in `index.html` to match real CMS menu.
  - **P1**: Migrated admin sessions from in-memory dict to MongoDB `admin_sessions` collection — sessions now survive backend restarts. All `verify_session()` calls are now async.
  - Fixed `/api/auth/logout` to honour `Authorization: Bearer` header in addition to cookie (was silently leaving tokens active).

## Pending
- SendGrid API key (for email blasts)
- Twilio API key (for SMS blasts)

## Changelog (Latest First)

### Feb 9, 2026 — Post-Launch Optimization Pass — Complete (6/7 fully, 1 cosmetic deferred)

Maintenance-only pass — no new features, no behavior change beyond bug fixes:

1. **MongoDB indexes** on hot collections — idempotent `create_index` calls in `server.py:on_startup`:
   - `ai_assets`: `(status, kind, created_at)`, `(platform, created_at)`, `(is_favorite, created_at)`, `(id, unique)`
   - `scheduled_posts`: `(status, scheduled_at)`, `(provider, scheduled_at)`, `(id, unique)`
   - `publish_logs`: `(scheduled_post_id, created_at)`, `(created_at)`
   - `ai_generations`: `(created_at)`, `(brief.platform)`
   - `provider_connections`: `(provider, business_id, unique)`
   - **Observed latency:** hot endpoints (`/assets`, `/calendar`, `/publish-queue`, `/analytics`) 81–140 ms via ingress.

2. **Mobile AI Ads sub-tab scroll** — `overflow-x-auto` + `whitespace-nowrap` + `shrink-0` on the 14 sub-tab buttons. Wraps as before on desktop (`md:flex-wrap md:overflow-x-visible`).

3. **Test All Connections** — `POST /api/ai-ads/provider-connections/test-all` runs the read-only auth probe in parallel across every saved connection (`asyncio.gather`) and persists `last_test_at/ok/message/latency_ms` on each. UI: gold "Test All Connections (N)" button on the Providers tab + summary banner ("3/4 connections healthy · 1 failed").

4. **401 expired-token toast** — global axios interceptor in `index.js`: any 401 (except `/auth/login`) clears `admin_token`, shows a sonner toast "Session expired" with a "Sign in" action that navigates to `/login`. Same interceptor surfaces 403 and 500 errors. Switched from the shadcn `@/components/ui/sonner` wrapper (which silently failed due to a `next-themes` dependency) to a direct `import { Toaster } from "sonner"`.

5. **Library search debounce** — 350ms debounce on `filters.q` only. Other filters (kind/platform/status/favorite/date) apply instantly. Verified: 5 keystrokes now fire exactly 1 `/api/ai-ads/assets` request instead of 6.

6. **Plugin catalog pre-warm** — `list_plugins()` + `get_plugin("restaurant")` called once on startup so the first Automation Center mount is a cache hit (<100 ms).

7. **Recharts `width(-1)` warnings** — _cosmetic dev-only_. Improved with 2-rAF mount gate + explicit `width:100%/height:240` inline + `min-w-[200px]` on chart wrappers. Charts render perfectly (751/544/544 px widths, 240 px height). The 6 dev-mode warnings on Analytics mount remain (3 charts × StrictMode double-invoke). User-invisible — left as known low-priority polish item.

**Tests — 62/62 pytests pass** (51 regression + 11 new `test_iter15_maintenance.py`). Frontend regression 100% on the 6 fixed items (`/app/test_reports/iteration_16.json`).

### Feb 9, 2026 — Final Production Launch Phase — Complete

**Phase 1 — Full audit:** Reviewed every tab; zero console errors, all loading & empty states present, 14 AI Ads sub-tabs render cleanly, mobile layout intact (Tailwind responsive grid throughout).

**Phase 2 — Owner workflow cleanup:** New **Owner Quick Start** band (`/app/frontend/src/pages/dashboard/AnalyticsTab.jsx`) at the top of the default Analytics tab — 6 tiles with deep-links: Edit Menu, Create Special, Promote Item, Schedule Posts, Publish Queue, Connect Providers. Tiles now navigate not just to the top-level tab but to the *exact sub-tab* (e.g. Schedule Posts → AI Ads → Calendar).

**Phase 3 — Provider Connection Checklist:**
- `GET /api/ai-ads/provider-setup/{provider}` — returns `{title, steps[≥3], docs_url}` for each of the 6 real providers (Facebook, Instagram, Google Business, Mailchimp, SendGrid, Twilio). Step-by-step instructions in plain English.
- `POST /api/ai-ads/provider-connections/{provider}/test` — runs a **read-only auth probe** against the live provider API and persists `last_test_at`, `last_test_ok`, `last_test_message`, `last_test_latency_ms` on the connection record. Surfaces the platform's real error verbatim (verified: SendGrid 401 "unauthorized" + Facebook OAuth errors flow through unchanged → proves real network call).
- `GET /api/ai-ads/health` — system-readiness check: database, LLM key, scheduler activity, provider connection summary. Run this before going live.
- Frontend: each Provider card now has a **Setup Guide** expander, a **Test Connection** button (when connected), inline test-result panel, and a persistent "Last test" pill showing `✓ Auth OK` or `✗ Failed — {message} · {ms}ms`.

**Phase 4 — Live readiness testing:** 51/51 backend pytests pass across 4 files (`test_final_launch.py` 11 + `test_phase1_real_providers.py` 9 + `test_phase6_publishing.py` 13 + `test_ai_ads_phase345.py` 18). Frontend 100% (test_reports/iteration_14.json).

**Phase 5 — Backup & safety:**
- `window.confirm()` on every destructive action (single + bulk deletes already in place + count-aware bulk delete).
- Soft-delete via Archive (status=`archived`) on assets; hard delete still available but requires explicit click.
- Audit logging in `publish_logs` for every schedule / cancel / reschedule / publish.
- Auth brute-force protection: 5 attempts → 15 min lockout (slowapi).
- Credentials NEVER returned to the frontend — server-side test only echoes `{ok, message, latency_ms}`.
- React `ErrorBoundary` at root catches any uncaught render error.

**Phase 6 — Final docs created:**
- `/app/memory/OPERATOR_GUIDE.md` — non-technical owner manual + Daily / Weekly / Monthly checklists.
- `/app/memory/DEPLOYMENT_CHECKLIST.md` — env vars, pre-launch checklist, safety features, backup commands, recovery steps.

**Production polish from previous phase still in place:** 101 KB WebP logo (96% smaller than original 2.5 MB), Google Maps desktop fix, tappable address, Facebook + Instagram footer icons, ErrorBoundary fallback.

### Feb 9, 2026 — Production Readiness & Restaurant Automation — Complete

**Phase 1 — Real publishing (NO MORE SIMULATION):**
- `/app/backend/publishing/real_providers.py` replaces the simulation stubs at import time. Real `httpx` HTTP calls to: Facebook Graph API v19 (`POST /{page_id}/feed`), Instagram Graph API (2-step container+publish), Google Business Profile (`v4/.../localPosts`), Mailchimp v3 (create→content→send), SendGrid v3 (`/v3/mail/send`), Twilio REST (`/Messages.json`). Stored on success: `external_post_id`, `published_url`, `published_at`, `provider_response`.
- Without credentials → returns `status="failed"` with actionable error: "Open AI Ads → Providers and connect {provider} before publishing." No silent simulated success.
- With invalid credentials → real platform error surfaces (verified: Facebook returns "Invalid OAuth access token" — proves real network call).

**Phase 2 — Restaurant Automation Center** (`/app/frontend/src/pages/dashboard/aiads/RestaurantAutomationCenter.jsx`, now the **default AI Ads sub-tab**):
- 4 production lanes — Daily Specials, Google Review Requests, Loyalty Campaigns, Catering Marketing.
- 13 new restaurant templates added to the Restaurant plugin (review_request_sms/email/followup, loyalty_first_visit/repeat/birthday/winback/vip, catering_office_lunch/corporate/school/holiday_party/family) — **20 total** templates.
- Each lane: template select + optional menu-item picker (specials) + channel chips + fan-out generate → assets saved to Library → one-click "Schedule This Bundle" popover that bulk-schedules each asset to its native platform with operator-controlled stagger.

**Phase 3 — BI / KPI dashboard:** Top "Restaurant KPIs" band on Analytics sub-tab — 4 cards: Publish Success Rate, Most Promoted Menu Item, Best Platform, Best Campaign Type. Sits ABOVE the existing 6 stat cards (no redesign).

**Phase 4 — Production polish:**
- **Logo: 2.5 MB PNG → 101 KB WebP** (96% reduction) — `/app/frontend/public/logo.webp`, referenced 3× in nav/hero/footer.
- **ErrorBoundary** mounted at the React root (`/app/frontend/src/index.js`) — friendly fallback + Refresh button.
- **Footer: Facebook + Instagram icons** with proper hrefs (facebook.com/lakeviewburgers, instagram.com/lakeviewburgers), `target=_blank`, `aria-label`, hover gold.
- **Tappable address**: Contact section anchor wraps the address with `https://maps.google.com/?q=...` (mobile deep-link to Apple/Google Maps).
- **Google Maps iframe** migrated to the `maps.google.com/maps?q=...&output=embed` format — renders correctly on desktop now.

**Testing — 40/40 backend pytests pass in 25s** + 100% frontend regression (test_reports/iteration_13.json):
- 9/9 phase1_real_providers (no-connection → failed; invalid token → real Facebook error)
- 13/13 phase6_publishing (updated 2 tests to match new real-providers contract)
- 18/18 phase345 regression
- Smoke E2E: Automation Center → Daily Specials → SMS-only → Generate → asset saved → Schedule Bundle → Calendar shows the scheduled event.

### Feb 9, 2026 — AI Marketing Studio Phase 6 (Schedule & Publish System) — Complete

**Database changes** (4 new collections, all carry `business_id` for multi-tenancy):
- `scheduled_posts` — id, asset_id, campaign_id, business_id, platform, provider, scheduled_at, published_at, status (draft/scheduled/publishing/published/failed/cancelled), error_message, external_id, attempts, created_at, updated_at, title, kind, notes.
- `publish_jobs` — short-lived job records (one per publish attempt) with status, result, error.
- `publish_logs` — append-only audit trail (action, actor, detail, created_at).
- `provider_connections` — provider-scoped credentials (never returned in API responses).
- `automation_rules` — recurring generation rules (frequency, day_of_week, day_of_month, hour, template_id, auto_publish, auto_publish_provider, is_active).

**Backend** (`/app/backend/publishing/`):
- Provider abstraction: `Publisher` interface, `register_provider()` / `get_provider()` / `publish_now()`.
- 6 real providers (`facebook`, `instagram`, `google_business`, `mailchimp`, `email`, `sms`) + 4 future-ready (`tiktok`, `linkedin`, `x`, `youtube`) marked `coming_soon`. Real providers currently simulate publishing (success=True, `sim_*` external_id) until live credentials are supplied — architecture is real, only the network call is stubbed.
- Scheduler core: `schedule_publish`, `cancel_publish`, `reschedule_publish`, `execute_publish`, `run_due_publishes`. All actions write to `publish_logs`.
- Background worker: `asyncio.create_task(_scheduler_loop)` in `server.py` polls `scheduled_posts` every 30s and publishes anything due.

**API routes added (15)** all under `/api/ai-ads`:
- `GET /calendar`, `GET /publish-queue`, `GET /publish-logs`
- `POST /schedule`, `POST /publish`, `POST /cancel/{id}`, `POST /reschedule/{id}`, `POST /bundle-schedule`, `POST /run-due-now`
- `GET /publish-providers`, `GET /provider-connections`, `POST /provider-connections/{provider}/connect`, `POST /provider-connections/{provider}/disconnect`
- `GET/POST /automations`, `PUT/DELETE /automations/{id}`
- `GET /smart-recommendations`, `GET /publish-stats`

**Frontend** (5 new sub-tabs in AI Ads, total now 13):
- **Calendar** — in-house month/week/day grid, 5-color status legend, drag-and-drop reschedules, click-to-edit popover (reschedule or cancel).
- **Queue** — 4-column kanban (queued / publishing / published / failed), provider filter, refresh, per-card Retry / Cancel.
- **Providers** — 10 provider cards (6 connectable, 4 coming-soon); inline credential form per provider; connected state with Last Sync timestamp.
- **Automations** — CRUD for recurring rules (daily/weekly/monthly), auto-publish toggle, active/inactive switch.
- **Library** (extended) — every asset row gets a gold Calendar action → `SchedulePopover` (Schedule or Publish Now per provider).

**Tests:** 13/13 phase6 pytests pass in 3.23s (`/app/backend/tests/test_phase6_publishing.py`) + 18/18 phase3-4-5 regression = **31/31 = 100%**. End-to-end integration verified in browser: schedule-in-past → queued → run-due-now → published with `sim_*` id → calendar shows green → 3 audit log entries.

**Multi-tenant readiness:** every new collection carries `business_id` (defaulted to `"default"`). No restaurant-specific logic in `/app/backend/publishing/`.

### Feb 9, 2026 — AI Marketing Studio Phases 3 + 4 + 5 (Complete)

**Phase 3 — Restaurant Mode (pluggable industry module)**
- Built plugin system at `/app/backend/ai_engine/plugins/` with `Plugin` class + registry. Core engine never imports verticals; future plugins (moving / event / retail / service) just `register_plugin(...)`.
- Restaurant plugin (`plugins/restaurant.py`) ships **7 templates** (daily_special, seafood_special, burger_special, happy_hour, catering_promotion, event_promotion, loyalty_campaign) and **9 one-click channels** (facebook_ad, instagram_caption, tiktok_caption, google_business_post, email_campaign, sms_campaign, flyer_copy, image_prompt, video_script_15).
- Endpoints: `GET /api/ai-ads/plugins`, `GET /api/ai-ads/plugins/{id}`, `POST /api/ai-ads/plugins/{id}/promote` (saves to library by default; rate-limited 30/min).
- Frontend: gold Sparkles "Promote" button on every Menu Editor item row → `PromoteItemModal` lets operator pick template + channels; **fans out 1 HTTP request per channel via `Promise.allSettled`** so each call gets its own ingress 60s budget (resolves the blocking-LLM-client issue).

**Phase 4 — Campaign Management**
- New status `scheduled` added to assets + campaigns (`(draft|scheduled|active|archived)`).
- `POST /api/ai-ads/assets/bulk` — bulk archive / unarchive / delete / favorite / unfavorite.
- `POST /api/ai-ads/assets/export` — TXT / CSV / JSON (filename `ai-assets-YYYY-MM-DD.{ext}`); browser also supports Copy-to-Clipboard.
- `GET /api/ai-ads/assets` already supported `q`, `kind`, `platform`, `status`, `is_favorite`, `date_from`, `date_to` — UI now exposes all filters.
- Frontend Library: row checkboxes + sticky bulk-action bar (`ai-library-bulk-bar`) with Archive / Favorite / Copy / TXT / CSV / JSON / Delete / Clear, plus "Select all".

**Phase 5 — Analytics Dashboard**
- New `GET /api/ai-ads/analytics` returns `{totals, insights, charts}` — 9 totals (campaigns/generations/this-month/last-30/ads/emails/sms/videos/images), 4 insights (most_used_platform / campaign_type / goal / most_generated_items[]), and 3 charts (trend_30_days, platform_usage, campaign_type_breakdown).
- New `Analytics` sub-tab in AI Ads with 6 stat cards + 4 insight cards + 3 Recharts panels (line trend, bar platform usage, pie campaign-type breakdown). Top items list per Menu Item (most-generated).

**Testing**
- 18/18 backend pytests pass (`/app/backend/tests/test_ai_ads_phase345.py`) — bulk, export, analytics, plugin metadata, single-action promote with wall<55s guard.
- Frontend regression 100% (iteration_11.json): all 10 dashboard tabs render, login + Menu Editor + Library bulk bar + Promote modal + Analytics sub-tab all working.
- Confirmed in browser DevTools: 2 parallel POST /api/ai-ads/plugins/restaurant/promote requests fan out at t=0, both return 200 OK around t+56s — no 502.

### Feb 9, 2026 — AI Marketing Studio Phase 2 (Complete) — see prior section

### Feb 9, 2026 — AI Marketing Studio Phase 2 (Complete)
- Unblocked Webpack build by adding defensive null-check in `/app/frontend/plugins/visual-edits/babel-metadata-plugin.js` (`lazyEvaluatePropSource` at line ~865 — `importPath.parentPath.parentPath` was null when traversing cached File ASTs). Single 1-line guard; no behavioral change.
- Refactored `/app/frontend/src/pages/dashboard/aiads/shared.jsx` to use plain styled `<div>` blocks instead of shadcn `Card*` imports (avoids re-triggering the plugin recursion).
- Phase 2 frontend fully wired: 8 sub-tabs in AI Ads — Campaign Builder, Social, Email, SMS, Image Studio, Video Studio, Library, Settings.
- Generators: each posts to `/api/ai-ads/generate/{kind}` with a reusable BriefForm + `useSpecialtyRunner` hook + OutputPanel; outputs are CopyableItems with one-click "Save to Library" via `POST /api/ai-ads/assets`.
- Creative Library: search (`q`), filter by kind/platform/status/favorite, Star/Archive/Duplicate/Delete row actions. **NEW** `POST /api/ai-ads/assets/{id}/duplicate` clones with new id, "(Copy)" suffix, status=draft, favorite=false.
- Settings panel: model selection persisted to MongoDB `ai_config` collection (provider + model swap supported across openai/anthropic/gemini via `emergentintegrations`). Provider catalog endpoint exposes text/image/video options for the UI.
- Multi-tenant data shape: `ai_campaigns`, `ai_assets`, `ai_generations` all carry `industry`, `platform`, `status`; ready for non-restaurant industries.
- Tests: 25/25 backend AI-Ads tests pass (`/app/backend/tests/test_ai_ads.py`). Frontend: zero console errors across all 10 tabs. Test report `/app/test_reports/iteration_9.json`.
- LLM Universal Key confirmed funded — all 6 generation endpoints return 200.

## P1 Backlog (Next)
- **Connect live API credentials** via the Providers UI — Facebook Page Access Token, IG Business User+Token, Mailchimp API key + audience, SendGrid API key + verified sender, Twilio account SID/token + sender number. The publishing code is already production-grade `httpx` calls; only credentials are needed.
- **Permissions / RBAC** — single-admin auth today. Add role field + middleware (admin/manager/staff).
- **Automation worker** — `automation_rules` CRUD is complete; add a cron tick that materializes active rules into generations + schedules at their next UTC hour.

## P2 Backlog (Polish)
- Instagram + Facebook footer links
- Tappable address (Google/Apple Maps deep link)
- Fix Google Maps iframe on desktop
- Google Reviews testimonials slider (manual entries)
- React `ErrorBoundary` around main app
- Compress 2.4 MB hero logo PNG to <100 KB (mobile LCP penalty)

## Future
- SendGrid + Twilio live wiring once keys provided


---

## AI Marketing Studio — Phase 8 (Media Studio) — COMPLETED Feb 2026

Comprehensive media-management module inside the AI Ads tab. Six sub-sections:

1. **Uploads** — drag & drop JPG/PNG/WEBP/MP4/MOV/WEBM with folder organization.
2. **AI Images** — generate restaurant marketing visuals via OpenAI gpt-image-1 (Emergent LLM Key).
3. **Image Editor** (NEW) — non-destructive edit modal with 5 tabs:
   - Adjust: brightness / contrast / saturation / sharpness sliders + rotate 0/90/180/270 + horizontal flip
   - Crop: %-based with quick presets (Full, Center 80%, Wide 16:9) + optional output resize
   - Text Overlay: positioned text with color + optional background box + size + alignment
   - Logo Overlay: pick logo from library, position/size/opacity
   - Background Removal: rembg (u2net) AI — first call downloads model (~170 MB / 30-90 s); optional replacement BG color
4. **Social Exports** (NEW) — bulk-resize one image to 8 platform presets in one click:
   - Instagram Post (1:1) · Portrait (4:5) · Reel/Story (9:16)
   - Facebook Post (1200×630) · Story (9:16)
   - TikTok Vertical (9:16) · Google Business (4:3) · Flyer 8.5×11" @ 300 DPI
   - Cover or Contain fit mode with custom pad color
5. **Video Studio** — FFmpeg-rendered slideshows (15/30/60s, 1:1 / 4:5 / 9:16 / 16:9) with title + CTA slide + optional logo. Background worker with poll-based progress. Error messages now surfaced clearly in queue cards.
6. **Asset Library** — search/filter/favorite/edit/download/delete with source-type badges (AI / Edited / Rendered / Social).

### New endpoints (POST/GET under /api/media)
- `POST /edit` — image editor pipeline (PIL + rembg)
- `POST /export-social` — multi-format bulk export
- `GET /social-formats` — preset metadata
- `GET /health` — ffmpeg + storage probe

### Operational guardrails added
- Startup logger warns if `shutil.which("ffmpeg")` is None
- `POST /video/render` returns 503 (with actionable message) instead of queueing a doomed job when ffmpeg is missing
- Orphan render jobs (queued/processing without a worker) are marked failed at server startup
- FileNotFoundError on the render path stores a clear ops-friendly message
- PIL source images wrapped in try/finally to avoid file-descriptor leaks

### Tech additions
- `ffmpeg` system package (apt)
- `rembg==2.0.76` + `onnxruntime==1.26.0` for background removal

## P1 Backlog (next)
- Split `/app/backend/routers/media.py` (~995 lines) into `media/{upload,edit,export,ai,render,health}.py`
- Drag-handle crop overlay (currently slider-based)
- "AI Marketing Pack" one-click button: single product photo → FB image + IG reel image + 15s video promo with CTA

## Phase 8 — Infrastructure Hardening Pass — COMPLETED Feb 2026

Made Media Studio survive container restarts/rebuilds without manual intervention.

### Container/runtime self-healing (NEW `/app/backend/bootstrap.py`)
- **`ensure_ffmpeg()`** — at backend startup, `shutil.which("ffmpeg")` is checked; if missing, runs `apt-get update && apt-get install -y --no-install-recommends ffmpeg`. ~25s on cold restart.
- **`prewarm_rembg()`** — fires off `asyncio.create_task(prewarm_rembg())` at startup. Loads u2net session so first BG removal drops from 30-90s → 5-8s.

### Extended health endpoint `GET /api/media/health`
Returns: `healthy` (composite) + `ffmpeg_available/path` + `rembg_available/model_ready/error` + `storage_mb` + `render_queue: {queued, processing, completed_recent, failed_recent}`

### Verification
- Removed ffmpeg → restarted backend → auto-reinstalled in ~25s ✓
- rembg u2net pre-warmed at startup ✓
- Live render after rebuild: 16s ✓
- Background removal post-rebuild (warm model): 6s ✓

## Phase 8 — Structured Error Consistency Pass — COMPLETED Feb 2026

Brought every long-running surface under one consistent error contract. No "Failed" or "Something went wrong" messages remain — every failure has a code, owner-friendly message, technical details, and a retry action.

- NEW `/app/backend/errors.py`: `StructuredError` dataclass + 3 classifiers (`classify_llm_error`, `classify_render_error`, `classify_publish_error`) + 18 stable error codes + `failure_audit_log` collection
- NEW `/app/frontend/src/pages/dashboard/aiads/StructuredErrorCard.jsx` shared component with smart retry actions
- 7 surfaces converted: AI image gen, video render, image edit, social export, publishing scheduler, provider publish, generic worker crashes
- NEW `GET /api/media/audit` endpoint with by_code aggregation
- All Phase 8 pytest still green (11/11)

## Cleanup Week — Trust, Deletion & Polish Pass — COMPLETED Feb 2026

Made the dashboard *trustworthy* — Home now shows numbers an owner can act on, not noise. The 87 stale test failures that polluted Home are gone. The "Promote Something" button now opens a Top-3 picker with real reasoning instead of grabbing the first menu item.

### Phase A — Failed publish cleanup (trust killer fixed)
- **Auto-retry with exponential backoff**: scheduler now retries failed publishes at 5 / 15 / 30 minutes before marking failed. Unrecoverable codes (auth/key/safety/payload/asset-missing) skip retry.
- **`POST /api/home/archive-failed?older_than_days=N`** — bulk-archive stale failures (default 7d).
- **`POST /api/home/dismiss-failed/{id}`** — single-post dismiss.
- **One-time migration ran**: 87 historical test failures archived → Home counter reset to 0.
- `scheduled_posts` gained: `retry_count`, `last_attempt_at`, `last_error`, `archived`, `archived_at` fields.

### Phase B — Promote Something fix
- **NEW `GET /api/home/promote-suggestions?limit=N`** — ranks menu items by `days_since_promoted` from `ai_campaigns` history. Returns name + category + reason.
- Home's "Promote Something" button now opens a **Top-3 picker modal** instead of grabbing item[0]. Each item shows its own reason ("Not promoted in 21 days" / "Never promoted — perfect first push").

### Phase C — Removed duplicate workflows
- **Campaign Builder** sub-tab moved from `promotions` → `advanced` group (no longer in primary nav)
- **Library** sub-tab moved from `promotions` → `advanced` group (Media is now the single library)
- Both components remain importable for any future advanced-mode toggle

### Phase D — Dead UI deferred (safer than deletion)
- 11 components remain physically in `/aiads/` but are hidden from every visible nav route (Builder, Library, Social, Email, SMS, Image Concepts, Video Concepts, Queue, Rules-legacy, Providers-legacy, Analytics-as-tab). They're only reachable via `group="advanced"` which no current UI surfaces.
- Files NOT deleted to avoid breaking `AiAdsTab.jsx` imports. Future task: a dedicated "delete advanced" cleanup pass.

### Phase E — Home as operating system
- **Composite health pill** in the Home header (green / yellow / red) powered by **NEW `GET /api/home/health`** which rolls up ffmpeg + rembg + LLM key + provider-connections health.
- **NEW `GET /api/home/summary`** — single aggregate replaces 7 separate fetches the Home page used to make. Faster and cleaner.

### Phase F — Settings orientation copy
- Each Settings sub-tab now shows a one-line italic blurb explaining what it's for (Providers / Automation Rules / Account / Analytics).

### Phase G — Calendar already shipped in Phase 9
- 6 status filter chips with live counts
- Failed filter folds in what was the Queue tab

### Files changed
- **NEW**: `backend/routers/home.py` (170 lines — 5 endpoints), updated `backend/server.py` to mount it
- **Modified**: `backend/publishing/scheduler.py` (auto-retry block, retry_count + last_error fields), `frontend/src/pages/dashboard/HomeTab.jsx` (health pill, Top-3 picker modal, `/api/home/*` integration), `frontend/src/pages/dashboard/AiAdsTab.jsx` (Builder + Library moved to advanced; Settings orientation copy)

### Verification
- `GET /api/home/summary` → real_failures=0 (was 87 before cleanup) ✓
- `GET /api/home/health` → level=yellow with issue "No social accounts connected" (correct) ✓
- `GET /api/home/promote-suggestions` → returns 3 ranked items with reasons ✓
- Frontend smoke test: health pill renders as yellow, Promote Something opens picker with 3 items ✓
- Backend + frontend lint: 0 blocking ✓
- 6 top tabs (unchanged from Phase 9) — Home / Menu / Promotions / Customers / Insights / Settings
- Promotions sub-tabs reduced 5 → **3** (Automations / Media / Calendar) ✓

## Phase 9 — Dashboard Simplification & Promote Workflow — COMPLETED Feb 2026

Turned the platform from a collection of tools into a collection of workflows. Target owner usage: 10 minutes per day.

### Navigation collapsed: 10 tabs + 15 AI Ads sub-tabs (25 surfaces) → **6 top tabs + 5 Promotions sub-tabs (11 surfaces)** — 56% reduction.

**Old top-level (10):** Analytics · Specials · Site Content · Menu Editor · Giveaway · Loyalty · Messages · Inquiries · Subscribers · AI Ads

**New top-level (6):** 🏠 Home · 📋 Menu · ⭐ Promotions · 👥 Customers · 📊 Insights · ⚙️ Settings

### Phase 9A — Home dashboard (NEW `/app/frontend/src/pages/dashboard/HomeTab.jsx`)
- 5 quick-action buttons across the top: **Promote Something** · Add Special · Upload Photo · Create Campaign · View Calendar
- TODAY section: scheduled today / active promos / new subs / new inquiries / failed publishes (red when > 0)
- THIS WEEK section: most-promoted item / best platform / loyalty growth / view analytics
- AI SUGGESTIONS panel (data-driven, not LLM-generated): "Promote [item not featured recently]" · "N catering leads need a reply" · "N failed publishes" · "Special ends soon" — each with its own 1-click CTA
- One-click `Promote Something` opens the existing `PromoteItemModal` (which AI-generates Facebook image + Instagram image + Google Business image + caption + hashtags + CTA + 15s promo video, then schedules)

### Phase 9B — Promote This Item (verified already wired in MenuEditor)
- Existing `PromoteItemModal.jsx` already provides the single-screen, multi-asset, AI-driven workflow
- Now also reachable from Home → Quick Action and from any AI suggestion card

### Phase 9C — Calendar consolidation
- Added 6 status filter chips to `ContentCalendar.jsx`: **All · Draft · Scheduled · Publishing · Published · Failed** with live counts
- The "Queue" tab no longer needs its own surface — the failed filter on Calendar replaces it
- Queue still accessible via the slim AI Ads nav under group="advanced" for power users

### Phase 9D — Settings consolidation
- `AiAdsTab.jsx` now accepts a `group` prop: `"promotions"` (5 visible) · `"settings"` (Rules/Providers/Settings) · `"insights"` (Analytics) · undefined (legacy 15)
- Settings tab routes Rules · Providers · Analytics · SettingsPanel into one surface

### Phase 9E — Navigation cleanup
- `Dashboard.js` slimmed from 10 → 6 tabs, default landing = `home`
- `CustomersTab.jsx` (NEW) merges Subscribers · Loyalty · Inquiries · Messages with filter chips — no data migration, just UI consolidation
- "Menu" tab now also includes Site Content (CMS) below Menu Editor — one "Website" surface

### Clicks-saved benchmarks (verified via UI walkthrough)
| Workflow | Before | After |
|---|---|---|
| Promote Friday's special on FB+IG | 14 clicks across 6 screens | **2 clicks** (Home suggestion → Confirm) |
| See what needs attention today | 4 tabs to scan | **1 page** (Home) |
| View failed publishes | Navigate to Queue tab | **1 click** (Calendar → Failed filter) |
| Reach Provider settings | 2 navigation levels deep | **2 clicks** (Settings → Providers) |

### Files changed
- NEW: `HomeTab.jsx` (245 lines), `CustomersTab.jsx` (60 lines)
- Modified: `Dashboard.js` (10→6 tab nav + PromoteItemModal portal), `AiAdsTab.jsx` (group-prop slim nav), `ContentCalendar.jsx` (status filter chips + filtered eventsByDay), `memory/PRD.md`

### Restrictions honored
- ❌ No DB schema changes
- ❌ No collection merges
- ❌ No `media.py` refactor
- ❌ No publishing/scheduler rewrite
- ❌ No new top-level features
- ✅ Pure UI / navigation consolidation only

### Regression
- Backend pytest 8/8 captured (TestVideoRender lifecycle runs ~25s, was killed by runner timeout in the regression batch but proven green in isolation in iter18/iter19) ✓
- Every new tab renders without console errors (errs=0 across menu/promotions/customers/insights/settings) ✓
- 6 status filter chips render on Calendar ✓
- Home page shows live data (1 active promo, 111 failed publishes flagged, AI suggestion "Promote Fried Oyster Po'Boy" auto-generated from menu) ✓
- Frontend lint: 0 blocking ✓


Brought every long-running surface under one consistent error contract — no part of the platform shows a generic "Failed" or "Something went wrong" anymore. Every failure tells the owner what happened, why, and what to do next.

### NEW `/app/backend/errors.py` — single source of truth
- `StructuredError` dataclass: `{code, status, user_message, technical, retryable, retry_action, context}`
- Three classifiers (string-based, stable across versions):
  - `classify_llm_error(exc)` — AI image + future LLM calls
  - `classify_render_error(exc, returncode, stderr)` — FFmpeg video pipeline
  - `classify_publish_error(provider, raw_error)` — Meta / SendGrid / Twilio / Mailchimp
- `log_failure(surface, err, **ctx)` — uniform backend log line for every failure
- `audit_log(db, surface, err, **ctx)` — append-only `failure_audit_log` collection
- `report_failure(db, surface, err, **ctx)` — one-call helper that logs + audits + returns

### 18 stable error codes (frontend maps each to an icon + title + retry CTA)
`budget_exhausted · key_invalid · key_missing · safety_reject · rate_limited · prompt_invalid · provider_unavailable · provider_empty · timeout · ffmpeg_missing · ffmpeg_failed · asset_missing · asset_invalid · provider_unregistered · not_connected · permission_denied · payload_too_large · network · unknown`

### Surfaces refactored (all share the same payload shape now)
1. **AI Image Generation** (`POST /api/media/ai-image`) — already structured in iter19, now uses shared classifier
2. **Video Rendering** — render_jobs.error field stores StructuredError payload; ffmpeg stderr captured via `capture_output=True` and passed to `classify_render_error`
3. **Image Editor** (`POST /api/media/edit`) — source missing, file gone, bg-removal crash, edit pipeline crash all classified
4. **Social Exports** (`POST /api/media/export-social`) — asset missing, unsupported format, corrupted source all classified
5. **Publishing scheduler** (`publishing/scheduler.py`) — scheduled_posts.error stores structured payload; worker-level crash + execute-time failures + missing asset all audited
6. **Provider publish** (`publishing/base.py`) — `PublishResult.structured_error` populated automatically for every provider failure
7. **Generic publishing worker crash** — `run_due_publishes` catches and audits

### NEW `GET /api/media/audit` endpoint
Lists last N failure_audit_log entries with `by_code` aggregation for admin triage. Filter by `surface=` or `code=`.

### NEW shared frontend component `StructuredErrorCard.jsx`
- Renders icon + title + plain-English message + collapsible technical details
- Action button auto-selected from `retry_action`:
  - `retry / retry_render / retry_publish` → "Try again" (calls `onRetry`)
  - `wait_and_retry` → "Try again in 30s"
  - `add_balance` → deep link to app.emergent.sh/profile
  - `reconnect_provider / open_provider_connections` → "Open Provider Connections"
  - `edit_prompt / edit_post` → "Edit and retry" (calls `onEditSource`)
  - `pick_assets` → "Pick different assets" (calls `onPickAssets`)
- `parseAxiosError(e)` helper converts network/timeout/HTTP errors into the same shape
- Supports `compact` mode for inline cards (queue rows, calendar event popovers)

### Frontend surfaces using the shared card
- `MediaStudio.jsx` AI Image Generator (full card)
- `MediaStudio.jsx` Video Render queue card (compact)
- `MediaStudio.jsx` Video Render submit-time errors
- `SocialExporter.jsx` export errors
- `PublishQueue.jsx` failed-post cards (compact)
- `ContentCalendar.jsx` event popovers

### Verification
- Unit-tested `classify_llm_error` — **8/8** categories correct
- Force-failure render with non-existent asset → **status=failed code=asset_missing retry_action=pick_assets retryable=true** ✓
- Audit log endpoint returns categorized failures with `by_code` aggregation ✓
- `/api/media/health` still reports `healthy=true` ✓
- Full Phase 8 pytest regression: **11/11 PASS** ✓
- Backend + frontend lint: 0 blocking ✓


Made Media Studio survive container restarts/rebuilds without manual intervention.

### Container/runtime self-healing (NEW `/app/backend/bootstrap.py`)
- **`ensure_ffmpeg()`** — at backend startup, `shutil.which("ffmpeg")` is checked; if missing, runs `apt-get update && apt-get install -y --no-install-recommends ffmpeg`. Idempotent. ~25s on cold restart. Logs `[bootstrap] ffmpeg installed: True` on success.
- **`prewarm_rembg()`** — fires off `asyncio.create_task(prewarm_rembg())` at startup. Loads u2net session in a worker thread so the model (~170 MB) is ready before any user clicks "Remove background". First-user latency drops from 30-90s → 5-8s.

### Extended health endpoint `GET /api/media/health`
Returns:
- `healthy` (composite boolean)
- `ffmpeg_available` + `ffmpeg_path`
- `rembg_available` + `rembg_model_ready` + `rembg_error`
- `storage_bytes` + `storage_mb`
- `render_queue: { queued, processing, completed_recent, failed_recent }` (24h window)

### Bug fixed during pass
- `/api/media/edit` background-removal path was throwing `Operation on closed image` because the try/finally was closing the PIL source image even when `_apply_edits` returned the same image unchanged. Now only closes if `base is not edited`.

### Verification
- Removed ffmpeg via `apt-get remove -y ffmpeg` → restarted backend → ffmpeg auto-reinstalled in ~25s ✓
- rembg u2net model pre-warmed in ~25s ✓
- Live video render after rebuild: 16s 9:16 with 3 images, status=completed ✓
- Live background removal after rebuild (warm model): 6s ✓
- Full pytest suite `test_phase8_media_studio.py`: **11/11 passed** in 30.79s ✓
- Health endpoint returns `healthy=true` with all subsystems green ✓



---

## Production Stability — AI Image Async Job Architecture (Feb 2026)

### Problem
- Production (Cloudflare-fronted) returned **"The origin web server sent a response that Cloudflare could not parse"** on AI Image Generator.
- Root cause: `POST /api/media/ai-image` was a blocking call that took ~85s; Cloudflare kills idle connections at ~60s.
- Same surface caused **Promotions → Automations stuck on "Loading automation center…"** because an inner `Promise.all` was firing `GET /api/menu` without an auth header (fixed prior).

### Fix — Async Job + Polling

**Backend (`/app/backend/routers/media.py`)**
- `POST /api/media/ai-image` → enqueues a job, returns **HTTP 202** with `{job_id, status: "pending"}` in **<150ms**.
- New `GET /api/media/ai-image/job/{job_id}` → returns full job state (`pending` | `processing` | `completed` | `failed`), `progress` 0–100, and either `result.assets` or structured `error`.
- Background worker `_run_ai_image_job` runs the actual generation via `asyncio.create_task` (180s internal cap; Cloudflare no longer in the path).
- MongoDB collection `ai_image_jobs` (indexes: `status+created_at`, unique `id`) — added in `server.py` startup.
- Fail-fast: missing `EMERGENT_LLM_KEY` returns 500 synchronously (so the form shows it immediately, not via a polled job).
- Schema fix: `AiImageRequest.style` `max_length` 60 → **200** (the FE default literal was 70 chars; clean-room users were getting silent 422s).

**Frontend (`/app/frontend/src/pages/dashboard/aiads/MediaStudio.jsx`)**
- `AiImageGenerator` now POSTs to receive `job_id`, then `setInterval` polls every **3s** via `pollOnce`.
- New UI: progress card (`data-testid="ai-image-progress"`) with status label and gold progress bar.
- 3-minute frontend ceiling → falls back to StructuredErrorCard with `code: "timeout"`.
- Transient poll errors are tolerated; only surface if cap exceeded.

### Verification (iter 19 + iter 20)
- Backend pytest: **9/9 PASS** — auth (POST/GET), enqueue <2s, 404 on unknown job, full pending→processing→completed lifecycle in ~13s for low/1 image, asset accessible via `/api/media/thumb/{id}`, regression endpoints (`/api/media/health`, `/api/ai-ads/plugins`, `/api/ai-ads/plugins/restaurant`, `/api/menu`) all 200.
- Frontend E2E (Playwright): login → Promotions → Media → AI Images → Generate 1 Image — progress card appears <50ms, status flips Queued → Generating, completes in ~12s, no error card, library AI counter increments.
- Production stability: ✅ POST initial response well under 60s Cloudflare ceiling; each poll is <100ms.

### Backlog (carried — non-blocking)
- Pydantic ValidationError → StructuredErrorCard mapper (so future field-length errors surface a clean message instead of "Unexpected error").
- Startup janitor for `ai_image_jobs` rows stuck in `pending`/`processing` older than N minutes after a backend restart.
- Split `routers/media.py` (~1300 lines) into `media/{upload,edit,ai_image,video,export,assets}.py` (P2 tech debt).
- Phase H: First Promotion Walkthrough (P1).
- Weekly AI Digest Email (P1), "Plan My Week" 7-day draft generation (P1).
- Merge `ai_assets` and `media_assets` collections (P2).


---

## Phase 10 — Persistent Media Storage + AI Job Janitor (Feb 2026)

### Problem (exposed by production verification of the async fix)
1. **Asset persistence**: AI-generated PNGs, uploaded files, and rendered MP4s were stored on the pod's local `/app/backend/media_storage`. Any pod restart (deploy, OOM, HPA scale) wiped them. Verified live in production — a freshly-generated PNG returned `{"detail":"File missing on disk"}` minutes later.
2. **Orphan jobs**: AI image jobs are run via `asyncio.create_task` — an in-process registry. A backend restart kills the task. With no janitor, the Mongo doc stays at `status="processing"` forever and the user's UI polls indefinitely (until the 3-min frontend timeout).

### Fix — Emergent Object Storage + Startup Janitor

**Backend — `/app/backend/storage.py` (NEW, 175 lines)**
- Thin façade over Emergent Object Storage API. Public functions: `init_storage()`, `put_bytes`, `get_bytes`, `exists`, `download_to_tmp`, `make_path`, `health`.
- Uses `EMERGENT_LLM_KEY` to bootstrap a session `storage_key` (auto re-init on 403).
- Legacy compat: bare-filename `storage_path` values fall back to LOCAL_STORAGE_DIR.

**Backend — `/app/backend/routers/media.py` (refactored)**
- All NEW writes → `lakeview/{uploads|ai_images|edits|exports|renders|thumbs}/{uuid}.{ext}`.
- Upload: stream to /tmp scratch, then put_bytes, then delete scratch.
- `/file/{id}` and `/thumb/{id}`: return bytes via `Response(content=...)`. Thumbs lazily generated + cached in object storage.
- Edit, export-social, video render: download sources to /tmp work_dir, process, upload result, cleanup in `finally`.
- Delete is SOFT (`status="archived"`) — object storage has no delete API.
- `cleanup_orphan_ai_image_jobs()` + `cleanup_orphan_render_jobs()` sweep `pending|processing` rows to `failed` with structured retryable error.
- `/api/media/health` expanded: `storage{backend, reachable, initialized}`, `asset_count`, `stale_*_jobs`, full queue counts. `healthy:true` requires ffmpeg + rembg + storage reachable + 0 stale jobs.

**Backend — `/app/backend/server.py`** — startup runs both janitors then `objstore.init_storage()` off the event loop.

### Verification (iteration 21)
- **Backend pytest 19/19 PASS** (~80s wall-clock).
- Restart survival: 638-byte upload PNG and 2 MB AI PNG both byte-identical pre/post `supervisorctl restart backend`.
- Janitor: enqueue → restart → poll → `{status:"failed", error:{code:"unknown", user_message:"interrupted by a server restart", retryable:true, retry_action:"retry"}}`.
- Health probe (PUT+GET roundtrip on `lakeview/_health/probe.txt`) → `reachable:true, initialized:true`.
- Regression: `/api/menu`, `/api/specials`, `/`, `/api/ai-ads/plugins`, `/api/ai-ads/plugins/restaurant` all 200.

### Operations summary
- **Architecture (post-fix):** Writes → Emergent Object Storage. Reads via FastAPI proxy. Mongo = metadata only.
- **Migration:** Hybrid — `is_remote_path()` discriminator. New writes always remote; old rows read from disk if present, else structured 404.
- **Rollback:** Revert `media.py` + `server.py` in one commit. Local fallback ensures already-uploaded files keep working.
- **Downtime:** Zero — code roll only.
- **Regression suite:** `/app/backend/tests/test_phase10_persistence.py`.

### Remaining risks
- Object storage has no delete API → archived assets accumulate. Acceptable until volume grows.
- All reads stream through FastAPI proxy. Fine for admin tool; expose CDN later if public traffic grows.

### Backlog (paused per user instruction — reliability first)
- (P2) Split `routers/media.py` (~1432 lines) into a subpackage.
- (P1) First Promotion Walkthrough, Weekly AI Digest Email, "Plan My Week" 7-day generator.
- (P2) Merge `ai_assets` + `media_assets` collections.
- (P2) Periodic purge of `status="archived"` rows.


---

## Phase 11 — Promote This Item 2.0 (Feb 2026)

### What it does
Owner-facing one-click marketing pack generator. Pick a photo (upload or library) → optionally tweak item details → one click → receive **5 image formats + a 15-s vertical promo MP4 + caption + hashtags + SMS + email subject/body + Google Business Profile copy**, all saved to the library under folder "Marketing Packs".

### Files changed
- `/app/backend/routers/marketing_pack.py` (NEW, ~580 lines): full router + 5-stage async pipeline.
- `/app/backend/server.py`: registers `marketing_pack.router`, adds indexes for `marketing_packs` (`id` unique, `status+created_at`) and `menu_promotions` (`item_key` unique), startup janitor.
- `/app/frontend/src/pages/dashboard/aiads/PromoteThisItem.jsx` (NEW, ~570 lines): 4-step wizard (PickPhotoStep → ItemDetailsStep → ProgressStep → ReviewStep) with debounced PATCH autosave.
- `/app/frontend/src/pages/dashboard/AiAdsTab.jsx`: adds `promote` as first sub-tab under Promotions (Sparkles icon).

### API routes (all /api prefix)
- `POST /marketing-pack/generate` → 202 `{job_id, status:"pending"}` in <250 ms
- `GET /marketing-pack/items-not-promoted-recently?limit=3` (LITERAL — registered BEFORE `/{pack_id}`)
- `GET /marketing-pack/job/{id}` — full polling state
- `GET /marketing-pack/{id}` — re-open saved pack
- `PATCH /marketing-pack/{id}` — save inline copy edits (debounced 800 ms FE autosave)
- `POST /marketing-pack/{id}/regenerate` → 202 with a NEW job_id

### Mongo collections (NEW)
- `marketing_packs` — `{id, status, progress, current_step, source_asset_id, menu_item_key, item, result, error, created_at, updated_at}`
- `menu_promotions` — `{item_key, last_promoted_at, last_pack_id}` (used by the "not promoted recently" recommender; updated when a pack completes)

### Object storage paths
- `lakeview/marketing_pack/{uuid}.jpg` — 4 social formats (1:1, 9:16, 1.91:1, 16:9)
- `lakeview/marketing_pack/{uuid}.mp4` — 15-s vertical promo video
- All assets also written to `media_assets` Mongo rows with folder=`Marketing Packs` and tags `["marketing-pack", "<format>", "pack:<pack_id>"]`. The 9:16 image gets dual labels: `ig_story` AND `tiktok_reel` (single file, two references in the result block).

### Pipeline stages
1. **inferring** (~2–5 s) — text LLM call fills missing `name`/`description` (`ai_engine.client.generate_structured` — note: returns wrapper `{data, model_used, raw}`, must unwrap with `.get("data")`)
2. **writing_copy** (~3–7 s) — single structured LLM call returns caption + hashtags + sms + email{subject, body} + gbp consistently
3. **rendering_images** (~2 s) — PIL `_fit_to` crops the source into 4 ratios, paints a brand overlay (dark bar + headline + price chip + CTA chip)
4. **rendering_video** (~25–40 s) — reuses `_render_sync` from `routers/media.py` (slideshow of the 4 images @1080x1920 with title + CTA drawtext)
5. **saving** (<1 s) — inserts pack row, stamps `menu_promotions.{item_key}.last_promoted_at`

### Test results
- **Manual E2E (preview)**: 44 s end-to-end for low/1024 source. All 5 image asset files accessible (200 image/jpeg) + video (200 video/mp4 51 KB). Captions, hashtags (10), SMS, email subject/body, GBP all populated with NOLA-flavored copy.
- **Auth probes**: POST/GET unauth → 401; GET unknown id (authed) → 404; PATCH unknown → 404.
- **Menu stamp**: `appetizers::caf-fries` → `menu_promotions` row created with `last_promoted_at` + `last_pack_id`.
- **Janitor**: enqueue → `supervisorctl restart backend` → status=`failed`, error.code=`unknown`, error.user_message=`"interrupted by a server restart"`, retryable=true, retry_action=`retry`.
- **PATCH autosave**: caption edit returns updated `result.caption`. PATCH on unknown id → 404.
- **Regenerate**: returns NEW job_id ≠ original. 
- **`items-not-promoted-recently`**: correctly returns never-promoted first then oldest. Test confirmed 60 menu items in `menu_categories`, 2 stamped in `menu_promotions`, endpoint ordering is correct ("not promoted recently" intent).
- **Frontend smoke**: all data-testids render (`promote-this-item`, `promote-suggestions`, `promote-upload-btn`, `promote-library-btn`, the stepper, suggestion cards with prices + "Never promoted" badge). Sub-tab `ai-subtab-promote` wired and selected by default.

### Average generation time
- Source size 1024×1024 low quality: **~44 s** total (POST 0.25 s → infer 5 s → copy 10 s → images 2 s → video 30 s → save 1 s)
- Restart-survival: assets persist (Phase 10), pending jobs marked failed (Phase 11 janitor).

### Fallback used because menu_items not its own collection
Code path `routers/marketing_pack.py::items_not_promoted_recently` flattens `menu_categories.items[]` arrays into a virtual list, joining via `item_key="{category_slug}::{slug(name)}"`. `fallback_used: false`, `source: "menu_categories"`. **No alternative entity (restaurants / episodes / media-only) was needed** because BTC NOLA / Lakeview's menu data lives in `menu_categories`.

### Backlog (paused per scope)
- (P1) Onboarding tour for first-time owners — sample-pack walkthrough.
- (P2) "Promote" entry point from menu item rows + Media Library asset cards (current entry only via Promotions sub-tab).
- (P2) Pack history list — past packs viewable + re-editable.
- (P2) Per-channel A/B copy variants.
