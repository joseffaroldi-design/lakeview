/**
 * PromoteItemModal — Phase 3 Restaurant Mode entry point.
 *
 * Opens from the Menu Editor "Promote This Item" button. Lets the operator
 * pick a template + which channels to generate, then hits
 *   POST /api/ai-ads/plugins/restaurant/promote
 * which calls the core engine via the Restaurant plugin and returns one
 * structured output per channel. Each result is saved to the Creative Library
 * automatically and can be copied or re-saved with a custom title.
 */
import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { X, Sparkles, Copy, CheckCheck, Save, Square, CheckSquare } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const flattenForCopy = (payload) => {
  if (payload == null) return "";
  if (typeof payload === "string") return payload;
  if (Array.isArray(payload)) return payload.map((x) => flattenForCopy(x)).join("\n");
  if (typeof payload === "object") {
    const out = [];
    for (const k of Object.keys(payload)) {
      out.push(`${k}: ${flattenForCopy(payload[k])}`);
    }
    return out.join("\n");
  }
  return String(payload);
};

const ResultCard = (props) => {
  const result = props.result;
  const [copied, setCopied] = useState(false);
  const text = useMemo(() => flattenForCopy(result.output), [result]);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (_) { /* noop */ }
  };
  if (result.error) {
    return (
      <div
        data-testid={`promote-result-${result.action_id}`}
        className="rounded-lg border-2 border-red-200 bg-red-50 p-4"
      >
        <p className="font-semibold text-red-700 text-sm">{result.label}</p>
        <p className="text-xs text-red-600 mt-1">{result.error}</p>
      </div>
    );
  }
  if (result.loading) {
    return (
      <div
        data-testid={`promote-result-${result.action_id}`}
        className="rounded-lg border-2 border-gold/30 bg-card p-4"
      >
        <div className="flex items-center gap-2 mb-2">
          <div className="w-3.5 h-3.5 border-2 border-gold/30 border-t-gold rounded-full animate-spin" />
          <p className="font-serif text-navy font-semibold text-sm">{result.action_id} · generating…</p>
        </div>
        <div className="h-16 bg-navy/5 rounded animate-pulse" />
      </div>
    );
  }
  return (
    <div
      data-testid={`promote-result-${result.action_id}`}
      className="rounded-lg border-2 border-navy/10 bg-card p-4"
    >
      <div className="flex items-center justify-between mb-2">
        <p className="font-serif text-navy font-semibold text-sm flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-gold" />
          {result.label}
          {result.platform ? <span className="text-xs text-muted-foreground font-sans">· {result.platform}</span> : null}
        </p>
        <Button
          size="sm"
          variant="outline"
          onClick={onCopy}
          className="border-navy/20"
          data-testid={`promote-copy-${result.action_id}`}
        >
          {copied ? <CheckCheck className="w-3.5 h-3.5 mr-1.5" /> : <Copy className="w-3.5 h-3.5 mr-1.5" />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre className="whitespace-pre-wrap text-sm text-navy font-sans bg-background p-3 rounded-sm border border-navy/5 max-h-72 overflow-y-auto">
        {text}
      </pre>
      {result.asset_id ? (
        <p className="text-[10px] uppercase tracking-wider text-forest mt-2">
          ✓ Saved to Library (id: {String(result.asset_id).slice(0, 8)}…)
        </p>
      ) : null}
    </div>
  );
};

