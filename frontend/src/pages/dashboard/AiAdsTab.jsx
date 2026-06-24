/**
 * AiAdsTab — Promote tab (Sprint 15B.8).
 *
 * Sprint 14B.3 collapsed the Marketing Pack / AI Designer mode toggle in
 * favor of a single Promote surface. Sprint 15B.8 adds a SECOND engine —
 * the AI Image Generator (Flux Pro / OpenAI gpt-image-1) — and presents
 * the two as a side-by-side mode switch.
 *
 * Modes:
 *   * "designer" — existing Template Designer (PIL composition + overlays)
 *   * "image"    — new AI Image Generator (real LLM image gen)
 *
 * Marketing Pack remains reachable via the footer cross-link from inside
 * the Template Designer surface.
 *
 * "Use In Ad" handoff: when AiImageGenerator emits onUseInAd(asset),
 * we drop the asset id into sessionStorage and switch back to designer.
 * AiDesigner's PickPhoto step reads it on mount and auto-selects it.
 */
import React, { useState } from "react";
import { Megaphone, ArrowLeft, Sparkles, LayoutGrid } from "lucide-react";
import PromoteThisItem from "./aiads/PromoteThisItem";
import AiDesigner from "./aiads/AiDesigner";
import PhotoToFlyer from "./aiads/PhotoToFlyer";

const HANDOFF_KEY = "lakeview.ai_designer.preload_asset_id";

const AiAdsTab = ({ getAuthHeader }) => {
  // Sprint 16D-fix: Photo→Flyer is the primary owner workflow. Template
  // Designer is kept as an "advanced" mode for users who want to start
  // from scratch without uploading a photo.
  const [mode, setMode] = useState("image");

  const handleUseInAd = (asset) => {
    if (asset?.id) {
      try {
        // Sprint 15B.8 — pass the full asset payload so AiDesigner doesn't
        // need a (non-existent) GET /assets/{id} endpoint to rehydrate.
        sessionStorage.setItem(HANDOFF_KEY, JSON.stringify(asset));
      } catch (e) {
        // sessionStorage can throw in some private-mode configs; silently fall back.
        console.warn("[aiads] handoff sessionStorage write failed", e);
      }
      setMode("designer");
    }
  };

  if (mode === "pack") {
    return (
      <div className="space-y-4" data-testid="aiads-tab">
        <button
          type="button"
          onClick={() => setMode("designer")}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-navy/70 hover:text-navy"
          data-testid="aiads-back-to-designer"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to AI Designer
        </button>
        <PromoteThisItem getAuthHeader={getAuthHeader} />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="aiads-tab">
      {/* Sprint 16D-fix: Photo → Flyer is the primary owner workflow.
          Template Designer is the secondary "advanced" mode. */}
      <div
        className="inline-flex p-0.5 bg-navy/5 rounded-sm"
        data-testid="aiads-engine-switch"
      >
        <button
          type="button"
          onClick={() => setMode("image")}
          className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-sm transition-colors ${
            mode === "image"
              ? "bg-white text-navy shadow-sm"
              : "text-navy/60 hover:text-navy"
          }`}
          data-testid="aiads-mode-image"
        >
          <Sparkles className="w-3.5 h-3.5" /> Photo → Flyer
        </button>
        <button
          type="button"
          onClick={() => setMode("designer")}
          className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-sm transition-colors ${
            mode === "designer"
              ? "bg-white text-navy shadow-sm"
              : "text-navy/60 hover:text-navy"
          }`}
          data-testid="aiads-mode-designer"
        >
          <LayoutGrid className="w-3.5 h-3.5" /> Template Designer
          <span className="ml-1 text-[9px] uppercase tracking-wider text-navy/40">Advanced</span>
        </button>
      </div>

      {mode === "image" ? (
        <PhotoToFlyer
          getAuthHeader={getAuthHeader}
        />
      ) : (
        <>
          <AiDesigner getAuthHeader={getAuthHeader} />

          {/* Secondary affordance — preserved access to Marketing Pack. */}
          <div
            className="border-t border-navy/10 pt-4 text-xs text-muted-foreground flex items-center justify-between gap-3"
            data-testid="aiads-secondary-cta"
          >
            <span className="flex items-center gap-1.5">
              <Megaphone className="w-3.5 h-3.5 text-navy/60" />
              Need a 15-second promo video for this item?
            </span>
            <button
              type="button"
              onClick={() => setMode("pack")}
              className="text-xs font-semibold text-gold hover:underline"
              data-testid="aiads-open-marketing-pack"
            >
              Make a video →
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default AiAdsTab;
export { HANDOFF_KEY };
