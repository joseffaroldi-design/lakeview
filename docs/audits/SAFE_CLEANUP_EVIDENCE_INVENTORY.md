# Safe Cleanup Evidence Inventory

Date: 2026-08-05
Branch: `agent/lakeview-safe-cleanup-foundation`

## Purpose

This document records evidence gathered before any runtime refactor. It is intentionally conservative. A package, page, route, renderer, or workflow is not considered removable until its production usage and test dependencies are confirmed.

## 1. Frontend dependency evidence

The current `frontend/package.json` includes a broad UI and utility dependency set. Repository searches found no indexed source usage for the following package names beyond the dependency manifest:

- `next-themes`
- `recharts`
- `react-resizable-panels`
- `input-otp`
- `cmdk`
- `react-day-picker`
- `embla-carousel-react`
- `vaul`
- `@radix-ui/react-menubar`
- `@radix-ui/react-context-menu`
- `@radix-ui/react-hover-card`

### Classification

**Status: dependency-removal candidates, not approved deletions.**

Before removal, run a local import scan that covers JavaScript, JSX, generated UI files, tests, and any dynamically imported modules. Then run the production build and relevant frontend tests after each small package group is removed.

### Required validation

```bash
cd frontend
rg -n "next-themes|recharts|react-resizable-panels|input-otp|cmdk|react-day-picker|embla-carousel-react|vaul|@radix-ui/react-menubar|@radix-ui/react-context-menu|@radix-ui/react-hover-card" src plugins test_*.js

yarn build
```

Do not remove multiple high-level UI packages in the same commit unless the import scan is clean and the build is verified.

## 2. Public application extraction seams

`frontend/src/App.js` currently owns several unrelated concerns:

- Browser routing
- Visitor session generation
- Analytics calls
- Public navbar and mobile navigation
- Hero section
- Featured and specials sections
- About section
- Menu section
- Email signup and loyalty sections
- Catering form
- Contact and footer
- Homepage content, menu, and layout fetching
- Backend-driven homepage section composition
- Sticky ordering controls

### Behavior-preserving extraction plan

Extract in this order:

1. `frontend/src/lib/analytics.js`
   - `getSessionId`
   - `trackPageView`
   - `trackButtonClick`

2. `frontend/src/config/homepageSections.js`
   - `SECTION_COMPONENTS`
   - `FALLBACK_LAYOUT`

3. `frontend/src/hooks/useHomepageContent.js`
   - content/menu/layout fetch orchestration
   - fallback preservation

4. `frontend/src/components/public/`
   - `Navbar.jsx`
   - `Hero.jsx`
   - `CateringForm.jsx`
   - remaining homepage sections
   - `Footer.jsx`
   - `StickyOrderBar.jsx`

5. `frontend/src/pages/PublicHome.jsx`
   - compose extracted sections only

6. Reduce `App.js` to router composition.

### Non-negotiable behavior gates

- Preserve every existing route.
- Preserve all `data-testid` values.
- Preserve section IDs used by smooth scrolling.
- Preserve analytics payload shapes.
- Preserve the homepage fallback layout.
- Preserve public content, menu, and layout endpoint calls.
- Preserve current visual class names during extraction.
- No copy, order, styling, or workflow redesign in the extraction commit.

## 3. Dashboard overlap inventory

Current top-level dashboard tabs:

- Home
- Workspace
- Menu
- Promote
- Library
- Layout
- Customers

Analytics remains implemented but hidden from the visible tab list.

### Observed overlap

#### Workspace and Library

Both appear to manage creative assets or generated work. The distinction between in-progress work, completed designs, uploads, and reusable assets must be explicitly documented before merging either surface.

#### Promote and Workspace

Promotion generation and active creative work are closely related. A future `Create` surface may unify entry points, but this is a product workflow change and must not be combined with code extraction.

#### Menu and website content

The Menu tab currently contains menu editing, Today's Pick, and public website copy editing. Website copy belongs to a lower-frequency `Website` or `Manage` area rather than the core menu workflow.

#### Layout

Homepage ordering and visibility are low-frequency controls. Layout is a candidate to move under `Website`, but should remain unchanged until workflow screenshots and owner usage are reviewed.

#### Analytics

Hidden code must be formally classified as active internal functionality, intentionally dormant functionality, or removable legacy functionality. Hidden indefinitely is not an acceptable final state.

## 4. Creative backend inventory

The backend exposes multiple neighboring creative domains and implementation layers:

### Routers

- `backend/routers/ai_ads.py`
- `backend/routers/ai_designer.py`
- `backend/routers/ai_image.py`
- `backend/routers/creative_director.py`
- `backend/routers/html_template.py`
- `backend/routers/marketing_pack.py`

### Services and renderer areas

- `backend/agency_renderer.py`
- `backend/agency_templates/`
- `backend/ai_designer/`
- `backend/ai_engine/`
- `backend/background_engine.py`
- `backend/flyer_config.py`
- `backend/html_renderer/`
- `backend/logo_renderer.py`
- `backend/media_storage/`

### Required path matrix

Complete this matrix before deleting or consolidating anything:

| User workflow | Frontend entry | API endpoint | Router function | Orchestrator/service | Renderer | Storage path | Tests | Status |
|---|---|---|---|---|---|---|---|---|
| Photo-to-Flyer: library image | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Active |
| Photo-to-Flyer: fresh upload | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Active |
| Promote menu item | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Active |
| Marketing Pack | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Verify |
| Template Designer | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Verify |
| AI Image generation | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Verify |
| HTML renderer fallback | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Verify |
| PIL/agency renderer fallback | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Verify |

### Classification rules

- **Active:** reached by a visible production workflow.
- **Fallback:** reached only when the primary renderer or provider fails.
- **Compatibility:** retained for older themes, stored jobs, or output formats.
- **Dormant:** intentionally hidden but still supported.
- **Legacy:** no visible workflow, no fallback role, but still referenced by tests or stored data.
- **Dead:** no runtime references, no fallback role, no stored-data compatibility requirement, and no necessary tests.

Only `Dead` code may be proposed for deletion, and deletion still requires focused regression coverage.

## 5. Safe next implementation unit

The first runtime change should be **analytics extraction from `App.js` only** because it has a narrow responsibility and clear behavior contract.

### Acceptance criteria

- Exact same analytics endpoints.
- Exact same request payloads.
- Exact same session-storage key and session ID format.
- Exact same call sites.
- Public site build succeeds.
- Relevant frontend tests pass.
- No visual changes.

If local build and tests cannot be run, do not merge the runtime extraction.

## 6. Stop conditions

Stop and investigate before proceeding if any of the following occurs:

- A suspected unused dependency is imported dynamically or through generated UI code.
- A public `data-testid`, section ID, API request, or analytics payload changes.
- Dashboard workflow ownership cannot be explained in one sentence per tab.
- A renderer path is used by hidden themes, stored jobs, or fallback behavior.
- Backend tests fail outside known transient network checks.
- Frontend build output gains preview URLs or loses production URLs.
- Production and preview behavior diverge after a cleanup change.

## Conclusion

The evidence supports continued documentation and a small behavior-preserving frontend extraction. It does not yet support deleting dependencies, merging dashboard workflows, or consolidating creative backend paths.