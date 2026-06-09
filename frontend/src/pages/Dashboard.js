import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft, BarChart3, Image as ImageIcon, LogOut, Mail,
  UtensilsCrossed, FileText, Pencil, Gift, CreditCard, Send, Sparkles,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { ContentEditor, MenuEditor } from "@/pages/ContentEditor";
import { GiveawayManager } from "@/pages/GiveawayManager";
import { LoyaltyManager, MessagingDashboard } from "@/pages/LoyaltyMessaging";
import AnalyticsTab from "@/pages/dashboard/AnalyticsTab";
import SpecialsTab from "@/pages/dashboard/SpecialsTab";
import CateringTab from "@/pages/dashboard/CateringTab";
import SubscribersTab from "@/pages/dashboard/SubscribersTab";
import AiAdsTab from "@/pages/dashboard/AiAdsTab";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TABS = [
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "specials", label: "Specials", icon: ImageIcon },
  { id: "content", label: "Site Content", icon: FileText },
  { id: "menu", label: "Menu Editor", icon: Pencil },
  { id: "giveaway", label: "Giveaway", icon: Gift },
  { id: "loyalty", label: "Loyalty", icon: CreditCard },
  { id: "messaging", label: "Messages", icon: Send },
  { id: "inquiries", label: "Inquiries", icon: UtensilsCrossed },
  { id: "subscribers", label: "Subscribers", icon: Mail },
  { id: "ai-ads", label: "AI Ads", icon: Sparkles },
];

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState("analytics");
  const [authChecked, setAuthChecked] = useState(false);
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

        {activeTab === "analytics" && <AnalyticsTab getAuthHeader={getAuthHeader} />}
        {activeTab === "specials" && <SpecialsTab getAuthHeader={getAuthHeader} />}
        {activeTab === "content" && (
          <section>
            <h2 className="font-serif text-2xl text-navy font-bold mb-6 flex items-center gap-2">
              <FileText className="w-6 h-6 text-gold" />
              Edit Site Content
            </h2>
            <ContentEditor getAuthHeader={getAuthHeader} />
          </section>
        )}
        {activeTab === "menu" && (
          <section>
            <h2 className="font-serif text-2xl text-navy font-bold mb-6 flex items-center gap-2">
              <Pencil className="w-6 h-6 text-gold" />
              Edit Menu
            </h2>
            <MenuEditor getAuthHeader={getAuthHeader} />
          </section>
        )}
        {activeTab === "giveaway" && (
          <section>
            <h2 className="font-serif text-2xl text-navy font-bold mb-6 flex items-center gap-2">
              <Gift className="w-6 h-6 text-gold" />
              Summer Giveaway
            </h2>
            <GiveawayManager getAuthHeader={getAuthHeader} />
          </section>
        )}
        {activeTab === "loyalty" && (
          <section>
            <h2 className="font-serif text-2xl text-navy font-bold mb-6 flex items-center gap-2">
              <CreditCard className="w-6 h-6 text-gold" />
              Loyalty Program
            </h2>
            <LoyaltyManager getAuthHeader={getAuthHeader} />
          </section>
        )}
        {activeTab === "messaging" && (
          <section>
            <h2 className="font-serif text-2xl text-navy font-bold mb-6 flex items-center gap-2">
              <Send className="w-6 h-6 text-gold" />
              Message Blasts
            </h2>
            <MessagingDashboard getAuthHeader={getAuthHeader} />
          </section>
        )}
        {activeTab === "inquiries" && <CateringTab getAuthHeader={getAuthHeader} />}
        {activeTab === "subscribers" && <SubscribersTab getAuthHeader={getAuthHeader} />}
        {activeTab === "ai-ads" && <AiAdsTab getAuthHeader={getAuthHeader} />}
      </main>
    </div>
  );
};

export default Dashboard;
