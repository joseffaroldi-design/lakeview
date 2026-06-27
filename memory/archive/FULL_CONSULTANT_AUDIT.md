# Full Codebase + Workflow Audit — Outside Consultant Review

**Engagement:** Brutal-honesty due-diligence audit of the Lakeview
Restaurant Marketing SaaS.
**Date:** Feb 2026
**Auditor:** External senior consultant (acting via E1)
**Mandate:** Tell the founder what's wrong, what's duplicated, what's
worth keeping, and what would make this a real commercial product.

---

## Part 1 — Executive Summary

### Direct answers

1. **Launch-ready?** *Conditionally yes for one specific persona —
   the existing restaurant owner who already knows what flyers are
   supposed to look like.* For a cold SaaS sale, no — the product is
   one persona-tested cohort away from being a real B2B tool.
2. **Architecture healthy?** *Mostly. The main rot is one 1750-line
   router (`ai_designer.py`) and one 1578-line React component
   (`AiDesigner.jsx`).* Outside those two files the codebase is
   surprisingly well-organised for its age.
3. **Workflow clear for a restaurant owner?** **No.** A non-technical
   owner has at least three indistinguishable paths to "make a flyer"
   (AI Designer / Photo→Flyer / Template Designer) and the labels
   don't tell them which one to pick. This is the #1 launch blocker.
4. **Biggest risks** — (a) the production deployment has been brittle
   ("ENVIRONMENT propagation failure" recurred 5+ times), (b)
   render-engine renders are still asset-quality-limited at 7.5–8.8 / 10
   Gemini (no real designer PNGs), (c) one engineer just shipped 4
   sprints in 6 weeks — there is *zero* documentation of how a third
   party would extend this.
5. **Biggest opportunities** — (a) the HTML/CSS renderer + Live
   Designer is genuinely a moat (most SaaS competitors render with
   procedural PIL/Canvas); (b) the bulk-render → Today's Featured loop
   is already a clear weekly habit; (c) the Workspace gives every
   menu item a "home" — that is the natural billing surface (one seat
   per restaurant, asset count cap per tier).
6. **What next?** Three things in this order: **freeze and ship**;
   **delete or hide the duplicate flyer paths**; **drop in real
   designer PNG backgrounds**. Everything else can wait.

### Scorecard (1–10)

| Dimension | Score | Why |
|---|---:|---|
| Product quality           | **6.5** | The output is real but the journey to it is confusing. |
| UX                        | **5.5** | Dashboard nav is OK; flyer-creation paths are duplicated and inconsistent. |
| Frontend architecture     | **6** | Lazy-load, good Suspense usage, but `AiDesigner.jsx` is a 1.5k-line monolith. |
| Backend architecture      | **6** | 21 routers ≈ healthy split; `ai_designer.py` is the 1.75k-line elephant. |
| AI workflow               | **7** | Emergent LLM key + Universal key are well-used; Design Memory + Creative Director are real. |
| Rendering engine          | **8** | HTML/CSS V3 + agency template + procedural fallback is genuinely strong. |
| Media management          | **7** | 1,838 assets, 11 sources, but ZERO TTL/archive flow — will drown the DB at 100 restaurants. |
| Performance               | **7** | Workspace list 314 ms is great; flyer cold-start 5 s is acceptable but warm path is fine. |
| Reliability               | **5** | Recurring production env-var propagation bug; 16 tests crash at import time without env vars. |
| Test coverage             | **6** | 455 tests collected, real coverage but several are tightly coupled to env state. |
| Maintainability           | **5** | Two megafiles + 17 markdown reports in `/app/memory/` is the wrong direction. |
| Commercial readiness      | **4** | No billing, no per-tenant isolation, no usage tracking, no onboarding flow, no rate limit. |

**Composite: 6.0 / 10** — "Works for one owner; not yet a SaaS."

---

## Part 2 — Code Audit

### Hard numbers

