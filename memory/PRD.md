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
- Chef Joseph & Josef photos

## Future
- Refactor `server.py` (1085 lines) into routers: auth, cms, loyalty, messaging, giveaway, analytics
- Lazy-load dashboard tab data instead of fetching everything on mount
- Rewrite `GiveawayManager.js` / `LoyaltyMessaging.js` back from `React.createElement` to JSX
- Social media links, photo gallery, customer reviews
