import React, { useEffect, useState } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  BarChart3, TrendingUp, Calendar, Users, Monitor, Smartphone, Tablet,
  Globe, Clock, MousePointer, Pencil, ImageIcon, Sparkles, Send, Link2,
  CalendarDays, ListChecks,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const QUICK_ACTIONS = [
  { id: "menu", icon: Pencil, label: "Edit Menu", help: "Add or update menu items", tab: "menu" },
  { id: "special", icon: ImageIcon, label: "Create Special", help: "Run a daily / weekly promo", tab: "specials" },
  { id: "promote", icon: Sparkles, label: "Promote Item", help: "AI campaign for any menu item", tab: "ai-ads", subTab: "automations" },
  { id: "schedule", icon: CalendarDays, label: "Schedule Posts", help: "Open the content calendar", tab: "ai-ads", subTab: "calendar" },
  { id: "queue", icon: ListChecks, label: "Publish Queue", help: "What's queued / published", tab: "ai-ads", subTab: "queue" },
  { id: "providers", icon: Link2, label: "Connect Providers", help: "Facebook · IG · SendGrid · Twilio", tab: "ai-ads", subTab: "providers" },
];

const QuickActionsStrip = ({ onJump }) => {
  const tiles = [];
  for (let i = 0; i < QUICK_ACTIONS.length; i += 1) {
    const a = QUICK_ACTIONS[i];
    tiles.push(
      <button
        key={a.id}
        type="button"
        onClick={() => onJump(a.tab, a.subTab)}
        className="bg-card border-2 border-navy/10 hover:border-gold rounded-lg p-3 text-left transition-colors"
        data-testid={`quick-${a.id}`}
      >
        <a.icon className="w-5 h-5 text-gold mb-1.5" />
        <p className="font-serif font-semibold text-navy text-sm">{a.label}</p>
        <p className="text-[10px] text-muted-foreground leading-tight">{a.help}</p>
      </button>
    );
  }
  return (
    <section className="mb-8" data-testid="owner-quick-actions">
      <h2 className="font-serif text-base text-navy font-semibold mb-3 flex items-center gap-2 uppercase tracking-wider">
        <Sparkles className="w-4 h-4 text-gold" /> Owner Quick Start
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">{tiles}</div>
    </section>
  );
};

