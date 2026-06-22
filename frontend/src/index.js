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
const isAdminRoute = () => {
  const p = window.location.pathname || "";
  return p.startsWith("/dashboard") || p.startsWith("/login");
};

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response && error.response.status;
    const path = (error.config && error.config.url) || "";
    // Ignore auth-probe endpoints we expect to fail.
    const isAuthEndpoint = path.includes("/auth/login");
    // Public site: log and bail. Diners never see admin-style toasts.
    if (!isAdminRoute()) {
      if (status >= 500) console.warn(`[axios] ${status} on ${path} (silenced on public route)`);
      return Promise.reject(error);
    }
    if (status === 401 && !isAuthEndpoint) {
      try { localStorage.removeItem("admin_token"); } catch (_) { /* noop */ }
      toast.error("Session expired", {
        description: "Please log in again.",
        action: { label: "Sign in", onClick: () => { window.location.href = "/login"; } },
      });
    } else if (status === 403 && !isAuthEndpoint) {
      toast.error("Access denied", { description: "You don't have permission for that action." });
    } else if (status >= 500) {
      // Include the failing path so the owner can report it.
      const shortPath = path.replace(/^https?:\/\/[^/]+/, "").slice(0, 80);
      toast.error("Server error", {
        description: `${shortPath || "An admin API"} returned ${status}. Please retry.`,
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
