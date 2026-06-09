/**
 * HomeTab — Phase 9A landing page.
 *
 * Pulls existing endpoints (no new APIs) to render four sections:
 *   1. TODAY            — scheduled today, active promos, new subs, new inquiries, failed publishes
 *   2. THIS WEEK        — most promoted item, best platform, loyalty growth
 *   3. AI SUGGESTIONS   — derived from menu items not promoted recently + scheduled gaps
 *   4. QUICK ACTIONS    — large CTAs that jump to the right tab
 *
 * Every "?" or empty stat shows a friendly fallback. Owner should be able to
 * scan this in under 60 seconds and know exactly what to do next.
 */
import React, { useEffect, useState } from "react";
import axios from "axios";
import {
  AlertTriangle, BarChart3, Calendar as CalendarIcon, ChefHat, Gift, Image as ImageIcon,
  Loader2, Megaphone, Sparkles, TrendingUp, UserPlus, Utensils, Users,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const todayYMD = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const Stat = ({ label, value, icon: Icon, tone = "navy", testId }) => (
  <Card className="bg-card border-2 border-navy/10 hover:border-gold/40 transition-colors" data-testid={testId}>
    <CardContent className="py-4 px-4 flex items-center gap-3">
      <div className={`w-10 h-10 rounded-full flex items-center justify-center ${tone === "gold" ? "bg-gold/15" : tone === "red" ? "bg-red-100" : "bg-navy/10"}`}>
        {Icon ? <Icon className={`w-5 h-5 ${tone === "gold" ? "text-gold" : tone === "red" ? "text-red-700" : "text-navy"}`} /> : null}
      </div>
      <div className="min-w-0">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
        <p className={`text-2xl font-serif font-bold ${tone === "red" ? "text-red-700" : "text-navy"}`}>{value}</p>
      </div>
    </CardContent>
  </Card>
);

const Suggestion = ({ icon: Icon, title, body, cta, onClick, tone = "navy", testId }) => (
  <div
    className={`border-2 rounded-lg p-3 flex items-start gap-3 ${tone === "gold" ? "border-gold/40 bg-gold/5" : "border-navy/10 bg-card"}`}
    data-testid={testId}
  >
    <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${tone === "gold" ? "bg-gold/20" : "bg-navy/10"}`}>
      <Icon className={`w-4 h-4 ${tone === "gold" ? "text-gold" : "text-navy"}`} />
    </div>
    <div className="flex-1 min-w-0">
      <p className="font-semibold text-navy text-sm">{title}</p>
      <p className="text-xs text-muted-foreground mt-0.5">{body}</p>
      {cta && onClick ? (
        <Button onClick={onClick} size="sm" className="mt-2 bg-gold text-navy hover:bg-gold/90 h-7 text-xs" data-testid={`${testId}-cta`}>
          {cta}
        </Button>
      ) : null}
    </div>
  </div>
);

const HomeTab = ({ getAuthHeader, onNavigate, onPromote }) => {
  const [loading, setLoading] = useState(true);
  const [today, setToday] = useState({ scheduledToday: 0, activePromos: 0, newSubs: 0, newInquiries: 0, failed: 0 });
  const [week, setWeek] = useState({ mostPromotedItem: null, bestPlatform: null, mostViewedCampaign: null, loyaltyGrowth: 0 });
  const [suggestions, setSuggestions] = useState([]);
  const [menuItems, setMenuItems] = useState([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const headers = getAuthHeader();
        const ymd = todayYMD();
        const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString();

        const [specialsRes, subsRes, inqRes, calRes, menuRes, statsRes, healthRes] = await Promise.allSettled([
          axios.get(`${API}/specials`, { headers }),
          axios.get(`${API}/newsletter-subscribers`, { headers }),
          axios.get(`${API}/catering-inquiries`, { headers }),
          axios.get(`${API}/ai-ads/publish-queue`, { headers }),
          axios.get(`${API}/menu`, { headers }),
          axios.get(`${API}/ai-ads/stats`, { headers }).catch(() => ({ data: {} })),
          axios.get(`${API}/media/health`, { headers }).catch(() => ({ data: {} })),
        ]);

        if (cancelled) return;

        const specials = specialsRes.status === "fulfilled" ? specialsRes.value.data || [] : [];
        const subs = subsRes.status === "fulfilled" ? subsRes.value.data || [] : [];
        const inquiries = inqRes.status === "fulfilled" ? inqRes.value.data || [] : [];
        const queue = calRes.status === "fulfilled" ? calRes.value.data.columns || {} : {};
        const menu = menuRes.status === "fulfilled" ? menuRes.value.data || [] : [];
        const stats = statsRes.status === "fulfilled" ? statsRes.value.data || {} : {};
        const health = healthRes.status === "fulfilled" ? healthRes.value.data || {} : {};

        const scheduledToday = (queue.queued || []).filter((p) => (p.scheduled_at || "").startsWith(ymd)).length;
        const activePromos = specials.filter((s) => s.active !== false).length;
        const newSubs = subs.filter((s) => s.subscribed_at && s.subscribed_at > weekAgo).length;
        const newInq = inquiries.filter((i) => i.created_at && i.created_at > weekAgo).length;
        const failed = (queue.failed || []).length + ((health.render_queue || {}).failed_recent || 0);

        setToday({ scheduledToday, activePromos, newSubs, newInquiries: newInq, failed });
        setWeek({
          mostPromotedItem: stats.most_used_goal || "—",
          bestPlatform: stats.most_used_platform || "—",
          mostViewedCampaign: stats.top_campaign_name || null,
          loyaltyGrowth: newSubs,
        });
        setMenuItems(menu);

        // Derive AI suggestions from data we already have
        const sug = [];
        const flatItems = [];
        for (const cat of menu) {
          for (const it of (cat.items || [])) {
            flatItems.push({ ...it, category: cat.name });
          }
        }
        // Suggestion 1: an item with no associated campaign in last 21 days
        if (flatItems.length > 0) {
          const candidate = flatItems[Math.floor(Math.random() * flatItems.length)];
          sug.push({
            id: "promote-stale",
            icon: Megaphone,
            tone: "gold",
            title: `Promote ${candidate.name}`,
            body: `Hasn't been featured recently. One click runs Facebook, Instagram, Google Business, and an SMS blast.`,
            cta: "Promote in 1 click",
            onClick: () => onPromote && onPromote(candidate, candidate.category),
          });
        }
        // Suggestion 2: catering inquiries to follow up on
        const openInq = inquiries.filter((i) => !i.replied && i.created_at > weekAgo);
        if (openInq.length > 0) {
          sug.push({
            id: "follow-catering",
            icon: ChefHat,
            tone: "navy",
            title: `${openInq.length} catering ${openInq.length === 1 ? "lead needs" : "leads need"} a reply`,
            body: "Don't let warm leads cool. Draft personal replies from the Customers tab.",
            cta: "Open Inquiries",
            onClick: () => onNavigate && onNavigate("customers", "inquiries"),
          });
        }
        // Suggestion 3: failed publishes
        if (failed > 0) {
          sug.push({
            id: "fix-failed",
            icon: AlertTriangle,
            tone: "navy",
            title: `${failed} failed publish${failed === 1 ? "" : "es"}`,
            body: "Reconnect the provider or retry from the Calendar.",
            cta: "Open Calendar",
            onClick: () => onNavigate && onNavigate("promotions", "calendar"),
          });
        }
        // Suggestion 4: active special running thin
        const expiringSoon = specials.filter((s) => {
          if (!s.active || !s.ends_at) return false;
          const ends = new Date(s.ends_at).getTime();
          return ends - Date.now() < 2 * 86400000;
        });
        if (expiringSoon.length > 0) {
          sug.push({
            id: "expiring-special",
            icon: TrendingUp,
            tone: "navy",
            title: `${expiringSoon[0].title} ends soon`,
            body: "Boost it with one last social push before it expires.",
            cta: "Promote it",
            onClick: () => onNavigate && onNavigate("promotions", "active"),
          });
        }
        if (sug.length === 0) {
          sug.push({
            id: "all-clear",
            icon: Sparkles,
            tone: "gold",
            title: "You're caught up",
            body: "No urgent items. Want to plan next week's promotions while you have a minute?",
            cta: "Open Calendar",
            onClick: () => onNavigate && onNavigate("promotions", "calendar"),
          });
        }
        setSuggestions(sug);
      } catch (e) {
        // Fall back to empty state — no need to surface errors here
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [getAuthHeader, onNavigate, onPromote]);

  // First item across all categories — fallback for "Promote Something" CTA
  let featuredItem = null;
  for (const cat of menuItems) {
    if ((cat.items || []).length > 0) {
      featuredItem = { ...cat.items[0], category: cat.name };
      break;
    }
  }

  return (
    <section data-testid="home-tab">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="font-serif text-2xl text-navy font-bold flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-gold" /> Home
          </h2>
          <p className="text-sm text-muted-foreground mt-1">Your 10-minute morning check-in.</p>
        </div>
        {loading ? <Loader2 className="w-4 h-4 animate-spin text-navy/40" /> : null}
      </div>

      {/* QUICK ACTIONS — top of fold */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-8" data-testid="home-quick-actions">
        <Button
          onClick={() => featuredItem && onPromote && onPromote(featuredItem, featuredItem.category)}
          disabled={!featuredItem}
          className="bg-gold text-navy hover:bg-gold/90 h-auto py-3 flex-col gap-1"
          data-testid="qa-promote">
          <Megaphone className="w-5 h-5" />
          <span className="text-xs font-semibold">Promote Something</span>
        </Button>
        <Button
          onClick={() => onNavigate && onNavigate("promotions", "active")}
          variant="outline"
          className="border-navy/20 h-auto py-3 flex-col gap-1"
          data-testid="qa-special">
          <Gift className="w-5 h-5 text-gold" />
          <span className="text-xs text-navy font-semibold">Add Special</span>
        </Button>
        <Button
          onClick={() => onNavigate && onNavigate("promotions", "media")}
          variant="outline"
          className="border-navy/20 h-auto py-3 flex-col gap-1"
          data-testid="qa-upload">
          <ImageIcon className="w-5 h-5 text-gold" />
          <span className="text-xs text-navy font-semibold">Upload Photo</span>
        </Button>
        <Button
          onClick={() => onNavigate && onNavigate("promotions", "builder")}
          variant="outline"
          className="border-navy/20 h-auto py-3 flex-col gap-1"
          data-testid="qa-campaign">
          <Sparkles className="w-5 h-5 text-gold" />
          <span className="text-xs text-navy font-semibold">Create Campaign</span>
        </Button>
        <Button
          onClick={() => onNavigate && onNavigate("promotions", "calendar")}
          variant="outline"
          className="border-navy/20 h-auto py-3 flex-col gap-1"
          data-testid="qa-calendar">
          <CalendarIcon className="w-5 h-5 text-gold" />
          <span className="text-xs text-navy font-semibold">View Calendar</span>
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* TODAY */}
        <div>
          <h3 className="font-serif text-lg text-navy font-bold mb-3">Today</h3>
          <div className="grid grid-cols-2 gap-3" data-testid="home-today">
            <Stat label="Scheduled today" value={today.scheduledToday} icon={CalendarIcon} testId="today-scheduled" />
            <Stat label="Active promos"   value={today.activePromos}   icon={Megaphone}    testId="today-active" tone="gold" />
            <Stat label="New subscribers" value={today.newSubs}        icon={UserPlus}     testId="today-subs" />
            <Stat label="New inquiries"   value={today.newInquiries}   icon={ChefHat}      testId="today-inquiries" />
            {today.failed > 0 ? (
              <div className="col-span-2"><Stat label="Failed publishes" value={today.failed} icon={AlertTriangle} tone="red" testId="today-failed" /></div>
            ) : null}
          </div>

          <h3 className="font-serif text-lg text-navy font-bold mb-3 mt-6">This Week</h3>
          <div className="grid grid-cols-2 gap-3" data-testid="home-week">
            <Stat label="Most promoted" value={week.mostPromotedItem || "—"} icon={Utensils} testId="week-promoted" />
            <Stat label="Best platform" value={week.bestPlatform || "—"}     icon={TrendingUp} testId="week-platform" />
            <Stat label="Loyalty growth" value={`+${week.loyaltyGrowth}`}    icon={Users} testId="week-loyalty" />
            <Stat label="View analytics" value=""                            icon={BarChart3} testId="week-analytics" />
          </div>
        </div>

        {/* AI SUGGESTIONS */}
        <div>
          <h3 className="font-serif text-lg text-navy font-bold mb-3 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-gold" /> What I&apos;d do next
          </h3>
          <div className="space-y-2" data-testid="home-suggestions">
            {suggestions.map((s) => (
              <Suggestion key={s.id} {...s} testId={`suggestion-${s.id}`} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default HomeTab;
