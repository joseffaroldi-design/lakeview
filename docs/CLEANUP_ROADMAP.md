# Lakeview Safe Cleanup Roadmap

## Objective

Reduce complexity without changing proven customer or owner workflows.

## Gate 0 — Scope freeze

Before each cleanup task:

- Confirm the change is inside `FROZEN_FEATURES.md`.
- State which user workflow is protected.
- List files expected to change.
- Identify focused regression tests.
- Keep the change reversible.

## Gate 1 — Repository clarity

Status: **In progress**

Tasks:

- [x] Replace placeholder root README with product and verification guidance.
- [x] Add Lakeview 1.0 architecture review.
- [ ] Create `docs/historical-sprints/` inventory.
- [ ] Move historical sprint reports in a dedicated documentation-only PR.
- [ ] Add a short current-state index linking only active documents.

Acceptance:

- A new developer can identify the public website, owner studio, backend, tests, and production-critical workflows in under ten minutes.

## Gate 2 — Frontend dependency inventory

Status: **Not started**

Tasks:

- [ ] Search imports for every direct dependency in `frontend/package.json`.
- [ ] Classify each dependency as active, indirect-support, test-only, or unused.
- [ ] Remove only confirmed unused direct dependencies.
- [ ] Run `yarn build` after each removal group.

Acceptance:

- Every direct dependency has a documented use or is removed.

## Gate 3 — Public application extraction

Status: **Not started**

Rules:

- No visual changes.
- No copy changes.
- No route changes.
- Preserve all `data-testid` attributes.
- Preserve section order and fallback behavior.

Tasks:

1. Extract analytics helpers.
2. Extract Navbar and Footer.
3. Extract low-coupling homepage sections.
4. Extract data fetching into a hook.
5. Leave `App.js` as router/composition only.

Acceptance:

- Production build passes.
- Public homepage behavior and DOM order remain unchanged.
- Catering submission, menu loading, homepage layout, and ordering links still work.

## Gate 4 — Public UX polish

Status: **Blocked by Gate 3**

Candidate changes:

- Remove the public dashboard icon.
- Replace generic hero photography.
- Move menu higher in the default layout.
- Combine email signup and loyalty presentation.
- Standardize error and loading messages.

Acceptance:

- Customers reach menu, ordering, hours, location, and catering faster.
- No owner capability is removed.

## Gate 5 — Dashboard workflow map

Status: **Not started**

Tasks:

- [ ] Document the purpose of Home, Workspace, Promote, Library, Menu, Layout, and Customers.
- [ ] Identify duplicate entry points.
- [ ] Define where drafts, uploads, outputs, and brand assets live.
- [ ] Measure clicks for the five most common owner tasks.

Target information architecture:

- Home
- Create
- Library
- Menu
- Manage

Acceptance:

- Each object has one obvious home.
- Each common task has one primary entry point.

## Gate 6 — Creative backend map

Status: **Not started**

Tasks:

- [ ] Map frontend entry points to API endpoints.
- [ ] Map endpoints to routers and services.
- [ ] Map renderer selection and fallbacks.
- [ ] Map storage and output retrieval.
- [ ] Attach tests to each active path.
- [ ] Classify paths as Active, Fallback, Compatibility, Hidden, Legacy, or Unreachable.

Acceptance:

- No creative path is refactored or deleted without documented callers, outputs, and regression coverage.

## Gate 7 — Backend extraction

Status: **Blocked by Gate 6**

Tasks:

- Thin oversized routers by moving orchestration into services.
- Consolidate canonical theme/platform configuration only after tests prove equivalence.
- Remove unreachable paths in separate commits.

Acceptance:

- Routers validate and delegate.
- Renderer selection has one canonical owner.
- Existing outputs remain compatible.

## Deferred work

These tasks are intentionally deferred until after stabilization:

- CRA/CRACO to Vite migration
- Major visual redesign
- New dashboard modules
- New rendering providers
- Database redesign
- Broad authentication rewrite

## Stop conditions

Stop a cleanup task and investigate when:

- A focused test fails unexpectedly.
- Production and preview behavior differ.
- A supposedly unused path has stored-data or migration dependencies.
- A change alters generated image dimensions, theme routing, storage URLs, authentication, or public content ordering.
- The task expands beyond its declared file list.
