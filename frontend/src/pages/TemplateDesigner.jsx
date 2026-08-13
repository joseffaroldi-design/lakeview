import React from "react";
import { Navigate } from "react-router-dom";

// Historical route retained so old bookmarks do not break. The standalone
// designer is intentionally retired; all staff work now starts in /dashboard.
export default function TemplateDesigner() {
  return <Navigate to="/dashboard" replace />;
}
