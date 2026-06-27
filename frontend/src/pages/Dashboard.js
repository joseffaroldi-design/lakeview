import React, { useState, useEffect, useCallback, Suspense, lazy } from "react";
import {
  ArrowLeft, LogOut, Pencil, Megaphone, Users, Home, Image as ImageIcon,
  Briefcase,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import HomeTab from "@/pages/dashboard/HomeTab";

// Sprint 19 perf: lazy-load every non-landing tab + the heavy Promote modal.
const ContentEditor = lazy(() => import(/* webpackPrefetch: true */ "@/pages/ContentEditor").then(m => ({ default: m.ContentEditor })));
const MenuEditor    = lazy(() => import(/* webpackPrefetch: true */ "@/pages/ContentEditor").then(m => ({ default: m.MenuEditor })));
const AiAdsTab      = lazy(() => import(/* webpackPrefetch: true */ "@/pages/dashboard/AiAdsTab"));
const CustomersTab  = lazy(() => import(/* webpackPrefetch: true */ "@/pages/dashboard/CustomersTab"));
const LibraryTab    = lazy(() => import(/* webpackPrefetch: true */ "@/pages/dashboard/LibraryTab"));
const AnalyticsTab  = lazy(() => import(/* webpackPrefetch: true */ "@/pages/dashboard/AnalyticsTab"));
const WorkspaceTab  = lazy(() => import(/* webpackPrefetch: true */ "@/pages/dashboard/WorkspaceTab"));
const PromoteThisItem = lazy(() => import(/* webpackPrefetch: true */ "@/pages/dashboard/aiads/PromoteThisItem"));

const TabFallback = () => (
  <div className="py-16 text-center text-sm text-navy/50" data-testid="tab-loading">
    Loading…
  </div>
);

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Sprint 21 — Analytics hidden from pilot nav (code retained).
const TABS = [
  { id: "home",        label: "Home",       icon: Home },
  { id: "workspace",   label: "Workspace",  icon: Briefcase },
  { id: "menu",        label: "Menu",       icon: Pencil },
  { id: "promotions",  label: "Promote",    icon: Megaphone },
  { id: "library",     label: "Library",    icon: ImageIcon },
  { id: "customers",   label: "Customers",  icon: Users },
];

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState("home");
  const [authChecked, setAuthChecked] = useState(false);
  const [customersInitialFilter, setCustomersInitialFilter] = useState(null);
  const [promoteCtx, setPromoteCtx] = useState(null);
  const navigate = useNavigate();

  const getAuthHeader = useCallback(() => {
    const token = localStorage.getItem("admin_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("admin_token");
    if (!token) { navigate("/login"); return; }
    (async () => {
      try {
        await axios.get(`${API}/auth/verify`, { headers: { Authorization: `Bearer ${token}` } });
        setAuthChecked(true);
      } catch (err) {
        localStorage.removeItem("admin_token");
        navigate("/login");
      }
    })();
  }, [navigate]);

  const handleLogout = async () => {
    try { await axios.post(`${API}/auth/logout`, {}, { headers: getAuthHeader() }); }
    catch (err) { console.error("Error logging out:", err); }
    localStorage.removeItem("admin_token");
    navigate("/login");
  };

  const switchTab = (tab, subTab) => {
    setActiveTab(tab);
    if (tab === "customers") setCustomersInitialFilter(subTab || null);
  };

  const openPromote = (item, category) => {
    if (!item) return;
    setPromoteCtx({ item, category: category || "" });
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
      {/* Glass top bar */}
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
                Lakeview <span className="text-gold">·</span> Studio
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

          {/* Tab strip */}
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
                  onClick={() => setActiveTab(tab.id)}
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
          <HomeTab getAuthHeader={getAuthHeader} onNavigate={switchTab} onPromote={openPromote} />
        )}
        {activeTab === "menu" && (
          <Suspense fallback={<TabFallback />}>
            <section data-testid="menu-tab">
              <header className="mb-8">
                <p className="ds-eyebrow mb-1">Menu &amp; site content</p>
                <h2 className="ds-display text-3xl sm:text-4xl">Edit your menu</h2>
                <p className="text-sm text-navy/60 mt-2 max-w-xl">
                  Update dishes, hero copy, gallery, and page content. Use the sparkle ✨ button on any dish to launch a flyer in one click.
                </p>
              </header>
              <div className="space-y-10">
                <MenuEditor
                  getAuthHeader={getAuthHeader}
                  onPromoteDeepLink={() => setActiveTab("promotions")}
                />
                <div className="pt-8 border-t border-navy/10">
                  <p className="ds-eyebrow mb-1">Site content</p>
                  <h3 className="ds-display text-xl sm:text-2xl mb-4">Public website copy</h3>
                  <ContentEditor getAuthHeader={getAuthHeader} />
                </div>
              </div>
            </section>
          </Suspense>
        )}
        {activeTab === "promotions" && (
          <Suspense fallback={<TabFallback />}>
            <AiAdsTab getAuthHeader={getAuthHeader} />
          </Suspense>
        )}
        {activeTab === "workspace" && (
          <Suspense fallback={<TabFallback />}>
            <WorkspaceTab getAuthHeader={getAuthHeader} onPromote={openPromote} />
          </Suspense>
        )}
        {activeTab === "library" && (
          <Suspense fallback={<TabFallback />}>
            <LibraryTab getAuthHeader={getAuthHeader}
              onRequestNavigate={(tab) => setActiveTab(tab === "promote" ? "promotions" : tab)} />
          </Suspense>
        )}
        {activeTab === "customers" && (
          <Suspense fallback={<TabFallback />}>
            <CustomersTab getAuthHeader={getAuthHeader} initialFilter={customersInitialFilter} />
          </Suspense>
        )}
        {activeTab === "analytics" && (
          <Suspense fallback={<TabFallback />}>
            <AnalyticsTab getAuthHeader={getAuthHeader} onSwitchTab={switchTab} />
          </Suspense>
        )}
      </main>

      {promoteCtx ? (
        <Suspense fallback={<TabFallback />}>
          <PromoteThisItem
            mode="modal"
            getAuthHeader={getAuthHeader}
            initialMenuItem={promoteCtx.item ? {
              item_key: `${(promoteCtx.category && promoteCtx.category.slug) || "menu"}::${(promoteCtx.item.name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`,
              name: promoteCtx.item.name,
              description: promoteCtx.item.description,
              price: promoteCtx.item.price,
              category_slug: promoteCtx.category && promoteCtx.category.slug,
              category_display_name: promoteCtx.category && (promoteCtx.category.display_name || promoteCtx.category.name),
            } : null}
            onClose={() => setPromoteCtx(null)}
          />
        </Suspense>
      ) : null}
    </div>
  );
};

export default Dashboard;
