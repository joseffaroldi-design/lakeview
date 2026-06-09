/**
 * AI Ads tab — top-level orchestrator with sub-tabs:
 * Campaign Builder · Social · Email · SMS · Image Studio · Video Studio · Library · Settings.
 * Lazy-loads catalog/stats and feeds them down to each module.
 */
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Sparkles, Share2, Mail, MessageSquare, Image as ImageIcon, Video as VideoIcon,
  Library as LibraryIcon, Settings as SettingsIcon, Wand2, BarChart3,
} from "lucide-react";
import { API } from "./aiads/shared";
import CampaignBuilder from "./aiads/CampaignBuilder";
import SocialGenerator from "./aiads/SocialGenerator";
import EmailGenerator from "./aiads/EmailGenerator";
import SmsGenerator from "./aiads/SmsGenerator";
import ImageStudio from "./aiads/ImageStudio";
import VideoStudio from "./aiads/VideoStudio";
import CreativeLibrary from "./aiads/CreativeLibrary";
import AnalyticsDashboard from "./aiads/AnalyticsDashboard";
import AiSettingsPanel from "./aiads/SettingsPanel";

const SUB_TABS = [
  { id: "builder", label: "Campaign Builder", icon: Wand2 },
  { id: "social", label: "Social", icon: Share2 },
  { id: "email", label: "Email", icon: Mail },
  { id: "sms", label: "SMS", icon: MessageSquare },
  { id: "image", label: "Image Studio", icon: ImageIcon },
  { id: "video", label: "Video Studio", icon: VideoIcon },
  { id: "library", label: "Library", icon: LibraryIcon },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "settings", label: "Settings", icon: SettingsIcon },
];

const StatCard = ({ label, value, accent = "text-navy", testId }) => (
  <Card className="bg-card border-2 border-navy/10" data-testid={testId}>
    <CardContent className="py-3 px-4">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className={`text-2xl font-serif font-bold ${accent}`}>{value}</p>
    </CardContent>
  </Card>
);

export const AiAdsTab = ({ getAuthHeader }) => {
  const [activeSub, setActiveSub] = useState("builder");
  const [catalog, setCatalog] = useState({ templates: [], goals: [], platforms: [], tones: [] });
  const [stats, setStats] = useState({ total_campaigns: 0, ads_generated: 0, generations_this_month: 0, most_used_platform: null, most_used_goal: null });

  const loadBase = useCallback(async () => {
    try {
      const headers = getAuthHeader();
      const [t, s] = await Promise.all([
        axios.get(`${API}/ai-ads/templates?industry=restaurant`, { headers }),
        axios.get(`${API}/ai-ads/stats`, { headers }),
      ]);
      return { catalog: t.data, stats: s.data };
    } catch (e) {
      console.error("ai-ads init:", e);
      return null;
    }
  }, [getAuthHeader]);

  const refresh = useCallback(async () => {
    const d = await loadBase();
    if (!d) return;
    setCatalog(d.catalog);
    setStats(d.stats);
  }, [loadBase]);

  useEffect(() => {
    let mounted = true;
    loadBase().then((d) => {
      if (!mounted || !d) return;
      setCatalog(d.catalog);
      setStats(d.stats);
    });
    return () => { mounted = false; };
  }, [loadBase]);

  // Precomputed sub-tab buttons (avoids Babel plugin recursion)
  const tabBtns = [];
  for (let i = 0; i < SUB_TABS.length; i += 1) {
    const t = SUB_TABS[i];
    const isActive = activeSub === t.id;
    tabBtns.push(
      <Button
        key={t.id}
        data-testid={`ai-subtab-${t.id}`}
        variant={isActive ? "default" : "outline"}
        size="sm"
        onClick={() => setActiveSub(t.id)}
        className={isActive ? "bg-navy text-cream hover:bg-navy/90" : "border-navy/20 text-navy hover:bg-navy/5"}
      >
        <t.icon className="w-3.5 h-3.5 mr-1.5" />
        {t.label}
      </Button>
    );
  }

  return (
    <section data-testid="ai-ads-tab">
      <div className="flex items-center gap-2 mb-6">
        <h2 className="font-serif text-2xl text-navy font-bold flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-gold" />
          AI Marketing Studio
        </h2>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
        <StatCard label="Total Campaigns" value={stats.total_campaigns} testId="ai-stat-campaigns" />
        <StatCard label="Ads Generated" value={stats.ads_generated} accent="text-gold" testId="ai-stat-generations" />
        <StatCard label="This Month" value={stats.generations_this_month} accent="text-forest" testId="ai-stat-month" />
        <StatCard label="Top Platform" value={stats.most_used_platform || "—"} testId="ai-stat-platform" />
        <StatCard label="Top Goal" value={stats.most_used_goal || "—"} testId="ai-stat-goal" />
      </div>

      <div className="flex flex-wrap gap-2 mb-6 border-b-2 border-navy/10 pb-4" data-testid="ai-subtabs">
        {tabBtns}
      </div>

      {activeSub === "builder" && (
        <CampaignBuilder catalog={catalog} getAuthHeader={getAuthHeader} onChange={refresh} />
      )}
      {activeSub === "social" && (
        <SocialGenerator catalog={catalog} getAuthHeader={getAuthHeader} onSavedCount={refresh} />
      )}
      {activeSub === "email" && (
        <EmailGenerator catalog={catalog} getAuthHeader={getAuthHeader} onSavedCount={refresh} />
      )}
      {activeSub === "sms" && (
        <SmsGenerator catalog={catalog} getAuthHeader={getAuthHeader} onSavedCount={refresh} />
      )}
      {activeSub === "image" && (
        <ImageStudio catalog={catalog} getAuthHeader={getAuthHeader} onSavedCount={refresh} />
      )}
      {activeSub === "video" && (
        <VideoStudio catalog={catalog} getAuthHeader={getAuthHeader} onSavedCount={refresh} />
      )}
      {activeSub === "library" && (
        <CreativeLibrary getAuthHeader={getAuthHeader} />
      )}
      {activeSub === "analytics" && (
        <AnalyticsDashboard getAuthHeader={getAuthHeader} />
      )}
      {activeSub === "settings" && (
        <AiSettingsPanel getAuthHeader={getAuthHeader} />
      )}
    </section>
  );
};

export default AiAdsTab;
