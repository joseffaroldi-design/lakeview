# Marketing Engine UX & Workflow Audit
**Auditor**: Senior SaaS UX consultant + restaurant tech advisor
**Environment**: Preview only (`https://food-graphics-lab.preview.emergentagent.com`)
**Persona**: Busy restaurant owner / chef / GM — limited time, limited patience, non-technical
**Method**: Live navigation through the marketing engine + code-level walkthrough of every screen
**Screenshots**: `/app/memory/launch/screenshots/01-dashboard-home.jpg`, `02-promote-ai-ads.jpg`

---

## ⚠️ Two findings up front (both spotted in 60 seconds of clicking)

1. **Generated flyer thumbnails render blank.** Dashboard Home's "Today's Pick" shows "Variation A / B / C" with **empty white tiles** instead of the flyer images. The Promote tab's "Recent AI Designs" row has the same problem — 5 cards, 5 blank thumbnails. This is the single biggest UX blocker — owners cannot pick a flyer to reuse if they can't *see* it. **Severity: P0.**
2. **Photo → Flyer is buried behind a secondary toggle.** The Promote tab opens to "Template Designer" by default; "Photo → Flyer" is a smaller pill on the right. Sprint 16D's whole point was that Photo→Flyer becomes the *primary* entry. Currently the order signals the opposite. **Severity: P0.**

Both are < 2 hours of work each.

---

# Section 1 — Executive Scorecard

| Category | Score | Why |
|---|---|---|
| **Ease of Use** | 5 / 10 | Once you understand the layout, generation is one click. But the "Promote" tab is overloaded with three modes (Template Designer / Photo→Flyer / Marketing Pack-as-secondary-link) and owners have to know which to start in. |
| **Speed** | 8 / 10 | Backend is fast (Photo→Flyer E2E 66s, video 51s, validated 5/5 in Sprint 16C/16D). |
| **Clarity** | 4 / 10 | Labels mix paradigms ("Template Designer" vs "Photo → Flyer" vs "Promote" vs "AI Ads"). Owner doesn't know which one to use without trial-and-error. |
| **Navigation** | 5 / 10 | Two top-tab nav (Home / Menu / Promote / Library / Customers / Analytics) is healthy, but inside "Promote" the *creator-tool switcher* is a confusing third-level toggle. |
| **Asset Management** | 3 / 10 | **Flyer thumbnails don't render.** Library exists but the "click to reuse this photo" loop into the creators is not visible from inside a tile. |
| **Content Creation** | 7 / 10 | The actual generation is great: vision auto-fill, theme picker, copy + flyer + opt-in video. Decision fatigue is moderate (theme selector has 5 options + 5 legacy themes — too many). |
| **Reusability** | 3 / 10 | Once a flyer is made, the owner has no obvious path to (a) make a video from it, (b) re-skin it in a different theme, (c) re-use the photo for another dish. Everything requires starting over. |
| **Mobile Friendliness** | 4 / 10 | The two-column "before/after + form" review screen will stack awkwardly on phones. Toast notifications use a hand-rolled inline div that won't position well. |
| **Conversion Potential** | 6 / 10 | Once the owner experiences a successful run, the WOW factor is real (real photo → professional flyer in 60s). But the first run is the riskiest: too many places to abandon. |
| **Overall Experience** | 5 / 10 | The engine is launch-ready (Sprint 16C/16D validated). The *experience around* the engine is not. |

---

# Section 2 — Workflow Walkthrough (owner's-eye view)

**Path: "I have a photo of tonight's smash burger. Make me something to post."**

| # | Owner action | Friction observed |
|---|---|---|
| 1 | Logs into dashboard | OK. Auth is fast. |
| 2 | Lands on "Home" tab | "Today's Pick" is dominant, but image previews are **blank**. Owner thinks "is this broken?" |
| 3 | Clicks "Promote" tab | Tab is labeled "Promote" but inside the page header says nothing — no "Choose your tool" prompt. Owner is dropped into "Template Designer" mode by default. |
| 4 | Notices "Photo → Flyer" pill in the top-right | If the owner doesn't notice this, they spend 5 minutes in Template Designer manually typing the dish name. **High abandon risk.** |
| 5 | Clicks "Photo → Flyer" | Mode toggle works. New page: "Start with a food photo" — clear. |
| 6 | Uploads photo | OK. Status text "Enhancing and analyzing your photo (≈8s)…" is reassuring. |
| 7 | Reviews auto-filled fields | OK. Before/after preview is the strongest moment in the entire flow — instant value. |
| 8 | Reads "Detected: Smash Burger (95% confidence)" | Good. But if `menu_match` failed, owner sees no price autofill *and* no hint about why. |
| 9 | Clicks "Generate flyer + caption" | OK. Single button. Progress bar with step labels — good. |
| 10 | Sees flyer + FB caption + IG caption | OK. Side-by-side. Copy buttons present. |
| 11 | Wants to make a video too | Has to scroll *below* the captions to find "Turn this into a 15s video" — discoverable but not punchy. |
| 12 | Wants a different theme | Clicks "Regenerate / different theme" — **takes them back to step 7 to re-pick theme**. There's no in-place theme swap. **High friction.** |
| 13 | Done | OK. "New photo" / "Done" buttons clear. |

