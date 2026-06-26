/**
 * AiAdsTab — Promote tab.
 *
 * Sprint 19 perf+UX pass: Template Designer mode retired from the UI.
 * Photo → Flyer is now the only surface here. AiDesigner.jsx is retained
 * in the codebase (still imported by any direct callers / sessionStorage
 * handoffs) but no longer reachable through this tab.
 *
 * If we ever need template browsing again, it'll be re-surfaced as part
 * of Sprint 20's Marketing Workspace where templates fold into per-item
 * Projects instead of living as a separate mode toggle.
 */
import React from "react";
import PhotoToFlyer from "./aiads/PhotoToFlyer";

// Preserved for any external surface still emitting onUseInAd handoffs.
const HANDOFF_KEY = "lakeview.ai_designer.preload_asset_id";

const AiAdsTab = ({ getAuthHeader }) => (
  <div className="space-y-4" data-testid="aiads-tab">
    <PhotoToFlyer getAuthHeader={getAuthHeader} />
  </div>
);

export default AiAdsTab;
export { HANDOFF_KEY };
