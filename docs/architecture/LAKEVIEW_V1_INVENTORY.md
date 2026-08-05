# Lakeview V1.0 Safe Cleanup — Architecture & Dependency Inventory

_Read-only inventory produced during the V1.0 Safe Cleanup Sprint (Feb 2026).
This is the audit output. It classifies subsystems as **ACTIVE**,
**COMPATIBILITY**, **FALLBACK**, **LEGACY**, or **DEAD** without proposing
deletions. Any removal must be re-authorized after this document._

Baseline captured at commit `79317ab` prior to any code moves:
- `frontend/src/App.js` — 1,186 lines, SHA-256 `edb933e9...`
- `yarn build` — passes in ~10 s
- `CI=true yarn build` — fails with 4 **pre-existing** exhaustive-deps
  warnings in `TemplateDesigner.jsx`, `PhotoToFlyer.jsx` (×2),
  `TodaysPick.jsx`. Not introduced by this sprint. Left as-is per scope.
- Public site: 110 unique data-testids, section order
  `navbar → hero-section → todays-featured-section → specials-section →
  about-section → menu-section → email-signup-section → loyalty-section →
  catering-section → contact-section → footer`.
- Public API contract: `GET /api/content`, `GET /api/menu`,
  `GET /api/homepage/layout`, `GET /api/specials?active_only=true`,
  `GET /api/html-template/featured` — all 200.
- Homepage layout API returns exactly the 9 sections above in the same order
  as `FALLBACK_LAYOUT`.

---

## 1. Frontend `App.js` extraction map

Original `App.js` (1,186 LOC) contained **17 top-level definitions** —
router shell, 11 public components, 2 constants blocks, 3 helper functions,
2 layout data structures. Extraction target below. All moves are verbatim;
no rewrite, rename, restyle, or reorder.

| Original (App.js line) | New location | LOC | Status |
|---|---|---:|---|
| Constants `LOGO`/`HERO_BG`/`ABOUT_IMG`/`API` (lines 13, 26–28) | `src/lib/publicConfig.js` | 8 | ACTIVE |
| `getSessionId` / `trackPageView` / `trackButtonClick` (lines 15–56) | `src/lib/analytics.js` | 42 | ACTIVE |
| `Navbar` (lines 59–190) | `src/components/public/Navbar.jsx` | 143 | ACTIVE |
| `Hero` (lines 193–278) | `src/components/public/Hero.jsx` | 95 | ACTIVE |
| `About` (lines 281–329) | `src/components/public/About.jsx` | 55 | ACTIVE |
| `Specials` (lines 332–405) | `src/components/public/Specials.jsx` | 82 | ACTIVE |
| `MenuItem` + `Menu` (lines 408–475) | `src/components/public/Menu.jsx` | 77 | ACTIVE |
| `Contact` (lines 478–581) | `src/components/public/Contact.jsx` | 111 | ACTIVE |
| `Footer` (lines 584–629) | `src/components/public/Footer.jsx` | 51 | ACTIVE |
| `StickyOrderBar` (lines 632–703) | `src/components/public/StickyOrderBar.jsx` | 82 | ACTIVE |
| `EmailSignup` (lines 706–785) | `src/components/public/EmailSignup.jsx` | 89 | ACTIVE |
| `LoyaltyCard` (lines 788–896) | `src/components/public/LoyaltyCard.jsx` | 122 | ACTIVE |
| `CateringForm` (lines 899–1088) | `src/components/public/CateringForm.jsx` | 200 | ACTIVE |
| `SECTION_COMPONENTS` + `FALLBACK_LAYOUT` (lines 1091–1115) | `src/components/public/sectionRegistry.jsx` | 39 | ACTIVE |
| `Home` composer (lines 1117–1167) | `src/pages/PublicSite.jsx` | 60 | ACTIVE |
| `App` router shell (lines 1170–1183) | `src/App.js` (final size 26 LOC) | 26 | ACTIVE |

Final `App.js` line count: **26** (down from 1,186 = 97.8% reduction).
Net LOC across the new files ≈ 1,182 — content moved, not duplicated.

**All 110 `data-testid` values verified identical post-extraction.**
**Section render order verified identical (see baseline capture).**

---

## 2. Frontend dependency audit

`frontend/package.json` declares 51 runtime + 12 dev dependencies. Grep-based
usage audit (source-tree only, excluding `src/components/ui/`):

