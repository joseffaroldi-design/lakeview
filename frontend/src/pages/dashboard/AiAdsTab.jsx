import React from "react";
import PhotoToFlyer from "./aiads/SimplePhotoToFlyer";
import { PageHeader } from "@/components/dashboard/primitives";

// Preserved for any external surface still emitting onUseInAd handoffs.
const HANDOFF_KEY = "lakeview.ai_designer.preload_asset_id";

const AiAdsTab = ({ getAuthHeader }) => (
  <div className="ds-fade" data-testid="aiads-tab">
    <PageHeader
      eyebrow="Promote"
      title={<>Photo <span className="text-gold">→</span> Flyer</>}
      subtitle="Choose a food photo, template, text, price, and size. The flyer renders predictably and saves to your Library."
    />
    <PhotoToFlyer getAuthHeader={getAuthHeader} />
  </div>
);

export default AiAdsTab;
export { HANDOFF_KEY };
