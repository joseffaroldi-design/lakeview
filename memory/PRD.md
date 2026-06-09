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