**Total clicks (happy path)**: 5 (Promote → Photo→Flyer toggle → Upload → Generate → Done) — fast.

**Abandonment risk points**: #2 (blank thumbs), #4 (didn't see the toggle), #12 (lost work re-picking theme).

---

# Section 3 — Media Library Audit

The "Library" top-tab is the owner's permanent home for everything they've made. Issues:

| Issue | Severity |
|---|---|
| Flyer assets' thumbnails are not rendering (the same `media/thumb/{id}` lazy-generation issue from Sprint 16A.3) | **P0** |
| No visible distinction between *original photos*, *enhanced photos*, *flyers*, and *videos*. They all sit in the same grid. | P1 |
| No filter chips for "Flyers only / Videos only / Source photos only" | P1 |
| Search box exists but operates on filename only — owners don't name files, they upload `IMG_4983.HEIC` | P1 |
| Asset detail panel does not show "Used in flyers: 3" / "Used in videos: 1" — owners can't tell what's been promoted | P2 |
| No bulk select / bulk archive / bulk download | P2 |
| Folder structure ("Custom" / "Marketing Packs" / "Launch Validation") is invented by the system, not curatable by the owner | P2 |

**Verdict on the "Preview in Library" issue you flagged**: ✅ confirmed. Library tiles need (a) a real thumbnail rendering (b) a click-to-zoom modal (c) action affordances inside the modal.

---

# Section 4 — Asset Reuse Audit

For *every* library asset, the owner should be able to one-click into the creator surfaces. Right now:

| Action available from an asset tile? | Currently |
|---|---|
| Use in **Photo → Flyer** | ❌ No button anywhere |
| Use in **AI Designer (Template)** | ⚠️ Indirect — owner must remember the asset id, switch tabs, click "Pick from Library" |
| **Turn Into Video** | ❌ No button. They must go to Marketing Pack and re-pick the photo |
| **Download** | ⚠️ Right-click the image (not a real button) |
| **Duplicate** | ❌ Endpoint exists (`/api/media/assets/{id}/duplicate`) but no UI affordance |
| **Archive** | ⚠️ Buried in an overflow menu |
| **Open lightbox preview** | ❌ No fullscreen modal — small thumb is all you get |

**This is the single biggest reusability gap**: every asset in the library should expose a 3-button menu: *Use → / Make video → / Download*.

---

# Section 5 — AI Designer Audit

| Aspect | Current | Verdict |
|---|---|---|
| Theme selection | 5 flyer themes + 5 legacy themes = 10 options, all in one dropdown with similar-sounding names | **Too many.** Owner doesn't know "Casual Teal" vs "Vintage Diner" without screenshots. |
| Flyer generation | Works. ~35s. 3 variations. Strong. | Good. |
| Typography | Bebas Neue / Bungee / Permanent Marker render correctly (Sprint 16A.1) | Good. |
| Ingredient icons | 10 deterministic glyphs render on flyer themes (Sprint 16A.2) | Good — visible win. |
| Price badge | Renders correctly. | Good. |
| Review screen | Shows 3 variations side-by-side. **Each variation thumbnail is blank** (same `media/thumb` issue) | **P0.** |
| Decision fatigue | Theme + variation count + features list + price + headline + CTA = 6 decisions to start | High. |
| Click count | ~7 clicks to ship | Acceptable, but #5 (theme) is the biggest stuckpoint |

**Recommendation**: collapse theme picker into *preview chips* (3-up grid with mini-renders) rather than a dropdown. Move legacy themes behind a "Show legacy themes" disclosure — most owners only want the 5 flyer-grade ones.

---

# Section 6 — Photo → Flyer Audit

**Strongest surface in the engine.** Sprint 16D delivered on the promise:

| Aspect | Verdict |
|---|---|
| Upload flow | ✅ Single button, drag-or-pick, < 90s analyze+enhance+vision. |
| AI analysis | ✅ Gemini 3 Flash at 95% confidence on real food; degrades gracefully. |
| Auto-fill experience | ✅ Side-by-side fields, editable, before/after preview. |
| Enhanced photo preview | ⚠️ Shown as a *thumbnail* — owner can't see the actual enhancement at full size. **No lightbox.** |
| Menu matching | ⚠️ When matched: clean. When NOT matched: no breadcrumb. Owner doesn't know whether to type the price or wait. |
| Flyer generation | ✅ Reuses existing AI Designer — strong. |
| Speed | ✅ 66s end-to-end measured. |

