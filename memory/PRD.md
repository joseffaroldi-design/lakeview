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
- **Schedule & Publish System** (highest priority next): asset action buttons Schedule / Publish Now / Save Draft. Provider-abstracted webhook layer to push to Facebook / Instagram / Google Business Profile / Mailchimp / Email / SMS. Future: TikTok / X / LinkedIn. Content Calendar with Monthly / Weekly / Scheduled-queue / Draft-queue / Published-queue views.
- **Additional plugins** to validate the plugin contract: Moving Company, Event/Festival, Retail, Home Services. Each ships its own templates + actions + `build_brief`.
- **AI Studio standalone SaaS extraction** — eventually move `ai_engine/` + `routers/ai_ads.py` into a separate service so the dashboard becomes one of many tenants.

## P2 Backlog (Polish)
- Instagram + Facebook footer links
- Tappable address (Google/Apple Maps deep link)
- Fix Google Maps iframe on desktop
- Google Reviews testimonials slider (manual entries)
- React `ErrorBoundary` around main app
- Compress 2.4 MB hero logo PNG to <100 KB (mobile LCP penalty)

## Future
- SendGrid + Twilio live wiring once keys provided
