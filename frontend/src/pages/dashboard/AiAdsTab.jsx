/**
 * AiAdsTab — Promote tab (Sprint 14B.3 consolidated).
 *
 * Previously this surface showed a prominent toggle between two equal modes
 * — "Marketing Pack" and "AI Designer" — which forced the owner to choose
 * a workflow before they knew what they wanted.
 *
 * Sprint 14B.3 collapses the toggle:
 *   • Default surface is **AI Designer** — the visual flagship that produces
 *     branded graphics plus optional auto-copy (the strictly larger artifact set).
 *   • A single footer link offers the **Marketing Pack** path for owners
 *     who want a quick text-only pack (captions, SMS, email, GBP, hashtags,
 *     plus 15-sec video that AI Designer does not produce).
 *   • Both capabilities are preserved; only the upfront cognitive load drops.
 */
import React, { useState } from "react";
import { Megaphone, ArrowLeft } from "lucide-react";
import PromoteThisItem from "./aiads/PromoteThisItem";
import AiDesigner from "./aiads/AiDesigner";

const AiAdsTab = ({ getAuthHeader }) => {
  // "designer" is the default. "pack" is reachable only via the footer link.
  const [mode, setMode] = useState("designer");

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
      <AiDesigner getAuthHeader={getAuthHeader} />

      {/* Secondary affordance — preserved access to Marketing Pack without
          duplicating the workflow in the primary view. */}
      <div
        className="border-t border-navy/10 pt-4 text-xs text-muted-foreground flex items-center justify-between gap-3"
        data-testid="aiads-secondary-cta"
      >
        <span className="flex items-center gap-1.5">
          <Megaphone className="w-3.5 h-3.5 text-navy/60" />
          Need a quick text-only pack (captions, SMS, email, 15-sec video)?
        </span>
        <button
          type="button"
          onClick={() => setMode("pack")}
          className="text-xs font-semibold text-gold hover:underline"
          data-testid="aiads-open-marketing-pack"
        >
          Use Marketing Pack →
        </button>
      </div>
    </div>
  );
};

export default AiAdsTab;
