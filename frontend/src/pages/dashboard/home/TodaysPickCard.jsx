/**
 * TodaysPickCard — self-contained wrapper around TodaysPick.
 *
 * Sprint 22F: TodaysPick used to live on the Dashboard Home tab inside
 * a giant hero card. The user asked to move it to the Menu tab (where
 * dish-level marketing decisions belong) and clean up the Home tab.
 * This wrapper owns the fetch + refresh plumbing so the consumer can
 * drop the card anywhere without rewiring data flow.
 */
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";

import TodaysPick from "./TodaysPick";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TodaysPickCard = ({ getAuthHeader }) => {
  const [pick, setPick] = useState(null);

  const fetchPick = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/todays-pick/today`, { headers: getAuthHeader() });
      setPick(r.data);
    } catch (e) {
      // 404 = no pick available yet; degrade quietly. Card shows skeleton.
      console.warn("[TodaysPickCard] fetch failed:", e?.response?.status || e?.message);
    }
  }, [getAuthHeader]);

  useEffect(() => { fetchPick(); }, [fetchPick]);

  return (
    <div className="ds-hero p-6 sm:p-8" data-testid="menu-todays-pick-card">
      <TodaysPick pick={pick} onRefresh={fetchPick} getAuthHeader={getAuthHeader} />
    </div>
  );
};

export default TodaysPickCard;
