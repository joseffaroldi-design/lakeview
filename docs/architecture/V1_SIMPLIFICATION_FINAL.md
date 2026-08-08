# Lakeview V1 Simplification — Final Architecture

Baseline: source archive from production-ready workspace HEAD `6d4d6d0` / tag `v1.0.0`.

## Product rule

Normal restaurant changes are settings, not coding projects.

## Active owner workflow

### Website
- Menu editor
- Public website copy
- Homepage section order / visibility

### Marketing
- Photo upload or existing Library photo
- Optional food-photo analysis
- Explicit item name, features, price, CTA
- Explicit deterministic template
- Explicit export size
- Render 1–3 deterministic variations
- Save automatically to the existing media library
- Download flyer and copy a simple social caption

Runtime path:

`PHOTO -> TEMPLATE -> TEXT/PRICE -> RENDER -> SAVE/EXPORT`

The active frontend no longer calls AI Designer, Creative Director, Design Memory,
Marketing Pack generation, AI Image generation, AI Ads, or Workspace APIs.

## Restaurant settings

`business_settings` is the owner-facing settings document. It covers:
- business name
- phone / email / address
- daily hours
- social URLs
- logo / brand values
- homepage announcement / default CTA
- default marketing template / size
- loyalty enabled state / reward threshold / reward label

Settings writes require an authenticated admin session. Public-safe settings are
available through a separate read endpoint. Existing `site_content.contact` and
`site_content.hero.announcement` fields are synchronized on save so the current
public website updates without a rewrite.

## Loyalty

Square ordering exists, but this repository has no Square Loyalty integration.
V1 therefore keeps the existing native punch-card model and makes it auditable.

Every stamp, redemption, and manual adjustment writes an append-only
`loyalty_events` row. Reward threshold and reward name are settings rather than
hard-coded values. Manual adjustments require a reason.

## Deterministic flyer templates

The existing HTML/CSS renderer is the canonical new renderer. The retained
owner-selectable templates are:
- cajun
- cajun_blackened
- luxury
- luxury_dark
- seafood
- seafood_coastal
- seafood_lagoon

The marketing service owns platform sizes and deterministic variation context.
It does not use an LLM or agent to decide layout.

## Legacy compatibility classification

### ACTIVE
- `routers/settings.py`
- `routers/marketing.py`
- `services/template_renderer.py`
- `routers/photo_flyer.py` for image analysis / persistence only
- `html_renderer/**`
- media storage/library
- CMS/menu/home/specials/customer/loyalty surfaces

### RETAIN FOR DATA COMPATIBILITY — NOT ACTIVE OWNER ARCHITECTURE
- `routers/ai_designer.py`
- `ai_designer/**`
- `theme_packs/**`
- `typography_engine.py`
- `agency_renderer.py`
- `routers/creative_director.py`
- `routers/design_memory.py`
- `routers/marketing_pack.py`
- `routers/ai_image.py`
- `routers/ai_ads.py`
- `routers/workspace.py`

These are no longer mounted as live generation/workspace APIs where removed from
`server.py`, but files are intentionally retained because historical database
rows reference legacy theme ids and historical media/jobs still depend on their
meaning. The V1 source comment documents roughly 3,396 themed media assets and
~1,832 rows referencing hidden legacy theme ids.

### DELETE CONDITION
Legacy renderer/theme implementation files may be physically deleted only after:
1. production data is inventoried,
2. historical theme ids are mapped to retained template ids or frozen assets,
3. saved jobs/templates/design-memory rows no longer require regeneration,
4. a backup exists,
5. migration is verified in preview,
6. explicit destructive-migration approval is given.

No production data deletion is part of this change.

## Admin navigation

Active navigation is intentionally small:
- Dashboard
- Website
- Marketing
- Photos
- Customers
- Settings

The old Workspace and standalone Template Designer surfaces are removed from the
frontend. Homepage layout editing is folded into Website.

## Security preserved

The V1 release-blocker protections remain present, including authenticated
admin writes for the previously affected endpoints, production CORS fail-safe,
removed flyer-share analytics drift, and environment-only admin passwords in
helper scripts.

## Verification performed in the archive sandbox

- source archive SHA-256 matched the owner-provided hash
- Python `compileall` passes after correcting two pre-existing future-import
  ordering errors in helper scripts
- `git diff --check` passes
- frontend relative / `@/` local import resolution passes
- zero active frontend references to the retired legacy generation APIs
- V1 blocker auth/CORS/password fixes spot-checked in source

Full pytest and frontend production build could not be executed in this sandbox
because the uploaded archive intentionally excludes dependency directories and
the execution environment cannot download the pinned packages. Those should be
the first CI/preview gates after the source is placed back into its normal build
environment.
