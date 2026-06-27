import React from "react";
import PhotoToFlyer from "./aiads/PhotoToFlyer";

// Preserved for any external surface still emitting onUseInAd handoffs.
const HANDOFF_KEY = "lakeview.ai_designer.preload_asset_id";

const AiAdsTab = ({ getAuthHeader }) => (
  <div className="ds-fade" data-testid="aiads-tab">
    <header className="mb-8">
      <p className="ds-eyebrow mb-1">Promote</p>
      <h2 className="ds-display text-3xl sm:text-4xl flex items-center gap-3">
        Photo <span className="text-gold">→</span> Flyer
      </h2>
      <p className="text-sm text-navy/60 mt-2 max-w-xl">
        Upload a food photo and we&apos;ll auto-build a flyer + caption in under a minute. Turn it into a 15-second video if you like.
      </p>
    </header>
    <PhotoToFlyer getAuthHeader={getAuthHeader} />
  </div>
);

export default AiAdsTab;
export { HANDOFF_KEY };
