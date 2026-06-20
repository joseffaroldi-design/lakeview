/**
 * AiAdsTab — Promote tab. Two modes:
 *   - "Marketing Pack" (default): one-click pack (captions, SMS, email, GBP,
 *      cropped photos w/ text overlays, 15-sec video). Cheap, ~$0.02/run.
 *   - "AI Designer": gpt-image-1 image-edit. Generates 1-5 themed graphic
 *      variations (Luxury/Vintage/Modern/Social/Cajun). Costs ~$0.04-$0.40/run.
 */
import React, { useState } from "react";
import { Megaphone, Wand2 } from "lucide-react";
import PromoteThisItem from "./aiads/PromoteThisItem";
import AiDesigner from "./aiads/AiDesigner";

const AiAdsTab = ({ getAuthHeader }) => {
  const [mode, setMode] = useState("pack"); // pack | designer

  return (
    <div className="space-y-4" data-testid="aiads-tab">
      <div className="flex flex-wrap gap-1 bg-navy/5 p-1 rounded-md w-fit" data-testid="aiads-mode-switch" role="tablist">
        <button
          type="button"
          onClick={() => setMode("pack")}
          role="tab"
          aria-selected={mode === "pack"}
          className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded transition-colors ${
            mode === "pack" ? "bg-card text-navy shadow-sm" : "text-navy/60 hover:text-navy"
          }`}
          data-testid="aiads-mode-pack"
        >
          <Megaphone className="w-3.5 h-3.5" /> Marketing Pack
        </button>
        <button
          type="button"
          onClick={() => setMode("designer")}
          role="tab"
          aria-selected={mode === "designer"}
          className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded transition-colors ${
            mode === "designer" ? "bg-card text-navy shadow-sm" : "text-navy/60 hover:text-navy"
          }`}
          data-testid="aiads-mode-designer"
        >
          <Wand2 className="w-3.5 h-3.5" /> AI Designer
        </button>
      </div>

      {mode === "pack" ? (
        <PromoteThisItem getAuthHeader={getAuthHeader} />
      ) : (
        <AiDesigner getAuthHeader={getAuthHeader} />
      )}
    </div>
  );
};

export default AiAdsTab;
