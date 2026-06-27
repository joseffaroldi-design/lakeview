# Sprint 19 Hotfix — Production Deployment Checklist

**Owner:** Lakeview Burgers & Seafood
**Target:** lakeview-grill.emergent.host (production)
**Source of truth:** Preview at `food-graphics-lab.preview.emergentagent.com`
**Approved on:** Feb 2026, after 25 / 25 menu items validated clean.

> ⚠️ DO NOT DEPLOY UNLESS THE SPRINT 19 VALIDATION REPORT IS SIGNED OFF.

---

## Phase 0 — Prerequisites (before deploy)

* [ ] Confirm `SPRINT19_HOTFIX_VALIDATION_REPORT.md` shows
      "Sprint 19 is approved for production deployment" at the bottom.
* [ ] Run `pytest tests/test_sprint19_hotfix.py tests/test_sprint18_design.py`
      from `/app/backend` — must return **24 / 24 PASS**.
* [ ] Re-run `python scripts/menu_validation.py --limit 25` —
      must return **`ran 25 OK, 0 failed`**.
* [ ] Re-run `python scripts/sprint19_visual_audit.py` —
      must return **15 / 15 pass**.
* [ ] Confirm Emergent Support has resolved the known production environment
      variable propagation issue (the previously logged 502/520 under load).
      DO NOT push if this is still open — the rollout will return 502s on
      every render request.

---

## Phase 1 — Files in the deployable diff (review)

Files modified by Sprint 19 + hotfix + this validation pass:

| File | Sprint 19 base | + Polish (this pass) |
|---|---|---|
| `backend/render_engine.py` | scale_up_to_target, badge disc, overlay 0.45 | text-band shrink, overlay 0.35, badge palette + canvas-sample safety net |
| `backend/theme_packs/seafood_pack.py` | — | body+branding cream, price.bg red |
| `backend/tests/test_sprint19_hotfix.py` | new | — |
| `backend/scripts/menu_validation.py` | new | — |
| `backend/scripts/sprint19_visual_audit.py` | — | new |
| `backend/scripts/sprint19_before_after.py` | — | new |

Diff scope is minimal: 1 render engine, 1 theme pack, 3 scripts, 1 test. No
new routes, no new collections, no env var changes.

---

## Phase 2 — Pre-deploy smoke (preview, last sanity)

Run these against `https://upload-stage-two.preview.emergentagent.com`
within 30 min of pushing to prod. All must return 200 + valid bodies:

```bash
API=https://upload-stage-two.preview.emergentagent.com
TOKEN=$(curl -s -X POST $API/api/auth/login \
   -H "Content-Type: application/json" \
   -H "X-Forwarded-For: 198.51.100.7" \
   -d '{"password":"<admin pwd from test_credentials.md>"}' \
   | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

# 1) Auth + menu fetch
curl -fsSL "$API/api/menu" -H "Authorization: Bearer $TOKEN" | wc -l

# 2) Library list
curl -fsSL "$API/api/media/assets?limit=5&kind=image" -H "Authorization: Bearer $TOKEN" | jq '.assets | length'

# 3) Creative Director recommendation
curl -fsSL -X POST "$API/api/creative-director/recommend" \
   -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
   -d '{"item_key":"appetizers::caf-fries","food_type":"Café Fries","features":["seasoned"]}' \
   | jq '.recommendations[0]'

# 4) End-to-end flyer render (uses the just-seeded burger photo asset)
JOB=$(curl -fsSL -X POST "$API/api/ai-designer/generate" \
   -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
   -d '{
     "source_asset_id":"ddfa3085-3bb6-40e6-b422-5f6124d0a973",
     "item_name":"Smoke Test","features":["smoke"],"price":"$0.00",
     "theme":"seafood_coastal","item_key":"qa::smoke"
   }' | jq -r .job_id)

# 5) Poll until completed (should take <30s)
for i in $(seq 1 30); do
  S=$(curl -fsSL "$API/api/ai-designer/job/$JOB" -H "Authorization: Bearer $TOKEN" \
      | jq -r .status); [ "$S" = "completed" ] && break; sleep 1; done
echo "Smoke test status: $S"
```

Expected: status=`completed`, 3 variations, at least one labelled "Very Good".

* [ ] All five curls return 200 / valid responses.
* [ ] Smoke E2E flyer renders to `completed` in <30 s.

---

## Phase 3 — Deploy

Use the standard Emergent deploy flow (the platform handles the actual
build + push). No manual steps required if Phase 0–2 are green.

* [ ] Click **Deploy** from the chat surface.
* [ ] Wait for the deploy banner to flip to "Deploy successful".
* [ ] Wait an extra 60 s for the production pod's `bootstrap.py` to finish
      `ensure_ffmpeg` + `prewarm_rembg`.

---

## Phase 4 — Production verification

Run the same five smoke curls in Phase 2 against
`https://lakeview-grill.emergent.host` (substitute the API URL).

* [ ] `/api/menu` returns the full menu.
* [ ] `/api/media/assets` returns non-empty list.
* [ ] `/api/creative-director/recommend` returns a `recommendations` array.
* [ ] `/api/ai-designer/generate` returns a `job_id` in <250 ms.
* [ ] The smoke flyer completes in <30 s.

If any step fails → STOP and rollback (Phase 6).

---

## Phase 5 — Visual sign-off (real owner)

* [ ] Owner logs into `https://lakeview-grill.emergent.host/dashboard`.
* [ ] Promote → Photo→Flyer → upload a real menu photo → confirm:
   * Food is the visual hero (filling ~60-75% of the canvas).
   * The photo blends into the background — no rectangular crop edge.
   * The price badge is clearly visible.
   * Decorative overlays sit BEHIND the food (not competing).
   * Branding text at the footer is readable.

If owner says yes, Sprint 19 is officially closed in production.

---

## Phase 6 — Rollback (if Phase 4 or 5 fails)

The Sprint 19 hotfix is a forward-only set of changes. To roll back:

```bash
# Revert the four hotfix files in one commit
git -C /app checkout ad739a9 -- backend/render_engine.py
# Restore the seafood_coastal palette to its pre-Sprint-19 state
git -C /app checkout ad739a9 -- backend/theme_packs/seafood_pack.py
git -C /app commit -m "Revert Sprint 19 hotfix"
```

Then redeploy with the standard Emergent flow. Database is not touched
during Sprint 19 — no migrations required, no data restore needed.

---

## Phase 7 — Post-deploy housekeeping (within 24 h)

* [ ] Archive the `/tmp/sprint19_samples` and `/tmp/sprint19_before_after`
      directories to long-term storage if you want to keep the visual
      evidence.
* [ ] Re-run `menu_validation.py` from `/app/backend` against production
      once with the production admin password — log the output to
      `/app/memory/SPRINT19_PROD_VERIFICATION.log`.
* [ ] Confirm the production billing card is updating (no LLM keys consumed
      during render — only at copy-write time).

---

## Owner-facing release notes (paste into changelog)

> ### Sprint 19 — Professional Flyer Composition
> Every flyer the platform creates now puts the food front-and-centre.
> Photos no longer sit in a hard rectangular box — their edges feather
> naturally into the background. Price badges are guaranteed to be solid,
> visible discs in every theme. Background textures (waves, smoke, confetti)
> recede behind the food instead of fighting it for attention. Across the
> 25-item Lakeview menu the average composition quality score climbed
> from ~65 to 76, and every item now generates without a failed render.
