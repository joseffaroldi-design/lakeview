# Lakeview Safe Cleanup Execution Checklist

## Purpose

This checklist converts the architecture review and audit evidence into a conservative, test-gated implementation sequence. It is intentionally designed to prevent broad refactors, accidental feature removal, renderer regressions, or dashboard workflow breakage.

## Ground rules

- Work from a dedicated branch.
- One concern per commit.
- Never combine structural extraction with visual redesign.
- Never delete a dependency, endpoint, renderer, theme, or fallback path based only on naming or visibility.
- Every runtime change must be followed by the smallest relevant focused checks and a production build.
- Stop immediately if generated output changes unexpectedly, authentication behavior changes, or production URLs reappear in preview code.

## Gate 1 — Frontend import inventory

Run an import scan across `frontend/src` and record actual usage for every package in `frontend/package.json`.

Suggested commands:

```bash
cd frontend
rg -n 'from "next-themes"|from '\''next-themes'\''' src
rg -n 'from "recharts"|from '\''recharts'\''' src
rg -n 'from "react-resizable-panels"|from '\''react-resizable-panels'\''' src
rg -n 'from "input-otp"|from '\''input-otp'\''' src
rg -n 'from "cmdk"|from '\''cmdk'\''' src
rg -n 'from "react-day-picker"|from '\''react-day-picker'\''' src
rg -n 'from "embla-carousel-react"|from '\''embla-carousel-react'\''' src
rg -n 'from "vaul"|from '\''vaul'\''' src
```

Acceptance criteria:

- Every removal candidate has zero source imports.
- No package is removed solely because a GitHub search returned no results.
- `yarn build` passes after any dependency removal.

## Gate 2 — Analytics extraction

Create `frontend/src/lib/analytics.js` and move only:

- visitor session creation
- page-view tracking
- button-click tracking

Behavior contract:

- Keep session key `visitor_session`.
- Keep session format `session_<timestamp>_<random>`.
- Keep `/api/analytics/track` and `/api/analytics/button-click` endpoints.
- Keep payload keys unchanged.
- Keep failure handling non-blocking.
- Keep every existing call site and event name unchanged.

Required checks:

```bash
cd frontend
yarn build
```

Manually verify:

- Homepage loads.
- View Menu still scrolls correctly.
- Uber Eats and Square links still open.
- Catering submission still works.
- Analytics failures do not block page rendering.

## Gate 3 — Public component extraction

Extract one component per commit from `frontend/src/App.js` in this order:

1. `Navbar`
2. `Hero`
3. `About`
4. `Specials`
5. `Menu`
6. `EmailSignup`
7. `LoyaltyCard`
8. `CateringForm`
9. `Contact`
10. `Footer`
11. `StickyOrderBar`

Rules:

- No copy changes.
- No class-name changes.
- No section-order changes.
- No image changes.
- No test-id changes.
- No endpoint changes.
- No analytics event-name changes.

After every extraction:

```bash
cd frontend
yarn build
```

## Gate 4 — Homepage orchestration extraction

Move homepage data loading and section orchestration into focused modules only after individual sections are extracted.

Target structure:

```text
frontend/src/
  app/
    AppRouter.jsx
    PublicSite.jsx
  components/public/
  config/homepageSections.js
  hooks/useHomepageContent.js
  lib/analytics.js
```

Acceptance criteria:

- All four routes remain unchanged.
- Fallback layout remains unchanged.
- Section visibility and custom title/body overrides remain unchanged.
- Public content, menu, and homepage-layout requests still occur once on load.

## Gate 5 — Dashboard information architecture review

Do not merge dashboard tabs in code until usage is observed and documented.

Review these overlaps:

- Promote vs Workspace
- Workspace vs Library
- Layout vs public website copy
- Customers vs subscribers and catering inquiries
- Hidden Analytics path

Before changing navigation, document:

- Current task represented by each tab
- Data created or modified
- Primary user frequency
- Deep-link expectations
- Tests tied to the tab

No tab should be removed until its capability has a new, explicit home.

## Gate 6 — Creative backend path matrix

Map every production creative workflow from request to stored output.

Required workflows:

- Photo-to-Flyer from library image
- Photo-to-Flyer from fresh upload
- Promote menu item
- Marketing Pack
- Template Designer
- AI Image generation
- HTML template generation
- Any current fallback renderer

For each workflow record:

| Field | Required evidence |
|---|---|
| Entry endpoint | Router and route |
| Authentication | Guard or public status |
| Request model | Schema used |
| Orchestrator | Service or function |
| Renderer | HTML, Pillow, external AI, or hybrid |
| Theme source | Registry/config source |
| Platform size source | Registry/config source |
| Storage path | Local/object/media path |
| Polling/status | Job lifecycle |
| Tests | Focused and regression tests |
| Classification | Active, fallback, compatibility, dormant, legacy, dead |

Nothing classified as fallback or compatibility may be deleted without a replacement test and explicit approval.

## Gate 7 — Repository cleanup

Move historical sprint material from repository root only through a dedicated documentation PR.

Target folders:

```text
docs/
  architecture/
  audits/
  deployment/
  implementation/
  product/
  historical-sprints/
```

Rules:

- Preserve file history where possible.
- Update links in README or other documents.
- Keep `README.md` and `FROZEN_FEATURES.md` at root.
- Do not mix documentation moves with runtime changes.

## Gate 8 — Final verification

Before merging runtime cleanup:

```bash
cd backend
pytest tests/

cd ../frontend
yarn build
```

Also run focused checks for:

- authentication
- homepage layout
- catering
- media storage
- Photo-to-Flyer
- hidden themes
- platform dimensions
- generated thumbnail retrieval

## Stop conditions

Stop and revert the current commit when any of the following occurs:

- Frontend production build fails.
- Public route behavior changes.
- Dashboard authentication changes.
- Analytics event names or payload fields change.
- Generated design output changes unexpectedly.
- A fallback renderer is reached differently.
- Production or preview URL references regress.
- A dependency appears dynamically referenced or required by build tooling.
- The intended change requires touching unrelated files.

## Definition of complete

The safe cleanup program is complete when:

- `App.js` is reduced to application composition and routing.
- Public components are independently organized without visual changes.
- Unused dependencies are removed only after verified zero usage.
- Dashboard responsibilities are documented and intentionally organized.
- Every creative path is mapped and classified.
- Historical documentation is organized.
- Full backend tests and frontend production build pass.
- No public, admin, storage, authentication, or generated-output regression is observed.
