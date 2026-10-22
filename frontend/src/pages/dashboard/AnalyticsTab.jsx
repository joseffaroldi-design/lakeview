import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Activity, BarChart3, Calendar, Clock, Globe, ImageIcon, Monitor,
  MousePointer, Pencil, RefreshCw, Smartphone, Sparkles, Tablet,
  Target, TrendingUp, Users,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const RANGE_OPTIONS = [7, 30, 90, 180];

const QUICK_ACTIONS = [
  { id: "menu", icon: Pencil, label: "Edit Menu", help: "Add or update menu items", tab: "menu" },
  { id: "promote", icon: Sparkles, label: "Promote Item", help: "AI campaign for any menu item", tab: "promotions" },
  { id: "library", icon: ImageIcon, label: "Media Library", help: "Browse photos and assets", tab: "library" },
  { id: "customers", icon: Users, label: "Customers", help: "Subscribers, loyalty, inquiries", tab: "customers" },
  { id: "home", icon: BarChart3, label: "Back to Home", help: "Daily check-in dashboard", tab: "home" },
];

const labelize = (value) => String(value || "Unknown")
  .replace(/^https?:\/\//, "")
  .replace(/_/g, " ")
  .replace(/\b\w/g, (character) => character.toUpperCase());
const number = (value) => Number(value || 0).toLocaleString();

const QuickActionsStrip = ({ onJump }) => (
  <section className="mb-8" data-testid="owner-quick-actions">
    <h2 className="font-serif text-base text-navy font-semibold mb-3 flex items-center gap-2 uppercase tracking-wider">
      <Sparkles className="w-4 h-4 text-gold" /> Owner Quick Start
    </h2>
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
      {QUICK_ACTIONS.map((action) => (
        <button key={action.id} type="button" onClick={() => onJump(action.tab, action.subTab)} className="bg-card border-2 border-navy/10 hover:border-gold rounded-lg p-3 text-left transition-colors" data-testid={`quick-${action.id}`}>
          <action.icon className="w-5 h-5 text-gold mb-1.5" />
          <p className="font-serif font-semibold text-navy text-sm">{action.label}</p>
          <p className="text-[10px] text-muted-foreground leading-tight">{action.help}</p>
        </button>
      ))}
    </div>
  </section>
);

const MetricCard = ({ label, value, note, icon: Icon = Activity, accent = "text-navy", testId }) => (
  <Card className="bg-card border-2 border-navy/10" data-testid={testId}>
    <CardHeader className="pb-2 pt-4 px-4">
      <CardTitle className="text-xs font-sans text-muted-foreground flex items-center gap-1.5"><Icon className="w-3.5 h-3.5" /> {label}</CardTitle>
    </CardHeader>
    <CardContent className="px-4 pb-4">
      <div className={`text-2xl font-serif font-bold ${accent}`}>{value}</div>
      {note ? <p className="text-[10px] font-sans text-muted-foreground mt-1 leading-snug">{note}</p> : null}
    </CardContent>
  </Card>
);

const BreakdownCard = ({ title, data, icon: Icon = BarChart3, empty = "No data yet", maxItems = 10 }) => {
  const entries = Object.entries(data || {}).slice(0, maxItems);
  const peak = Math.max(...entries.map(([, count]) => Number(count)), 1);
  return (
    <Card className="bg-card border-2 border-navy/10 min-w-0">
      <CardHeader className="pb-3"><CardTitle className="font-serif text-navy flex items-center gap-2 text-base"><Icon className="w-4 h-4 text-gold shrink-0" /> {title}</CardTitle></CardHeader>
      <CardContent>
        {entries.length ? <div className="space-y-3">{entries.map(([key, count]) => (
          <div key={key}>
            <div className="flex justify-between gap-3 items-center text-sm"><span className="font-sans text-muted-foreground truncate" title={key}>{labelize(key)}</span><span className="font-sans font-bold text-navy shrink-0">{number(count)}</span></div>
            <div className="h-1.5 bg-navy/5 rounded-full mt-1 overflow-hidden"><div className="h-full bg-gold rounded-full" style={{ width: `${Math.max((Number(count) / peak) * 100, 3)}%` }} /></div>
          </div>
        ))}</div> : <p className="text-muted-foreground text-sm">{empty}</p>}
      </CardContent>
    </Card>
  );
};

const TrendCard = ({ label, value, change }) => {
  const direction = Number(change) > 0 ? "+" : "";
  const color = Number(change) > 0 ? "text-forest" : Number(change) < 0 ? "text-red-700" : "text-muted-foreground";
  return (
    <div className="rounded-lg border border-navy/10 bg-card px-4 py-3 flex items-center justify-between gap-4">
      <div><p className="text-xs text-muted-foreground">{label}</p><p className="font-serif font-bold text-xl text-navy">{number(value)}</p></div>
      <span className={`text-xs font-bold ${color}`}>{direction}{Number(change || 0).toFixed(1)}%</span>
    </div>
  );
};

export const AnalyticsTab = ({ getAuthHeader, onSwitchTab }) => {
  const [analytics, setAnalytics] = useState(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await axios.get(`${API}/analytics?days=${days}`, { headers: getAuthHeader() });
      setAnalytics(response.data);
    } catch (err) {
      console.error("Error fetching analytics:", err);
      setError(err?.response?.data?.detail || "Analytics could not be loaded. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [days, getAuthHeader]);

  useEffect(() => { loadAnalytics(); }, [loadAnalytics]);

  const dailyEntries = useMemo(() => Object.entries(analytics?.daily_views || {}), [analytics]);
  const dailyPeak = Math.max(...dailyEntries.map(([, count]) => Number(count)), 1);
  const outcomes = analytics?.business_outcomes || {};
  const funnel = analytics?.conversion_funnel || {};
  const engagement = analytics?.engagement || {};

  return (
    <>
      {onSwitchTab ? <QuickActionsStrip onJump={onSwitchTab} /> : null}
      <section className="mb-12" data-testid="analytics-dashboard">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
          <div>
            <h2 className="font-serif text-2xl text-navy font-bold flex items-center gap-2"><BarChart3 className="w-6 h-6 text-gold" /> Website Analytics</h2>
            <p className="text-xs text-muted-foreground mt-1">First-party reports · America/Chicago · no customer PII</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {RANGE_OPTIONS.map((option) => <button key={option} type="button" onClick={() => setDays(option)} className={`px-3 py-1.5 rounded-md text-xs font-semibold border transition-colors ${days === option ? "bg-navy text-white border-navy" : "bg-card text-navy border-navy/15 hover:border-gold"}`}>{option} days</button>)}
            <button type="button" onClick={loadAnalytics} disabled={loading} className="p-2 rounded-md border border-navy/15 text-navy hover:border-gold disabled:opacity-50" aria-label="Refresh analytics"><RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /></button>
          </div>
        </div>

        {error ? <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div> : null}
        {loading && !analytics ? <p className="text-muted-foreground">Loading analytics…</p> : null}

        {analytics ? <>
          <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3 mb-6">
            <MetricCard label={`Visitors · ${days}d`} value={number(analytics.unique_visitors_range)} icon={Users} accent="text-forest" testId="analytics-visitors" />
            <MetricCard label={`Sessions · ${days}d`} value={number(analytics.sessions_range)} icon={Activity} testId="analytics-sessions-range" />
            <MetricCard label="All-time Views" value={number(analytics.total_views)} icon={BarChart3} testId="analytics-total" />
            <MetricCard label="Order Intent" value={`${analytics.conversion_rates?.order_intent_rate || 0}%`} note="Pickup, delivery or phone action" icon={Target} accent="text-gold" />
            <MetricCard label="Bounce Rate" value={`${analytics.bounce_rate || 0}%`} note="Single-page sessions" icon={TrendingUp} />
            <MetricCard label="Avg Engagement" value={`${engagement.average_seconds || 0}s`} note={`${engagement.average_scroll_depth || 0}% average scroll depth`} icon={Clock} accent="text-forest" />
            <MetricCard label="Pages / Visit" value={analytics.avg_pages_per_session || 0} icon={MousePointer} accent="text-gold" testId="analytics-avg-pages" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-8">
            <TrendCard label="Views today" value={analytics.views_today} change={analytics.trends?.today_vs_yesterday} />
            <TrendCard label="Views this week" value={analytics.views_this_week} change={analytics.trends?.week_vs_previous} />
            <TrendCard label="Views this month" value={analytics.views_this_month} change={analytics.trends?.month_vs_previous} />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-8">
            <Card className="bg-card border-2 border-navy/10 xl:col-span-2">
              <CardHeader><CardTitle className="font-serif text-navy flex items-center gap-2"><Calendar className="w-5 h-5 text-gold" /> Daily Traffic · Last {days} Days</CardTitle></CardHeader>
              <CardContent><div className="h-48 flex items-end gap-1 overflow-x-auto pb-6">
                {dailyEntries.map(([date, count], index) => <div key={date} className="flex flex-col justify-end items-center min-w-[10px] flex-1 h-full group relative" title={`${date}: ${count} views`}>
                  <span className="opacity-0 group-hover:opacity-100 absolute -top-4 text-[9px] font-bold text-navy bg-white border rounded px-1 z-10">{count}</span>
                  <div className="w-full max-w-5 bg-gold rounded-t-sm" style={{ height: `${Math.max((Number(count) / dailyPeak) * 100, count ? 4 : 1)}%` }} />
                  {(index === 0 || index === dailyEntries.length - 1 || (days <= 30 && index % 7 === 0)) ? <span className="absolute -bottom-5 text-[8px] text-muted-foreground whitespace-nowrap">{date.slice(5)}</span> : null}
                </div>)}
              </div></CardContent>
            </Card>

            <Card className="bg-card border-2 border-gold/30">
              <CardHeader><CardTitle className="font-serif text-navy flex items-center gap-2"><Target className="w-5 h-5 text-gold" /> Customer Actions</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {[["Website sessions", funnel.website_sessions], ["Menu interest sessions", funnel.menu_interest_sessions], ["Order-intent sessions", funnel.order_intent_sessions], ["Pickup actions", funnel.order_pickup_events], ["Delivery actions", funnel.delivery_events], ["Phone actions", funnel.phone_events], ["Directions actions", funnel.directions_events], ["Catering actions", funnel.catering_events]].map(([label, value]) => <div key={label} className="flex justify-between gap-4 text-sm"><span className="text-muted-foreground">{label}</span><strong className="text-navy">{number(value)}</strong></div>)}
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
            <MetricCard label="Catering Inquiries" value={number(outcomes.catering_inquiries_range)} note={`${number(outcomes.catering_inquiries_total)} all time`} icon={Users} accent="text-forest" />
            <MetricCard label="Newsletter Signups" value={number(outcomes.newsletter_subscribers_range)} note={`${number(outcomes.newsletter_subscribers_total)} all time`} icon={Users} accent="text-gold" />
            <MetricCard label="Loyalty Members" value={number(outcomes.loyalty_members_range)} note={`${number(outcomes.loyalty_members_total)} all time`} icon={Users} />
          </div>

          <h3 className="font-serif text-xl font-bold text-navy mb-4">Acquisition & Audience</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5 mb-8">
            <BreakdownCard title="Traffic Sources" data={analytics.source_breakdown} icon={Globe} />
            <BreakdownCard title="Top Referrers" data={analytics.top_referrers} icon={TrendingUp} />
            <BreakdownCard title="Campaigns" data={analytics.campaign_breakdown} icon={Target} empty="No tagged campaigns yet" />
            <BreakdownCard title="Devices" data={analytics.device_breakdown} icon={Monitor} />
            <BreakdownCard title="Browsers" data={analytics.browser_breakdown} icon={Globe} />
            <BreakdownCard title="Screen Sizes" data={analytics.viewport_breakdown} icon={Smartphone} />
            <BreakdownCard title="Languages" data={analytics.language_breakdown} icon={Globe} />
            <BreakdownCard title="Visitor Time Zones" data={analytics.timezone_breakdown} icon={Clock} />
          </div>

          <h3 className="font-serif text-xl font-bold text-navy mb-4">Content & Behavior</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
            <BreakdownCard title="Page Views" data={analytics.page_breakdown_range} icon={BarChart3} />
            <BreakdownCard title="Landing Pages" data={analytics.landing_pages} icon={Activity} />
            <BreakdownCard title="Exit Pages" data={analytics.exit_pages} icon={Activity} />
            <BreakdownCard title="Event Categories" data={analytics.event_category_breakdown} icon={Target} />
            <BreakdownCard title="All Events" data={analytics.events_range} icon={MousePointer} maxItems={20} />
            <BreakdownCard title="Clicks Today" data={analytics.button_clicks_today} icon={MousePointer} />
            <BreakdownCard title="Views This Week" data={analytics.daily_views_week} icon={Calendar} />
            <BreakdownCard title="Device Summary" data={analytics.device_breakdown} icon={Tablet} />
          </div>

          <p className="text-[10px] text-muted-foreground mt-6 text-right">Updated {analytics.generated_at ? new Date(analytics.generated_at).toLocaleString() : "now"}</p>
        </> : null}
      </section>
    </>
  );
};

export default AnalyticsTab;
