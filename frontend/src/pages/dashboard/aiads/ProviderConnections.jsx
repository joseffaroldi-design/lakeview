/**
 * Provider Connections — connect/disconnect each publishing provider.
 * Credentials are submitted to the backend which stores them in
 * provider_connections (server never returns the secret values back).
 */
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import {
  Link2, Unlink, CheckCircle2, Lock, ArrowRight, Loader2, AlertTriangle, ExternalLink, Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API, Section } from "./shared";

const ProviderCard = (props) => {
  const { provider, connection, onConnect, onDisconnect, onTest, getAuthHeader } = props;
  const [open, setOpen] = useState(false);
  const [creds, setCreds] = useState({});
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [setupOpen, setSetupOpen] = useState(false);
  const [setupInfo, setSetupInfo] = useState(null);
  const connected = !!connection;
  const comingSoon = provider.coming_soon;

  const loadSetup = async () => {
    if (setupInfo) { setSetupOpen(!setupOpen); return; }
    try {
      const res = await axios.get(`${API}/ai-ads/provider-setup/${provider.id}`, { headers: getAuthHeader() });
      setSetupInfo(res.data);
      setSetupOpen(true);
    } catch (_) { /* ignore */ }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const r = await onTest(provider.id);
      setTestResult(r);
    } finally {
      setTesting(false);
    }
  };

  const submit = async () => {
    setBusy(true);
    try {
      await onConnect(provider.id, creds);
      setOpen(false);
      setCreds({});
    } finally {
      setBusy(false);
    }
  };

  const fields = [];
  for (let i = 0; i < (provider.credential_fields || []).length; i += 1) {
    const f = provider.credential_fields[i];
    fields.push(
      <div key={f.key}>
        <label className="block text-xs text-muted-foreground mb-0.5">{f.label}</label>
        <Input
          type={f.type === "password" ? "password" : "text"}
          value={creds[f.key] || ""}
          onChange={(e) => setCreds({ ...creds, [f.key]: e.target.value })}
          className="border-navy/20 text-sm"
          placeholder={f.label}
          data-testid={`provider-${provider.id}-field-${f.key}`}
        />
      </div>
    );
  }

  // Build setup steps without .map() — the visual-edits plugin has a known
  // recursion bug on inline array iteration patterns. Manual loop sidesteps it.
  const setupStepEls = [];
  if (setupInfo && setupInfo.steps) {
    for (let i = 0; i < setupInfo.steps.length; i += 1) {
      setupStepEls.push(<li key={i}>{setupInfo.steps[i]}</li>);
    }
  }

  return (
    <div
      className={`rounded-lg border-2 ${connected ? "border-forest" : "border-navy/15"} bg-card p-4`}
      data-testid={`provider-card-${provider.id}`}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <Link2 className="w-4 h-4 text-gold" />
          <p className="font-serif font-semibold text-navy">{provider.label}</p>
        </div>
        {connected ? (
          <span className="text-[10px] uppercase tracking-wider bg-forest/15 text-forest px-2 py-0.5 rounded-full font-semibold">
            <CheckCircle2 className="w-3 h-3 inline mr-1" /> Connected
          </span>
        ) : comingSoon ? (
          <span className="text-[10px] uppercase tracking-wider bg-navy/10 text-navy/60 px-2 py-0.5 rounded-full">
            Coming Soon
          </span>
        ) : (
          <span className="text-[10px] uppercase tracking-wider bg-navy/5 text-navy/60 px-2 py-0.5 rounded-full">
            Not Connected
          </span>
        )}
      </div>
      <p className="text-xs text-muted-foreground mb-3">{provider.description}</p>
      {connected && connection.last_sync ? (
        <p className="text-[10px] text-muted-foreground mb-2">Last sync: {connection.last_sync.slice(0, 16).replace("T", " ")}</p>
      ) : null}

      {/* Last test status pulled from connection record */}
      {connected && connection.last_test_at ? (
        <div className={`text-[10px] rounded p-1.5 mb-2 ${connection.last_test_ok ? "bg-forest/10 text-forest border border-forest/30" : "bg-red-50 text-red-700 border border-red-200"}`}>
          <span className="font-semibold">Last test: </span>
          {connection.last_test_ok ? "✓ Auth OK" : "✗ Failed"}
          {connection.last_test_message ? ` — ${connection.last_test_message.slice(0, 90)}` : ""}
          {connection.last_test_latency_ms ? <span className="opacity-60"> · {connection.last_test_latency_ms}ms</span> : null}
        </div>
      ) : null}

      {/* Live test result (after Test Connection clicked) */}
      {testResult ? (
        <div className={`text-[10px] rounded p-2 mb-2 flex items-start gap-1.5 ${testResult.ok ? "bg-forest/10 text-forest border border-forest/30" : "bg-red-50 text-red-700 border border-red-200"}`} data-testid={`provider-${provider.id}-test-result`}>
          {testResult.ok ? <CheckCircle2 className="w-3 h-3 mt-0.5 flex-shrink-0" /> : <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />}
          <span>{testResult.message}</span>
        </div>
      ) : null}

      {/* Setup guide expander */}
      {setupOpen && setupInfo ? (
        <div className="mb-3 bg-navy/5 border border-navy/15 rounded-sm p-3 text-xs text-navy" data-testid={`provider-${provider.id}-setup`}>
          <p className="font-semibold mb-2">{setupInfo.title}</p>
          <ol className="list-decimal list-inside space-y-1 text-[11px]">
            {setupStepEls}
          </ol>
          {setupInfo.docs_url ? (
            <a href={setupInfo.docs_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-gold underline text-[11px] mt-2">
              Official Docs <ExternalLink className="w-3 h-3" />
            </a>
          ) : null}
        </div>
      ) : null}

      {open ? (
        <div className="space-y-2 mt-3">
          {fields}
          <div className="flex gap-2 mt-2">
            <Button size="sm" onClick={submit} disabled={busy} className="bg-gold text-navy hover:bg-gold/90" data-testid={`provider-${provider.id}-save`}>
              {busy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : null} Save & Connect
            </Button>
            <Button size="sm" variant="outline" onClick={() => setOpen(false)} className="border-navy/20">Cancel</Button>
          </div>
          <p className="text-[10px] text-muted-foreground italic flex items-center gap-1">
            <Lock className="w-2.5 h-2.5" /> Credentials are stored encrypted in your tenant database.
          </p>
        </div>
      ) : (
        <div className="flex gap-2 flex-wrap">
          {connected ? (
            <Button
              size="sm"
              variant="outline"
              onClick={handleTest}
              disabled={testing}
              className="border-gold text-navy hover:bg-gold/10"
              data-testid={`provider-${provider.id}-test`}
            >
              {testing ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5 mr-1" />}
              Test Connection
            </Button>
          ) : null}
          {connected ? (
            <Button size="sm" variant="outline" onClick={() => onDisconnect(provider.id)} className="border-destructive text-destructive" data-testid={`provider-${provider.id}-disconnect`}>
              <Unlink className="w-3.5 h-3.5 mr-1" /> Disconnect
            </Button>
          ) : null}
          {!connected ? (
            <Button
              size="sm"
              onClick={() => setOpen(true)}
              disabled={comingSoon}
              className="bg-navy text-cream hover:bg-navy/90"
              data-testid={`provider-${provider.id}-connect`}
            >
              <Link2 className="w-3.5 h-3.5 mr-1" /> Connect <ArrowRight className="w-3 h-3 ml-1" />
            </Button>
          ) : null}
          {!comingSoon ? (
            <Button
              size="sm"
              variant="outline"
              onClick={loadSetup}
              className="border-navy/20"
              data-testid={`provider-${provider.id}-setup-toggle`}
            >
              <Info className="w-3.5 h-3.5 mr-1" /> {setupOpen ? "Hide" : "Setup Guide"}
            </Button>
          ) : null}
        </div>
      )}
    </div>
  );
};

export const ProviderConnections = (props) => {
  const { getAuthHeader } = props;
  const [providers, setProviders] = useState([]);
  const [connections, setConnections] = useState([]);

  const load = useCallback(async () => {
    try {
      const [pRes, cRes] = await Promise.all([
        axios.get(`${API}/ai-ads/publish-providers`, { headers: getAuthHeader() }),
        axios.get(`${API}/ai-ads/provider-connections`, { headers: getAuthHeader() }),
      ]);
      setProviders(pRes.data.providers || []);
      setConnections(cRes.data.connections || []);
    } catch (e) {
      console.error("providers load:", e);
    }
  }, [getAuthHeader]);

  useEffect(() => { load(); }, [load]);

  const connectProvider = async (id, creds) => {
    await axios.post(
      `${API}/ai-ads/provider-connections/${id}/connect`,
      { credentials: creds },
      { headers: getAuthHeader() }
    );
    load();
  };

  const disconnectProvider = async (id) => {
    if (!window.confirm(`Disconnect ${id}?`)) return;
    await axios.post(`${API}/ai-ads/provider-connections/${id}/disconnect`, {}, { headers: getAuthHeader() });
    load();
  };

  const testProvider = async (id) => {
    try {
      const r = await axios.post(`${API}/ai-ads/provider-connections/${id}/test`, {}, { headers: getAuthHeader() });
      load(); // refresh connection.last_test_* fields
      return r.data;
    } catch (e) {
      const detail = e.response && e.response.data && e.response.data.detail;
      return { ok: false, message: typeof detail === "string" ? detail : "Test failed" };
    }
  };

  const cards = [];
  const byId = {};
  for (const c of connections) byId[c.provider] = c;
  for (let i = 0; i < providers.length; i += 1) {
    cards.push(
      <ProviderCard
        key={providers[i].id}
        provider={providers[i]}
        connection={byId[providers[i].id]}
        onConnect={connectProvider}
        onDisconnect={disconnectProvider}
        onTest={testProvider}
        getAuthHeader={getAuthHeader}
      />
    );
  }

  return (
    <Section title="Provider Connections" icon={Link2} testId="ai-provider-connections">
      <p className="text-xs text-muted-foreground mb-4">
        Connect each platform once. Then any scheduled post for that channel publishes automatically. Stored credentials never leave your database.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">{cards}</div>
    </Section>
  );
};

export default ProviderConnections;
