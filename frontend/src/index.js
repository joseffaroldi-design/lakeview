import React from "react";
import ReactDOM from "react-dom/client";
import axios from "axios";
import { toast, Toaster } from "sonner";
import "@/index.css";
import App from "@/App";
import ErrorBoundary from "@/components/ErrorBoundary";

// ---- Global axios interceptor: surface auth + server errors instead of silent failure ----
// Sprint 15B: Only show error toasts on admin/dashboard routes. Public diners
// should never see "Server error" banners — failures on /menu, /content, /specials,
// /analytics/track are logged silently and the page keeps rendering with cached state.
// Sprint 15B.1: Add one auto-retry on transient proxy/server failures so brief
// deploy-window blips don't pop toasts to the owner.
const isAdminRoute = () => {
  const p = window.location.pathname || "";
  return p.startsWith("/dashboard") || p.startsWith("/login");
};

// Statuses that get one automatic retry (transient infra/proxy failures).
// Do NOT retry 4xx (400/401/403/404/422) — those are caller-side and won't change.
const RETRY_STATUSES = new Set([500, 502, 503, 504, 520, 522, 524]);
const RETRY_DELAY_MS = 1000;

axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response && error.response.status;
    const config = error.config || {};
    const path = config.url || "";
    // Ignore auth-probe endpoints we expect to fail.
    const isAuthEndpoint = path.includes("/auth/login");
    // Public site: log and bail. Diners never see admin-style toasts.
    if (!isAdminRoute()) {
      if (status >= 500 && process.env.NODE_ENV !== "production") console.warn(`[axios] ${status} on ${path} (silenced on public route)`);
      return Promise.reject(error);
    }

    // Sprint 15B.1: one auto-retry on transient infra/proxy failures.
    if (RETRY_STATUSES.has(status) && !config.__retried) {
      config.__retried = true;
      if (process.env.NODE_ENV !== "production") console.warn(`[axios] ${status} on ${path} — retrying once after ${RETRY_DELAY_MS}ms`);
      await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
      try {
        return await axios.request(config);
      } catch (retryError) {
        // Retry failed. The recursive interceptor invocation has already shown
        // the toast (config.__retried prevents another retry but still toasts).
        // Propagate without re-toasting.
        return Promise.reject(retryError);
      }
    }

    const finalStatus = status;
    if (finalStatus === 401 && !isAuthEndpoint) {
      try { localStorage.removeItem("admin_token"); } catch (_) { /* noop */ }
      toast.error("Session expired", {
        description: "Please log in again.",
        action: { label: "Sign in", onClick: () => { window.location.href = "/login"; } },
      });
    } else if (finalStatus === 403 && !isAuthEndpoint) {
      toast.error("Access denied", { description: "You don't have permission for that action." });
    } else if (finalStatus >= 500) {
      // Include the failing path so the owner can report it.
      const shortPath = path.replace(/^https?:\/\/[^/]+/, "").slice(0, 80);
      toast.error("Server error", {
        description: `${shortPath || "An admin API"} returned ${finalStatus}. Please retry.`,
      });
    }
    return Promise.reject(error);
  }
);

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
      <Toaster richColors position="top-right" />
    </ErrorBoundary>
  </React.StrictMode>,
);
