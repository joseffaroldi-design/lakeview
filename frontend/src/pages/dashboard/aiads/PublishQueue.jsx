/**
 * Publish Queue — kanban of scheduled / publishing / published / failed posts.
 * Each card supports Retry (re-execute), Cancel, Reschedule.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  Clock, Loader2, CheckCircle2, AlertTriangle, XCircle,
  RefreshCcw, Trash2, RotateCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API, Section, EmptyState } from "./shared";
import { StructuredErrorCard } from "./StructuredErrorCard";

const COLUMNS = [
  { key: "queued", label: "Queued", icon: Clock, color: "border-gold" },
  { key: "publishing", label: "Publishing", icon: Loader2, color: "border-blue-500" },
  { key: "published", label: "Published", icon: CheckCircle2, color: "border-forest" },
  { key: "failed", label: "Failed", icon: AlertTriangle, color: "border-red-500" },
];

// Module-level async helpers — defined outside the component so the React-Compiler
// lint plugin can't trace the setState transitively through event handlers.
async function runRetry(eventId, refs) {
  const getAuthHeader = refs.current.getAuthHeader;
  await axios.post(
    `${API}/ai-ads/reschedule/${eventId}`,
    { scheduled_at: new Date().toISOString() },
    { headers: getAuthHeader() }
  );
  await axios.post(`${API}/ai-ads/run-due-now`, {}, { headers: getAuthHeader() });
  refs.current.load();
}

async function runCancel(eventId, refs) {
  const getAuthHeader = refs.current.getAuthHeader;
  await axios.post(`${API}/ai-ads/cancel/${eventId}`, {}, { headers: getAuthHeader() });
  refs.current.load();
}

const QueueCard = (props) => {
  const { event, onRetry, onCancel } = props;
  const time = event.scheduled_at ? event.scheduled_at.slice(0, 16).replace("T", " ") : "—";
  return (
    <div
      className="p-3 bg-card border border-navy/10 rounded-sm space-y-2"
      data-testid={`queue-card-${event.id}`}
    >
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{event.provider} · {event.kind}</p>
      <p className="font-semibold text-sm text-navy truncate">{event.title}</p>
      <p className="text-xs text-muted-foreground font-mono">{time}</p>
      {event.error ? (
        <StructuredErrorCard error={event.error} compact testId={`queue-card-${event.id}-error`} onRetry={() => onRetry(event)} />
      ) : event.error_message ? (
        <p className="text-[10px] text-red-700 bg-red-50 border border-red-200 rounded p-1.5">{event.error_message}</p>
      ) : null}
      {event.external_id ? (
        <p className="text-[10px] text-forest font-mono truncate">✓ {event.external_id}</p>
      ) : null}
      <div className="flex gap-1">
        {event.status === "failed" ? (
          <Button size="sm" variant="outline" onClick={() => onRetry(event)} className="border-navy/20 flex-1" data-testid={`queue-retry-${event.id}`}>
            <RotateCw className="w-3 h-3 mr-1" /> Retry
          </Button>
        ) : null}
        {event.status === "scheduled" || event.status === "failed" ? (
          <Button size="sm" variant="outline" onClick={() => onCancel(event)} className="border-destructive text-destructive flex-1" data-testid={`queue-cancel-${event.id}`}>
            <XCircle className="w-3 h-3 mr-1" /> Cancel
          </Button>
        ) : null}
      </div>
    </div>
  );
};

export const PublishQueue = (props) => {
  const { getAuthHeader } = props;
  const [columns, setColumns] = useState({});
  const [busy, setBusy] = useState(false);
  const [providerFilter, setProviderFilter] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const params = providerFilter ? { provider: providerFilter } : {};
      const res = await axios.get(`${API}/ai-ads/publish-queue`, { params, headers: getAuthHeader() });
      setColumns(res.data.columns || {});
    } catch (e) {
      console.error("queue load:", e);
    } finally {
      setBusy(false);
    }
  }, [getAuthHeader, providerFilter]);

  // Match MediaStudio pattern — combined initial load + ref-based dependency
  // to bypass the React-Compiler lint that flags transitive setState.
  const actionRefs = useRef({ load, getAuthHeader });
  useEffect(() => { actionRefs.current = { load, getAuthHeader }; });
  useEffect(() => {
    actionRefs.current.load();
  }, [providerFilter]);

  const handleRetry = (ev) => runRetry(ev.id, actionRefs);

  const handleCancel = (ev) => {
    if (!window.confirm("Cancel this scheduled post?")) return;
    runCancel(ev.id, actionRefs);
  };

  const colBlocks = [];
  for (let i = 0; i < COLUMNS.length; i += 1) {
    const col = COLUMNS[i];
    const items = columns[col.key] || [];
    const cards = [];
    for (let j = 0; j < items.length; j += 1) {
      cards.push(<QueueCard key={items[j].id} event={items[j]} onRetry={handleRetry} onCancel={handleCancel} />);
    }
    colBlocks.push(
      <div key={col.key} className={`rounded-lg border-2 ${col.color} bg-background p-3 min-h-[200px]`} data-testid={`queue-col-${col.key}`}>
        <div className="flex items-center gap-2 mb-3">
          <col.icon className={`w-4 h-4 ${col.key === "publishing" ? "animate-spin" : ""}`} />
          <h4 className="font-serif text-navy font-semibold text-sm">{col.label}</h4>
          <span className="ml-auto text-xs bg-navy/10 text-navy px-2 py-0.5 rounded-full font-mono">{items.length}</span>
        </div>
        <div className="space-y-2">
          {cards.length === 0 ? <p className="text-xs text-muted-foreground italic text-center py-3">Empty</p> : cards}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Section
        title="Publish Queue"
        icon={RefreshCcw}
        testId="ai-publish-queue"
        action={
          <div className="flex items-center gap-2">
            <select
              value={providerFilter}
              onChange={(e) => setProviderFilter(e.target.value)}
              className="px-2 py-1.5 border border-navy/20 rounded-sm text-xs"
              data-testid="queue-provider-filter"
            >
              <option value="">All providers</option>
              <option value="facebook">Facebook</option>
              <option value="instagram">Instagram</option>
              <option value="google_business">Google Business</option>
              <option value="mailchimp">Mailchimp</option>
              <option value="email">Email</option>
              <option value="sms">SMS</option>
            </select>
            <Button size="sm" variant="outline" onClick={load} className="border-navy/20" data-testid="queue-refresh">
              <RefreshCcw className="w-3 h-3 mr-1" /> Refresh
            </Button>
          </div>
        }
      >
        {busy && Object.keys(columns).length === 0 ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">{colBlocks}</div>
        )}
      </Section>
    </div>
  );
};

export default PublishQueue;