| Metric | Value |
|---:|---|
| Backend LOC (Python) | 21,895 |
| Frontend LOC (JS/JSX) | 12,051 |
| Routers | 21 |
| Mongo collections | 24 |
| Test files | 27 |
| Tests collected | 455 |
| Markdown reports in `/app/memory/` | 17 |
| Active media assets | 1,779 |
| Asset sources | 11 distinct |

### Ranked findings

| # | Severity | Files | Issue | Business impact | Technical impact | Fix | Effort | Risk |
|---|---|---|---|---|---|---|---|---|
| **F1** | **CRITICAL** | `routers/ai_designer.py` (1750 LOC) | One file owns: PIL drawing, Jinja-style theming, route handling, mongo writes, scoring orchestration, agency-template dispatch, HTML-engine dispatch, copy generation, and job state. `_pil_background` is 165 lines; `_compose_design` is 157 lines. | Every future flyer change risks a regression in unrelated logic. Onboarding a second engineer is impossible. | Cyclomatic complexity is in the red; cannot be safely unit-tested. | Split into `routers/ai_designer.py` (HTTP only) + `services/ai_design/{procedural,agency,html,score,copy}.py`. Each ≤ 200 LOC. | **2 days** | Medium — heavy regression surface; the renderer test suite (40+ tests) is the safety net. |
| **F2** | **CRITICAL** | `pages/dashboard/aiads/AiDesigner.jsx` (1578 LOC) | Monolithic React component holding theme picker, food upload, prompt builder, job polling, scoring display, library save, retry logic, history list, and design-memory writes. | Touching any one piece of the AI Designer UI carries unrelated regression risk. | React DevTools rendering of this file is laggy in development. | Split into `<AiDesignerShell>`, `<JobRunner>`, `<HistoryDrawer>`, `<ThemePicker>`, `<ResultCanvas>`. Each ≤ 300 LOC. | **2 days** | Low — UI is well-tested via screenshots in past sprints. |
| **F3** | **HIGH** | `pages/dashboard/aiads/PhotoToFlyer.jsx` (1217), `PromoteThisItem.jsx` (425), `AiImageGenerator.jsx` (388) | **Three separate flyer-creation UIs**. Each renders a slightly different theme picker, a slightly different food uploader, a slightly different output preview. | Restaurant owner sees 3 paths labelled "Promote", "Photo→Flyer", "AI Designer" and can't tell which to use first. | Same `/api/ai-designer/generate` underneath all three; the duplication is purely UI. | Pick one "Generate Flyer" surface; collapse the other two into it with mode flags. | **1.5 days** | Medium — `PromoteThisItem` is used from `WorkspaceTab.onPromote`; route plumbing has to thread. |
| **F4** | **HIGH** | `App.js` (1135 LOC), `TodaysPick.jsx` (509) | Both hold business logic that belongs in components/hooks. `App.js` does menu fetching, hero rotation, auth gating, layout shell, and route registration in one file. | Cold-start LCP is slower than it needs to be; bundle includes business logic for the home page even on dashboard routes. | Code-splitting is partial. | Extract `useMenu()`, `useTodaysFeatured()`, `<Layout/>`, move `Hero` and `Specials` to lazy chunks tied to `/`. | 1 day | Low. |
| **F5** | **HIGH** | 11 distinct `media_assets.source` values, 1,838 docs | No TTL, no archive, no per-source quota. `ai_designer` alone owns 1,051 assets; `marketing_pack` 198; `social_export` 148; `image_edit` 63. | At 100 restaurants × 1,800 assets per = 180,000 docs in one collection; mongo + Cloudflare object-store costs blow up. | Existing `orphan_assets.py` script is dry-run only — never executed in cron. | (a) per-tenant `tenant_id` field; (b) cron archives anything `status="active"` older than 90 d AND `is_favorite=false` to `status="archived"`; (c) per-source caps. | 0.5 day | Low. |
| **F6** | **HIGH** | `marketing_pack.py` (565), `todays_pick.py` (762), `ai_designer.py` | Two and a half overlapping "generate a marketing thing" pipelines. `marketing_pack` writes to `marketing_packs` and produces both designs + copy; `todays_pick` writes to `todays_pick` and produces graphics; `ai_designer` writes to `ai_design_jobs` and produces flyers. Each has its own job state machine, polling endpoint, retry logic. | A bug fix in one doesn't propagate to the others. | Three independent retry/backoff/timeout implementations to maintain. | Pick one job runner (`ai_design_jobs`); deprecate the others, migrate their data, surface as views. | 2 days | High — `marketing_pack` is in production paths. |
| **F7** | **MEDIUM** | `tests/test_theme_packs.py`, `test_sprint_12c.py`, `test_flyer_themes.py`, +13 others | **16 test files crash at import time** because they read `os.environ['ADMIN_PASSWORD']` / `REACT_APP_BACKEND_URL` / `MONGO_URL` at module level. CI doesn't run them. | Coverage report claim is inflated; new env in CI silently fails. | Hidden regressions. | Move env reads into fixtures (`@pytest.fixture(scope="session")`), default to safe fallbacks for collection. | 0.5 day | Low. |
| **F8** | **MEDIUM** | `/app/memory/*.md` (17 files) | Sprint reports have grown into a paper trail nobody will read. Useful at the time, stale forever. | Engineering attention spent on documentation that doesn't ship. | None. | Keep PRD, CHANGELOG, ROADMAP, latest sprint report; archive the rest to `/app/memory/archive/`. | 30 min | None. |
| **F9** | **MEDIUM** | `agency_templates/`, `theme_packs/`, `html_renderer/templates/` | **Three template systems** living in parallel. Procedural themes, JSON manifests, HTML/CSS files. Each one resolves a different way per theme. | Adding a new theme requires choosing which system; designer hand-off path is unclear. | The "frozen engine" promise is hard to hold. | Document one canonical theme creation path (HTML/CSS) in the Live Designer; mark the other two "legacy, do not extend". | 1 hour (doc) | None. |
| **F10** | **MEDIUM** | `routers/ai_ads.py`, `routers/ai_designer.py`, `routers/ai_image.py` | Three "AI" routers with overlapping `/generate` endpoints. The frontend uses `ai_designer` exclusively; the others are present "just in case". | Mental load; security review surface area. | API surface inflation. | Delete `ai_ads.py` if no caller; collapse `ai_image.py` into `ai_designer.py` as `/api/ai-designer/image`. | 1 day | Medium. |
| **F11** | **MEDIUM** | `services/menu_matcher.py` vs `_slug` in `workspace.py` | At least 3 different `_slug` and 2 `item_key` builders across the codebase. | Inconsistent IDs (e.g. `cafe-fries-5fb490` vs `cafe-fries`) leak into design_memory. | Workspace matcher already has fallback regex for the legacy 6-char hash. | One shared `services/keys.py`. | 1 hour | Low. |
| **F12** | **LOW** | `routers/todays_pick.py` (762) | Earlier scheduled-pick system that pre-dated Today's Featured. Still ships a daily cron and writes to its own collection. | Confusion: two "Today's" surfaces. | Two pieces of code that do similar things. | Pick one. Today's Featured (HTML hero) won. | 1 day | Medium — operator may be relying on the older cron. |
| **F13** | **LOW** | `seed_agency_template_backgrounds.py` (362) | Generates V2 procedural backgrounds — superseded by real designer PNG drop-in plan. | None today. | Dead code path. | Move to `scripts/legacy/` once real PNGs land. | 5 min | None. |
| **F14** | **LOW** | `quality_score.py` (407) | Internal scorer was tuned to procedural renderer; doesn't score HTML renders meaningfully (whitespace caps at 35). | Telemetry numbers misleading. | "Score" displayed in UI is unreliable for V3 outputs. | Either feed HTML renders through Gemini Vision in-line, OR write a V2 scorer for HTML. | 1 day | None — the score is currently advisory. |
| **F15** | **LOW** | `failure_audit_log` collection (exists, 0 grep refs to write to it) | Empty collection. | None. | Mongo overhead, mental noise. | Drop. | 5 min | None. |

