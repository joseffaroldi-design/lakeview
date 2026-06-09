/**
 * SchedulePopover — modal for scheduling a single asset to a provider/time.
 *
 * Used by Creative Library row "Schedule" button and by future bundle flows.
 */
import React, { useEffect, useState } from "react";
import axios from "axios";
import { Calendar as CalendarIcon, Send, X, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API } from "./shared";

const PROVIDERS = ["facebook", "instagram", "google_business", "mailchimp", "email", "sms"];

const defaultLocalDateTime = () => {
  const d = new Date();
  d.setMinutes(d.getMinutes() + 60);
  d.setSeconds(0, 0);
  // Format YYYY-MM-DDTHH:MM (datetime-local expects local, no tz)
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

export const SchedulePopover = (props) => {
  const { asset, getAuthHeader, onClose, onScheduled } = props;
  const [provider, setProvider] = useState("facebook");
  const [whenLocal, setWhenLocal] = useState(defaultLocalDateTime());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    // Smart default: pick a provider that matches the asset.kind/platform when possible
    if (asset.platform) {
      const p = String(asset.platform).toLowerCase().replace(/\s+/g, "_");
      if (PROVIDERS.indexOf(p) !== -1) setProvider(p);
      else if (asset.kind === "email") setProvider("email");
      else if (asset.kind === "sms") setProvider("sms");
    } else if (asset.kind === "email") setProvider("email");
    else if (asset.kind === "sms") setProvider("sms");
  }, [asset]);

  const doSchedule = async (immediate) => {
    setBusy(true);
    setError("");
    try {
      if (immediate) {
        const res = await axios.post(
          `${API}/ai-ads/publish`,
          { asset_id: asset.id, provider },
          { headers: getAuthHeader() }
        );
        onScheduled(res.data);
      } else {
        const iso = new Date(whenLocal).toISOString();
        const res = await axios.post(
          `${API}/ai-ads/schedule`,
          { asset_id: asset.id, provider, scheduled_at: iso },
          { headers: getAuthHeader() }
        );
        onScheduled(res.data);
      }
      onClose();
    } catch (e) {
      const d = e.response && e.response.data && e.response.data.detail;
      setError(typeof d === "string" ? d : "Failed to schedule.");
    } finally {
      setBusy(false);
    }
  };

  const providerOpts = [];
  for (let i = 0; i < PROVIDERS.length; i += 1) {
    providerOpts.push(<option key={PROVIDERS[i]} value={PROVIDERS[i]}>{PROVIDERS[i].replace("_", " ")}</option>);
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
      onClick={onClose}
      data-testid="schedule-popover"
    >
      <div className="bg-card rounded-lg max-w-md w-full p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-serif text-navy font-bold text-lg flex items-center gap-2">
            <CalendarIcon className="w-5 h-5 text-gold" /> Schedule
          </h3>
          <button onClick={onClose} aria-label="Close" data-testid="schedule-close">
            <X className="w-4 h-4 text-navy" />
          </button>
        </div>
        <p className="text-sm text-navy font-semibold mb-1 truncate">{asset.title}</p>
        <p className="text-xs text-muted-foreground mb-4">{asset.kind} · {asset.platform || "—"}</p>

        <div className="space-y-3">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Provider</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm"
              data-testid="schedule-provider"
            >
              {providerOpts}
            </select>
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">When</label>
            <Input
              type="datetime-local"
              value={whenLocal}
              onChange={(e) => setWhenLocal(e.target.value)}
              className="border-navy/20 text-sm"
              data-testid="schedule-when"
            />
          </div>
          {error ? (
            <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2" data-testid="schedule-error">{error}</div>
          ) : null}
          <div className="flex gap-2 pt-2">
            <Button
              onClick={() => doSchedule(false)}
              disabled={busy || !whenLocal}
              className="bg-gold text-navy hover:bg-gold/90 flex-1"
              data-testid="schedule-btn"
            >
              <CalendarIcon className="w-4 h-4 mr-2" /> Schedule
            </Button>
            <Button
              variant="outline"
              onClick={() => doSchedule(true)}
              disabled={busy}
              className="border-navy/20 flex-1"
              data-testid="schedule-publish-now-btn"
            >
              <Zap className="w-4 h-4 mr-2" /> Publish Now
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SchedulePopover;