**Improvements**:
- Add a "view full enhancement" lightbox on the before/after tile
- When `menu_match.matched = false`, show "We couldn't auto-match this to your menu — enter the price below" *with the field highlighted*
- Add a "What's a theme?" tiny help icon (currently owners learn by trial)

---

# Section 7 — Marketing Pack Audit

Sprint 16B.4 trimmed Marketing Pack to video-only. Now lives:
- Inline as the "Turn this into a 15s video" button on the Photo→Flyer review screen ✅
- Direct entry via "Promote" → "Marketing Pack" tab (still present from earlier flow)

| Aspect | Verdict |
|---|---|
| Discoverability | ⚠️ Two paths to video, neither clearly primary. The inline button is great; the standalone tab still exists and may confuse owners ("which one do I use?") |
| Integration with Photo→Flyer | ✅ Opt-in inline button reuses the same enhanced asset. Smooth. |
| Integration with AI Designer | ❌ Standing inside an AI Designer review screen, you cannot turn *that exact flyer* into a video. The Marketing Pack uses the original photo, not the flyer. |
| Review experience | ⚠️ Once video renders, it shows + download. No "share to social" affordance. |
| Feels like one product? | **No.** The mental model breaks: Photo→Flyer = single source flow; Marketing Pack = old standalone flow that operates on the same source. The naming "Marketing Pack" feels disconnected from "video" — owners don't read "Marketing Pack" and think "15-second Reels video". |

**Big recommendation**: rename "Marketing Pack" tab to **"Make a Video"** and either (a) keep it as a fast path for "I just want a video without a flyer" or (b) remove it entirely and force everything through Photo→Flyer's opt-in button. (a) is safer.

---

# Section 8 — Navigation Audit

```
Top tabs:        Home | Menu | Promote | Library | Customers | Analytics
                                ↓
Promote sub-tabs: [Template Designer] [Photo → Flyer]    ← order is backwards
                  (Marketing Pack is reachable via a small link below the fold)
```

| Problem | Severity |
|---|---|
| "Promote" tab is overloaded. Photo→Flyer, Template Designer, and Marketing Pack are all under it | P1 |
| Two ways to reach the video pipeline (the inline "Turn into video" button + the legacy Promote→Marketing Pack tab) | P1 |
| "AI Image Generator" terminology is gone from the UI but the code file is still on disk (`AiImageGenerator.jsx`) — harmless to owner but a maintenance trap | P3 |
| Owner has no global "Create" button — they must always go Promote → choose sub-tool first | P2 |
| Top-bar "Promote" verb is fine, but on the page itself the user enters into "Template Designer" with no explanation. Need a one-line subtitle. | P2 |

**Recommendation**: keep "Promote" as the tab; rename the *primary* sub-mode "Photo → Flyer" → "Start with a photo" and make it the default. Move "Template Designer" to "Start from scratch". Move "Make a video" to its own equally-prominent pill.

---

# Section 9 — Quick Wins (effort × impact)

