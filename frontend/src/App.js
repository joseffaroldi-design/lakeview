import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import TemplateDesigner from "@/pages/TemplateDesigner";
import PublicSite from "@/pages/PublicSite";
// Sprint 12D: SpinWheel + InstallPrompt removed

// Main App Component
function App() {
  return (
    <div className="App" data-testid="app-container">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<PublicSite />} />
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/template-designer" element={<TemplateDesigner />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
