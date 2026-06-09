/**
 * AI Studio Analytics — Phase 5 dashboard with cards, insights, and charts.
 *
 * Powered by GET /api/ai-ads/analytics. Uses recharts (already installed) for
 * a 30-day trend line, platform usage bars, and campaign-type pie.
 */
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis,
  Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from "recharts";
import {
  Sparkles, MessageSquare, Mail, Video as VideoIcon,
  Image as ImageIcon, TrendingUp, BarChart3, PieChart as PieIcon, Award,
} from "lucide-react";
import { API, Section } from "./shared";

const StatCard = (props) => {
  const { label, value, icon: Icon, accent, testId } = props;
  return (
    <div
      className="rounded-lg border-2 border-navy/10 bg-card p-4 flex items-start justify-between"
      data-testid={testId}
    >
      <div>
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
        <p className={`text-3xl font-serif font-bold ${accent || "text-navy"} mt-1`}>{value}</p>
      </div>
      {Icon ? <Icon className={`w-6 h-6 ${accent || "text-navy/40"} opacity-60`} /> : null}
    </div>
  );
};

const InsightCard = (props) => {
  const { label, value, testId } = props;
  return (
    <div className="rounded-lg border-2 border-gold/30 bg-gold/5 p-4" data-testid={testId}>
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="text-xl font-serif font-semibold text-navy mt-1 truncate">{value || "—"}</p>
    </div>
  );
};

const PIE_COLORS = ["#C8A95E", "#0E2A47", "#3F6B4F", "#A33B3B", "#6E4F8A", "#C76E2E", "#5C7A8E"];

export const AnalyticsDashboard = (props) => {
  const { getAuthHeader } = props;
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const res = await axios.get(`${API}/ai-ads/analytics`, { headers: getAuthHeader() });
      setData(res.data);
    } catch (e) {
      console.error("analytics:", e);
    } finally {
      setBusy(false);
    }
  }, [getAuthHeader]);

  useEffect(() => {
    load();
  }, [load]);

  if (busy && !data) {
    return <p className="text-sm text-muted-foreground" data-testid="ai-analytics-loading">Loading analytics…</p>;
  }
  if (!data) return null;

  const totals = data.totals || {};
  const insights = data.insights || {};
  const charts = data.charts || {};

  const trend = (charts.trend_30_days || []).map((t) => ({ date: (t.date || "").slice(5), count: t.count }));
  const platformUsage = charts.platform_usage || [];
  const typeBreakdown = charts.campaign_type_breakdown || [];
  const items = insights.most_generated_items || [];

  const itemRows = [];
  for (let i = 0; i < items.length; i += 1) {
    itemRows.push(
      <li key={i} className="flex items-center justify-between py-1.5 border-b border-navy/5 last:border-0 text-sm">
        <span className="text-navy truncate flex-1 mr-2">{items[i].item}</span>
        <span className="font-mono text-xs text-muted-foreground">{items[i].count}</span>
      </li>
    );
  }

  const typePieData = [];
  for (let i = 0; i < typeBreakdown.length; i += 1) {
    if (typeBreakdown[i].name) typePieData.push({ name: typeBreakdown[i].name, value: typeBreakdown[i].count });
  }
  const pieCells = [];
  for (let i = 0; i < typePieData.length; i += 1) {
    pieCells.push(<Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />);
  }

  return (
    <div className="space-y-6" data-testid="ai-analytics-tab">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard label="Total Campaigns" value={totals.total_campaigns} icon={Sparkles} testId="ai-analytics-total-campaigns" />
        <StatCard label="Total Generations" value={totals.total_generations} icon={TrendingUp} accent="text-gold" testId="ai-analytics-total-generations" />
        <StatCard label="Ads Generated" value={totals.ads_generated} icon={Sparkles} testId="ai-analytics-ads" />
        <StatCard label="Emails" value={totals.emails_generated} icon={Mail} testId="ai-analytics-emails" />
        <StatCard label="SMS" value={totals.sms_generated} icon={MessageSquare} testId="ai-analytics-sms" />
        <StatCard label="Videos" value={totals.videos_generated} icon={VideoIcon} testId="ai-analytics-videos" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <InsightCard label="Most Used Platform" value={insights.most_used_platform} testId="ai-analytics-top-platform" />
        <InsightCard label="Most Used Campaign Type" value={insights.most_used_campaign_type} testId="ai-analytics-top-type" />
        <InsightCard label="Most Used Goal" value={insights.most_used_goal} testId="ai-analytics-top-goal" />
        <InsightCard label="Generations · Last 30 Days" value={totals.generations_last_30_days} testId="ai-analytics-30d" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Section title="Generation Trend · Last 30 Days" icon={TrendingUp} testId="ai-analytics-trend">
            {trend.length === 0 ? (
              <p className="text-sm text-muted-foreground py-6 text-center">No generations in the last 30 days.</p>
            ) : (
              <div style={{ width: "100%", height: 240 }}>
                <ResponsiveContainer>
                  <LineChart data={trend} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e6e3dd" />
                    <XAxis dataKey="date" stroke="#0E2A47" fontSize={11} />
                    <YAxis stroke="#0E2A47" fontSize={11} allowDecimals={false} />
                    <Tooltip />
                    <Line type="monotone" dataKey="count" stroke="#C8A95E" strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </Section>
        </div>
        <div>
          <Section title="Most Generated Items" icon={Award} testId="ai-analytics-top-items">
            {items.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">No "Promote Item" runs yet.</p>
            ) : (
              <ul>{itemRows}</ul>
            )}
          </Section>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Section title="Platform Usage" icon={BarChart3} testId="ai-analytics-platforms">
          {platformUsage.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6 text-center">No platform data yet.</p>
          ) : (
            <div style={{ width: "100%", height: 240 }}>
              <ResponsiveContainer>
                <BarChart data={platformUsage} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e6e3dd" />
                  <XAxis dataKey="name" stroke="#0E2A47" fontSize={11} />
                  <YAxis stroke="#0E2A47" fontSize={11} allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#0E2A47" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Section>
        <Section title="Campaign Type Breakdown" icon={PieIcon} testId="ai-analytics-types">
          {typePieData.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6 text-center">No campaign type data yet.</p>
          ) : (
            <div style={{ width: "100%", height: 240 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={typePieData} dataKey="value" nameKey="name" outerRadius={80} label>
                    {pieCells}
                  </Pie>
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: "11px" }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </Section>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