### Actively imported by application code
`axios`, `react`, `react-dom`, `react-router-dom`, `react-scripts`,
`lucide-react`, `class-variance-authority`, `clsx`, `tailwind-merge`,
`sonner`, `recharts`, `@radix-ui/react-dialog`, `@radix-ui/react-dropdown-menu`,
`@radix-ui/react-tabs`, `@radix-ui/react-select`, `@radix-ui/react-popover`,
`@radix-ui/react-slot`, `@radix-ui/react-switch`, `@radix-ui/react-tooltip`,
`@radix-ui/react-scroll-area`, `@radix-ui/react-slider`,
`@radix-ui/react-progress`, `@radix-ui/react-toast`, `@radix-ui/react-label`,
`@radix-ui/react-radio-group`, `@radix-ui/react-checkbox`,
`@radix-ui/react-separator`, `@radix-ui/react-toggle`,
`@radix-ui/react-toggle-group`.

### Referenced ONLY inside unused `src/components/ui/*.jsx` (removal candidates — NOT removed this sprint)
| Package | Only user | Verdict |
|---|---|---|
| `@radix-ui/react-accordion` | `components/ui/accordion.jsx` (no app import) | **DEAD** (but keep — deletion out of scope) |
| `@radix-ui/react-alert-dialog` | `components/ui/alert-dialog.jsx` | **DEAD** |
| `@radix-ui/react-aspect-ratio` | `components/ui/aspect-ratio.jsx` | **DEAD** |
| `@radix-ui/react-avatar` | `components/ui/avatar.jsx` | **DEAD** |
| `@radix-ui/react-collapsible` | `components/ui/collapsible.jsx` | **DEAD** |
| `@radix-ui/react-context-menu` | `components/ui/context-menu.jsx` | **DEAD** |
| `@radix-ui/react-hover-card` | `components/ui/hover-card.jsx` | **DEAD** |
| `@radix-ui/react-menubar` | `components/ui/menubar.jsx` | **DEAD** |
| `@radix-ui/react-navigation-menu` | `components/ui/navigation-menu.jsx` | **DEAD** |
| `cmdk` | `components/ui/command.jsx` | **DEAD** |
| `embla-carousel-react` | `components/ui/carousel.jsx` | **DEAD** |
| `input-otp` | `components/ui/input-otp.jsx` | **DEAD** |
| `react-day-picker` | `components/ui/calendar.jsx` | **DEAD** |
| `react-hook-form`, `@hookform/resolvers`, `zod` | `components/ui/form.jsx` | **DEAD** (form.jsx not imported anywhere) |
| `react-resizable-panels` | `components/ui/resizable.jsx` | **DEAD** |
| `vaul` | `components/ui/drawer.jsx` | **DEAD** |
| `next-themes` | `components/ui/sonner.jsx` (the shadcn wrapper — `sonner` itself is imported directly in `index.js`) | **DEAD** wrapper file |
| `date-fns` | (no non-ui users besides `calendar.jsx`) | **DEAD** |
| `input-otp`, `react-day-picker`, `react-resizable-panels`, `vaul` | shadcn wrappers only | **DEAD** |
| `cra-template` | initial CRA scaffold | **DEAD** |

**Report only. Not removed in this sprint.** A follow-up cleanup pass could
delete these packages plus the 20+ orphan `components/ui/` files that reference
them (`accordion.jsx`, `alert-dialog.jsx`, `aspect-ratio.jsx`, `avatar.jsx`,
`calendar.jsx`, `carousel.jsx`, `collapsible.jsx`, `command.jsx`,
`context-menu.jsx`, `drawer.jsx`, `form.jsx`, `hover-card.jsx`,
`input-otp.jsx`, `menubar.jsx`, `navigation-menu.jsx`, `resizable.jsx`, etc.)
after independent owner sign-off. Removing them would cut ~15 packages and
several MB of `node_modules`. Zero user-visible impact.

### Dev deps — all actively used by build pipeline (KEEP)
`@craco/craco`, `eslint`, `eslint-plugin-*`, `postcss`, `tailwindcss`,
`autoprefixer`, `@babel/plugin-proposal-private-property-in-object`.

---

## 3. Dashboard overlap / workflow matrix

Current dashboard surfaces (from `pages/dashboard/`):

