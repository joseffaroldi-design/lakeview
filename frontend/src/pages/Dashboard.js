import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft, LogOut, Pencil, Megaphone, Users, Home, Image as ImageIcon, BarChart3,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { ContentEditor, MenuEditor } from "@/pages/ContentEditor";
import AiAdsTab from "@/pages/dashboard/AiAdsTab";
import HomeTab from "@/pages/dashboard/HomeTab";
import CustomersTab from "@/pages/dashboard/CustomersTab";
import LibraryTab from "@/pages/dashboard/LibraryTab";
import AnalyticsTab from "@/pages/dashboard/AnalyticsTab";
import PromoteThisItem from "@/pages/dashboard/aiads/PromoteThisItem";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Sprint 12D — 5 top tabs: Settings retired, Library promoted from a sub-tab.
const TABS = [
  { id: "home",        label: "Home",       icon: Home },
  { id: "menu",        label: "Menu",       icon: Pencil },
  { id: "promotions",  label: "Promote",    icon: Megaphone },
  { id: "library",     label: "Library",    icon: ImageIcon },
  { id: "customers",   label: "Customers",  icon: Users },
  { id: "analytics",   label: "Analytics",  icon: BarChart3 },
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
        )}
        {activeTab === "promotions" && (
          <AiAdsTab getAuthHeader={getAuthHeader} />
        )}
        {activeTab === "library" && (
          <LibraryTab getAuthHeader={getAuthHeader} />
        )}
        {activeTab === "customers" && (
          <CustomersTab getAuthHeader={getAuthHeader} initialFilter={customersInitialFilter} />
        )}
        {activeTab === "analytics" && (
          <AnalyticsTab getAuthHeader={getAuthHeader} onSwitchTab={switchTab} />
        )}
        {/* Sprint 12D: Settings tab retired */}
      </main>

      {promoteCtx ? (
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
      ) : null}
    </div>
  );
};

export default Dashboard;
