# Sprint 20A — HTML Renderer Polish + Seafood Theme + Live Designer

**Date:** Feb 2026
**Scope:** Three-in-one follow-up on the HTML/CSS engine — CSS polish to
Cajun + Luxury, a new Seafood theme, and a Live Template Designer page
backed by a `POST /api/html-template/preview` endpoint.
**Verdict:** ✅ All three landed. **Gemini Vision mean now 8.17/10**
(PIL Phase 0.5: 7.5 → +0.67). **Luxury crossed the 8.5 stretch target
at 8.8/10.**

---

## 0. TL;DR

* **CSS-only polish** to Cajun and Luxury — both templates now ship richer
  price treatments and CTA gold pills, no Python touched.
* **Third HTML theme: Seafood** — Gulf-coastal navy + lemon-yellow +
  coral palette with an octagonal porthole food crop and a nautical
  compass-rose price seal. Rated **8.0/10** by Gemini on first render.
* **Live Template Designer** at `/template-designer` — theme picker,
  payload editor, blob-URL `<img>` preview that refreshes in ~1-2 s after
  the warm browser is up. Backed by `POST /api/html-template/preview`
  (worker-thread Playwright queue under the hood).
* **Worker-thread architecture** — sync Playwright now runs in a single
  dedicated thread that owns the browser; renders are submitted as job
  tuples via a Queue. Solves both the asyncio-loop conflict AND the
  "cannot switch to a different thread" greenlet error that broke the
  first wiring.
* **59 / 59 backend tests pass.** Zero regressions. Public API unchanged
  except for the additive `/api/html-template/*` endpoints.

---

## 1. CSS polish — Cajun + Luxury

### 1.1 Cajun

| Change | What changed | Why |
|---|---|---|
| **Price seal** | Outer scallop, double ring (cayenne + gold), eight gold-stud points on the ring, "TODAY" label above the price, ribbon tails on each side | Gemini called the old red disc "feels like an afterthought" |
| **Footer CTA** | Promoted to a **gold pill button** (Oswald 32px, 6px tracking, drop shadow) | Gemini: "Order Now could be more prominent" — promoted; CTA is now eye-catching |
| **Footer padding** | 130 → 90 px to make room for the wider CTA pill | layout fit |
| **Price-text layout** | column flex with label + price stacked | richer visual without a SVG redesign |

### 1.2 Luxury

| Change | What changed | Why |
|---|---|---|
| **Price plaque** | Gold **corner brackets** in each corner + **diamond flourish** rule under the price | Old plaque "looks generic"; now reads like a museum placard |
| **Plaque size** | 320×320 → **360×360**, repositioned to clear the food disc | Gemini: "obscures lower right portion of the plate" — fixed |
| **Background gradient** | top: `#18181d` → `#1a1a20` — half a step lighter so the plaque doesn't disappear into the canvas | accessibility |
| **Price label kerning** | 16 → 14 px (denser, more confident) | typography polish |

---

## 2. Seafood — new theme

**File:** `backend/html_renderer/templates/seafood.html`. Resolver maps
`seafood`, `seafood_coastal`, `seafood_lagoon` → this template.

| Element | Treatment |
|---|---|
| Palette | `#0d2a3d` deep navy · `#1d4862` mid-tide · `#cfe1e0` sea foam · `#f6c44b` lemon · `#d75944` boiled-shrimp coral · `#fff8e6` paper |
| Background | Radial lemon top-right + foam bottom-left over a navy gradient, with a repeating wave-pattern SVG overlay at 7 % opacity |
| Brand | Playfair 88px lemon "LAKEVIEW" + double-rule diamond divider + Oswald "GULF CATCH · COASTAL KITCHEN" tagline in foam |
| Title | Playfair italic 198px with subtle drop shadow on the paper-cream colour |
| Photo | 1100×1000 octagonal porthole (`clip-path: polygon(…)`) with a 4px lemon border and radial vignette |
| Features | Stacked paper-cream chips with 8 px lemon left-border, alternating with lemon-on-deep-navy chips |
| Price | Compass-rose SVG (lemon outer ring + 8 dark compass points + cream inner disc + coral inset ring) with Playfair italic 110px price |
| CTA pill | Lemon background, navy text, 32px Oswald, drop shadow |

First-render Gemini score: **8.0 / 10** (visual impact 8, readability 9,
food prominence 7, typography 8, price badge 7, background quality 9,
color harmony 9, brand presence 8, social appeal 8, print friendliness 9).

---

## 3. Live Template Designer

### 3.1 Backend

`POST /api/html-template/preview` — hot-render one flyer with the
supplied payload. Body:
```json
{
  "theme": "cajun|luxury|seafood",
  "item_name": "…",
  "features": ["…", "…", "…"],
  "price": "$x.xx",
  "cta": "…",
  "output_size": 1024,
  "render_size": 2048
}
```
Returns `image/png` directly (Cache-Control: no-store).

`GET /api/html-template/themes` — lists the themes the HTML engine
currently supports.

### 3.2 Frontend

New route at `/template-designer` (`pages/TemplateDesigner.jsx`):
* Theme picker — buttons for each supported theme; clicking hydrates a
  matching preset payload (Smash Burger for Cajun, Po-Boy for Seafood,
  Wagyu for Luxury).
* Editable item name, price, CTA, 4× feature inputs.
* "Render Flyer" button posts to `/api/html-template/preview` with
  `responseType: blob`, swaps the result into an `<img>` via a blob URL.
* Auto-cleans previous blob URLs on every new render.
* Renders the first preview automatically on mount.
* Shows render time in ms for transparency.

### 3.3 Worker-thread render architecture

