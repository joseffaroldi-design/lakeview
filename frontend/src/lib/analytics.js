// Public-site analytics helpers. Extracted verbatim from App.js during the
// V1.0 Safe Cleanup sprint (Feb 2026). Behaviour is preserved 1:1.

import axios from "axios";
import { API } from "@/lib/publicConfig";

// Generate or get session ID
export const getSessionId = () => {
  let sessionId = sessionStorage.getItem("visitor_session");
  if (!sessionId) {
    sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    sessionStorage.setItem("visitor_session", sessionId);
  }
  return sessionId;
};

// Track page view with enhanced data
export const trackPageView = async (page) => {
  try {
    await axios.post(`${API}/analytics/track`, {
      page,
      user_agent: navigator.userAgent,
      referrer: document.referrer || null,
      session_id: getSessionId(),
      screen_width: window.screen.width,
      screen_height: window.screen.height
    });
  } catch (error) {
    console.error("Error tracking page view:", error);
  }
};

// Track button clicks
export const trackButtonClick = async (buttonName) => {
  try {
    await axios.post(`${API}/analytics/button-click`, {
      button_name: buttonName,
      session_id: getSessionId()
    });
  } catch (error) {
    console.error("Error tracking button click:", error);
  }
};
