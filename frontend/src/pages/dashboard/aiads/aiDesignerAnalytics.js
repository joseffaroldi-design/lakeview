/**
 * AI Designer Analytics Tracker
 * Sprint 14B.1A: Track abandonment before building solutions
 * 
 * Events:
 * - ai_designer_generation_started
 * - ai_designer_generation_completed
 * - ai_designer_abandoned
 * - ai_designer_generation_resumed
 */

import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Track active generation for abandonment detection
let activeGeneration = null;
let generationStartTime = null;
let abandonmentTracked = false;

/**
 * Track AI Designer analytics event
 */
export const trackAIDesignerEvent = async (eventName, metadata, getAuthHeader) => {
  try {
    await axios.post(
      `${API}/todays-pick/analytics`,
      {
        event: eventName,
        metadata: {
          ...metadata,
          timestamp: new Date().toISOString(),
        },
      },
      { headers: getAuthHeader() }
    );
    console.log(`[Analytics] ${eventName}`, metadata);
  } catch (err) {
    console.error("Analytics tracking failed:", err);
  }
};

/**
 * Mark generation as started
 */
export const markGenerationStarted = (jobData, formData, getAuthHeader) => {
  activeGeneration = {
    job_id: jobData.job_id,
    item_name: formData.item_name,
    theme: formData.theme,
    variation_count: 3,
    auto_copy_enabled: formData.auto_copy || false,
  };
  generationStartTime = Date.now();
  abandonmentTracked = false;

  // Store in localStorage for cross-session tracking
  localStorage.setItem(
    "ai_designer_active",
    JSON.stringify({
      ...activeGeneration,
      started_at: generationStartTime,
    })
  );

  trackAIDesignerEvent("ai_designer_generation_started", activeGeneration, getAuthHeader);
};

/**
 * Mark generation as completed
 */
export const markGenerationCompleted = (jobData, getAuthHeader) => {
  if (!activeGeneration) return;

  const durationSeconds = generationStartTime
    ? Math.floor((Date.now() - generationStartTime) / 1000)
    : null;

  trackAIDesignerEvent(
    "ai_designer_generation_completed",
    {
      job_id: activeGeneration.job_id,
      duration_seconds: durationSeconds,
      theme: activeGeneration.theme,
      variation_count: activeGeneration.variation_count,
      copy_generated: !!jobData.copy_pack,
    },
    getAuthHeader
  );

  // Clear active generation
  activeGeneration = null;
  generationStartTime = null;
  abandonmentTracked = false;
  localStorage.removeItem("ai_designer_active");
};

/**
 * Mark generation as abandoned
 */
export const markGenerationAbandoned = (reason, getAuthHeader) => {
  if (!activeGeneration || abandonmentTracked) return;

  const elapsedSeconds = generationStartTime
    ? Math.floor((Date.now() - generationStartTime) / 1000)
    : null;

  trackAIDesignerEvent(
    "ai_designer_abandoned",
    {
      job_id: activeGeneration.job_id,
      item_name: activeGeneration.item_name,
      theme: activeGeneration.theme,
      variation_count: activeGeneration.variation_count,
      elapsed_seconds: elapsedSeconds,
      reason, // e.g., "navigation", "page_close", "refresh"
    },
    getAuthHeader
  );

  abandonmentTracked = true;
};

/**
 * Check if there's an active generation and mark as resumed
 */
export const checkAndResumeGeneration = (getAuthHeader) => {
  const stored = localStorage.getItem("ai_designer_active");
  if (!stored) return null;

  try {
    const data = JSON.parse(stored);
    const elapsedSeconds = Math.floor((Date.now() - data.started_at) / 1000);

    // If less than 10 minutes old, consider it resumable
    if (elapsedSeconds < 600) {
      trackAIDesignerEvent(
        "ai_designer_generation_resumed",
        {
          job_id: data.job_id,
          elapsed_seconds: elapsedSeconds,
        },
        getAuthHeader
      );

      // Restore active generation state
      activeGeneration = data;
      generationStartTime = data.started_at;
      abandonmentTracked = false;

      return data;
    } else {
      // Too old, clear it
      localStorage.removeItem("ai_designer_active");
    }
  } catch (err) {
    console.error("Failed to parse stored generation:", err);
    localStorage.removeItem("ai_designer_active");
  }

  return null;
};

/**
 * Setup abandonment detection listeners
 */
export const setupAbandonmentDetection = (getAuthHeader) => {
  // Track page unload (close tab, navigate away, refresh)
  const handleBeforeUnload = () => {
    if (activeGeneration && !abandonmentTracked) {
      // Use sendBeacon for reliable tracking on page unload
      const data = {
        event: "ai_designer_abandoned",
        metadata: {
          job_id: activeGeneration.job_id,
          item_name: activeGeneration.item_name,
          theme: activeGeneration.theme,
          variation_count: activeGeneration.variation_count,
          elapsed_seconds: generationStartTime
            ? Math.floor((Date.now() - generationStartTime) / 1000)
            : null,
          reason: "page_unload",
          timestamp: new Date().toISOString(),
        },
      };

      // Try sendBeacon first (more reliable for page unload)
      const blob = new Blob([JSON.stringify(data)], { type: "application/json" });
      const sent = navigator.sendBeacon(`${API}/todays-pick/analytics`, blob);

      if (!sent) {
        // Fallback to synchronous request
        try {
          const xhr = new XMLHttpRequest();
          xhr.open("POST", `${API}/todays-pick/analytics`, false); // synchronous
          xhr.setRequestHeader("Content-Type", "application/json");
          const headers = getAuthHeader();
          if (headers.Authorization) {
            xhr.setRequestHeader("Authorization", headers.Authorization);
          }
          xhr.send(JSON.stringify(data));
        } catch (err) {
          console.error("Failed to track abandonment:", err);
        }
      }

      abandonmentTracked = true;
    }
  };

  // Track visibility change (tab switch)
  const handleVisibilityChange = () => {
    if (document.hidden && activeGeneration && !abandonmentTracked) {
      // User switched tabs while generation running
      // Don't immediately mark as abandoned, just note it
      const elapsedSeconds = generationStartTime
        ? Math.floor((Date.now() - generationStartTime) / 1000)
        : null;

      // Only track as abandoned if they've been away for > 60 seconds
      setTimeout(() => {
        if (document.hidden && activeGeneration && !abandonmentTracked) {
          markGenerationAbandoned("tab_switch_timeout", getAuthHeader);
        }
      }, 60000); // 60 seconds
    }
  };

  window.addEventListener("beforeunload", handleBeforeUnload);
  document.addEventListener("visibilitychange", handleVisibilityChange);

  // Return cleanup function
  return () => {
    window.removeEventListener("beforeunload", handleBeforeUnload);
    document.removeEventListener("visibilitychange", handleVisibilityChange);
  };
};

/**
 * Get current active generation info
 */
export const getActiveGeneration = () => activeGeneration;

/**
 * Check if there's an active generation
 */
export const hasActiveGeneration = () => !!activeGeneration;
