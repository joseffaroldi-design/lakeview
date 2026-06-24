# Sprint 16D — Photo-to-Flyer Fusion Workflow

## Goal
Restaurant owner uploads a real food photo → receives flyer + caption +
15-second video in < 60s, **with zero manual data entry**. The existing
`AiImageGenerator.jsx` page is **replaced** by this new entry point;
all heavy lifting reuses the AI Designer + Marketing Pack systems.

---

## Data-flow diagram

```
                ┌─────────────────────────────────────────────────┐
                │   FRONTEND  (replaces AiImageGenerator.jsx)     │
                │   /dashboard → AI Ads → "Photo → Flyer"          │
                └─────────────────────────────────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
   ┌────▼─────┐                ┌───────▼──────┐                ┌──────▼──────┐
   │ 1.UPLOAD │                │ 2.AUTOFILL   │                │ 3.GENERATE  │
   │  step    │                │  step        │                │  step       │
   └────┬─────┘                └───────┬──────┘                └──────┬──────┘
        │                              │                              │
   POST /api/photo-flyer/analyze       │                  ┌───────────┴──────────┐
        │                              │                  │                      │
        ▼                              │             POST /api/ai-designer  POST /api/marketing-
   ┌──────────────────────────────┐    │             /generate              pack/generate
   │  /api/photo-flyer/analyze    │    │             (auto_copy=True)            │
   │  (new orchestrator)          │    │                  │                      │
   │                              │    │                  │                      │
   │  a. accept upload            │    │                  │                      │
   │  b. PIL enhance              │    │                  │                      │
   │  c. Gemini Flash vision      │    │                  │                      │
   │  d. fuzzy-match /api/menu    │    │                  │                      │
   │  e. return analysis JSON     │    │                  │                      │
   └──────────────┬───────────────┘    │                  │                      │
                  │                    │                  │                      │
                  ▼                    │                  ▼                      ▼
       ┌─────────────────────┐         │       ┌──────────────────┐  ┌──────────────────┐
       │ Returns to UI:      │         │       │ Existing AI      │  │ Existing video   │
       │  - original_id      │─────────┘       │ Designer pipeline│  │ pipeline         │
       │  - enhanced_id      │                 │ (PIL + LLM copy) │  │ (PIL + ffmpeg)   │
       │  - food_type        │                 └──────────────────┘  └──────────────────┘
       │  - confidence       │                          │                      │
       │  - features[]       │                          │                      │
       │  - suggested_theme  │                          ▼                      ▼
       │  - menu_match       │              ┌──────────────────────────────────────┐
       │  - menu_price       │              │ 4.REVIEW SCREEN                      │
       │  - dominant_colors  │              │  - original photo                    │
       │  - vision_ok        │              │  - enhanced photo                    │
       │  (degrades to       │              │  - generated flyer (+ regenerate)    │
       │   manual on LLM     │              │  - generated 15-s video              │
       │   failure)          │              │  - captions (fb_post + ig_post)      │
       └─────────────────────┘              │  Actions:                            │
                                            │  - Download Flyer                    │
                                            │  - Download Video                    │
                                            │  - Copy Caption                      │
                                            │  - Regenerate / Different Theme      │
                                            └──────────────────────────────────────┘
```

---

## Existing components reused

| What we reuse | Where | New code needed? |
|---|---|---|
| `POST /api/media/upload` | `routers/media.py` | No — called as-is |
| `POST /api/ai-designer/generate` (with `auto_copy=True`) | `routers/ai_designer.py` | No — called as-is |
| `GET /api/ai-designer/job/{id}` | `routers/ai_designer.py` | No — called as-is |
| `POST /api/marketing-pack/generate` | `routers/marketing_pack.py` | No — called as-is |
| `GET /api/marketing-pack/job/{id}` | `routers/marketing_pack.py` | No — called as-is |
| `GET /api/media/file/{id}` + `/thumb/{id}` | `routers/media.py` | No — called as-is |
| 5 flyer themes + ingredient icons + typography | `routers/ai_designer.py` (Sprint 16A.1/16A.2) | No — already in production |
| Copy pack generator (`_write_designer_copy`) | `routers/ai_designer.py` | No — invoked by `auto_copy` flag |
| Video pipeline (15-s slideshow) | `routers/marketing_pack.py` (Sprint 16B.4 video-only) | No — invoked as-is |
| Emergent object storage | `storage.py` | No |
| `verify_session` auth | `auth.py` | No |

**New components**:

| What's new | Where | Why |
|---|---|---|
| Vision client wrapper | `services/vision_client.py` | Gemini 3 Flash multimodal call via `emergentintegrations` |
| PIL enhancement helper | `services/photo_enhance.py` | Deterministic auto-levels + sharpen + white-balance + denoise |
| Menu fuzzy matcher | `services/menu_matcher.py` | Substring + token overlap against live `/api/menu` |
| Orchestrator router | `routers/photo_flyer.py` | One endpoint `POST /api/photo-flyer/analyze` |
| Frontend page | `pages/dashboard/aiads/PhotoToFlyer.jsx` | Replaces `AiImageGenerator.jsx` |

