import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  Image as ImageIcon,
  MousePointerClick,
  Pencil,
  Users,
  UtensilsCrossed,
} from "lucide-react";
import { PageHeader } from "@/components/dashboard/primitives";
import Ga4Summary from "@/pages/dashboard/Ga4Summary";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BUSINESS_TIME_ZONE = "America/Chicago";

const QuickAction = ({ icon: Icon, label, sub, onClick, testId }) => (
  <button
    type="button"
    onClick={onClick}
    className="ds-card p-4 text-left hover:-translate-y-0.5 transition-transform"
    data-testid={testId}
  >
    <div className="w-9 h-9 rounded-xl bg-navy/8 text-navy flex items-center justify-center mb-3">
      <Icon className="w-4 h-4" />
    </div>
    <p className="font-semibold text-navy text-sm">{label}</p>
    <p className="text-xs text-navy/55 mt-0.5">{sub}</p>
  </button>
);

const MetricCard = ({ label, value, sub, icon: Icon }) => (
  <div className="ds-card p-4" data-testid={`metric-${label.toLowerCase().replace(/\s+/g, "-")}`}>
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-navy/50">{label}</p>
        <p className="ds-display text-3xl mt-1">{value}</p>
        <p className="text-xs text-navy/50 mt-1">{sub}</p>
      </div>
      <div className="w-9 h-9 rounded-xl bg-navy/8 text-navy flex items-center justify-center shrink-0">
        <Icon className="w-4 h-4" />
      </div>
    </div>
  </div>
);

const businessDateKey = (value = new Date()) => {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: BUSINESS_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
};

