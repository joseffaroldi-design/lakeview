/**
 * Provider Connections — connect/disconnect each publishing provider.
 * Credentials are submitted to the backend which stores them in
 * provider_connections (server never returns the secret values back).
 */
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import {
  Link2, Unlink, CheckCircle2, Lock, ArrowRight, Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API, Section } from "./shared";

const ProviderCard = (props) => {
  const { provider, connection, onConnect, onDisconnect } = props;
  const [open, setOpen] = useState(false);
  const [creds, setCreds] = useState({});
  const [busy, setBusy] = useState(false);
  const connected = !!connection;
  const comingSoon = provider.coming_soon;

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
        <div className="flex gap-2">
          {connected ? (
            <Button size="sm" variant="outline" onClick={() => onDisconnect(provider.id)} className="border-destructive text-destructive" data-testid={`provider-${provider.id}-disconnect`}>
              <Unlink className="w-3.5 h-3.5 mr-1" /> Disconnect
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={() => setOpen(true)}
              disabled={comingSoon}
              className="bg-navy text-cream hover:bg-navy/90"
              data-testid={`provider-${provider.id}-connect`}
            >
              <Link2 className="w-3.5 h-3.5 mr-1" /> Connect <ArrowRight className="w-3 h-3 ml-1" />
            </Button>
          )}
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
