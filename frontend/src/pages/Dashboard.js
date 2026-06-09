import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft, BarChart3, LogOut, Pencil, Megaphone, Users, Sparkles, Home, Settings as SettingsIcon,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { ContentEditor, MenuEditor } from "@/pages/ContentEditor";
import AnalyticsTab from "@/pages/dashboard/AnalyticsTab";
import AiAdsTab from "@/pages/dashboard/AiAdsTab";
import HomeTab from "@/pages/dashboard/HomeTab";
import CustomersTab from "@/pages/dashboard/CustomersTab";
import { PromoteItemModal } from "@/pages/dashboard/aiads/PromoteItemModal";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Phase 9 — collapsed from 10 → 6 top-level tabs.
const TABS = [
  { id: "home",        label: "Home",       icon: Home },
  { id: "menu",        label: "Menu",       icon: Pencil },
  { id: "promotions",  label: "Promotions", icon: Megaphone },
  { id: "customers",   label: "Customers",  icon: Users },
  { id: "insights",    label: "Insights",   icon: BarChart3 },
  { id: "settings",    label: "Settings",   icon: SettingsIcon },
];

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState("home");
  const [authChecked, setAuthChecked] = useState(false);
  const [aiAdsInitialSubTab, setAiAdsInitialSubTab] = useState(null);
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

  const [promoteCtxLocal] = useState(null);  // placeholder retained for compatibility
  void promoteCtxLocal;

  const switchTab = (tab, subTab) => {
    setActiveTab(tab);
    if (tab === "promotions" || tab === "settings" || tab === "insights") {
      setAiAdsInitialSubTab(subTab || null);
    }
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
          <section>
            <h2 className="font-serif text-2xl text-navy font-bold mb-2 flex items-center gap-2">
              <Pencil className="w-6 h-6 text-gold" /> Menu & Site Content
            </h2>
            <p className="text-sm text-muted-foreground mb-6">Edit your menu, hero, gallery, and page copy in one place.</p>
            <div className="space-y-8">
              <MenuEditor getAuthHeader={getAuthHeader} />
              <div className="border-t-2 border-navy/10 pt-6">
                <h3 className="font-serif text-lg text-navy font-bold mb-4">Site Content</h3>
                <ContentEditor getAuthHeader={getAuthHeader} />
              </div>
            </div>
          </section>
        )}
        {activeTab === "promotions" && (
          <AiAdsTab
            getAuthHeader={getAuthHeader}
            initialSubTab={aiAdsInitialSubTab}
            group="promotions"
            title="Promotions"
            icon={Megaphone}
            hideStats={false}
          />
        )}
        {activeTab === "customers" && (
          <CustomersTab getAuthHeader={getAuthHeader} initialFilter={customersInitialFilter} />
        )}
        {activeTab === "insights" && (
          <section>
            <AnalyticsTab getAuthHeader={getAuthHeader} onSwitchTab={switchTab} />
            <div className="border-t-2 border-navy/10 mt-10 pt-8">
              <h3 className="font-serif text-xl text-navy font-bold mb-4 flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-gold" /> AI Marketing Performance
              </h3>
              <AiAdsTab getAuthHeader={getAuthHeader} group="insights" title=" " hideStats />
            </div>
          </section>
        )}
        {activeTab === "settings" && (
          <AiAdsTab
            getAuthHeader={getAuthHeader}
            initialSubTab={aiAdsInitialSubTab}
            group="settings"
            title="Settings"
            icon={SettingsIcon}
            hideStats
          />
        )}
      </main>

      {promoteCtx ? (
        <PromoteItemModal
          item={promoteCtx.item}
          category={promoteCtx.category}
          getAuthHeader={getAuthHeader}
          onClose={() => setPromoteCtx(null)}
        />
      ) : null}
    </div>
  );
};

export default Dashboard;