export const PromoteItemModal = (props) => {
  const { item, category, getAuthHeader, onClose } = props;
  const [plugin, setPlugin] = useState(null);
  const [templateId, setTemplateId] = useState("daily_special");
  const [selectedActions, setSelectedActions] = useState([]);
  const [campaignName, setCampaignName] = useState("");
  const [results, setResults] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    axios
      .get(`${API}/ai-ads/plugins/restaurant`, { headers: getAuthHeader() })
      .then((res) => {
        if (!mounted) return;
        setPlugin(res.data);
        const all = (res.data.actions || []).map((a) => a.id);
        setSelectedActions(all);
        setCampaignName(`Promote ${item.name || "Menu Item"}`);
      })
      .catch((e) => setError("Failed to load restaurant plugin."));
    return () => { mounted = false; };
  }, [getAuthHeader, item.name]);

  const toggleAction = (id) => {
    setSelectedActions((prev) =>
      prev.indexOf(id) === -1 ? [...prev, id] : prev.filter((x) => x !== id)
    );
  };

  const toggleAll = () => {
    if (!plugin) return;
    const all = plugin.actions.map((a) => a.id);
    setSelectedActions(selectedActions.length === all.length ? [] : all);
  };

  const runPromote = async () => {
    setBusy(true);
    setError("");
    setResults(null);
    // Fan out 1 request per action so each gets its own ingress timeout (60s).
    // The /promote endpoint accepts arbitrary action_ids, but if we send all
    // in one request the backend LLM calls serialize and trip the 60s cap.
    const payloadBase = {
      context: {
        item: {
          name: item.name,
          description: item.description || "",
          category: category || "",
          price: item.price || "",
          image_url: item.image_url || null,
        },
      },
      template_id: templateId,
      save_to_library: true,
      campaign_name: campaignName,
    };
    setResults(selectedActions.map((id) => ({ action_id: id, label: id, loading: true })));
    try {
      const settled = await Promise.allSettled(
        selectedActions.map((actionId) =>
          axios.post(
            `${API}/ai-ads/plugins/restaurant/promote`,
            { ...payloadBase, action_ids: [actionId] },
            { headers: getAuthHeader(), timeout: 70000 }
          )
        )
      );
      const merged = [];
      for (let i = 0; i < settled.length; i += 1) {
        const id = selectedActions[i];
        const res = settled[i];
        if (res.status === "fulfilled") {
          const r = (res.value.data.results || [])[0];
          merged.push(r || { action_id: id, label: id, error: "Empty response" });
        } else {
          const detail = res.reason && res.reason.response && res.reason.response.data && res.reason.response.data.detail;
          merged.push({
            action_id: id,
            label: id,
            error: typeof detail === "string" ? detail : (res.reason && res.reason.message) || "Request failed",
          });
        }
      }
      setResults(merged);
    } catch (e) {
      const detail = e.response && e.response.data && e.response.data.detail;
      setError(typeof detail === "string" ? detail : "Promote run failed.");
    } finally {
      setBusy(false);
    }
  };

  if (!plugin) {
    return (
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
        <div className="bg-card rounded-lg p-6 max-w-md w-full">
          <p className="text-sm text-muted-foreground">Loading Restaurant plugin…</p>
        </div>
      </div>
    );
  }

  const allSelected = selectedActions.length === plugin.actions.length;

  const templateOpts = [];
  for (let i = 0; i < plugin.templates.length; i += 1) {
    templateOpts.push(<option key={plugin.templates[i].id} value={plugin.templates[i].id}>{plugin.templates[i].label}</option>);
  }
  const actionRows = [];
  for (let i = 0; i < plugin.actions.length; i += 1) {
    const a = plugin.actions[i];
    const isOn = selectedActions.indexOf(a.id) !== -1;
    actionRows.push(
      <button
        key={a.id}
        type="button"
        onClick={() => toggleAction(a.id)}
        data-testid={`promote-action-toggle-${a.id}`}
        className={`flex items-center gap-2 px-3 py-2 rounded-sm border text-sm text-left transition-colors ${
          isOn
            ? "border-gold bg-gold/10 text-navy font-semibold"
            : "border-navy/15 text-navy/70 hover:border-gold/40"
        }`}
      >
        {isOn ? <CheckSquare className="w-4 h-4 text-gold" /> : <Square className="w-4 h-4 text-navy/40" />}
        {a.label}
      </button>
    );
  }

  const resultBlocks = [];
  if (results) {
    for (let i = 0; i < results.length; i += 1) {
      resultBlocks.push(<ResultCard key={results[i].action_id} result={results[i]} />);
    }
  }

  return (
    <div
      data-testid="promote-modal"
      className="fixed inset-0 bg-black/60 z-50 flex items-start justify-center p-4 overflow-y-auto"
      onClick={onClose}
    >
      <div
        className="bg-card rounded-lg max-w-4xl w-full my-8 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-navy/10">
          <div>
            <h2 className="font-serif text-xl text-navy font-bold flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-gold" />
              Promote: {item.name}
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {category} · ${item.price || "—"} · One-click multi-channel campaign
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-navy hover:text-gold"
            data-testid="promote-close-btn"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Campaign Name</label>
              <input
                value={campaignName}
                onChange={(e) => setCampaignName(e.target.value)}
                data-testid="promote-campaign-name"
                className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Restaurant Template</label>
              <select
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                data-testid="promote-template-select"
                className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm"
              >
                {templateOpts}
              </select>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-xs text-muted-foreground">
                Channels ({selectedActions.length}/{plugin.actions.length} selected)
              </label>
              <button
                type="button"
                onClick={toggleAll}
                data-testid="promote-toggle-all"
                className="text-xs text-navy underline hover:text-gold"
              >
                {allSelected ? "Deselect All" : "Select All"}
              </button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">{actionRows}</div>
          </div>

          {error ? (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-sm p-3" data-testid="promote-error">
              {error}
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button
              onClick={runPromote}
              disabled={busy || selectedActions.length === 0}
              className="bg-gold text-navy hover:bg-gold/90 flex-1 min-w-[200px]"
              data-testid="promote-run-btn"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              {busy ? `Generating ${selectedActions.length} channels…` : `Generate ${selectedActions.length} Channels`}
            </Button>
            {results ? (
              <Button
                variant="outline"
                onClick={() => setResults(null)}
                className="border-navy/20"
                data-testid="promote-reset-btn"
              >
                <Save className="w-4 h-4 mr-2" />
                Start Over
              </Button>
            ) : null}
          </div>

          {results ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mt-4" data-testid="promote-results">
              {resultBlocks}
            </div>
          ) : (
            <div className="text-center py-10 border-2 border-dashed border-navy/10 rounded-sm" data-testid="promote-empty">
              <p className="font-serif text-navy text-base">Pick your channels and hit Generate.</p>
              <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
                Each channel runs the core AI engine through the Restaurant plugin and saves
                results to the Creative Library automatically.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PromoteItemModal;
