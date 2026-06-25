/**
 * AiAdsTab — Promote tab.
 *
 * Sprint 16F.2 — Surgical consolidation:
 *   * Photo → Flyer is the default surface (Sprint 16D-fix established this).
 *   * Template Designer remains as the "advanced" mode for manual control.
 *   * The duplicate "Make a video →" footer CTA was removed — video is
 *     already an opt-in step inside Photo → Flyer (step 4) and inside
 *     AI Designer's per-design "Make video" button. PromoteThisItem is
 *     still mounted from MenuEditor / HomeTab for backwards compatibility
 *     but is no longer reachable from inside this tab.
 *
 * Modes:
 *   * "image"    — Photo → Flyer (default)
 *   * "designer" — Template Designer (advanced)
 *
 * "Use In Ad" handoff: legacy AiImageGenerator handoff is no longer
 * triggered here; the constant + sessionStorage key remain so any other
 * surface that still emits onUseInAd continues to work.
 */
import React, { useState } from "react";
import { Sparkles, LayoutGrid } from "lucide-react";
import AiDesigner from "./aiads/AiDesigner";
import PhotoToFlyer from "./aiads/PhotoToFlyer";

const HANDOFF_KEY = "lakeview.ai_designer.preload_asset_id";

const AiAdsTab = ({ getAuthHeader }) => {
  const [mode, setMode] = useState("image");

  return (
    <div className="space-y-4" data-testid="aiads-tab">
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
        <PhotoToFlyer getAuthHeader={getAuthHeader} />
      ) : (
        <AiDesigner getAuthHeader={getAuthHeader} />
      )}
    </div>
  );
};

export default AiAdsTab;
export { HANDOFF_KEY };