export const AnalyticsTab = ({ getAuthHeader, onSwitchTab }) => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await axios.get(`${API}/analytics`, { headers: getAuthHeader() });
        if (mounted) setAnalytics(res.data);
      } catch (err) {
        console.error("Error fetching analytics:", err);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [getAuthHeader]);

  if (loading) {
    return <p className="text-muted-foreground">Loading analytics…</p>;
  }

  return (
    <>
      {onSwitchTab ? <QuickActionsStrip onJump={onSwitchTab} /> : null}
      <section className="mb-12">
        <h2 className="font-serif text-2xl text-navy font-bold mb-6 flex items-center gap-2">
          <BarChart3 className="w-6 h-6 text-gold" />
          Website Analytics
        </h2>

        {/* Main Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          <Card className="bg-card border-2 border-navy/10" data-testid="analytics-total">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-xs font-sans text-muted-foreground">Total Views</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <div className="text-2xl font-serif font-bold text-navy">{analytics?.total_views || 0}</div>
            </CardContent>
          </Card>

          <Card className="bg-card border-2 border-navy/10" data-testid="analytics-today">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-xs font-sans text-muted-foreground flex items-center gap-1">
                <Calendar className="w-3 h-3" /> Today
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <div className="text-2xl font-serif font-bold text-forest">{analytics?.views_today || 0}</div>
            </CardContent>
          </Card>

          <Card className="bg-card border-2 border-navy/10" data-testid="analytics-week">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-xs font-sans text-muted-foreground flex items-center gap-1">
                <TrendingUp className="w-3 h-3" /> This Week
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <div className="text-2xl font-serif font-bold text-gold">{analytics?.views_this_week || 0}</div>
            </CardContent>
          </Card>

          <Card className="bg-card border-2 border-navy/10" data-testid="analytics-month">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-xs font-sans text-muted-foreground">This Month</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <div className="text-2xl font-serif font-bold text-navy">{analytics?.views_this_month || 0}</div>
            </CardContent>
          </Card>

          <Card className="bg-card border-2 border-navy/10" data-testid="analytics-sessions">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-xs font-sans text-muted-foreground flex items-center gap-1">
                <Users className="w-3 h-3" /> Unique Visitors
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <div className="text-2xl font-serif font-bold text-forest">{analytics?.unique_sessions || 0}</div>
            </CardContent>
          </Card>

          <Card className="bg-card border-2 border-navy/10" data-testid="analytics-avg-pages">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-xs font-sans text-muted-foreground">Avg Pages/Visit</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <div className="text-2xl font-serif font-bold text-gold">{analytics?.avg_pages_per_session || 0}</div>
            </CardContent>
          </Card>

          <Card className="bg-card border-2 border-gold/30" data-testid="analytics-pwa-installs">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-xs font-sans text-muted-foreground flex items-center gap-1">
                <Smartphone className="w-3 h-3" /> PWA Installs
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <div className="text-2xl font-serif font-bold text-gold">
                {analytics?.button_clicks?.pwa_install_completed || 0}
              </div>
              <p className="text-[10px] font-sans text-muted-foreground mt-1">
                {analytics?.button_clicks?.pwa_install_accepted || 0} accepted · {analytics?.button_clicks?.pwa_install_dismissed || 0} dismissed
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Detailed Analytics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <Card className="bg-card border-2 border-navy/10">
            <CardHeader>
              <CardTitle className="font-serif text-navy flex items-center gap-2">
                <Monitor className="w-5 h-5 text-gold" /> Devices
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {analytics?.device_breakdown && Object.keys(analytics.device_breakdown).length > 0 ? (
                  Object.entries(analytics.device_breakdown).map(([device, count]) => (
                    <div key={device} className="flex justify-between items-center">
                      <span className="font-sans text-muted-foreground capitalize flex items-center gap-2">
                        {device === "desktop" && <Monitor className="w-4 h-4" />}
                        {device === "mobile" && <Smartphone className="w-4 h-4" />}
                        {device === "tablet" && <Tablet className="w-4 h-4" />}
                        {device}
                      </span>
                      <span className="font-sans font-bold text-navy">{count}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-muted-foreground text-sm">No data yet</p>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-2 border-navy/10">
            <CardHeader>
              <CardTitle className="font-serif text-navy flex items-center gap-2">
                <Globe className="w-5 h-5 text-gold" /> Browsers
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {analytics?.browser_breakdown && Object.keys(analytics.browser_breakdown).length > 0 ? (
                  Object.entries(analytics.browser_breakdown).map(([browser, count]) => (
                    <div key={browser} className="flex justify-between items-center">
                      <span className="font-sans text-muted-foreground">{browser}</span>
                      <span className="font-sans font-bold text-navy">{count}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-muted-foreground text-sm">No data yet</p>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-2 border-navy/10">
            <CardHeader>
              <CardTitle className="font-serif text-navy">Page Views</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {analytics?.page_breakdown && Object.keys(analytics.page_breakdown).length > 0 ? (
                  Object.entries(analytics.page_breakdown).map(([page, count]) => (
                    <div key={page} className="flex justify-between items-center">
                      <span className="font-sans text-muted-foreground capitalize">{page}</span>
                      <span className="font-sans font-bold text-navy">{count}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-muted-foreground text-sm">No data yet</p>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-2 border-navy/10">
            <CardHeader>
              <CardTitle className="font-serif text-navy flex items-center gap-2">
                <Calendar className="w-5 h-5 text-gold" /> Daily Views (This Week)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {analytics?.daily_views_week && Object.keys(analytics.daily_views_week).length > 0 ? (
                  Object.entries(analytics.daily_views_week).map(([day, count]) => (
                    <div key={day} className="flex justify-between items-center">
                      <span className="font-sans text-muted-foreground">{day}</span>
                      <div className="flex items-center gap-2">
                        <div className="h-2 bg-gold rounded-full" style={{ width: `${Math.max(count * 10, 4)}px` }} />
                        <span className="font-sans font-bold text-navy w-8 text-right">{count}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-muted-foreground text-sm">No data yet</p>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-2 border-navy/10">
            <CardHeader>
              <CardTitle className="font-serif text-navy flex items-center gap-2">
                <Clock className="w-5 h-5 text-gold" /> Today by Hour
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end justify-between h-24 gap-1">
                {analytics?.hourly_views_today &&
                  Object.entries(analytics.hourly_views_today)
                    .filter(([hour]) => parseInt(hour) >= 8 && parseInt(hour) <= 23)
                    .map(([hour, count]) => (
                      <div key={hour} className="flex flex-col items-center flex-1">
                        <div className="w-full bg-gold rounded-t" style={{ height: `${Math.max(count * 8, 2)}px` }} />
                        <span className="text-xs text-muted-foreground mt-1">{hour}</span>
                      </div>
                    ))}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-2 border-navy/10">
            <CardHeader>
              <CardTitle className="font-serif text-navy flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-gold" /> Top Referrers
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {analytics?.top_referrers && Object.keys(analytics.top_referrers).length > 0 ? (
                  Object.entries(analytics.top_referrers).map(([referrer, count]) => (
                    <div key={referrer} className="flex justify-between items-center">
                      <span className="font-sans text-muted-foreground text-sm truncate max-w-[180px]">{referrer}</span>
                      <span className="font-sans font-bold text-navy">{count}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-muted-foreground text-sm">No referrer data yet</p>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-2 border-navy/10">
            <CardHeader>
              <CardTitle className="font-serif text-navy flex items-center gap-2">
                <MousePointer className="w-5 h-5 text-gold" /> Button Clicks (All Time)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {analytics?.button_clicks && Object.keys(analytics.button_clicks).length > 0 ? (
                  Object.entries(analytics.button_clicks).map(([button, count]) => (
                    <div key={button} className="flex justify-between items-center">
                      <span className="font-sans text-muted-foreground capitalize">{button.replace(/_/g, " ")}</span>
                      <span className="font-sans font-bold text-navy">{count}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-muted-foreground text-sm">No button clicks yet</p>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-2 border-navy/10">
            <CardHeader>
              <CardTitle className="font-serif text-navy flex items-center gap-2">
                <MousePointer className="w-5 h-5 text-gold" /> Button Clicks (Today)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {analytics?.button_clicks_today && Object.keys(analytics.button_clicks_today).length > 0 ? (
                  Object.entries(analytics.button_clicks_today).map(([button, count]) => (
                    <div key={button} className="flex justify-between items-center">
                      <span className="font-sans text-muted-foreground capitalize">{button.replace(/_/g, " ")}</span>
                      <span className="font-sans font-bold text-forest">{count}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-muted-foreground text-sm">No clicks today</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </>
  );
};

export default AnalyticsTab;
