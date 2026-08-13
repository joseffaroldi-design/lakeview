import React from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import TemplateDesigner from "@/pages/TemplateDesigner";
import { PublicHome, PublicMenu } from "@/PublicSite";

const RootApp = () => (
  <div className="App" data-testid="app-container">
    <BrowserRouter>
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
