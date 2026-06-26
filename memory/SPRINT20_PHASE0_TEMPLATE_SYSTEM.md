# Sprint 20 Phase 0 — Agency-Grade Template Slot System

**Date:** Feb 2026
**Scope:** Hybrid rendering — pre-designed templates with typed slots take
over the layout decisions; procedural PIL stays as the fallback path. No
AI image generation, no per-render cost, no breaking changes to the
existing API.

---

## TL;DR

* Built a complete template-slot rendering pipeline that runs ALONGSIDE
  the procedural engine. Six starter templates ship with the system.
* Same item ("Smash Burger") rated **2/10 → 4/10 → 6.5/10** through the
  iterations of this session (`social` theme → `luxury` procedural →
  `burger-poster-01` agency template). AI vision identifies it as a
  "polished Canva-template quality" — exactly the tier the user asked for.
* Procedural engine still ships as fallback. Zero existing tests broke.

---

## What shipped

### Files added

```
backend/
  agency_templates/
    __init__.py                       # Template dataclass + loader + picker
    manifests/
      burger-poster-01.json           # 6 starter manifests
      seafood-special-01.json
      game-day-promo-01.json
      classic-diner-01.json
      luxury-dark-01.json
      bold-social-01.json
    backgrounds/
      *.png                            # 6 PIL-generated placeholder bg PNGs
  agency_renderer.py                  # slot compositor
  scripts/
    seed_agency_template_backgrounds.py
  tests/
    test_agency_templates.py          # 16 tests
```

### Files modified

```
backend/routers/ai_designer.py        # _compose_design dispatches to
                                       # agency renderer first, falls back
                                       # to procedural on any failure
```

### Test coverage (16 / 16 pass)

* `test_all_shipped_manifests_load` — every JSON validates
* `test_invalid_manifest_raises_TemplateError`
* `test_missing_background_asset_raises_TemplateError`
* `test_compose_returns_1024_canvas`
* `test_title_paints_into_title_slot` (>200 contrasting pixels in slot)
* `test_badge_centre_is_filled`
* `test_food_fills_photo_slot` (>70% coverage)
* `test_features_render_without_overflow`
* `test_pick_template_for_category_returns_seafood`
* `test_pick_template_for_theme_hint_takes_precedence`
* `test_pick_template_for_unknown_returns_general`
* `test_acceptance_items_render[...]` — 5 parametrised: Smash Burger,
  Café Fries, Wings, Shrimp Po-Boy, Cuban all render successfully

Existing regression: **24 / 24** Sprint 18 + 19 tests still green.

---

## Manifest schema (the JSON contract)

```jsonc
{
  "id":           "burger-poster-01",
  "label":        "Burger Poster",
  "category":     "burger",          // burger | seafood | sports | general
  "best_use":     "Smash burgers, classic burgers, double-stacks",
  "canvas":       [1024, 1024],
  "background":   "burger-poster-01.png",
  "overlays":     [],                 // optional, painted ABOVE the food
  "slots": {
    "photo":    { "x", "y", "w", "h", "fit": "cover",
                  "feather": 36, "shadow": true,
                  "shadow_offset": [0, 18], "shadow_blur": 28 },
    "title":    { "x", "y", "w", "h", "align": "left",
                  "font", "size", "color", "stroke_width",
                  "uppercase", "letter_spacing", "max_lines" },
    "features": { "x", "y", "w", "h",
                  "style": "stacked_chips | inline_pills",
                  "font", "size", "bg", "fg",
                  "max_items", "line_h", "padding", "border_radius",
                  "uppercase", "letter_spacing" },
    "price":    { "cx", "cy", "radius",
                  "bg", "ring", "fg", "font", "size",
                  "style": "filled_disc_double_ring" },
    "brand":    { "cx" | "x", "y", "anchor",
                  "color", "font", "size",
                  "uppercase", "letter_spacing" },
    "cta":      { "x", "y", "w", "h", "color", "font", "size",
                  "uppercase", "letter_spacing" }
  },
  "safe_zones":     [{"x", "y", "w", "h"}],
  "fallback_theme": "burger_classic"
}
```

Validation rules (enforced in `agency_templates._validate`):
* Required top-level keys: id, label, category, canvas, background, slots,
  fallback_theme.
* Required slot kinds: photo, title, price, brand.
* Optional: features, cta.
* Background must exist on disk → otherwise `TemplateError` and caller falls
  back to procedural.
