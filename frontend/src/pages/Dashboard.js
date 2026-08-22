import React, { useState, useEffect, useCallback, Suspense, lazy } from "react";
import {
  ArrowLeft, LogOut, Pencil, Users, Home, Image as ImageIcon, UtensilsCrossed, ImagePlus, BarChart3,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import HomeTab from "@/pages/dashboard/HomeTab";

const ContentEditor = lazy(() => import("@/pages/ContentEditor").then(m => ({ default: m.ContentEditor })));
const MenuEditor = lazy(() => import("@/pages/ContentEditor").then(m => ({ default: m.MenuEditor })));
const CustomersTab = lazy(() => import("@/pages/dashboard/CustomersTab"));
const LibraryTab = lazy(() => import("@/pages/dashboard/LibraryTab"));
const CateringTab = lazy(() => import("@/pages/dashboard/CateringTab").then(m => ({ default: m.CateringTab })));
const WebsiteImagesTab = lazy(() => import("@/pages/dashboard/WebsiteImagesTab"));
const AnalyticsTab = lazy(() => import("@/pages/dashboard/AnalyticsTab"));

const TabFallback = () => (
  <div className="py-16 text-center text-sm text-navy/50" data-testid="tab-loading">
    Loading…
  </div>
);

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TABS = [
  { id: "home", label: "Home", icon: Home },
  { id: "menu", label: "Menu & Website", icon: Pencil },
  { id: "images", label: "Website Images", icon: ImagePlus },
  { id: "library", label: "Library", icon: ImageIcon },
  { id: "customers", label: "Customers", icon: Users },
  { id: "catering", label: "Catering", icon: UtensilsCrossed },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
];

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState("home");
  const [authChecked, setAuthChecked] = useState(false);
  const [customersInitialFilter, setCustomersInitialFilter] = useState(null);
  const navigate = useNavigate();

  const getAuthHeader = useCallback(() => {
    const token = localStorage.getItem("admin_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("admin_token");
    if (!token) {
      navigate("/login");
      return;
    }

    (async () => {
      try {
        await axios.get(`${API}/auth/verify`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setAuthChecked(true);
      } catch {
        localStorage.removeItem("admin_token");
        navigate("/login");
      }
    })();
  }, [navigate]);

  const handleLogout = async () => {
    try {
      await axios.post(`${API}/auth/logout`, {}, { headers: getAuthHeader() });
    } catch (err) {
      console.error("Error logging out:", err);
    }
    localStorage.removeItem("admin_token");
    navigate("/login");
  };

  const switchTab = (tab, subTab) => {
    const allowed = new Set(TABS.map((item) => item.id));
    const safeTab = allowed.has(tab) ? tab : "home";
    setActiveTab(safeTab);
    if (safeTab === "customers") setCustomersInitialFilter(subTab || null);
  };

  if (!authChecked) {
    return (
      <div className="min-h-screen bg-cream flex items-center justify-center">
        <div className="text-navy font-serif text-xl">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="dashboard-shell min-h-screen" data-testid="dashboard-shell">
      <header className="ds-topnav sticky top-0 z-40" data-testid="dashboard-topbar">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="h-16 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link to="/" data-testid="back-to-site" className="ds-btn-secondary !py-1.5 !px-3 text-xs">
                <ArrowLeft className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Back to Site</span>
              </Link>
              <div className="hidden sm:block h-6 w-px bg-navy/10" />
              <div className="ds-display text-base sm:text-lg leading-none" style={{ fontWeight: 600 }}>
                Lakeview <span className="text-gold">·</span> Admin
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="ds-btn-secondary !py-1.5 !px-3 text-xs"
              data-testid="logout-btn"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>

          <nav
            className="ds-nav-scroll flex items-center gap-1 -mb-px overflow-x-auto pb-2 pt-1"
            data-testid="dashboard-tabs"
          >
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  data-testid={`tab-${tab.id}`}
                  onClick={() => switchTab(tab.id)}
                  className={`ds-tab whitespace-nowrap shrink-0 ${active ? "is-active" : ""}`}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        {activeTab === "home" && (
          <HomeTab onNavigate={switchTab} getAuthHeader={getAuthHeader} />
        )}

        {activeTab === "menu" && (
          <Suspense fallback={<TabFallback />}>
            <section data-testid="menu-tab">
              <header className="mb-8">
                <p className="ds-eyebrow mb-1">Restaurant basics</p>
                <h2 className="ds-display text-3xl sm:text-4xl">Menu &amp; website</h2>
                <p className="text-sm text-navy/60 mt-2 max-w-xl">
                  Update dishes, prices, descriptions and the public website copy from one place.
                </p>
              </header>

              <div className="space-y-10">
                <MenuEditor getAuthHeader={getAuthHeader} />
                <div className="pt-8 border-t border-navy/10">
                  <p className="ds-eyebrow mb-1">Website copy</p>
                  <h3 className="ds-display text-xl sm:text-2xl mb-4">Public restaurant information</h3>
                  <ContentEditor getAuthHeader={getAuthHeader} />
                </div>
              </div>
            </section>
          </Suspense>
        )}

        {activeTab === "library" && (
          <Suspense fallback={<TabFallback />}>
            <LibraryTab
              getAuthHeader={getAuthHeader}
              onRequestNavigate={(tab) => switchTab(tab)}
            />
          </Suspense>
        )}

        {activeTab === "images" && (
          <Suspense fallback={<TabFallback />}>
            <WebsiteImagesTab getAuthHeader={getAuthHeader} />
          </Suspense>
        )}

        {activeTab === "customers" && (
          <Suspense fallback={<TabFallback />}>
            <CustomersTab
              getAuthHeader={getAuthHeader}
              initialFilter={customersInitialFilter}
            />
          </Suspense>
        )}

        {activeTab === "catering" && (
          <Suspense fallback={<TabFallback />}>
            <CateringTab getAuthHeader={getAuthHeader} />
          </Suspense>
        )}

        {activeTab === "analytics" && (
          <Suspense fallback={<TabFallback />}>
            <AnalyticsTab getAuthHeader={getAuthHeader} onSwitchTab={switchTab} />
          </Suspense>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
