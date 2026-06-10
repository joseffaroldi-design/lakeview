/**
 * BillingCard — Home dashboard widget for the self-tracked virtual LLM budget.
 *
 * Tracks usage against a configurable monthly cap (see /api/billing/status).
 * The cap mirrors the owner's real Emergent Universal Key credits; the owner
 * clicks "I just topped up" after adding balance in Emergent to reset it.
 *
 * Tiers:
 *   healthy  (≥ $1.00)  — green, default state
 *   low      (<$1.00)   — amber warning, BUDGET_WARNING_SHOWN telemetry
 *   critical (<$0.50)   — red warning, BUDGET_WARNING_SHOWN telemetry
 *   blocked  ($0)       — red blocked, "Add Balance" + "I just topped up" CTAs
 */
import React, { useEffect, useState } from "react";
import axios from "axios";
import { Wallet, AlertTriangle, ShieldAlert, RefreshCcw, ExternalLink, CheckCircle2 } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const getAuthHeader = () => {
  const t = localStorage.getItem("admin_token");
  return t ? { Authorization: `Bearer ${t}` } : {};
};

const ADD_BALANCE_URL = "https://app.emergent.sh/account/billing";

export default function BillingCard() {
  const [status, setStatus] = useState(null);
  const [spentMonth, setSpentMonth] = useState(0);
  const [loading, setLoading] = useState(true);
  const [resetting, setResetting] = useState(false);
  const warnedRef = React.useRef({ low: false, critical: false });

  const load = async () => {
    try {
      const [s, u] = await Promise.all([
        axios.get(`${API}/billing/status`, { headers: getAuthHeader() }),
        axios.get(`${API}/billing/usage?limit=200`, { headers: getAuthHeader() }),
      ]);
      setStatus(s.data);
      setSpentMonth(u.data.spent_in_window_usd || 0);

      // Emit BUDGET_WARNING_SHOWN telemetry (browser console; backend has its own)
      if (s.data.is_critical && !warnedRef.current.critical) {
        console.info("BUDGET_WARNING_SHOWN tier=critical balance=$" + s.data.current_balance_usd.toFixed(2));
        warnedRef.current.critical = true;
      } else if (s.data.is_low && !warnedRef.current.low) {
        console.info("BUDGET_WARNING_SHOWN tier=low balance=$" + s.data.current_balance_usd.toFixed(2));
        warnedRef.current.low = true;
      }
    } catch (e) {
      console.error("BillingCard load failed", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30000); // refresh every 30s
    return () => clearInterval(id);
  }, []);

  const handleReset = async () => {
    setResetting(true);
    try {
      const r = await axios.post(`${API}/billing/reset`, {}, { headers: getAuthHeader() });
      setStatus(r.data);
      warnedRef.current = { low: false, critical: false };
      toast.success("Virtual balance reset", {
        description: `Restored to $${r.data.monthly_cap_usd.toFixed(2)}. Generate away.`,
      });
    } catch (e) {
      toast.error("Reset failed", { description: String(e?.response?.data?.detail || e.message) });
    } finally {
      setResetting(false);
    }
  };

  if (loading || !status) {
    return (
      <Card className="p-5" data-testid="billing-card-loading">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Wallet className="h-4 w-4" /> Loading AI budget…
        </div>
      </Card>
    );
  }

  const { current_balance_usd, monthly_cap_usd, estimated_packs_remaining,
          estimated_pack_cost_usd, tier, is_blocked, is_low, is_critical } = status;
  const pct = monthly_cap_usd > 0 ? Math.max(0, Math.min(100, (current_balance_usd / monthly_cap_usd) * 100)) : 0;

  const tierStyle = {
    healthy:  { bar: "bg-emerald-500", border: "border-emerald-200", text: "text-emerald-700", bg: "bg-emerald-50" },
    low:      { bar: "bg-amber-500",   border: "border-amber-300",   text: "text-amber-800",   bg: "bg-amber-50" },
    critical: { bar: "bg-red-500",     border: "border-red-300",     text: "text-red-800",     bg: "bg-red-50" },
    blocked:  { bar: "bg-red-600",     border: "border-red-400",     text: "text-red-900",     bg: "bg-red-100" },
  }[tier];

  return (
    <Card className={`p-5 ${tierStyle.border}`} data-testid="billing-card">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          <Wallet className="h-5 w-5 text-amber-700" />
          <h3 className="font-semibold text-base">Estimated Available Budget</h3>
        </div>
        {is_blocked && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
            <ShieldAlert className="h-3 w-3" /> Blocked
          </span>
        )}
        {is_critical && !is_blocked && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
            <AlertTriangle className="h-3 w-3" /> Critical
          </span>
        )}
        {is_low && !is_critical && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
            <AlertTriangle className="h-3 w-3" /> Low
          </span>
        )}
        {tier === "healthy" && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
            <CheckCircle2 className="h-3 w-3" /> Healthy
          </span>
        )}
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-3xl font-bold tracking-tight" data-testid="billing-balance">
          ${current_balance_usd.toFixed(2)}
        </span>
        <span className="text-sm text-muted-foreground">of ${monthly_cap_usd.toFixed(2)}</span>
      </div>
      <div className="mt-2 h-2 w-full rounded-full bg-stone-100 overflow-hidden">
        <div className={`h-full ${tierStyle.bar} transition-all`} style={{ width: `${pct}%` }} />
      </div>

      <div className="mt-3 grid grid-cols-3 gap-3 text-sm">
        <div>
          <div className="text-muted-foreground text-xs uppercase tracking-wide">Packs remaining</div>
          <div className="font-semibold" data-testid="billing-packs-remaining">
            {estimated_packs_remaining.toLocaleString()}
          </div>
        </div>
        <div>
          <div className="text-muted-foreground text-xs uppercase tracking-wide">Est. cost / pack</div>
          <div className="font-semibold">${estimated_pack_cost_usd.toFixed(3)}</div>
        </div>
        <div>
          <div className="text-muted-foreground text-xs uppercase tracking-wide">Spent this month</div>
          <div className="font-semibold" data-testid="billing-spent-month">${spentMonth.toFixed(2)}</div>
        </div>
      </div>

      {(is_blocked || is_critical || is_low) && (
        <div className={`mt-4 p-3 rounded-lg ${tierStyle.bg} ${tierStyle.text} text-sm`}>
          {is_blocked && (
            <span><strong>Generation blocked.</strong> Top up in Emergent, then click &ldquo;I just topped up&rdquo;.</span>
          )}
          {is_critical && !is_blocked && (
            <span><strong>Below ${0.50}.</strong> Plan to top up your Emergent Universal Key soon.</span>
          )}
          {is_low && !is_critical && (
            <span>Balance is below ${1.00}. Consider topping up before your next marketing push.</span>
          )}
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          variant={is_blocked ? "default" : "outline"}
          size="sm"
          onClick={() => window.open(ADD_BALANCE_URL, "_blank", "noopener")}
          data-testid="billing-add-balance-btn"
          className="gap-2"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          Add Balance in Emergent
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleReset}
          disabled={resetting}
          data-testid="billing-topped-up-btn"
          className="gap-2"
          title="Click this after you've added balance in Emergent"
        >
          <RefreshCcw className={`h-3.5 w-3.5 ${resetting ? "animate-spin" : ""}`} />
          I just topped up
        </Button>
      </div>
    </Card>
  );
}