const HomeTab = ({ onNavigate, getAuthHeader }) => {
  const [analytics, setAnalytics] = useState(null);
  const [operations, setOperations] = useState({ cateringLeads: 0, newCustomersToday: 0 });
  const [analyticsError, setAnalyticsError] = useState(false);
  const go = (tab, subTab) => onNavigate && onNavigate(tab, subTab);

  useEffect(() => {
    let cancelled = false;

    const loadDashboard = async () => {
      const headers = getAuthHeader ? getAuthHeader() : {};
      const [analyticsResult, cateringResult, loyaltyResult, newsletterResult] = await Promise.allSettled([
        axios.get(`${API}/analytics`, { headers }),
        axios.get(`${API}/catering/inquiries`, { headers }),
        axios.get(`${API}/loyalty/members`, { headers }),
        axios.get(`${API}/newsletter/subscribers`, { headers }),
      ]);

      if (cancelled) return;

      if (analyticsResult.status === "fulfilled") {
        setAnalytics(analyticsResult.value.data);
        setAnalyticsError(false);
      } else {
        setAnalyticsError(true);
      }

      const today = businessDateKey();
      const inquiries = cateringResult.status === "fulfilled" ? (cateringResult.value.data?.inquiries || []) : [];
      const members = loyaltyResult.status === "fulfilled" ? (loyaltyResult.value.data?.members || []) : [];
      const subscribers = newsletterResult.status === "fulfilled" ? (newsletterResult.value.data?.subscribers || []) : [];

      setOperations({
        cateringLeads: inquiries.filter((item) => item.status === "new").length,
        newCustomersToday:
          members.filter((item) => businessDateKey(item.joined_at) === today).length +
          subscribers.filter((item) => businessDateKey(item.subscribed_at) === today).length,
      });
    };

    loadDashboard();
    return () => {
      cancelled = true;
    };
  }, [getAuthHeader]);

  const orderClicksToday = useMemo(() => {
    if (!analytics?.button_clicks_today) return 0;
    return Object.entries(analytics.button_clicks_today).reduce((sum, [name, count]) => {
      const key = name.toLowerCase();
      if (key.includes("uber") || key.includes("square")) return sum + Number(count || 0);
      return sum;
    }, 0);
  }, [analytics]);

  const orderIntent = useMemo(() => {
    const visitors = Number(analytics?.unique_sessions_today || 0);
    if (!visitors) return 0;
    return Math.round((orderClicksToday / visitors) * 1000) / 10;
  }, [analytics, orderClicksToday]);

  return (
    <section data-testid="home-tab" className="ds-fade">
      <PageHeader
        eyebrow="Lakeview Admin"
        title={<>Keep it simple<span className="text-gold">.</span></>}
        subtitle="The everyday tools you need to keep the restaurant website and customer information current."
      />

      <div className="mb-8" data-testid="traffic-overview">
        <div className="flex items-end justify-between gap-4 mb-3">
          <div>
            <p className="ds-eyebrow">Today</p>
            <h2 className="ds-display text-xl">Business at a glance</h2>
          </div>
          {analytics ? (
            <p className="text-xs text-navy/45 text-right">
              {orderIntent}% order intent · {analytics.views_this_week ?? 0} views this week
            </p>
          ) : null}
        </div>

        {analytics ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <MetricCard
              label="Visitors"
              value={analytics.unique_sessions_today ?? 0}
              sub="Website visitors today"
              icon={Users}
            />
            <MetricCard
              label="Order clicks"
              value={orderClicksToday}
              sub="Pickup + delivery today"
              icon={MousePointerClick}
            />
            <MetricCard
              label="Catering leads"
              value={operations.cateringLeads}
              sub="New inquiries to follow up"
              icon={UtensilsCrossed}
            />
            <MetricCard
              label="New customers"
              value={operations.newCustomersToday}
              sub="Loyalty + email signups today"
              icon={Users}
            />
          </div>
        ) : analyticsError ? (
          <div className="ds-card p-4 text-sm text-navy/55">
            Traffic data is temporarily unavailable. The rest of the dashboard is unaffected.
          </div>
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[0, 1, 2, 3].map((item) => (
              <div key={item} className="ds-card p-4 h-28 animate-pulse" />
            ))}
          </div>
        )}
      </div>

      <Ga4Summary getAuthHeader={getAuthHeader} />

      <div className="mb-8" data-testid="home-quick-actions">
        <p className="ds-eyebrow mb-3">Quick actions</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <QuickAction
            icon={Pencil}
            label="Menu & Website"
            sub="Prices, dishes and public copy"
            onClick={() => go("menu")}
            testId="qa-menu"
          />
          <QuickAction
            icon={ImageIcon}
            label="Library"
            sub="Photos and saved media"
            onClick={() => go("library")}
            testId="qa-library"
          />
          <QuickAction
            icon={Users}
            label="Customers"
            sub="Loyalty and subscribers"
            onClick={() => go("customers")}
            testId="qa-customers"
          />
          <QuickAction
            icon={UtensilsCrossed}
            label="Catering"
            sub="Review event inquiries"
            onClick={() => go("catering")}
            testId="qa-catering"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="ds-card p-5">
          <p className="ds-eyebrow mb-1">Most common task</p>
          <h3 className="ds-display text-xl">Update the menu</h3>
          <p className="text-sm text-navy/60 mt-2">
            Change prices, descriptions and restaurant website copy without digging through extra tools.
          </p>
          <button
            type="button"
            onClick={() => go("menu")}
            className="ds-btn-secondary mt-4 text-xs"
          >
            Open Menu & Website
          </button>
        </div>

        <div className="ds-card p-5">
          <p className="ds-eyebrow mb-1">Customer follow-up</p>
          <h3 className="ds-display text-xl">Customers & catering</h3>
          <p className="text-sm text-navy/60 mt-2">
            Keep loyalty, subscriber and catering follow-up easy to find and easy to use.
          </p>
          <div className="flex flex-wrap gap-2 mt-4">
            <button
              type="button"
              onClick={() => go("customers", "loyalty")}
              className="ds-btn-secondary text-xs"
            >
              Open Customers
            </button>
            <button
              type="button"
              onClick={() => go("catering")}
              className="ds-btn-secondary text-xs"
            >
              Open Catering
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default HomeTab;