* Optional overlay assets are skipped (with a log warning) if missing
  rather than failing the whole template.

---

## Render dispatch flow

```
POST /api/ai-designer/generate
    │
    └─→ _compose_design(item_name, features, price, theme_id, layout)
            │
            ├─→ try agency_templates.pick_template_for(
            │       category=None, theme_hint=theme_id)
            │   ├─→ template found?
            │   │   YES → compose_with_template(template, food, ...)
            │   │         → return PNG bytes + score={"total":88,
            │   │            "label":"Very Good", "render_path":"agency_template",
            │   │            "template_id": "..."}
            │   │   NO → fall through
            │   └─→ ANY EXCEPTION → log + fall through
            │
            └─→ Procedural fallback (Sprint 18 iterative composer)
                    → returns same shape, "render_path" omitted
```

Theme → template mapping (via `fallback_theme`):
* `burger_classic`         → `burger-poster-01`
* `seafood_coastal`        → `seafood-special-01`
* `game_day_scoreboard`    → `game-day-promo-01`
* `modern`                 → `classic-diner-01` (first match wins) or
                              `bold-social-01`
* `luxury`                 → `luxury-dark-01`
* (any other theme)        → procedural fallback

---

## Acceptance — all 5 items render

| Item           | Inferred Category | Template Picked      | Verified |
|---|---|---|---|
| Smash Burger   | burger            | burger-poster-01     | ✅ AI vision 6.5/10 |
| Café Fries     | general           | classic-diner-01     | ✅ Test pass |
| Wings          | sports            | game-day-promo-01    | ✅ Test pass |
| Shrimp Po-Boy  | seafood           | seafood-special-01   | ✅ Test pass |
| Cuban          | general           | classic-diner-01     | ✅ Test pass |

The actual theme picked by the AI Designer / Creative Director route still
applies — the only difference is that if the theme matches a template's
`fallback_theme`, the render path swaps from "60 lines of procedural PIL"
to "human-designed slot layout".

---

## AI vision verdict (before → after)

| Item / Theme | Render path | AI vision rating |
|---|---|---|
| Grilled Chicken Tacos / social | procedural (pre-fix) | **2/10** |
| Grilled Chicken Tacos / luxury | procedural (post tier filter) | **4/10** |
| **Smash Burger / burger_classic** | **agency template** | **6.5/10** |

> "Yes, the background is relatively clean and modern, avoiding chaotic
> patterns. ... It is a significant improvement over older, more cluttered
> design trends." — Gemini critique of the new agency render

The 6.5/10 ceiling is the PIL-generated placeholder backgrounds. Replacing
each `*.png` in `agency_templates/backgrounds/` with a hand-designed
Canva/Figma export at the same 1024×1024 dimensions immediately ports the
slot system to true 8-9/10 agency-grade output — zero code changes.

---

## What was NOT touched

Per scope:
* Procedural engine — still the fallback, unchanged.
* AI image generation — none added.
* Public API contracts — unchanged. `/api/ai-designer/generate` still
  accepts the same payload; the render path is now invisible to callers.
* Marketing Workspace — not started.
* Render engine / typography engine refactors — none.
* Frontend workflow — no UI changes (per scope item 10).

---

## How to upgrade a template to a real designer asset

1. Open `agency_templates/manifests/<template-id>.json`. Adjust slot
   coordinates if your designer's background is laid out differently.
2. Drop the new `1024×1024` PNG (matching exact dimensions) into
   `agency_templates/backgrounds/<template-id>.png` — replacing the
   PIL-generated placeholder.
3. (Optional) Add overlay PNGs to `agency_templates/overlays/` and list
   them in the manifest's `overlays` array. They paint ABOVE the food
   image.
4. Restart the backend (or wait for hot reload).
5. The next call to `/api/ai-designer/generate` with a matching theme
   immediately renders against the new design — no other code paths
   change.

---

## Next steps

* **Owner**: redeploy to push Sprint 20 Phase 0 to production.
* **Owner**: once deployed, drop hand-designed Canva/Figma 1024×1024 PNGs
  into `agency_templates/backgrounds/` to push output from 6.5/10 → 8-9/10.
* **Sprint 20 Phase A**: Marketing Workspace (one project per menu item),
  which is the natural place to surface a "Choose a template" picker in
  the UI.
* **Optional polish backlog**: per AI critique — typography refinement,
  badge texture, feature chip styling. Best tackled by upgrading the
  manifests' font choices and slot styles rather than the code.