| Component | File | Purpose | Overlap? |
|---|---|---|---|
| Home | `HomeTab.jsx` | Landing + quick actions | — |
| Menu | (inside `AnalyticsTab`) | Menu editor | — |
| Layout | `LayoutTab.jsx` | Homepage section order + on/off | — |
| Analytics | `AnalyticsTab.jsx` | KPIs + owner quick start | — |
| Specials | `SpecialsTab.jsx` (inside AnalyticsTab) | Legacy — reads from `marketing_packs` | Overlaps Library "specials" tag |
| Catering | `CateringTab.jsx` | Inquiry inbox | — |
| Subscribers | `SubscribersTab.jsx` | Newsletter list | — |
| Customers | `CustomersTab.jsx` | Loyalty + newsletter combined | Slight overlap with `SubscribersTab` (subscribers is a subset of customers) |
| Workspace | `WorkspaceTab.jsx` | Project/collection groupings | **FROZEN** (see `FROZEN_FEATURES.md` §2) |
| Library | `LibraryTab.jsx` | Flat media grid + uploads | Some overlap with `PhotoToFlyer` "existing library" tab |
| Billing | `BillingCard.jsx` (on Home) | Virtual budget | — |
| AI Ads | `AiAdsTab.jsx` → `PromoteThisItem.jsx` | Marketing Pack generator | **PARTIALLY FROZEN** (§1) |
| Photo-to-Flyer | `aiads/PhotoToFlyer.jsx` | Photo → Flyer wizard | Overlaps with `AiDesigner.jsx` (which is unreachable) |
| AI Designer | `aiads/AiDesigner.jsx` | **UNREACHABLE** — no nav route | **DEAD** (Lock Variant frozen per §11) |
| Creative Director | `aiads/CreativeDirectorRecs.jsx` | Top-3 recs behind "View other themes" | **FROZEN** (§6) |
| Template Designer | `pages/TemplateDesigner.jsx` | Feeds Today's Featured pool | **FROZEN** (§5) |
| Recommended Style | `aiads/RecommendedStyleCard.jsx` | Primary discovery surface | — |
| Structured Error | `aiads/StructuredErrorCard.jsx` | Retry banner | — |

**Verdict:** Two overlaps identified, both minor:
- `SubscribersTab` ⊂ `CustomersTab` — the newsletter list is a subset of the
  customer list. Consolidating would require product review.
- `LibraryTab` and `PhotoToFlyer` "existing library" tab both browse
  `media_assets`. Different UX; not true duplication.
- `AiDesigner.jsx` is genuinely orphaned but its removal is deferred by
  `FROZEN_FEATURES.md` §11 pending owner sign-off.

**No merges recommended in this sprint per the SAFE CLEANUP directive.**

---

## 4. AI / renderer workflow map

```
User photo (PhotoToFlyer)                Template Designer (bulk-render)
     │                                            │
     ▼                                            ▼
 /api/photo-flyer/analyze-existing         /api/html-template/bulk-render
     │                                            │
     └──────────► /api/ai-designer/generate ◄─────┘
                          │
                          ▼
                    ai_designer/renderer.py
                          │
                  ┌───────┴───────┐
              theme ∈ {cajun,       theme ∈ {agency manifest
              luxury, seafood_*}     for burger_classic, modern,
                  │                  game_day_scoreboard}
                  ▼                  │
        HTML/Chromium engine         │  everything else
        (html_renderer/engine.py)    │  ────────────► procedural
        (executable_path from        │  (agency_renderer.py
         PLAYWRIGHT_CHROME_          │   `_apply_archetype`
         EXECUTABLE_PATH or          │   + PIL `_pil_background`)
         Playwright cache)           │
                  │                  │
                  ▼                  ▼
             PNG output          PNG output
                          │
                          ▼
                  Today's Featured pool
                          │
                          ▼
             /api/html-template/featured
             SHA-256 deterministic daily pick
             (57 assets in pool as of Feb 2026)
```

- **Renderer selection:** decided in `ai_designer/renderer.py` via
  `_is_chromium_available()` (4-path resolver). If HTML render fails →
  PIL fallback to agency template → procedural.
- **`FROZEN_FEATURES.md` §13** prohibits new HTML templates until an owner
  decision on Chromium.
- **Theme routing:** `agency_templates.pick_template_for(theme_hint=X)` now
  does **exact match only** (Sprint 22J). Themes without a manifest go
  through procedural — this is intentional.
- **57-asset featured pool** is replenished only by the frozen
  `TemplateDesigner.jsx` bulk-render endpoint.

**No renderer/theme/dimension changes in this sprint.**

---

## 5. Backend router audit

23 routers (5,450 total LOC). Oversized candidates and duplicate logic:

