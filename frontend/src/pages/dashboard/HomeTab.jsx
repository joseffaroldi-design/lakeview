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
  AlertTriangle, BarChart3, Calendar as CalendarIcon, ChefHat, Image as ImageIcon,
  Loader2, Megaphone, Share2, Sparkles, TrendingUp, UserPlus, Utensils, Users,
} from "lucide-react";
// Sprint 22F — Today's Pick moved to the Menu tab; BillingCard kept.
import BillingCard from "./BillingCard";
import OnboardingGuide from "./home/OnboardingGuide";
import { PageHeader, StatTile } from "@/components/dashboard/primitives";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const todayYMD = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const Suggestion = ({ icon: Icon, title, body, cta, onClick, tone = "navy", testId }) => (
  <div
    className={`ds-card p-4 flex items-start gap-3 ${tone === "gold" ? "ring-1 ring-gold/25" : ""}`}
    data-testid={testId}
  >
    <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${tone === "gold" ? "bg-gold/15 text-gold" : "bg-navy/8 text-navy"}`}>
      <Icon className="w-4 h-4" />
    </div>
    <div className="flex-1 min-w-0">
      <p className="font-semibold text-navy text-sm">{title}</p>
      <p className="text-xs text-navy/60 mt-0.5">{body}</p>
      {cta && onClick ? (
        <button onClick={onClick}
          className="mt-2 text-xs font-semibold text-navy hover:text-gold transition-colors inline-flex items-center gap-1"
          data-testid={`${testId}-cta`}>
          {cta} →
        </button>
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
  const [health, setHealth] = useState({ level: "green", issues: [] });
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [topItems, setTopItems] = useState([]);
  const [issuesOpen, setIssuesOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const headers = getAuthHeader();
        const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString();

        const [summaryRes, healthRes, suggestRes, specialsRes, inqRes, statsRes] = await Promise.allSettled([
          axios.get(`${API}/home/summary`, { headers }),
          axios.get(`${API}/home/health`, { headers }),
          axios.get(`${API}/home/promote-suggestions?limit=3`, { headers }),
          axios.get(`${API}/specials`, { headers }),
          axios.get(`${API}/catering/inquiries`, { headers }),
          axios.get(`${API}/ai-ads/stats`, { headers }).catch(() => ({ data: {} })),
        ]);

        if (cancelled) return;

        const summary = summaryRes.status === "fulfilled" ? summaryRes.value.data.today || {} : {};
        const healthData = healthRes.status === "fulfilled" ? healthRes.value.data || {} : { level: "green", issues: [] };
        const top3 = suggestRes.status === "fulfilled" ? suggestRes.value.data.items || [] : [];
        const specials = specialsRes.status === "fulfilled" ? specialsRes.value.data || [] : [];
        const inquiries = inqRes.status === "fulfilled" ? (inqRes.value.data && inqRes.value.data.inquiries) || [] : [];
        const stats = statsRes.status === "fulfilled" ? statsRes.value.data || {} : {};

        setToday({
          scheduledToday: summary.scheduled || 0,
          activePromos: summary.active_promos || 0,
          newSubs: summary.new_subscribers || 0,
          newInquiries: summary.new_inquiries || 0,
          failed: summary.real_failures || 0,
        });
        setHealth(healthData);
        setTopItems(top3);
        setMenuItems([]);  // no longer needed — using top3 instead

        setWeek({
          mostPromotedItem: stats.most_used_goal || "—",
          bestPlatform: stats.most_used_platform || "—",
          mostViewedCampaign: stats.top_campaign_name || null,
          loyaltyGrowth: summary.new_subscribers || 0,
        });

        // Suggestions — top-3 + catering follow-ups + failures + expiring
        const sug = [];
        if (top3.length > 0) {
          sug.push({
            id: "promote-stale",
            icon: Megaphone, tone: "gold",
            title: `Promote ${top3[0].name}`,
            body: top3[0].reason,
            cta: "Promote in 1 click",
            onClick: () => onPromote && onPromote({ name: top3[0].name, description: top3[0].description, price: top3[0].price }, top3[0].category),
          });
        }
        const openInq = inquiries.filter((i) => !i.replied && i.created_at > weekAgo);
        if (openInq.length > 0) {
          sug.push({
            id: "follow-catering", icon: ChefHat, tone: "navy",
            title: `${openInq.length} catering ${openInq.length === 1 ? "lead needs" : "leads need"} a reply`,
            body: "Don't let warm leads cool.",
            cta: "Open Inquiries",
            onClick: () => onNavigate && onNavigate("customers", "inquiries"),
          });
        }
        if ((summary.real_failures || 0) > 0) {
          sug.push({
            id: "fix-failed", icon: AlertTriangle, tone: "navy",
            title: `${summary.real_failures} failed publish${summary.real_failures === 1 ? "" : "es"}`,
            body: "Auto-retried 3 times. Open the Calendar to inspect or reconnect a provider.",
            cta: "Open Calendar",
            onClick: () => onNavigate && onNavigate("promotions", "calendar"),
          });
        }
        const expiringSoon = specials.filter((s) => {
          if (!s.active || !s.ends_at) return false;
          const ends = new Date(s.ends_at).getTime();
          return ends - Date.now() < 2 * 86400000;
        });
        if (expiringSoon.length > 0) {
          sug.push({
            id: "expiring-special", icon: TrendingUp, tone: "navy",
            title: `${expiringSoon[0].title} ends soon`,
            body: "Boost it with one last social push.",
            cta: "Promote it",
            onClick: () => onNavigate && onNavigate("promotions", "automations"),
          });
        }
        if (sug.length === 0) {
          sug.push({
            id: "all-clear", icon: Sparkles, tone: "gold",
            title: "You're caught up",
            body: "Nothing urgent. Want to plan next week while you have a minute?",
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

  // Sprint 22F — Today's Pick + refresh moved to TodaysPickCard (Menu tab).

  // Featured = first top-3 item (fallback null)
  const featuredItem = topItems[0] || null;
  void featuredItem;
  void menuItems; // legacy state, no longer rendered

  const HEALTH_TONES = {
    green:  { dot: "bg-forest", text: "All systems healthy" },
    yellow: { dot: "bg-gold",   text: "Minor issues" },
    red:    { dot: "bg-red-600", text: "Action needed" },
  };
  const healthTone = HEALTH_TONES[health.level] || HEALTH_TONES.green;

  return (
    <section data-testid="home-tab" className="ds-fade">
      <PageHeader
        eyebrow="Studio"
        title={<>Good to see you<span className="text-gold">.</span></>}
        subtitle="Your morning check-in — everything that needs your attention, at a glance."
        actions={
          <>
            {loading ? <Loader2 className="w-4 h-4 animate-spin text-navy/40" /> : null}
            <button type="button"
              onClick={() => setIssuesOpen((o) => !o)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full border transition-all hover:shadow-sm ${health.level === "red" ? "border-red-200 bg-red-50" : health.level === "yellow" ? "border-gold/30 bg-gold/8" : "border-forest/20 bg-forest/5"}`}
              title={(health.issues || []).length ? "Click to see details" : "All systems healthy"}
              data-testid="home-health-pill" data-health-level={health.level}
              aria-expanded={issuesOpen}>
              <span className={`w-2 h-2 rounded-full ${healthTone.dot}`} />
              <span className="text-xs font-semibold text-navy">{healthTone.text}</span>
              {(health.issues || []).length > 0 ? (
                <span className="text-[10px] font-bold text-navy/60 bg-white/70 rounded-full px-1.5 py-0.5">
                  {(health.issues || []).length}
                </span>
              ) : null}
            </button>
          </>
        }
      />

      {/* HEALTH ISSUES PANEL */}
      {issuesOpen ? (
        <div
          className={`mb-6 ds-card p-4 ${health.level === "red" ? "border-red-200 bg-red-50/40" : health.level === "yellow" ? "border-gold/30 bg-gold/5" : "border-forest/20 bg-forest/5"}`}
          data-testid="home-health-issues-panel"
        >
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-semibold text-navy">
              {(health.issues || []).length === 0 ? "All systems healthy" : `${health.issues.length} issue${health.issues.length === 1 ? "" : "s"} detected`}
            </p>
            <button type="button" onClick={() => setIssuesOpen(false)}
              className="text-[11px] font-semibold text-navy/60 hover:text-navy underline"
              data-testid="home-health-issues-close">Hide</button>
          </div>
          {(health.issues || []).length === 0 ? (
            <p className="text-xs text-navy/70">Nothing needs your attention right now.</p>
          ) : (
            <ul className="space-y-1.5">
              {(health.issues || []).map((iss, idx) => {
                const text = typeof iss === "string" ? iss : (iss.message || iss.text || JSON.stringify(iss));
                return (
                  <li key={`issue-${text.slice(0, 32)}-${idx}`} className="text-xs text-navy flex items-start gap-2"
                      data-testid={`home-health-issue-${idx}`}>
                    <span className="text-[14px] leading-none mt-0.5">•</span>
                    <span className="flex-1">{text}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}

      {/* Sprint 22F — Today's Pick moved to the Menu tab.
          Quick actions are now the primary CTAs on the Home dashboard. */}

      {/* QUICK ACTIONS */}
      <div className="mb-8" data-testid="home-quick-actions">
        <p className="ds-eyebrow mb-3">Quick actions</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <QuickAction icon={Megaphone} label="Promote a dish"
            sub="Photo → Flyer in 60s"
            tone="gold"
            onClick={() => onNavigate && onNavigate("promotions")}
            testId="qa-promote" />
          <QuickAction icon={Utensils} label="Menu &amp; Today&apos;s Pick"
            sub="Edit dishes &amp; pick"
            onClick={() => onNavigate && onNavigate("menu")}
            testId="qa-menu" />
          <QuickAction icon={ImageIcon} label="Library"
            sub="Saved flyers &amp; videos"
            onClick={() => onNavigate && onNavigate("library")}
            testId="qa-library" />
          <QuickAction icon={UserPlus} label="Customers"
            sub="Subscribers &amp; leads"
            onClick={() => onNavigate && onNavigate("customers")}
            testId="qa-customers" />
        </div>
      </div>

      {/* WORKSPACE SUMMARY */}
      <div className="mb-8" data-testid="home-workspace-summary">
        <div className="flex items-end justify-between mb-3">
          <div>
            <p className="ds-eyebrow">Workspace</p>
            <h3 className="ds-display text-lg sm:text-xl">Today at a glance</h3>
          </div>
          <button onClick={() => onNavigate && onNavigate("workspace")}
            className="text-xs text-navy/60 hover:text-navy font-semibold"
            data-testid="home-open-workspace">
            View all projects →
          </button>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatTile label="Active Promos" value={today.activePromos} icon={Megaphone} tone="navy" testId="home-active-promos" />
          <StatTile label="New Inquiries" value={today.newInquiries} icon={Users} tone={today.newInquiries > 0 ? "gold" : "navy"} testId="home-new-inquiries" />
          <StatTile label="Items in queue" value={topItems.length > 0 ? topItems.length : "—"} icon={TrendingUp} tone="navy" testId="home-week-summary" />
          <StatTile label="View Analytics" value="→" icon={BarChart3} tone="navy" testId="home-analytics-link" />
        </div>
      </div>

      {/* BILLING */}
      <div className="mb-8">
        <p className="ds-eyebrow mb-3">Budget</p>
        <BillingCard getAuthHeader={getAuthHeader} />
      </div>

      {/* MOST SHARED FLYERS — Item 2 (Feb 2026) */}
      <TopSharedFlyers getAuthHeader={getAuthHeader} />

      {/* RECENT ACTIVITY / SUGGESTIONS */}
      {suggestions.length > 0 && (
        <div className="mb-8" data-testid="home-suggestions">
          <p className="ds-eyebrow mb-3">Recent activity</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {suggestions.slice(0, 4).map((s) => (
              <Suggestion key={s.id} {...s} />
            ))}
          </div>
        </div>
      )}

      {/* ONBOARDING — subtle, last */}
      <OnboardingGuide getAuthHeader={getAuthHeader} onNavigate={onNavigate} />
    </section>
  );
};

const QuickAction = ({ icon: Icon, label, sub, onClick, tone = "navy", testId }) => (
  <button
    onClick={onClick}
    className={`ds-card ds-card-interactive p-4 text-left flex flex-col gap-2 ${tone === "gold" ? "ring-1 ring-gold/30" : ""}`}
    data-testid={testId}
  >
    <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${tone === "gold" ? "bg-gold/15 text-gold" : "bg-navy/8 text-navy"}`}>
      <Icon className="w-5 h-5" />
    </div>
    <div>
      <div className="text-sm font-semibold text-navy">{label}</div>
      <div className="text-xs text-navy/55 mt-0.5">{sub}</div>
    </div>
  </button>
);

export default HomeTab;

// TopSharedFlyers — Item 2 (Feb 2026): compact leaderboard of the menu
// items whose flyers were shared most (via the Photo→Flyer Share button).
// Hidden when nothing has ever been shared so first-run owners don't see
// an empty card.
const TopSharedFlyers = ({ getAuthHeader }) => {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/analytics/flyer-shares`, {
          headers: getAuthHeader(),
          timeout: 8000,
        });
        if (cancel) return;
        setItems(r.data?.items || []);
        setTotal(r.data?.total_shares || 0);
      } catch {
        // Silent — this is a supplementary widget, not critical.
      } finally {
        if (!cancel) setLoading(false);
      }
    })();
    return () => { cancel = true; };
  }, [getAuthHeader]);

  if (loading || items.length === 0) return null;

  const top = items.slice(0, 5);
  return (
    <div className="mb-8" data-testid="home-top-shared-flyers">
      <div className="flex items-baseline justify-between mb-3">
        <p className="ds-eyebrow">Most shared flyers</p>
        <span className="text-xs text-navy/50">{total} share{total === 1 ? "" : "s"} total</span>
      </div>
      <div className="ds-card p-4">
        <div className="divide-y divide-navy/5">
          {top.map((it, idx) => (
            <div
              key={it.item_key}
              className="flex items-center justify-between py-2"
              data-testid={`home-shared-flyer-row-${idx}`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="w-6 h-6 rounded-full bg-gold/15 text-gold text-xs font-bold flex items-center justify-center flex-shrink-0">
                  {idx + 1}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-navy truncate">{it.item_name || it.item_key}</p>
                  <p className="text-xs text-navy/50 truncate">
                    {it.last_theme ? `Last theme: ${it.last_theme.replace(/_/g, " ")}` : ""}
                  </p>
                </div>
              </div>
              <span className="inline-flex items-center gap-1 text-sm font-semibold text-forest whitespace-nowrap">
                <Share2 className="w-3.5 h-3.5" />
                {it.share_count}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
