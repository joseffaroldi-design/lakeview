import React from "react";
import ReactDOM from "react-dom/client";
import axios from "axios";
import { toast } from "sonner";
import "@/index.css";
import App from "@/App";
import ErrorBoundary from "@/components/ErrorBoundary";
import { Toaster } from "@/components/ui/sonner";

// ---- Global axios interceptor: surface auth + server errors instead of silent failure ----
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response && error.response.status;
    const path = (error.config && error.config.url) || "";
    // Ignore auth-probe endpoints we expect to fail.
    const isAuthEndpoint = path.includes("/auth/login");
    if (status === 401 && !isAuthEndpoint) {
      try { localStorage.removeItem("admin_token"); } catch (_) { /* noop */ }
      toast.error("Session expired", {
        description: "Please log in again.",
        action: { label: "Sign in", onClick: () => { window.location.href = "/login"; } },
      });
    } else if (status === 403 && !isAuthEndpoint) {
      toast.error("Access denied", { description: "You don't have permission for that action." });
    } else if (status >= 500) {
      toast.error("Server error", { description: "Something broke on our side. Please retry." });
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