| Router | LOC | Verdict | Note |
|---|---:|---|---|
| `ai_designer.py` | 871 | **LARGE** | Has intentional `# noqa: F401` overlay/icon re-exports (Sprint 22H). Split would be safe but out of scope. |
| `todays_pick.py` | 767 | **LARGE** | Handles pool ingestion + rotation logic. Could split. |
| `marketing_pack.py` | 573 | **LARGE** | 4-stage pipeline (inferring, copy, images, video). **FROZEN** (§1). |
| `creative_director.py` | 486 | Medium | **FROZEN** (§6). |
| `workspace.py` | 477 | Medium | **FROZEN** (§2). |
| `html_template.py` | 361 | Medium | Contains SHA-256 daily-index. Recently touched — leave alone. |
| `ai_image.py` | 345 | Medium | Bounded. OK. |
| `photo_flyer.py` | 269 | Small | OK. |
| `analytics.py` | 247 | Small | OK. |
| `cms.py` | 238 | Small | OK. |
| `home.py` | 172 | Small | OK. |
| `design_memory.py` | 127 | Small | OK. |
| `media/` (subpackage) | — | Already split (Sprint 12C) | OK. |
| Others (<125 LOC) | — | OK | ai_ads (67), billing (55), catering (51), loyalty (76), messaging (109), misc (12), newsletter (39), specials (107) |

**Findings:**
1. `ai_designer.py` and `todays_pick.py` are the two largest live routers.
   Neither has documented duplicate business logic; they are large but
   focused. **No split recommended this sprint** — the frozen areas
   (§1, §5, §6) intersect too much of these files.
2. No cross-router duplicate logic detected in the audit grep pass.

---

## 6. Repository documentation move inventory

Moved (via `git mv` to preserve history):

| From (repo root) | To |
|---|---|
| `SPRINT_13A_SUMMARY.md` | `docs/historical-sprints/` |
| `SPRINT_14A_FRONTEND_REPORT.md` | `docs/historical-sprints/` |
| `SPRINT_14A_REPORT.md` | `docs/historical-sprints/` |
| `SPRINT_14B1_REPORT.md` | `docs/historical-sprints/` |
| `SPRINT_14B2_PLAN.md` | `docs/historical-sprints/` |
| `SPRINT_15C_DEPLOY_READINESS.md` | `docs/deployment/` |
| `SPRINT_15_AUDIT.md` | `docs/audits/` |
| `UX_AUDIT_REPORT.md` | `docs/audits/` |
| `image_testing.md` | `docs/implementation/` |

Kept at root:
- `README.md` (project readme)
- `FROZEN_FEATURES.md` (source of truth — must be immediately visible)
- `test_result.md` (agent-workflow scaffolding — NOT documentation; moving
  it would break `finish` tool references and the testing subagent workflow)

`CHANGELOG.md` and `CONTRIBUTING.md` were NOT created — no existing content
to seed them and the user rules disallow empty placeholder files.

**`memory/` directory left untouched** — it contains PRD, test credentials,
operator guide, deployment checklist, and archived sprint reports that
already live in a well-organized sub-hierarchy (`memory/archive/`,
`memory/launch/`). Moving them into `docs/` would break the many code
references to `/app/memory/PRD.md` and `/app/memory/test_credentials.md`.

---

## 7. FROZEN_FEATURES conflict check

Verified against `FROZEN_FEATURES.md` §§1–13. **No conflict.** Every move
in this sprint is:
- A verbatim source-file relocation (no logic changes)
- Zero touch to renderer selection, theme registry, `PLATFORM_SIZES`,
  media storage, authentication, billing, or the database
- Zero touch to `PromoteThisItem`, `WorkspaceTab`, `TemplateDesigner`,
  `CreativeDirectorRecs`, `BillingCard`, `AiDesigner`, or any of the frozen
  surfaces
- Zero package installs or removals

---

## 8. Deferred / owner decisions

The following were **identified** in this audit but **not acted on**, per
the SAFE CLEANUP mandate:

1. **Dead-package removal** — 15+ packages exclusively used by unused
   shadcn UI wrappers. Deletion requires owner approval and a separate
   cleanup PR.
2. **Orphan shadcn UI files** — 20+ `.jsx` files in `components/ui/` are
   never imported by app code. Deletion requires owner approval.
3. **`AiDesigner.jsx` removal** — frozen per §11; needs owner unfreeze.
4. **Router splits** — `ai_designer.py` (871 LOC) and `todays_pick.py`
   (767 LOC) are large but touch too many frozen areas to split safely
   without dedicated owner review.
5. **`SubscribersTab` ⊂ `CustomersTab` consolidation** — product decision,
   not a code decision.
6. **Pre-existing `CI=true` lint warnings** (4 total) — out of scope per
   the "move only, do not improve" rule.

---

_End of inventory._