---

## Implementation plan (4 testable steps)

### Step 1 — Vision + Enhancement primitives (backend only, no UI)
Build the three new services in isolation, unit-test each. **Output**: passing
unit tests, no FastAPI routes added yet.

- `services/photo_enhance.py::enhance_photo(bytes) -> bytes` — PIL pipeline
- `services/vision_client.py::analyze_food_photo(bytes) -> dict` — Gemini Flash
  multimodal call returning `{food_type, confidence, features[], suggested_theme,
  dominant_colors[], vision_ok}`. Graceful degradation: on any LLM error,
  returns `{vision_ok: False, error: "..."}` and lets the caller continue
  with manual entry.
- `services/menu_matcher.py::match_food_to_menu(food_type, db) -> dict` —
  fuzzy match against `menu_items` collection; returns `{matched: bool,
  item_key, name, price, confidence}` (uses Python `difflib.get_close_matches`,
  no LLM).

**Test gate**: pytest on the three modules with hand-crafted inputs.

### Step 2 — Orchestrator endpoint
Single new route `POST /api/photo-flyer/analyze` that:
1. Accepts multipart upload (image file).
2. Uploads via existing media flow → original_asset.
3. PIL-enhances → enhanced bytes → uploads → enhanced_asset.
4. Calls vision on enhanced bytes (server-side; never trusts client).
5. Calls menu matcher.
6. Returns aggregated JSON.

**Test gate**: curl real food photo, get `{original_id, enhanced_id, food_type,
features, suggested_theme, menu_match, vision_ok}` back in < 8s.

### Step 3 — Frontend page (replace `AiImageGenerator.jsx`)
New file `PhotoToFlyer.jsx` with the 4-step UX:
1. **Upload** — drag/drop or file picker.
2. **Analysis review** — show side-by-side (original + enhanced), AI-detected
   fields editable, theme picker pre-selected to vision suggestion.
3. **Generating** — single progress bar fed by polling both designer + pack
   jobs (the slower of the two wins).
4. **Review** — flyer + video + captions + download / copy / regenerate.

Route the existing `AiImageGenerator` route to this new component (one-line
import swap in the parent tab).

**Test gate**: manual smoke + screenshot of each of the 4 steps in preview.

### Step 4 — End-to-end + budget-degradation tests
- Live happy-path: upload → flyer + video + caption in < 60s (preview).
- LLM-budget-exhausted path: simulate `vision_ok=False`; the UI must let the
  user manually enter name/features and still produce a flyer + video.
- Regenerate-theme path: switch theme, only re-runs the designer (cheap).

**Test gate**: 1 happy-path + 1 degradation test passes via testing agent.

---

## API contracts

### `POST /api/photo-flyer/analyze`
Request:
```
Content-Type: multipart/form-data
  file: <image>  (jpg/png/webp, ≤10 MB)
```
Response (200):
```json
{
  "original_asset_id": "uuid",
  "enhanced_asset_id": "uuid",
  "vision_ok": true,
  "food_type": "Shrimp Taco",
  "confidence": 0.96,
  "features": ["Shrimp", "Lettuce", "Cheese", "Pico de Gallo", "Sour Cream"],
  "suggested_theme": "bold_purple_pop",
  "dominant_colors": ["#c44a3e", "#f6d56b", "#3b6c41"],
  "menu_match": {
    "matched": true,
    "item_key": "tacos::shrimp-taco",
    "name": "Shrimp Taco",
    "price": "$9.95",
    "confidence": 0.82
  }
}
```
Response on graceful degradation (200, still useful):
```json
{
  "original_asset_id": "uuid",
  "enhanced_asset_id": "uuid",
  "vision_ok": false,
  "vision_error": "LLM budget exceeded",
  "food_type": null,
  "features": [],
  "suggested_theme": "comic_pop",
  "menu_match": {"matched": false}
}
```

### Generation phase (no new endpoints — calls existing systems)
After review, frontend POSTs to:
- `POST /api/ai-designer/generate` with `source_asset_id = enhanced_asset_id`,
  `auto_copy=True`, theme + features + price/name from the review form
- `POST /api/marketing-pack/generate` with same `source_asset_id` and headline

Polling: existing `GET /api/{ai-designer,marketing-pack}/job/{id}`.

---

**Estimated LOC**: +400 backend (3 services + 1 router) +500 frontend (1 page);
ZERO LOC deleted from existing AI Designer / Marketing Pack code (per spec).

**Estimated LLM cost per end-to-end run**: $0.005 vision + $0.05 copy_pack = **$0.055**.
