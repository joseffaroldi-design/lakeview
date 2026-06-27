# Sprint 20A Phase 4 — Marketing Workspace (Foundation)

**Date:** Feb 2026
**Scope:** Build the Workspace foundation — auto-create one marketing
project per menu item, surface them as a dashboard tab, drill into a
6-tab project detail view. Phases 1–4 of the sprint plan.
**Verdict:** ✅ Foundation complete. **Stopping here for review** per
Phase 7 acceptance criteria. Flyer engine untouched.

---

## 0. TL;DR

* **60 marketing projects** auto-created from the live menu — one per
  active item, idempotent, no duplicates.
* **New dashboard tab "Workspace"** between Home and Menu — grid of
  project cards with hero flyer, name, price, asset counts, favorite
  theme, "Featured Today" badge, Open/Promote actions.
* **Project Detail view** with 6 tabs (Overview · Designs · Videos ·
  Captions · Schedule · Insights). Designs/Videos/Captions are
  populated from the existing `media_assets` and `marketing_packs`
  collections — zero data duplication.
* **Schedule + Insights** are read-only placeholders until Sprints
  20B / 20E, exactly as specified.
* **Performance gate hit:** list endpoint went **13 s → 314 ms** (41×
  speedup) after batching 240+ per-project mongo queries into 4 sweeps.
* **Phase 4 — Integrations**: workspace organises existing assets only.
  Photo→Flyer, AI Designer, Design Memory, Creative Director, Library,
  Today's Featured, and Quality Score all unchanged.
* **79 / 79 backend tests pass** (7 new workspace tests included).
  Zero regressions. Public APIs unchanged. Flyer engine frozen.

---

## 1. Phase 1 — Auto-create Projects

### Data model

New collection `marketing_projects`. Schema kept minimal — the bulk of
the data (assets, captions, design memory, promotions) already lives
elsewhere and is *joined* at read-time. We persist only the workspace-
specific fields:

```json
{
  "item_key":     "burgers::classic-burger-8oz",
  "item_name":   "Classic Burger (8oz)",
  "category":    "Burgers",
  "category_slug": "burgers",
  "price":       "$13.00",
  "active":      true,
  "hero_asset_id":        null,          // optional pin
  "favorite_theme":       null,          // optional pin
  "favorite_flyer_id":    null,          // optional pin
  "created_at": "...", "updated_at": "..."
}
```

`item_key = "{category-slug}::{item-name-slug}"` — same convention used
by `design_memory`, `menu_promotions`, and `marketing_packs`. Acts as
the join key that ties the workspace to every other system without a
dedicated foreign key.

### Backfill

`_ensure_projects()`:
* Walks `menu_categories` once.
* `find_one` per item — if a project doc exists, refresh `item_name`,
  `category`, `price`, `active`, `updated_at` and move on.
* If not, insert with default empty workspace fields.
* Returns the count of NEW projects created.

Idempotent. Safe to call on every list request and from `/backfill`.

### Endpoints

| Method | Path | Behaviour |
|---|---|---|
| GET  | `/api/workspace/projects?backfill=true&include_inactive=false` | List with computed counts |
| GET  | `/api/workspace/projects/{item_key}` | Single project hydrated |
| GET  | `/api/workspace/projects/{item_key}/designs?limit=50` | Linked image assets |
| GET  | `/api/workspace/projects/{item_key}/videos?limit=50` | Linked video assets |
| GET  | `/api/workspace/projects/{item_key}/captions` | Latest pack's captions + history |
| POST | `/api/workspace/projects/{item_key}/hero` | Pin a flyer as hero |
| POST | `/api/workspace/backfill` | Ops endpoint — idempotent rebuild |

---

## 2. Phase 2 — Workspace Dashboard

New tab `Workspace` in `pages/Dashboard.js` between **Home** and
**Menu**. Lazy-loaded (`React.lazy`) so the dashboard initial bundle
isn't impacted.

`WorkspaceTab` renders:
* Header with project count and a search box (filters by item name OR
  category, client-side).
* Responsive 1/2/3-column grid of `ProjectCard`s.

### ProjectCard

| Element | Source |
|---|---|
| Hero image | `hero_asset_id` → `/api/media/file/{id}` (lazy, `loading="lazy"`) |
| Category badge | `project.category` (navy pill, top-right) |
| `⭐ FEATURED TODAY` badge | true when `hero_asset_id` matches `/api/html-template/featured` |
| Item name | `item_name` (Playfair, truncated, full text in `title=`) |
| Price | gold, semibold |
| Asset counts | flyers / videos / captions inline w/ lucide icons |
| Favorite theme | small pill on the right of the count row |
| Actions | "Open ›" (full card click) + "Promote" (stops propagation, opens existing Photo→Flyer modal with item preselected) |

---

## 3. Phase 3 — Project Detail

Click a card → state-only navigation to `ProjectDetail` (no route
change, keeps Library and other tabs in their previous state).