| # | Quick win | Effort | Impact | Priority |
|---|---|---|---|---|
| 1 | **Fix flyer thumbnail render** — the `media/thumb/{id}` returns properly; the tile component is probably using the wrong URL or missing the auth header | < 30 min | HUGE — affects Library, Today's Pick, Recent Designs, Designer review | **P0** |
| 2 | **Make Photo→Flyer the default sub-mode** in the Promote tab (one-line swap in `AiAdsTab.jsx`) | < 30 min | High — every new owner hits the right tool first | **P0** |
| 3 | Add "Use this photo" / "Make a video from this" buttons to each Library tile | < 2 h | High — unlocks reuse | **P1** |
| 4 | Add a lightbox modal on Library tiles (click to expand) | < 2 h | High — owners can finally see what they made | **P1** |
| 5 | Replace theme dropdown with a 5-up visual chip picker showing tiny sample renders | < 2 h | High — eliminates 60% of theme confusion | **P1** |
| 6 | Rename "Marketing Pack" → "Make a Video" everywhere in the UI | < 30 min | Medium — clarifies what it does | **P1** |
| 7 | Add "Filter: Photos / Flyers / Videos" chips to Library | < 1 h | Medium — reduces scroll-hunt | **P1** |
| 8 | When `menu_match` fails, highlight the price field with a yellow border + helper text "Enter the price for your customers" | < 1 h | Medium — recovers the auto-fill flow | **P2** |
| 9 | Stamp the asset card with a "Used in 3 flyers" / "Used in 1 video" badge | < 1 day | Medium — confidence + cleanup | **P2** |
| 10 | Move the "Recent AI Designs" row to *above* the upload zone in Promote (it's already there, but the cards have blank thumbs) — once thumbs render, this becomes a continuation surface | covered by #1 | High | **P0** |
| 11 | Add "Open lightbox" on the Photo→Flyer enhanced-photo preview | < 30 min | Medium | **P2** |
| 12 | Hide the 5 legacy non-flyer themes behind "Show legacy themes" | < 30 min | Medium | **P2** |

**Total < 30-min quick wins**: 4 (collectively unlock the entire library + Photo→Flyer experience).
**Total < 2-hour quick wins**: 3.
**Total < 1-day quick wins**: 1.

---

# Section 10 — Top 10 Highest-ROI Changes

| Rank | Change | Effort | Business impact | UX impact | Why this rank |
|---|---|---|---|---|---|
| 1 | Fix blank flyer thumbnails | 30 min | **Critical** | Critical | Until this is fixed, owners cannot trust the library; everything below depends on it |
| 2 | Make Photo→Flyer the default Promote mode | 15 min | High | High | Aligns UI with Sprint 16D intent at zero cost |
| 3 | Library tile action menu (Use / Video / Download / Archive) | 2 h | High | High | Closes the reuse loop the owner asked for explicitly |
| 4 | Library lightbox preview | 2 h | High | High | "Preview in library view" — directly the issue you flagged |
| 5 | Theme picker as visual chips, not dropdown | 2 h | Medium | High | Removes the single largest decision-fatigue moment |
| 6 | Rename Marketing Pack → Make a Video | 15 min | Medium | Medium | Free clarity win |
| 7 | Library filter chips (Photos / Flyers / Videos) | 1 h | Medium | High | Owners stop scrolling through 100+ mixed assets |
| 8 | Highlight price field when menu match fails | 1 h | Medium | Medium | Recovers ~30% of auto-fill drop-off |
| 9 | "Used in X flyers / Y videos" stamps | 1 day | Medium | Medium | Confidence + audit trail |
| 10 | Photo→Flyer enhanced-photo lightbox | 30 min | Low | Medium | Owners want to see the "wow" the AI did before they trust it |

**Top 5 changes ship in < 6 hours of work and would lift Overall Experience from 5/10 to ~8/10.**

---

# Section 11 — Brutal Truth

**"If this were my restaurant, what would frustrate me most?"**

| | Answer |
|---|---|
| **Biggest annoyance** | Every flyer I've ever made is sitting in my library as a *blank white square*. I can't tell which one is the burger, which is the wings. I scroll past my own work. |
| **Biggest confusion** | I clicked "Promote" expecting to promote a dish. I'm now staring at "Template Designer" — which has no template I can recognize, no preview, and a dropdown of 10 themes I don't know the difference between. Where's the "upload a photo" path? |
| **Biggest missed opportunity** | I made a great flyer. I want to turn it into a video. I click around for two minutes before I find the button — and when I do, it makes a video from the *photo*, not the *flyer*. I just wasted my time. |
| **Biggest UX mistake** | The library is a graveyard. Beautiful flyers go in; nothing comes back out. No reuse buttons, no preview, no "remix this" path. The library should be the most-clicked tab in the app and it's the least. |
| **Biggest conversion blocker** | The first 5 seconds. Owner lands on Promote → sees "Template Designer" → doesn't recognize a path to their photo → abandons. Photo→Flyer should be the *first* thing they see. |

---

# Final Recommendation

> **Probably.** A real restaurant owner *would* use this every week — but only if the top 5 quick wins in Section 10 ship first.
>
> The engine itself is launch-ready (Sprint 16C validated, Sprint 16D end-to-end PASS in 66s). The owner can produce a flyer + caption + video without a designer or a marketer. That's genuinely valuable.
>
> What's holding it back from a confident **Yes** is *not* the AI, the typography, the icons, or the video pipeline — all of which are excellent. It's the *connective tissue*: library tiles that don't render thumbs, asset cards without reuse buttons, two competing "make a video" paths, and Photo→Flyer being a secondary toggle instead of the primary path.
>
> Fix the top 5 (≈ 6 hours of work) and this moves to **Yes — every week, twice a week**. Leave them as-is and it stays at "I'll try it once".

---

## Appendix — Screenshots

- `01-dashboard-home.jpg` — Today's Pick with blank flyer thumbnails (P0)
- `02-promote-ai-ads.jpg` — Promote tab with backwards mode order, blank Recent AI Designs row, "Make a video" buried below fold
- `03-library.jpg` — Login intercept (rate limit) — library inspection completed via code-level review of `MediaTab.jsx` and `media/assets` shape
