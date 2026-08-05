# Lakeview 1.0 Architecture Review

## Purpose

This document defines the safe cleanup boundary for Lakeview. It is intentionally conservative: the goal is to simplify the product without changing proven production behavior.

## Product boundaries

### Public website

Primary outcomes:

1. Help customers understand what Lakeview serves.
2. Make menu discovery fast.
3. Drive online orders and phone calls.
4. Produce catering inquiries.
5. Communicate hours, location, and trust.

### Lakeview Studio

Primary owner outcomes:

1. Update menu items and public-site content.
2. Choose and promote featured items.
3. Create marketing graphics from menu items and photos.
4. Store, retrieve, and reuse media and generated assets.
5. Review customer, subscriber, and catering activity.

Anything that does not directly support these outcomes should be treated as secondary, advanced, or a removal candidate.

## Current frontend architecture

### Public application

`frontend/src/App.js` currently owns routing, analytics helpers, navigation, homepage sections, data fetching, the catering workflow, footer behavior, and homepage composition.

This file is a maintainability hotspot, but it is not a functional blocker. The safe remediation is behavior-preserving extraction.

Recommended target structure:

```text
frontend/src/
  app/
    AppRouter.jsx
    PublicSite.jsx
  components/public/
    Navbar.jsx
    Hero.jsx
    FeaturedSection.jsx
    SpecialsSection.jsx
    MenuSection.jsx
    CateringSection.jsx
    AboutSection.jsx
    ContactSection.jsx
    Footer.jsx
    StickyOrderBar.jsx
  config/
    homepageSections.js
  hooks/
    useHomepageContent.js
  lib/
    analytics.js
```

### Dashboard

The dashboard already lazy-loads most heavy tabs. That organization should be preserved.

Current top-level areas:

- Home
- Workspace
- Menu
- Promote
- Library
- Layout
- Customers

Long-term information architecture target:

- Home
- Create
- Library
- Menu
- Manage

This is a workflow redesign and must not be combined with low-level component extraction.

## Current backend architecture

The backend has domain-specific routers and multiple creative-generation systems, including AI Designer, AI image generation, Creative Director, HTML templates, marketing packs, agency rendering, and supporting registries/services.

The creative subsystem is powerful but has overlapping names and likely contains primary, fallback, compatibility, and historical paths.

No renderer or endpoint should be removed until a production usage matrix exists.

## Required creative-path matrix

Before backend consolidation, document every workflow using this schema:

| Workflow | Frontend entry | API endpoint | Router | Service/orchestrator | Renderer | Storage path | Tests | Status |
|---|---|---|---|---|---|---|---|---|
| Photo-to-Flyer | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Active |
| Promote menu item | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Active |
| Marketing Pack | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Review |
| Template Designer | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Review |
| AI Image | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Review |

Status values:

- Active
- Fallback
- Compatibility
- Hidden
- Legacy
- Unreachable

Only `Unreachable` paths with no test, production, migration, or stored-data dependency should become deletion candidates.

## Canonical ownership rules

The application should move toward one canonical owner for each concern:

- Theme definitions: one registry
- Platform dimensions: one registry
- Renderer selection: one service
- Storage URL generation: one abstraction
- Authentication token handling: one frontend helper and one backend dependency
- Analytics transport: one frontend module
- Homepage section configuration: one schema and fallback
- Error response shape: one backend contract

## Safe cleanup order

### Stage 1 — Documentation and inventory

- Maintain the root README.
- Organize historical documentation.
- Create the creative-path matrix.
- Inventory frontend dependencies and imports.
- Identify hidden and frozen functionality.

### Stage 2 — Behavior-preserving frontend extraction

- Move analytics helpers out of `App.js`.
- Extract public sections one at a time.
- Keep routes, DOM order, test IDs, API calls, and styles unchanged.
- Run the production build and focused tests after each extraction group.

### Stage 3 — Public UX cleanup

- Remove the dashboard icon from public navigation.
- Replace generic hero photography with owned imagery.
- Move the menu higher in the default homepage order.
- Combine loyalty and email signup when content and backend ownership are confirmed.

### Stage 4 — Dashboard workflow redesign

- Define Create versus Library ownership.
- Move website copy and layout under Manage/Website.
- Preserve deep links and migration compatibility.
- Change navigation only after owner workflow acceptance.

### Stage 5 — Backend consolidation

- Complete the creative-path matrix.
- Add characterization tests around active/fallback paths.
- Extract router orchestration into services.
- Remove code only in separate, reviewable commits.

## Non-negotiable safety rules

1. Do not mix UI redesign with structural extraction.
2. Do not delete compatibility paths based only on visibility.
3. Do not change theme routing without hidden-theme and platform-size regression tests.
4. Do not change media storage without retrievability and health checks.
5. Do not migrate CRA/CRACO during the current stabilization phase.
6. Do not expose preview URLs in production assets.
7. Keep fallback homepage behavior operational.
8. Keep every cleanup commit narrowly scoped and reversible.

## Definition of Lakeview 1.0 complete

Lakeview 1.0 is complete when:

- The public website is focused on menu, ordering, catering, and trust.
- The owner can create a promotion with minimal navigation decisions.
- Public-site code is no longer concentrated in one oversized file.
- Creative-generation paths are documented and tested.
- The repository root is understandable without historical archaeology.
- No new major feature is required for normal restaurant operations.
