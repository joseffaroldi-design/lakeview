/**
 * AI Ads tab — top-level orchestrator with sub-tabs:
 * Campaign Builder · Social · Email · SMS · Image Studio · Video Studio · Library · Settings.
 * Lazy-loads catalog/stats and feeds them down to each module.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Sparkles, Share2, Mail, MessageSquare, Image as ImageIcon, Video as VideoIcon,
  Library as LibraryIcon, Settings as SettingsIcon, Wand2, BarChart3,
  Calendar as CalendarIcon, ListChecks, Link2, Repeat, UtensilsCrossed, Film,
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
import ContentCalendar from "./aiads/ContentCalendar";
import PublishQueue from "./aiads/PublishQueue";
import ProviderConnections from "./aiads/ProviderConnections";
import AutomationRules from "./aiads/AutomationRules";
import RestaurantAutomationCenter from "./aiads/RestaurantAutomationCenter";
import MediaStudio from "./aiads/MediaStudio";
import AiSettingsPanel from "./aiads/SettingsPanel";

const ALL_SUB_TABS = [
  { id: "automations", label: "Automations", icon: UtensilsCrossed, groups: ["promotions"] },
  { id: "media", label: "Media", icon: Film, groups: ["promotions"] },
  { id: "calendar", label: "Calendar", icon: CalendarIcon, groups: ["promotions"] },
  { id: "builder", label: "Campaign Builder", icon: Wand2, groups: ["advanced"] },
  { id: "library", label: "Library", icon: LibraryIcon, groups: ["advanced"] },
  { id: "social", label: "Social", icon: Share2, groups: ["advanced"] },
  { id: "email", label: "Email", icon: Mail, groups: ["advanced"] },
  { id: "sms", label: "SMS", icon: MessageSquare, groups: ["advanced"] },
  { id: "image", label: "Image Concepts", icon: ImageIcon, groups: ["advanced"] },
  { id: "video", label: "Video Concepts", icon: VideoIcon, groups: ["advanced"] },
  { id: "queue", label: "Queue", icon: ListChecks, groups: ["advanced"] },
  { id: "rules", label: "Rules", icon: Repeat, groups: ["settings"] },
  { id: "providers", label: "Providers", icon: Link2, groups: ["settings"] },
  { id: "analytics", label: "Analytics", icon: BarChart3, groups: ["insights", "advanced"] },
  { id: "settings", label: "Settings", icon: SettingsIcon, groups: ["settings"] },
];
const SUB_TABS = ALL_SUB_TABS;  // legacy alias — used when no group filter applied

const StatCard = ({ label, value, accent = "text-navy", testId }) => (
  <Card className="bg-card border-2 border-navy/10" data-testid={testId}>
    <CardContent className="py-3 px-4">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className={`text-2xl font-serif font-bold ${accent}`}>{value}</p>
    </CardContent>
  </Card>
);

export const AiAdsTab = ({ getAuthHeader, initialSubTab, group, title, icon: HeaderIcon, hideStats }) => {
  // group: undefined = all 15 tabs (legacy); "promotions" | "settings" | "insights" | "advanced" = slim
  const visibleTabs = group
    ? ALL_SUB_TABS.filter((t) => (t.groups || []).indexOf(group) !== -1)
    : ALL_SUB_TABS;
  const defaultSub = (visibleTabs[0] && visibleTabs[0].id) || "automations";
  const [activeSub, setActiveSub] = useState(initialSubTab || defaultSub);
  const [catalog, setCatalog] = useState({ templates: [], goals: [], platforms: [], tones: [] });
  const [stats, setStats] = useState({ total_campaigns: 0, ads_generated: 0, generations_this_month: 0, most_used_platform: null, most_used_goal: null });

  // Deep-link from parent — track via ref-in-effect to bypass set-state-in-effect rule
  const deepLinkRef = useRef({ last: null, setActiveSub });
  useEffect(() => { deepLinkRef.current = { last: deepLinkRef.current.last, setActiveSub }; });
  useEffect(() => {
    if (initialSubTab && initialSubTab !== deepLinkRef.current.last) {
      deepLinkRef.current.last = initialSubTab;
      deepLinkRef.current.setActiveSub(initialSubTab);
    }
  }, [initialSubTab]);

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

  // Settings orientation copy (Phase F)
  const SETTINGS_BLURB = {
    rules:     "Configure recurring marketing actions and triggers.",
    providers: "Connect social and marketing accounts (Facebook, Instagram, SendGrid, Twilio).",
    settings:  "Account and notification preferences.",
    analytics: "AI marketing performance over time.",
  };

  // Precomputed sub-tab buttons (avoids Babel plugin recursion)
  const tabBtns = [];
  for (let i = 0; i < visibleTabs.length; i += 1) {
    const t = visibleTabs[i];
    const isActive = activeSub === t.id;
    tabBtns.push(
      <Button
        key={t.id}
        data-testid={`ai-subtab-${t.id}`}
        variant={isActive ? "default" : "outline"}
        size="sm"
        onClick={() => setActiveSub(t.id)}
        className={`whitespace-nowrap shrink-0 ${isActive ? "bg-navy text-cream hover:bg-navy/90" : "border-navy/20 text-navy hover:bg-navy/5"}`}
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
          {HeaderIcon ? <HeaderIcon className="w-6 h-6 text-gold" /> : <Sparkles className="w-6 h-6 text-gold" />}
          {title || "AI Marketing Studio"}
        </h2>
      </div>

      {hideStats ? null : (
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
        <StatCard label="Total Campaigns" value={stats.total_campaigns} testId="ai-stat-campaigns" />
        <StatCard label="Ads Generated" value={stats.ads_generated} accent="text-gold" testId="ai-stat-generations" />
        <StatCard label="This Month" value={stats.generations_this_month} accent="text-forest" testId="ai-stat-month" />
        <StatCard label="Top Platform" value={stats.most_used_platform || "—"} testId="ai-stat-platform" />
        <StatCard label="Top Goal" value={stats.most_used_goal || "—"} testId="ai-stat-goal" />
      </div>
      )}

      <div
        className="flex gap-2 mb-6 border-b-2 border-navy/10 pb-4 overflow-x-auto -mx-2 px-2 md:flex-wrap md:overflow-x-visible md:mx-0 md:px-0"
        data-testid="ai-subtabs"
        style={{ scrollbarWidth: "thin" }}
      >
        {tabBtns}
      </div>

      {group === "settings" && SETTINGS_BLURB[activeSub] ? (
        <p className="text-xs text-muted-foreground mb-4 italic" data-testid="settings-blurb">{SETTINGS_BLURB[activeSub]}</p>
      ) : null}

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
      {activeSub === "calendar" && (
        <ContentCalendar getAuthHeader={getAuthHeader} />
      )}
      {activeSub === "queue" && (
        <PublishQueue getAuthHeader={getAuthHeader} />
      )}
      {activeSub === "automations" && (
        <RestaurantAutomationCenter getAuthHeader={getAuthHeader} />
      )}
      {activeSub === "media" && (
        <MediaStudio getAuthHeader={getAuthHeader} />
      )}
      {activeSub === "rules" && (
        <AutomationRules getAuthHeader={getAuthHeader} />
      )}
      {activeSub === "providers" && (
        <ProviderConnections getAuthHeader={getAuthHeader} />
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
