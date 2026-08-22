import React, { useEffect } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import TemplateDesigner from "@/pages/TemplateDesigner";
import { PublicHome, PublicMenu } from "@/PublicSite";
import { initGA, pageview } from "@/lib/gaAnalytics";

// Public-only routes get GA4. Admin routes (/dashboard, /login,
// /template-designer) never load analytics or fire pageviews.
const isPublicPath = (path) => {
  if (!path) return true;
  return !(
    path.startsWith("/dashboard") ||
    path.startsWith("/login") ||
    path.startsWith("/template-designer")
  );
};

const AnalyticsListener = () => {
  const location = useLocation();
  useEffect(() => {
    if (!isPublicPath(location.pathname)) return;
    // initGA is idempotent — safe to call on every public navigation.
    initGA();
    pageview(location.pathname + location.search);
  }, [location.pathname, location.search]);
  return null;
};

const RootApp = () => (
  <div className="App" data-testid="app-container">
    <BrowserRouter>
      <AnalyticsListener />
      <Routes>
        <Route path="/" element={<PublicHome />} />
        <Route path="/menu" element={<PublicMenu />} />
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/template-designer" element={<TemplateDesigner />} />
      </Routes>
    </BrowserRouter>
  </div>
);

export default RootApp;
