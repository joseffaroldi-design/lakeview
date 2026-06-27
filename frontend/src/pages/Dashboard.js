import React, { useState, useEffect, useCallback, Suspense, lazy } from "react";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft, LogOut, Pencil, Megaphone, Users, Home, Image as ImageIcon,
  Briefcase,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import HomeTab from "@/pages/dashboard/HomeTab";

// Sprint 19 perf: lazy-load every non-landing tab + the heavy Promote modal.
// First paint = HomeTab only; other chunks load on click → ~50% less JS on
// the critical path. Each chunk is webpackPrefetched so it warms in idle time.
const ContentEditor = lazy(() => import(/* webpackPrefetch: true */ "@/pages/ContentEditor").then(m => ({ default: m.ContentEditor })));
const MenuEditor    = lazy(() => import(/* webpackPrefetch: true */ "@/pages/ContentEditor").then(m => ({ default: m.MenuEditor })));
const AiAdsTab      = lazy(() => import(/* webpackPrefetch: true */ "@/pages/dashboard/AiAdsTab"));
const CustomersTab  = lazy(() => import(/* webpackPrefetch: true */ "@/pages/dashboard/CustomersTab"));
const LibraryTab    = lazy(() => import(/* webpackPrefetch: true */ "@/pages/dashboard/LibraryTab"));
const AnalyticsTab  = lazy(() => import(/* webpackPrefetch: true */ "@/pages/dashboard/AnalyticsTab"));
const WorkspaceTab  = lazy(() => import(/* webpackPrefetch: true */ "@/pages/dashboard/WorkspaceTab"));
const PromoteThisItem = lazy(() => import(/* webpackPrefetch: true */ "@/pages/dashboard/aiads/PromoteThisItem"));

const TabFallback = () => (
  <div className="py-12 text-center text-sm text-navy/60" data-testid="tab-loading">
    Loading…
  </div>
);

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Sprint 12D — 5 top tabs: Settings retired, Library promoted from a sub-tab.
// Launch Cleanup Sprint — Analytics hidden from pilot nav (code retained;
// route still works if accessed via switchTab('analytics')).
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
  const [promoteCtx, setPromoteCtx] = useState(null);  // {item, category}
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
        await axios.get(`${API}/auth/verify`, { headers: { Authorization: `Bearer ${token}` } });
        setAuthChecked(true);
      } catch (err) {
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
    setActiveTab(tab);
    if (tab === "customers") {
      setCustomersInitialFilter(subTab || null);
    }
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
    <div className="min-h-screen bg-cream">
      <header className="bg-navy text-cream py-6 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/" data-testid="back-to-site">
              <Button variant="outline" className="border-gold text-gold hover:bg-gold hover:text-navy">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Site
              </Button>
            </Link>
            <h1 className="font-serif text-2xl md:text-3xl font-bold">Dashboard</h1>
          </div>
          <Button
            variant="ghost"
            onClick={handleLogout}
            className="text-cream hover:text-gold"
            data-testid="logout-btn"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Logout
          </Button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div
          className="flex flex-wrap gap-2 mb-8 border-b-2 border-navy/10 pb-4"
          data-testid="dashboard-tabs"
        >
          {TABS.map((tab) => (
            <Button
              key={tab.id}
              data-testid={`tab-${tab.id}`}
              variant={activeTab === tab.id ? "default" : "outline"}
              onClick={() => setActiveTab(tab.id)}
              className={
                activeTab === tab.id
                  ? "bg-navy text-cream hover:bg-navy/90"
                  : "border-navy/20 text-navy hover:bg-navy/5"
              }
              size="sm"
            >
              <tab.icon className="w-4 h-4 mr-1.5" />
              {tab.label}
            </Button>
          ))}
        </div>

        {activeTab === "home" && (
          <HomeTab getAuthHeader={getAuthHeader} onNavigate={switchTab} onPromote={openPromote} />
        )}
        {activeTab === "menu" && (
          <Suspense fallback={<TabFallback />}>
            <section>
              <h2 className="font-serif text-2xl text-navy font-bold mb-2 flex items-center gap-2">
                <Pencil className="w-6 h-6 text-gold" /> Menu & Site Content
              </h2>
              <p className="text-sm text-muted-foreground mb-6">Edit your menu, hero, gallery, and page copy in one place.</p>
              <div className="space-y-8">
                <MenuEditor
                  getAuthHeader={getAuthHeader}
                  onPromoteDeepLink={() => setActiveTab("promotions")}
                />
                <div className="border-t-2 border-navy/10 pt-6">
                  <h3 className="font-serif text-lg text-navy font-bold mb-4">Site Content</h3>
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
        {/* Sprint 12D: Settings tab retired */}
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