### Dead / nearly-dead

* `ai_ads.py` router — no frontend reference (search returns 0 hits in `frontend/`).
* `failure_audit_log` collection — never written.
* Sprint 17/18/19 sample renders in `/tmp/` — disk junk, not in git anyway.
* PIL v2 background generator script — superseded by HTML/CSS engine.
* Legacy `theme_packs/` for any theme already ported to HTML.

### Risky dependencies

* **Playwright + sync API + greenlets** — works, but anyone reading the
  code first time will be confused by the dedicated worker thread
  pattern. Document or migrate to async Playwright on next refactor.
* **rembg** referenced in `ai_designer.py:_prepare_food_cutout` —
  pulls heavy ONNX runtime; only used optionally; ship behind a feature
  flag in production.

---

## Part 3 — Workflow Audit

### The journey today

```
[Owner clicks "Login"]
    ↓
[Dashboard → 7 tabs]
    ↓
   ┌───────────── Home ──────────────────────────────────────────┐
   │ Workspace · Menu · Promote · Library · Customers · Analytics│
   └─────────────────────────────────────────────────────────────┘
                              ↓
   ┌─ "I want a flyer" ──────────────────────────────────────────┐
   │  Promote tab (top-level)                                     │
   │  Photo→Flyer (inside Promote)                                │
   │  AI Designer (inside Promote)                                │
   │  Workspace → ProjectCard → Promote (modal)                   │
   │  /template-designer (separate route, hidden from nav)        │
   │  Menu sparkle button (4-finger gesture from owner perspective)│
   └──────────────────────────────────────────────────────────────┘
```

