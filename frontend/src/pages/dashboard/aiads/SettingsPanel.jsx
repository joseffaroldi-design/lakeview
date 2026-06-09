/**
 * Settings panel — model selection (provider+model), defaults, providers catalog.
 */
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Save, Settings as SettingsIcon, Cpu, ImageIcon, Video as VideoIcon } from "lucide-react";
import { API, Section, Field } from "./shared";

const ProviderList = ({ title, icon: Icon, providers, enabled, testId }) => {
  const rows = [];
  for (let i = 0; i < (providers || []).length; i += 1) {
    const p = providers[i];
    const isDefault = !!p.default;
    rows.push(
      <li
        key={`${p.provider}-${p.model}-${i}`}
        className="flex items-center justify-between text-sm py-1.5 border-b border-navy/5 last:border-0"
      >
        <span>{p.label}</span>
        <span className="text-xs text-muted-foreground font-mono">{p.provider}/{p.model}{isDefault ? " · default" : ""}</span>
      </li>
    );
  }
  return (
    <Section title={title} icon={Icon} testId={testId}>
      <p className="text-xs text-muted-foreground mb-2">
        {enabled ? "Active — generations supported." : "Concept-only — wire a provider to enable rendering."}
      </p>
      <ul className="text-sm">{rows}</ul>
    </Section>
  );
};

export const AiSettingsPanel = ({ getAuthHeader }) => {
  const [config, setConfig] = useState({ provider: "openai", model: "gpt-5" });
  const [settings, setSettings] = useState({ default_industry: "restaurant", default_tone: "", default_platform: "", monthly_generation_limit: 0 });
  const [providers, setProviders] = useState({ text: { available: [] }, image: { available: [], enabled: false }, video: { available: [], enabled: false } });
  const [savedJustNow, setSavedJustNow] = useState(false);

  const load = useCallback(async () => {
    try {
      const headers = getAuthHeader();
      const [cfg, st, pr] = await Promise.all([
        axios.get(`${API}/ai-ads/config`, { headers }),
        axios.get(`${API}/ai-ads/settings`, { headers }),
        axios.get(`${API}/ai-ads/providers`, { headers }),
      ]);
      return { cfg: cfg.data, st: st.data, pr: pr.data };
    } catch (e) {
      console.error("settings load:", e);
      return null;
    }
  }, [getAuthHeader]);

  useEffect(() => {
    let mounted = true;
    load().then((d) => {
      if (!mounted || !d) return;
      setConfig(d.cfg);
      setSettings(d.st);
      setProviders(d.pr);
    });
    return () => { mounted = false; };
  }, [load]);

  const save = async () => {
    try {
      await Promise.all([
        axios.put(`${API}/ai-ads/config`, config, { headers: getAuthHeader() }),
        axios.put(`${API}/ai-ads/settings`, settings, { headers: getAuthHeader() }),
      ]);
      setSavedJustNow(true);
      setTimeout(() => setSavedJustNow(false), 2000);
    } catch (e) { console.error("save settings:", e); }
  };

  // Build provider <option>s with precomputed array
  const textProviderOpts = [];
  const tp = providers.text.available || [];
  for (let i = 0; i < tp.length; i += 1) {
    const p = tp[i];
    textProviderOpts.push(<option key={`${p.provider}-${p.model}`} value={`${p.provider}|${p.model}`}>{p.label}</option>);
  }

  const onPickProvider = (val) => {
    const parts = val.split("|");
    setConfig({ provider: parts[0], model: parts[1] });
  };

  return (
    <div className="space-y-6">
      <Section title="AI Model" icon={Cpu} testId="ai-settings-model">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Field label="Active Text Model">
            <select
              data-testid="ai-settings-model-select"
              value={`${config.provider}|${config.model}`}
              onChange={(e) => onPickProvider(e.target.value)}
              className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm"
            >
              {textProviderOpts}
              <option value={`${config.provider}|${config.model}`}>
                Current: {config.provider}/{config.model}
              </option>
            </select>
          </Field>
          <Field label="Provider">
            <Input value={config.provider} onChange={(e) => setConfig({ ...config, provider: e.target.value })} className="border-navy/20" />
          </Field>
          <Field label="Model">
            <Input value={config.model} onChange={(e) => setConfig({ ...config, model: e.target.value })} className="border-navy/20" />
          </Field>
        </div>
      </Section>

      <Section title="Defaults" icon={SettingsIcon} testId="ai-settings-defaults">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Field label="Default Industry">
            <Input data-testid="ai-settings-default-industry" value={settings.default_industry || ""} onChange={(e) => setSettings({ ...settings, default_industry: e.target.value })} className="border-navy/20" placeholder="restaurant" />
          </Field>
          <Field label="Default Tone">
            <Input data-testid="ai-settings-default-tone" value={settings.default_tone || ""} onChange={(e) => setSettings({ ...settings, default_tone: e.target.value })} className="border-navy/20" />
          </Field>
          <Field label="Default Platform">
            <Input data-testid="ai-settings-default-platform" value={settings.default_platform || ""} onChange={(e) => setSettings({ ...settings, default_platform: e.target.value })} className="border-navy/20" />
          </Field>
          <Field label="Monthly Generation Limit (0 = unlimited)">
            <Input
              data-testid="ai-settings-limit"
              type="number"
              value={settings.monthly_generation_limit || 0}
              onChange={(e) => setSettings({ ...settings, monthly_generation_limit: parseInt(e.target.value, 10) || 0 })}
              className="border-navy/20"
            />
          </Field>
        </div>
        <div className="mt-4">
          <Button data-testid="ai-settings-save" onClick={save} className="bg-gold text-navy hover:bg-gold/90">
            <Save className="w-4 h-4 mr-2" />
            {savedJustNow ? "Saved ✓" : "Save Settings"}
          </Button>
        </div>
      </Section>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ProviderList title="Text Providers" icon={Cpu} providers={providers.text.available} enabled={providers.text.enabled} testId="ai-providers-text" />
        <ProviderList title="Image Providers" icon={ImageIcon} providers={providers.image.available} enabled={providers.image.enabled} testId="ai-providers-image" />
        <ProviderList title="Video Providers" icon={VideoIcon} providers={providers.video.available} enabled={providers.video.enabled} testId="ai-providers-video" />
      </div>
    </div>
  );
};

export default AiSettingsPanel;