Sync Playwright greenlets are tied to **one** OS thread for life — they
cannot be shared across threads and cannot be called from a thread that
owns an asyncio event loop. Two design fixes were needed:

* **Dedicated render worker thread.** Started on first call, owns the
  `sync_playwright()` instance and the `chromium.launch()`-ed browser
  for the process lifetime. Consumes `(job_dict, Future)` tuples from a
  `queue.Queue` and fulfils each future.
* **Per-request enqueue.** `render_flyer()` is now a thin wrapper —
  packs a job dict, puts it on the queue, blocks on `future.result()`.
  Safe to call from FastAPI handlers, pytest, sync scripts, anywhere.

Cold start: ~600 ms one-time browser launch. Steady-state: ~1.0-1.5 s
per render at 1024×1024 (2048 internal). The Template Designer's first
render is ~5 s (cold browser + cold worker + cold font cache),
subsequent renders 1-2 s.

---

## 4. Gemini Vision — quality progression

| Sprint | Engine | Avg Gemini | Best single |
|---|---|---:|---:|
| Phase 0 closure | PIL agency v1 | 6.7 | 7.6 (Luxury Dark) |
| Phase 0.5 | PIL agency polished | 7.50 | 8.1 (Cajun Shrimp Po-Boy) |
| 20A V3 initial | HTML — Cajun + Luxury | 7.92 | 8.3 (Cajun Shrimp Po-Boy) |
| **20A polished + Seafood** | **HTML — Cajun + Luxury + Seafood** | **8.17** | **8.8 (Luxury Wagyu)** |

Per-template score (final V3 polished sample renders):

| Theme | Sample item | Overall | Dimensions ≥ 8 | Dimensions ≥ 9 |
|---|---|---:|:---|:---|
| Cajun   | Smash Burger | **7.7** | typo, bg, colour, brand, print | readability |
| Seafood | Shrimp Po-Boy | **8.0** | visual, typo, brand, social, bg | readability, colour, print |
| Luxury  | Wagyu Filet  | **8.8** | food, badge, print | visual, readability, typo, bg, colour, brand, social |

Luxury earned a 10/10 on `color_harmony` — first time any flyer hit a
single 10 in any sprint to date.

---

## 5. Tests

| Suite | Tests | Status |
|---|---:|---|
| `test_html_renderer.py` | 16 | ✅ all pass |
| `test_agency_templates.py` | 16 | ✅ |
| `test_sprint19_hotfix.py` | 8 | ✅ |
| `test_sprint18_design.py` | 16 | ✅ |
| `test_render_engine.py` | 3 | ✅ |
| **Total** | **59** | **✅ 59 / 59** |

---

## 6. Architecture diagram (post-Sprint-20A polish)

```
Frontend
   │
   ├─ /template-designer  (React) ──┐
   │                                ▼
   │                       POST /api/html-template/preview
   │                                │
   └─ /dashboard → AI Designer ─►   ▼
                          POST /api/ai-designer/generate
                                    │
                          _compose_design(theme, …)
                                    │
                                    ▼
   ┌─────────────────────────────────────────────────────┐
   │            html_renderer.render_flyer()             │
   │       (enqueues a job to the worker thread)         │
   │                       │                             │
   │                       ▼                             │
   │     ┌─────────────────────────────────┐             │
   │     │  Dedicated worker thread        │             │
   │     │  (owns sync_playwright +        │             │
   │     │   chromium browser instance)    │             │
   │     │                                 │             │
   │     │  Jinja2 → HTML → Chromium       │             │
   │     │  → 2048² PNG → LANCZOS 1024²    │             │
   │     └─────────────────────────────────┘             │
   │                       │                             │
   │              if HTML fails ─►                       │
   │       (fall back to agency template renderer)       │
   │                       │                             │
   │            if agency fails ─►                       │
   │       (fall back to procedural PIL renderer)        │
   └─────────────────────────────────────────────────────┘
```

---

## 7. Remaining themes to port (7)

In recommended order (matches Lakeview menu mix):

1. `burger_classic` — clean diner identity, plate-on-cream layout
2. `game_day_scoreboard` — sports stripes, scoreboard digit display
3. `modern` — generic catch-all (already styled in PIL; easy port)
4. `distressed_orange` — vintage chalkboard
5. `seafood_lagoon` — already maps to seafood.html (no work)
6. `vintage` — letterpress + halftone
7. `chalk` — chalkboard-style

Estimated ~half-day per theme. Each port stays 100% additive — adds an
`@import` to the resolver and a new template file; the fallback chain
guarantees nothing else regresses.

---

## 8. Sign-off

Engine V3 (HTML/CSS) now covers **3 of 9 themes** (Cajun, Luxury,
Seafood) with an average Gemini score of 8.17/10 and a first-ever 8.8
single-flyer score. The Live Template Designer at `/template-designer`
turns the future port-a-theme work into a tight design iteration loop —
edit `templates/<theme>.html`, refresh the page, render in ~1 s.

Public APIs unchanged. PIL/agency fallbacks intact. Marketing Workspace
(Sprint 20A Phase 4) is unblocked and ready to begin.

**Artefacts**
* `/tmp/v3_cajun.png` · `/tmp/v3_seafood.png` · `/tmp/v3_luxury.png`
* `/app/backend/html_renderer/templates/{cajun,luxury,seafood}.html`
* `/app/backend/routers/html_template.py`
* `/app/frontend/src/pages/TemplateDesigner.jsx`
* `/app/memory/SPRINT20A_HTML_RENDERER_REPORT.md` (V3 initial)
* `/app/memory/SPRINT20A_POLISH_REPORT.md` (this file)