### Friction findings

| # | Friction | Severity | Fix |
|---|---|---|---|
| W1 | **Five entry points to "make a flyer".** Each shows a slightly different theme picker. | Critical | Collapse to one: a single "Create Flyer" button in the project header (Workspace), with mode tabs (Quick / Photo Upload / AI). |
| W2 | **Template Designer at `/template-designer` is not linked from the dashboard.** Discoverable only if you know the URL. | High | Add nav link OR remove the page (it's an internal tool). |
| W3 | Workspace shows ProjectCards with **"Open" + "Promote" buttons** — Promote opens Photo→Flyer modal; Open opens the project detail. The two verbs are confusing — Promote is the desirable action, but Open is the bigger button. | High | Make "Promote" the primary CTA on the card; demote "Open" to a chevron. |
| W4 | Detail tabs include **Schedule and Insights with "Soon" badges** — placeholders advertised before they exist. | Medium | Hide entirely until shipped (no "Soon" UI). |
| W5 | After bulk-render, **no notification or success surface** in the dashboard. The owner has to revisit the Library. | Medium | Toast + Library link + recent renders list on Workspace home. |
| W6 | The **Library tab still exists** alongside Workspace, but they overlap heavily. | Medium | Keep Library as the "all media" raw surface; rename to "All Media". |
| W7 | `Today's Special` band on the public homepage — when a flyer's source photo is wrong (steak placeholder for a Caesar Salad), the public site shows it. | High | Filter out html_bulk assets whose `item_name` doesn't match a real food photo until photos are uploaded. |
| W8 | Menu sparkle button → opens a flow that **rewrites the menu item description with AI**, separate from the design surface. | Low | Move into the project detail Overview tab as a single "Improve copy" button. |
| W9 | Login is a single password field with no rate-limiting hint. | Medium | Add bruteforce delay messaging. |
| W10 | No global "What does Lakeview do this week?" landing screen for the owner. Dashboard "Home" tab shows analytics-y widgets, not "you have 3 unpromoted items, 2 new captions to review". | High | Workspace becomes the "Home" with a status feed; analytics moves to its own tab. |

### Would a busy restaurant owner understand this in under 60 seconds?

**No.** They would understand the homepage and the menu. They would not
understand why "Promote", "Photo→Flyer", and "AI Designer" are
separate things, and they would never find `/template-designer`.

---

## Part 4 — Rendering + Template System Audit

### What works

* **HTML/CSS V3 renderer** is genuinely strong — 8.17 / 10 average,
  Luxury Wagyu at 8.8, first-ever 10/10 on color harmony. This is
  unusual for SaaS render engines (most use procedural PIL/Canvas).
* The fallback chain (HTML → agency → procedural) is conceptually
  clean and correct.
* The **Live Template Designer** is the right surface for designer
  iteration — edit a CSS file, refresh, render in 1.5 s.

### What's broken

* **Agency template renderer (Sprint 20 Phase 0) is now half-dead.**
  Three of its six themes have HTML equivalents that are clearly
  better. Anyone debugging will hit two systems and have to choose.
* **Quality Score engine doesn't score HTML renders correctly** —
  whitespace metric caps at 35 because it was tuned for procedural
  texture density. The score shown next to HTML renders is misleading.
* **Procedural PIL fallback** is fine as a safety net but should never
  be the user-facing default.

### Recommendations

1. **Freeze**: HTML/CSS renderer (engine + worker thread pattern).
   Procedural PIL fallback (don't touch — it's the safety net).
2. **Improve**: Quality Score V2 that works for HTML renders, OR
   replace with inline Gemini Vision scoring on a sample basis.
3. **Asset-quality limited**: Background PNGs for all 9 themes. This
   is the single highest ROI improvement and requires zero code.
4. **Code-quality limited**: Nothing significant. The engine is fine.
5. **Replace with real Canva/Figma**: All 6 agency template
   backgrounds (`agency_templates/backgrounds/*.png`). Drop-in path is
   already documented.
6. **Themes to hide**: `game_day_scoreboard` (lowest Gemini score at
   6.8), `vintage`, `distressed_orange` (no HTML counterpart, weak
   PIL output). Hide from theme pickers until ported.

---

## Part 5 — Marketing Workspace Audit

### What's right

* **One project per menu item** is the right primitive. The decision
  to use `item_key` as the cross-system join is correct — it already
  matches `design_memory`, `menu_promotions`, `marketing_packs`.
* **Lazy backfill** is the right pattern — no migration script
  required.
* **Batched query optimisation** (4 sweeps instead of 240+) is
  textbook; the 314 ms list time is a fair gate.

### What's wrong / missing

| # | Issue | Sev | Fix |
|---|---|---|---|
| WS1 | **Schedule + Insights tabs already shipped as "Soon" placeholders.** They aren't yet built. Promising features before delivery. | High | Hide the tabs entirely until shipped. |
| WS2 | **No project-level state for "ready / draft / archived"**. Every project is implicitly active. | High | Add `status: "draft" | "ready" | "archived"` so owners can hide off-menu items. |
| WS3 | **No "What's stale?" signal.** The data is there (`last_promoted_at`, `last_generated_at`) but the UI doesn't surface it. | High | Add an Activity Stream / Stale projects filter. |
| WS4 | **Bulk caption count is wrong** — only the LATEST marketing pack's captions count, not historical. | Medium | Count distinct caption channels across all packs for the item. |
| WS5 | **No "promote this from the project" output preview.** Clicking Promote opens Photo→Flyer modal with item preselected, but the result doesn't feed back to the project — owner has to refresh the Workspace. | High | After Photo→Flyer save, fire a callback that refreshes the parent project's counts. |
| WS6 | `is_featured_today` only works when the featured asset is also the project's hero. If a different flyer is featured, the badge silently doesn't show. | Medium | Either match by `item_name` OR explicitly link featured back to its source project. |

### Answers

1. **Right foundation?** Yes. The data model is correct.
2. **Missing before Scheduling?** A status field, a stale signal, and
   a real "campaign" entity (vs the current loose pile of assets).
3. **Simplify?** Hide Schedule + Insights tabs. Don't ship empty
   placeholders.
4. **Add next?** Activity Stream + project-level status field.
5. **Production ready?** *Yes for read-only operator review*. Not yet
   ready as the central marketing surface because the
   Promote-create-flyer round-trip doesn't refresh the parent.

---

## Part 6 — Deployment + Production Readiness

### Hard facts

* **Production lives at** `https://lakeview-grill.emergent.host`
* **Recurring blocker**: ENVIRONMENT variable propagation failure has
  surfaced 5+ times. Emergent Support ticket exists.
* **`.gitignore`**: `/app/.gitignore` excludes `/.emergent/`, `.env`,
  `node_modules` — looks fine but should be re-audited.
* **Cold start**: backend ~2 s; Playwright first render ~5 s. Fine
  for async background jobs; not fine for `/api/html-template/preview`
  on first hit each morning.
* **Caching**: `Cache-Control` headers added in Phase 0.5 for `/api/menu`
  and `/api/content`. Workspace and html-template responses are NOT
  cached — they should be (`?backfill=true` short-circuits caching).

### Recommendations

1. **Can this be deployed safely now?** Yes, but only if the env-var
   propagation issue is closed. **Verify on production immediately:**
   `/api/`, `/api/menu`, `/api/workspace/projects`, `/api/html-template/featured`.
2. **Production risks remaining:**
   * Playwright browser binary may be in a different path on
     production pods than preview (we hit this in preview).
     **MUST verify production has chromium at the expected path.**
   * MongoDB connection pool: with 1,838 active assets and the batched
     Workspace sweeps, watch for pool exhaustion under concurrent users.
   * Object storage quota — `media_assets` will grow ~20 docs per
     bulk-render call; no archival policy.
3. **Escalate to Emergent Support**:
   * Production env-var propagation
   * Playwright Chromium browser availability on production deploy
   * Disk quota / object-store cleanup policy

---

## Part 7 — Testing Audit

### Numbers

* **27 test files**, **455 tests collected**.
* **16 collect-time crashes** when env vars are missing — these tests
  are effectively unrun in CI.

### Strong coverage

* `test_agency_templates.py` (16) — covers the agency renderer well.
* `test_sprint19_hotfix.py` (11) — locks down badge/feathering rules.
* `test_workspace.py` (7) — covers the new Workspace endpoints.
* `test_render_engine.py` (28) — broad procedural-renderer suite.

### Weak / missing

* **No end-to-end test** for the Library → Workspace asset linking
  path (the heuristic matcher is purely heuristic).
* **No frontend tests** beyond ad-hoc Playwright screenshots taken
  in chat. Zero Jest/Vitest tests.
* **No integration test** for the HTML renderer route under load
  (the slow-marked tests are skipped in regression).
* **No test** verifying Today's Featured rotation is stable across a
  day boundary.
* **No test** that `marketing_packs` writes round-trip to Workspace
  captions correctly.

### Flaky / fragile

* `test_html_template_routes.py` — the 2 slow tests fail when bunched
  with other Playwright tests in the same pytest session (lifespan
  + sync_playwright sharing issue). Reliable when run in isolation.

### Recommendations

* **Keep**: agency, sprint19, workspace, render_engine, html_renderer.
* **Delete**: any test that crashes on collection without env vars —
  rewrite with fixtures or delete outright. **16 candidates.**
* **Rewrite**: `test_html_template_routes.py` to use HTTPX +
  uvicorn-on-subprocess pattern (avoid TestClient + Playwright clash).
* **Add before refactor**: end-to-end Library matching test;
  Workspace → Promote → flyer-saved round-trip test.

---

## Part 8 — Refactor Plan (staged)

### R1 — Split `ai_designer.py` (1750 → ~600 LOC)

* **LOC reduction**: ~1,150 lines moved, ~150 deleted via DRY.
* **Files affected**: `routers/ai_designer.py`, NEW `services/ai_design/{procedural.py, agency.py, html.py, score.py, copy.py, jobs.py}`.
* **Tests required before**: a smoke test for `_compose_design`
  returning bytes + score for every theme. Currently exists but lives
  inside `test_typography_engine.py`.
* **Risk**: Medium — the renderer suite catches most breakage.
* **Rollback**: revert one PR; mongo schema unchanged.

### R2 — Split `AiDesigner.jsx` (1578 → ~400 LOC)

* **LOC reduction**: ~1,100 lines distributed.
* **Files affected**: NEW `aiads/{AiDesignerShell.jsx, JobRunner.jsx, HistoryDrawer.jsx, ThemePicker.jsx, ResultCanvas.jsx}`.
* **Tests required before**: Playwright screenshot baseline of the
  current page.
* **Risk**: Low.
* **Rollback**: revert PR; no API changes.

### R3 — Collapse the three flyer-creation UIs

* **LOC reduction**: ~1,500 lines (PhotoToFlyer + PromoteThisItem +
  AiImageGenerator collapsed into one shell).
* **Files affected**: 4 frontend; 1 backend (`photo_flyer.py` may
  become routes on `ai_designer.py`).
* **Tests required before**: smoke tests for each existing entry
  point.
* **Risk**: High — most user-facing change. Behind a feature flag.
* **Rollback**: feature flag.

### R4 — Move flyer-engine helpers into `services/render/`

* `agency_renderer.py`, `quality_score.py`, `typography_engine.py`,
  `render_engine.py` are at backend root. They are services, not
  routers. Move them.
* **LOC reduction**: 0 (organisational).
* **Risk**: Low — imports change only.

### R5 — Test hygiene

* Fix the 16 env-var-at-import test files.
* Delete dead tests for removed code (legacy procedural variants).
* Migrate Playwright route tests off TestClient.

### R6 — Workspace bulk-asset matching

* The string-matching heuristic is brittle. Migrate every new
  generated asset to write a hard `item_key` field.
* Backfill once: scan `media_assets`, infer `item_key` from existing
  fields, persist.

### Order

R5 (tests) → R1 (ai_designer.py) → R2 (AiDesigner.jsx) → R4 (services
move) → R3 (UI collapse) → R6 (asset matching).

---

## Part 9 — What To Delete

| Item | Reason | LOC removed | Risk |
|---|---|---:|---|
| `routers/ai_ads.py` | No frontend caller | ~150 | Low |
| `tests/test_sprint_12c.py` | Env-var crash, sprint long over | ~280 | Low |
| Legacy `theme_packs/*` for themes that have HTML equivalents | Duplicate template system | ~400 | Medium |
| `seed_agency_template_backgrounds.py` and all V2 PNGs once designer PNGs land | Superseded | ~360 | None when real assets land |
| `routers/todays_pick.py` (if Today's Featured stays) | Older pick system | ~760 | Medium — operator may rely on cron |
| `failure_audit_log` collection | Never written | 0 LOC, drops a collection | None |
| 15 of 17 `/app/memory/` sprint reports | Archive | ~5,000 lines of markdown | None |
| Suspense placeholders for "Schedule" + "Insights" tabs | Don't advertise unbuilt features | ~30 LOC | None |
| `AiImageGenerator.jsx` | Niche, used twice in entire UI | ~390 LOC | Medium |
| Sprint 17/18/19 audit `/tmp/*` PNG files | Not in git | n/a | None |

**Estimated removable**: ~3,000 lines of Python + ~2,000 lines of JS +
5,000 lines of markdown + 1 collection + 1 router.

---

## Part 10 — What To Build Next

Ranked by business value × effort × risk. Top of list = ship first.

| # | Task | Biz value | Tech risk | Effort | Priority |
|---|---|:---:|:---:|:---:|---|
| 1 | **Ship current preview to production** | ⭐⭐⭐⭐⭐ | Low (preview is healthy) | 0.5 day | **DO NOW** |
| 2 | **Drop in real designer PNGs for 3 themes** | ⭐⭐⭐⭐⭐ | None (no code) | 1 day (designer) | **DO NEXT** |
| 3 | **Collapse three flyer-creation UIs into one** | ⭐⭐⭐⭐ | Medium | 1.5 days | High |
| 4 | **Workspace status field + Stale-items filter** | ⭐⭐⭐⭐ | Low | 0.5 day | High |
| 5 | **Promote-saves-back-to-project loop** | ⭐⭐⭐⭐ | Low | 0.5 day | High |
| 6 | **Hide Schedule + Insights "Soon" placeholders** | ⭐⭐⭐ | None | 15 min | High (quick win) |
| 7 | **Activity Stream on project cards** | ⭐⭐⭐ | Low | 0.5 day | Medium |
| 8 | **Test hygiene (R5)** | ⭐⭐ | None | 0.5 day | Medium — do before R1/R2 |
| 9 | **Refactor `ai_designer.py` (R1)** | ⭐⭐⭐ | Medium | 2 days | Medium |
| 10 | **Real Scheduling (Sprint 20B)** | ⭐⭐⭐⭐ | Medium | 5 days | Low — only after #1–6 |

**Do not** build Insights, Batch Campaign Generator, FAL AI activation,
template picker UI, or project remix **until #1–6 are done**.
They're solving problems the owner doesn't have yet.

---

## Part 11 — Brutal Consultant Opinion

### 1. If this were my SaaS, what would I do next?

**Stop adding sprints. Sell three pilot accounts.** The product is
fine for one restaurant; you'll learn more about what to build next
from one paying owner than from ten more sprints.

### 2. What would I stop doing?

* Adding placeholder UI for unbuilt features ("Schedule — Soon").
* Maintaining three flyer-creation paths.
* Writing sprint markdown reports nobody reads (17 of them in
  `/app/memory/`).

### 3. What would I delete?

* `routers/ai_ads.py`, `failure_audit_log` collection,
  `seed_agency_template_backgrounds.py`, `AiImageGenerator.jsx`,
  15 of 17 memory reports, the Schedule/Insights placeholder tabs,
  `tests/test_sprint_12c.py` and 15 sibling env-fragile tests.

### 4. What would I refuse to build?

* **Calendars and Insights before real owners have asked for them.**
* **Per-item AI image generation** (FAL Flux). The HTML/CSS engine
  already produces 8/10 flyers. Per-render generative AI adds cost +
  unpredictability for marginal quality gain. Defer indefinitely.
* **A template picker UI**. The Live Template Designer is enough for
  the designer; an owner-facing picker is solving the wrong problem.

### 5. Fastest path to revenue

* 3 pilot accounts × $99/mo = $300 MRR within 60 days.
* The product as it stands today is sellable to **independent
  restaurants who already do social media themselves but hate the
  weekly Canva grind.** That is a specific, addressable, painful
  niche.
* Pitch: *"Stop opening Canva on Mondays. Lakeview generates a week's
  worth of menu flyers in 90 seconds, every Monday, automatically,
  using your menu and your food photos."*
* What's missing for that pitch: (a) "auto every Monday" (the
  scheduling primitive, but you can ship it with a literal cron in a
  weekend); (b) a 90-second onboarding video.

### 6. Biggest waste of time right now

* The agency template renderer (Sprint 20 Phase 0). It served its
  purpose; now it's a parallel system to the HTML/CSS engine. Every
  hour spent on its v2 procedural backgrounds is an hour not spent
  on selling pilots or porting more HTML themes.

### 7. What would make a restaurant owner actually use this every week?

Three things, none of which are built yet:

1. **A Monday morning email**: "Your 8 new flyers are ready. Click to
   approve, edit, or schedule." (One cron job.)
2. **One-click post to Facebook/Instagram**. Not a download.
   Connected social accounts. (~3 days of OAuth + Graph API work.)
3. **A one-page weekly performance summary**: "Smash Burger got the
   most clicks last week. Want to repeat?" (Insights, but only the
   one number that matters.)

Everything else is icing. Build those three things, ship to 3 pilots,
take their money, listen to them, build sprint 21 from THAT.

---

## Final Recommendation

**Launch.** The product is good enough for early customers; further
engineering without owner feedback is gold-plating. Specifically:

1. **Today**: Redeploy preview → production, verify the 7 critical
   endpoints, sign off.
2. **This week**: Delete the dead code listed in Part 9. Hide the
   Schedule + Insights placeholders. Fix the Promote-saves-to-project
   loop.
3. **Next 30 days**: Sell 3 pilot accounts. Ship a Monday-morning
   email cron. Build the FB/IG posting integration.
4. **Defer until customer 5**: Refactor work, Insights, Scheduling
   calendar UI, agency renderer cleanup, FAL AI.

**The codebase is more ready for paying customers than the founder
is for paying customers.** That's a good problem to have. Use it.

---

*End of audit. No code changed.*
