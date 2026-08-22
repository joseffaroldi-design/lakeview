import React, { useEffect, useState } from "react";
import axios from "axios";
import {
  Users, Eye, Utensils, ShoppingBag, Truck, Phone, MapPin, ClipboardList,
  TrendingUp, Globe, LineChart,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Tile = ({ label, value, icon: Icon, testId }) => (
  <div className="ds-card p-3.5" data-testid={testId}>
    <div className="flex items-start justify-between gap-2">
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-navy/50">{label}</p>
        <p className="ds-display text-2xl mt-1">{value}</p>
      </div>
      <div className="w-8 h-8 rounded-lg bg-navy/8 text-navy flex items-center justify-center shrink-0">
        <Icon className="w-4 h-4" />
      </div>
    </div>
  </div>
);

const formatGaDate = (ga) => (ga && ga.length === 8 ? `${ga.slice(4, 6)}/${ga.slice(6, 8)}` : ga || "");

const Ga4Summary = ({ getAuthHeader }) => {
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading"); // loading | ready | unavailable | error

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        // Treat 503 (credentials not configured) as a normal response so the
        // global axios interceptor doesn't fire a "Server error" toast for
        // the graceful-degraded state.
        const res = await axios.get(`${API}/ga4/summary`, {
          headers: getAuthHeader(),
          validateStatus: (s) => (s >= 200 && s < 300) || s === 503,
        });
        if (!mounted) return;
        if (res.status === 503) {
          setState("unavailable");
          return;
        }
        setData(res.data);
        setState("ready");
      } catch (err) {
        if (!mounted) return;
        setState("error");
      }
    })();
    return () => { mounted = false; };
  }, [getAuthHeader]);

  if (state === "loading") {
    return (
      <div className="mb-8" data-testid="ga4-summary">
        <div className="flex items-center justify-between mb-3">
          <p className="ds-eyebrow">Google Analytics · Today</p>
          <span className="text-[11px] text-navy/45">Loading GA4…</span>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (<div key={i} className="ds-card p-3.5 h-20 animate-pulse" />))}
        </div>
      </div>
    );
  }
  if (state === "unavailable" || state === "error") {
    return (
      <div className="mb-8" data-testid="ga4-summary">
        <div className="flex items-center justify-between mb-3">
          <p className="ds-eyebrow">Google Analytics · Today</p>
        </div>
        <div className="ds-card p-4 text-sm text-navy/60" data-testid="ga4-unavailable">
          <p className="font-semibold text-navy mb-0.5">Analytics unavailable</p>
          <p className="text-xs text-navy/55">
            {state === "unavailable"
              ? "Google Analytics credentials aren't configured on the backend yet. Once the service-account credential is added, this section will populate automatically."
              : "We couldn't reach Google Analytics right now. Try again in a few minutes."}
          </p>
        </div>
      </div>
    );
  }

  const t = data?.today || {};
  const ev = t.events || {};
  const trend = Array.isArray(data?.trend_7d) ? data.trend_7d : [];
  const sources = Array.isArray(data?.traffic_sources) ? data.traffic_sources : [];
  const maxTrend = Math.max(1, ...trend.map((d) => d.sessions || 0));

  const tiles = [
    { key: "visitors",   label: "Visitors",         value: t.visitors ?? 0,              Icon: Users },
    { key: "pageviews",  label: "Page views",       value: t.page_views ?? 0,            Icon: Eye },
    { key: "menu",       label: "Menu clicks",      value: ev.menu_click ?? 0,           Icon: Utensils },
    { key: "pickup",     label: "Pickup clicks",    value: ev.order_pickup_click ?? 0,   Icon: ShoppingBag },
    { key: "delivery",   label: "Delivery clicks",  value: ev.order_delivery_click ?? 0, Icon: Truck },
    { key: "phone",      label: "Phone clicks",     value: ev.phone_click ?? 0,          Icon: Phone },
    { key: "directions", label: "Directions",       value: ev.directions_click ?? 0,     Icon: MapPin },
    { key: "leads",      label: "Catering leads",   value: ev.generate_lead ?? 0,        Icon: ClipboardList },
  ];

  return (
    <div className="mb-8" data-testid="ga4-summary">
      <div className="flex items-center justify-between mb-3">
        <p className="ds-eyebrow">Google Analytics · Today</p>
        <span className="text-[11px] text-navy/45">Live from GA4 (property timezone)</span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {tiles.map((tile) => (
          <Tile key={tile.key} label={tile.label} value={tile.value} icon={tile.Icon} testId={`ga4-${tile.key}`} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mt-3">
        <div className="ds-card p-4" data-testid="ga4-trend">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-navy/70" />
            <p className="text-xs font-semibold uppercase tracking-wider text-navy/60">7-day traffic trend</p>
          </div>
          {trend.length === 0 ? (
            <p className="text-xs text-navy/55">No trend data yet.</p>
          ) : (
            <div className="flex items-end justify-between h-24 gap-1.5">
              {trend.map((d) => {
                const pct = Math.round(((d.sessions || 0) / maxTrend) * 100);
                return (
                  <div key={d.date} className="flex flex-col items-center flex-1 min-w-0">
                    <div className="w-full rounded-t bg-navy" style={{ height: `${Math.max(pct, 6)}%` }} title={`${d.sessions} sessions`} />
                    <span className="text-[10px] text-navy/50 mt-1">{formatGaDate(d.date)}</span>
                    <span className="text-[11px] font-semibold text-navy">{d.sessions || 0}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="ds-card p-4" data-testid="ga4-sources">
          <div className="flex items-center gap-2 mb-3">
            <Globe className="w-4 h-4 text-navy/70" />
            <p className="text-xs font-semibold uppercase tracking-wider text-navy/60">Top traffic sources (7d)</p>
          </div>
          {sources.length === 0 ? (
            <p className="text-xs text-navy/55">No traffic source data yet.</p>
          ) : (
            <div className="space-y-2">
              {sources.slice(0, 6).map((s) => (
                <div key={s.channel} className="flex justify-between items-center">
                  <span className="text-sm text-navy/70">{s.channel}</span>
                  <span className="text-sm font-semibold text-navy">{s.sessions}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Ga4Summary;
