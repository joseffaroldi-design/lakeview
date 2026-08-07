# FROZEN FEATURES — No New Development Authorized

_Last updated: Feb 2026 (Phase 2E of the audit simplification sprint)_

This document is the source of truth for what is **not** allowed to receive
new development, features, expansion or scope creep. It does **not** disable
or delete anything — every listed feature stays fully operational for any
existing owner workflow that depends on it.

Any pull request or agent session that proposes work in these areas must be
rejected or escalated for explicit re-authorization by the owner.

---

## Frozen areas

### 1. Marketing Pack video (`routers/marketing_pack.py`, `PromoteThisItem.jsx`)
The 15-second AI-generated video pipeline stays functional for any existing
call site, but **no new features, provider swaps, model upgrades, quality
knobs, format outputs or UI expansions** are authorized. If a bug blocks an
existing flow, fix minimally and stop.

### 2. Workspace expansion (`routers/workspace.py`, `WorkspaceTab.jsx`)
Existing project/collection groupings remain intact. **No new collection
types, no new sharing/permission features, no new bulk operations, no new
list/search dimensions.**

### 3. Quality Score (`quality_score.py`)
Composition-scoring code stays in place because live render paths consume it.
**No new scoring dimensions, no thresholds, no user-facing exposure, no
tuning, no retraining.**

### 4. rembg improvements (`bootstrap.py`, opt-in flag in `PhotoToFlyer.jsx`)
Current opt-in background removal stays as-is. **No new models, no
auto-invocation, no default-on toggle, no UX to make it more prominent.**

### 5. Template Designer expansion (`TemplateDesigner.jsx`, `routers/html_template.py`)
The page and its `bulk-render` endpoint are the only known mechanism that
replenishes the Today's Featured pool (57 assets active as of Feb 2026).
It stays functional. **No new UI, no new bulk-render themes, no new preview
formats, no new persistence.** Do not delete this page during this phase.

### 6. Creative Director top-three recommendations (`routers/creative_director.py`, `CreativeDirectorRecs.jsx`)
The top-3 recommender endpoint stays live and reachable behind "View other
themes". **No new recommendation dimensions, no new signals, no new UI
surfaces, no new banners.** The single "Recommended Style" card remains the
primary discovery surface.

### 7. New themes
**No new themes may be added to `THEME_STYLES`.** No new pack files, no new
pack registry entries. The 22-theme registry is a closed set; the 11-theme
visible picker is the closed subset. See §Phase 2B for the visible/hidden
allocation.

### 8. New output sizes / social presets
**No new keys may be added to `PLATFORM_SIZES`.** The picker exposes exactly
three sizes:
- `facebook_post` (1200×630)
- `instagram_square` (1080×1080)
- `instagram_story` (1080×1920)

Legacy keys (`instagram_post`, `facebook`, `facebook_feed`, `facebook_landscape`,
`tiktok`, `twitter`, `email`) remain in `PLATFORM_SIZES` for backward
compatibility with saved jobs and MUST NOT be deleted or renamed. But no new
entries may be introduced.

### 9. New analytics events
The current analytics footprint is already excessive for a single restaurant.
**No new `trackEvent` types**, no new event properties, no new backend
collections for analytics.

### 10. New billing controls
`BillingCard.jsx` stays as it is. **No new caps, no new reset flows, no new
alerts, no new spend visualisations.** Owner already has Emergent's platform-
level billing UI.

### 11. Lock Variant (`AiDesigner.jsx` — removed Feb 2026)
`AiDesigner.jsx` and its two helpers (`aiDesignerAnalytics.js`,
`aiDesignerBoot.js`) were **deleted** in Feb 2026 after owner sign-off
during the V1.0 follow-up cleanup. The three files were unreachable (no
navigation route imported them) and totaled 2,056 LOC of dead code.
No re-implementation, no port to `PhotoToFlyer.jsx`, no new "pin this
design" UI. The concept remains frozen.

### 12. Save-as-Template (`POST /api/ai-designer/jobs/{id}/save-template`)
Backend endpoint stays intact for the moment. `ai_design_templates`
collection has zero rows. **No new UI to save/list/apply templates**, no
new template-based generation flows.

### 13. Additional HTML renderer themes
The HTML/Chromium renderer supports exactly three themes: `cajun`, `luxury`,
`seafood_coastal`. **No new HTML templates may be added** until the owner has
formally decided (via the Phase 2H side-by-side evaluation) whether Chromium
remains in the stack at all.

---

## Rules for anyone (human or agent) touching this codebase

1. If a proposed change is in a frozen area, stop and ask the owner.
2. If a bug in a frozen area blocks a working feature, fix the minimum
   necessary path and stop — do not "improve" the surrounding code.
3. If usage evidence emerges that justifies unfreezing an area, document
   the evidence here in a "Rationale for unfreeze" section before
   proceeding.
4. This document is authoritative. If it conflicts with a task ticket or
   sprint plan, this document wins until formally amended.

---

_This document is intentionally at the repository root (not `/app/memory/`)
so it is visible to any agent session working on this codebase without
requiring a memory read._