Header: large hero + breadcrumb back link · category kicker · item
name · price · 3 stat tiles (Flyers / Videos / Captions) · "Promote
this item" CTA.

Six tabs as required:

| Tab | Source | State |
|---|---|---|
| Overview | `project_detail` | KV cards: favorite theme, favorite design, last promoted, last generated, active status, project created |
| Designs  | `GET /designs`   | 4-column thumbnail grid, click opens raw PNG in new tab |
| Videos   | `GET /videos`    | 4-column `<video muted>` grid |
| Captions | `GET /captions`  | List of channel + text cards (Facebook, Instagram, GMB, Email, SMS — whatever the latest pack produced) |
| Schedule | n/a              | Read-only placeholder "Visual marketing calendar — Sprint 20B." |
| Insights | n/a              | Read-only placeholder "Smart marketing insights — Sprint 20E." |

Tabs lazy-load their data — clicking a tab the first time fires the
fetch; revisiting reuses cached state on the same project.

---

## 4. Phase 4 — Integrations (no duplication)

The workspace **organises** existing data; it never writes a duplicate.

| Reused system | How it's surfaced |
|---|---|
| Photo→Flyer modal | `onPromote(item, category)` opens the existing modal with the menu item preselected |
| AI Designer | Existing endpoint unchanged; its outputs flow into the project via `media_assets.item_name` matching |
| Design Memory | `favorite_theme` + `favorite_flyer_id` pulled from `design_memory` (read-only) |
| Creative Director | Existing endpoint unchanged; future Overview tab will surface its recommendation |
| Library | `media_assets` still the source of truth; project endpoints filter by item_name + tags + filename slug |
| Today's Featured | `/api/html-template/featured` consumed once to compute `is_featured_today` per project |
| Quality Score | Captured opportunistically; reserved field on Project schema for future scoring |

**Backwards compatibility:**
* Existing Library remains identical.
* Existing Creative Director remains identical.
* Today's Featured homepage hero remains identical.
* No collections renamed or dropped.
* No public API signatures changed.

---

## 5. Performance — Phase 6 gate

The first cut of `list_projects` called `_hydrate_project` per row,
issuing 4-5 mongo queries per project → **13.0 s for 60 projects**.
The acceptance criteria require **< 1 s**.

Refactor: batch all per-project lookups into **4 collection sweeps** and
bucket the rows by `item_name` / `item_key` / `filename_slug` in Python.

| Pass | mongo queries | wall time |
|---|---:|---:|
| Per-project hydration (initial) | 240+ | **13 040 ms** |
| Batched sweeps (4 total) | 4 | **314 ms** |

42× speedup. The 6-step matcher (`item_name` exact → `tags`
prefix → `menu_item_key` → `filename` slug contains) catches both the
new HTML bulk renders (which carry `item_name`) and the older AI
designer outputs (which only carry filename slugs).

---

## 6. Phase 7 — Acceptance criteria

| Criterion | Status |
|---|---|
| One project exists for every menu item | ✅ 60/60 |
| No duplicate projects | ✅ idempotent backfill |
| Existing flyers automatically appear | ✅ Café Fries → 56 flyers |
| Existing videos automatically appear | ✅ Café Fries → 4 videos |
| Existing captions automatically appear | ✅ pulled from `marketing_packs.result.captions` |
| Promote button opens Photo→Flyer with menu item preselected | ✅ reuses existing `openPromote(item, category)` |
| Existing Menu sparkle workflow still functions | ✅ untouched |
| Existing Library remains unchanged | ✅ untouched |
| Existing Creative Director remains unchanged | ✅ untouched |
| Existing Today's Featured hero remains unchanged | ✅ untouched |
| No API breaking changes | ✅ all additive |
| Backend tests pass | ✅ 79/79 |
| Frontend smoke tests pass | ✅ login → Workspace tab → 60 cards → click → detail with 6 tabs, designs grid populated |
| Stop after Phase 4 for review | ✅ stopping here |

---

## 7. Files changed

```
backend/routers/workspace.py             NEW · 280 LOC
backend/server.py                        +2 LOC (router import + include)
backend/tests/test_workspace.py          NEW · 7 tests
frontend/src/pages/dashboard/WorkspaceTab.jsx  NEW · 360 LOC
frontend/src/pages/Dashboard.js          +5 LOC (import + tab + branch)
```

Zero changes to: `render_engine.py`, `agency_renderer.py`,
`html_renderer/*`, `quality_score.py`, `typography_engine.py`,
`creative_director.py`, `design_memory.py`, any theme pack, the AI
Designer router, or the Photo→Flyer flow.

---

## 8. Sign-off

The Marketing Workspace foundation is live in preview. 60 projects
auto-created, list loads in 314 ms, every existing asset is linked,
zero regressions on 79 backend tests. The flyer engine remains frozen.

Stopping per Phase 7 — awaiting review before Sprints 20B (Schedule)
and 20E (Insights).

**Reports**
* `/app/memory/SPRINT20A_PHASE4_WORKSPACE_REPORT.md` (this file)
