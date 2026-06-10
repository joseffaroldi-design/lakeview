/**
 * AiAdsTab — Sprint 12D collapse.
 *
 * Pre-12D this tab hosted 8 sub-tabs: Promote / Automations / Media / Calendar /
 * Queue / Library / Analytics / Settings. Six of those were either duplicates of
 * Promote, dependent on the dead Publishing pipeline, or unreachable.
 *
 * Post-12D: the entire "Promotions" tab is just PromoteThisItem. Library and
 * Media editor have been promoted to top-level tabs. No sub-tabs remain.
 */
import React from "react";
import PromoteThisItem from "./aiads/PromoteThisItem";

const AiAdsTab = ({ getAuthHeader }) => {
  return (
    <div className="space-y-6" data-testid="aiads-tab">
      <PromoteThisItem getAuthHeader={getAuthHeader} />
    </div>
  );
};

export default AiAdsTab;
