import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Sparkles, Wand2, Save, RotateCcw, Trash2,
  Settings as SettingsIcon,
} from "lucide-react";
import GenerationOutput from "@/pages/dashboard/AiAdsOutput";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Section = ({ title, icon: Icon, children, testId }) => (
  <Card className="bg-card border-2 border-navy/10" data-testid={testId}>
    <CardHeader className="pb-3">
      <CardTitle className="font-serif text-navy text-base flex items-center gap-2">
        {Icon && <Icon className="w-4 h-4 text-gold" />} {title}
      </CardTitle>
    </CardHeader>
    <CardContent>{children}</CardContent>
  </Card>
);

const TemplateOption = ({ template }) => (
  <option value={template.id}>{template.label}</option>
);

const CampaignRow = ({ campaign, onLoad, onDelete }) => {
  const id = campaign.id;
  const name = campaign.name;
  const platform = campaign.platform;
  const goal = campaign.goal;
  const tone = campaign.tone;
  const status = campaign.status;
  return (
    <div
      className="flex flex-wrap items-center gap-2 p-3 bg-background border border-navy/5 rounded-sm hover:border-gold/40"
      data-testid={`ai-campaign-${id}`}
    >
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-navy text-sm">{name}</p>
        <p className="text-xs text-muted-foreground">
          {platform} · {goal} · {tone}
          {status && <span className="ml-2 px-2 py-0.5 rounded-full bg-gold/15 text-[10px] uppercase">{status}</span>}
        </p>
      </div>
      <div className="flex gap-1.5">
        <Button variant="outline" size="sm" onClick={() => onLoad(campaign)} className="border-navy/20 text-xs">
          Load
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onDelete(id)}
          className="border-destructive text-destructive hover:bg-destructive hover:text-white"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
};

const INIT_FORM = {
  name: "",
  goal: "Increase Sales",
  platform: "Facebook",
  audience: "",
  offer: "",
  budget: "",
  tone: "Local New Orleans Style",
  template_id: "",
  industry: "restaurant",
  context: "",
};

export const AiAdsTab = ({ getAuthHeader }) => {
  const [catalog, setCatalog] = useState({ templates: [], goals: [], platforms: [], tones: [] });
  const [form, setForm] = useState(INIT_FORM);
  const [generating, setGenerating] = useState(false);
  const [variationSeed, setVariationSeed] = useState(0);
  const [output, setOutput] = useState(null);
  const [genId, setGenId] = useState(null);
  const [modelUsed, setModelUsed] = useState("");
  const [campaigns, setCampaigns] = useState([]);
  const [stats, setStats] = useState({ total_campaigns: 0, ads_generated: 0 });
  const [config, setConfig] = useState({ provider: "openai", model: "gpt-5" });
  const [error, setError] = useState("");
  const [savedJustNow, setSavedJustNow] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  const loadAll = useCallback(async () => {
    try {
      const headers = getAuthHeader();
      const [t, c, s, cfg] = await Promise.all([
        axios.get(`${API}/ai-ads/templates?industry=restaurant`, { headers }),
        axios.get(`${API}/ai-ads/campaigns`, { headers }),
        axios.get(`${API}/ai-ads/stats`, { headers }),
        axios.get(`${API}/ai-ads/config`, { headers }),
      ]);
      return { catalog: t.data, campaigns: c.data.campaigns || [], stats: s.data, config: cfg.data };
    } catch (e) {
      console.error("AI Ads load error:", e);
      return null;
    }
  }, [getAuthHeader]);

  const refresh = useCallback(async () => {
    const d = await loadAll();
    if (!d) return;
    setCatalog(d.catalog);
    setCampaigns(d.campaigns);
    setStats(d.stats);
    setConfig(d.config);
  }, [loadAll]);

  useEffect(() => {
    let mounted = true;
    loadAll().then((d) => {
      if (!mounted || !d) return;
      setCatalog(d.catalog);
      setCampaigns(d.campaigns);
      setStats(d.stats);
      setConfig(d.config);
    });
    return () => { mounted = false; };
  }, [loadAll]);

  // Filter restaurant templates with a plain loop (avoids Babel plugin recursion bug)
  const restaurantTemplates = [];
  const allTpls = catalog.templates || [];
  for (let i = 0; i < allTpls.length; i += 1) {
    const tpl = allTpls[i];
    if (tpl && tpl.industry === "restaurant") restaurantTemplates.push(tpl);
  }

  // Precompute option/list arrays to avoid Babel plugin recursion bug on inline `.map` with member access
  const templateOptions = [];
  for (let i = 0; i < restaurantTemplates.length; i += 1) {
    templateOptions.push(<TemplateOption key={restaurantTemplates[i].id} template={restaurantTemplates[i]} />);
  }

  const goalOptions = [];
  for (let i = 0; i < (catalog.goals || []).length; i += 1) {
    const g = catalog.goals[i];
    goalOptions.push(<option key={g}>{g}</option>);
  }

  const platformOptions = [];
  for (let i = 0; i < (catalog.platforms || []).length; i += 1) {
    const p = catalog.platforms[i];
    platformOptions.push(<option key={p}>{p}</option>);
  }

  const toneOptions = [];
  for (let i = 0; i < (catalog.tones || []).length; i += 1) {
    const tn = catalog.tones[i];
    toneOptions.push(<option key={tn}>{tn}</option>);
  }


  const selectTemplate = (id) => {
    const tpl = catalog.templates.find((t) => t.id === id);
    if (!tpl) {
      setForm((f) => ({ ...f, template_id: "" }));
      return;
    }
    setForm((f) => ({ ...f, template_id: id, ...tpl.defaults }));
  };

  const runGenerate = async (extra = {}) => {
    setError("");
    setGenerating(true);
    try {
      const payload = { ...form, ...extra };
      // Drop empty optional fields
      ["audience", "offer", "context", "template_id"].forEach((k) => {
        if (!payload[k]) delete payload[k];
      });
      if (payload.budget === "" || payload.budget == null) delete payload.budget;
      else payload.budget = parseFloat(payload.budget);

      const res = await axios.post(`${API}/ai-ads/generate`, payload, { headers: getAuthHeader() });
      setOutput(res.data.output);
      setGenId(res.data.generation_id);
      setModelUsed(res.data.model_used);
      refresh();
    } catch (e) {
      console.error("generate error:", e);
      const detail = e.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Generation failed. Please try again.");
    } finally {
      setGenerating(false);
    }
  };

  const generateMore = () => {
    const next = variationSeed + 1;
    setVariationSeed(next);
    runGenerate({ variation_seed: next });
  };

  const resetForm = () => {
    setForm(INIT_FORM);
    setOutput(null);
    setGenId(null);
    setVariationSeed(0);
    setError("");
  };

  const saveCampaign = async () => {
    if (!output) return;
    if (!form.name.trim()) {
      setError("Please give your campaign a name before saving.");
      return;
    }
    try {
      const payload = {
        name: form.name,
        goal: form.goal,
        platform: form.platform,
        audience: form.audience || null,
        offer: form.offer || null,
        budget: form.budget === "" || form.budget == null ? null : parseFloat(form.budget),
        tone: form.tone,
        template_id: form.template_id || null,
        industry: form.industry,
        context: form.context || null,
        output,
        status: "draft",
      };
      await axios.post(`${API}/ai-ads/campaigns`, payload, { headers: getAuthHeader() });
      setSavedJustNow(true);
      setTimeout(() => setSavedJustNow(false), 2000);
      refresh();
    } catch (e) {
      console.error("save error:", e);
      setError("Failed to save campaign.");
    }
  };

  const deleteCampaign = async (id) => {
    if (!window.confirm("Delete this campaign?")) return;
    try {
      await axios.delete(`${API}/ai-ads/campaigns/${id}`, { headers: getAuthHeader() });
      refresh();
    } catch (e) { console.error(e); }
  };

  const loadCampaign = (c) => {
    setForm({
      name: c.name || "",
      goal: c.goal || "Increase Sales",
      platform: c.platform || "Facebook",
      audience: c.audience || "",
      offer: c.offer || "",
      budget: c.budget == null ? "" : String(c.budget),
      tone: c.tone || "Local New Orleans Style",
      template_id: c.template_id || "",
      industry: c.industry || "restaurant",
      context: c.context || "",
    });
    setOutput(c.output || null);
    setGenId(null);
    setVariationSeed(0);
    setError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const saveModelConfig = async () => {
    try {
      await axios.put(`${API}/ai-ads/config`, config, { headers: getAuthHeader() });
      setShowSettings(false);
    } catch (e) { console.error(e); }
  };

  const campaignRows = [];
  for (let i = 0; i < campaigns.length; i += 1) {
    campaignRows.push(
      <CampaignRow key={campaigns[i].id} campaign={campaigns[i]} onLoad={loadCampaign} onDelete={deleteCampaign} />
    );
  }

  return (
    <section data-testid="ai-ads-tab">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="flex items-center gap-2">
          <h2 className="font-serif text-2xl text-navy font-bold flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-gold" />
            AI Ad Builder
          </h2>
          {modelUsed && (
            <span className="text-[10px] font-sans px-2 py-0.5 rounded-full bg-navy/5 text-navy/70">
              {modelUsed}
            </span>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowSettings((v) => !v)}
          className="border-navy/20 text-navy"
          data-testid="ai-ads-settings-btn"
        >
          <SettingsIcon className="w-4 h-4 mr-1.5" />
          Model
        </Button>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Card className="bg-card border-2 border-navy/10" data-testid="ai-stat-campaigns">
          <CardContent className="py-3 px-4">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Total Campaigns</p>
            <p className="text-2xl font-serif font-bold text-navy">{stats.total_campaigns}</p>
          </CardContent>
        </Card>
        <Card className="bg-card border-2 border-navy/10" data-testid="ai-stat-generations">
          <CardContent className="py-3 px-4">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Ads Generated</p>
            <p className="text-2xl font-serif font-bold text-gold">{stats.ads_generated}</p>
          </CardContent>
        </Card>
        <Card className="bg-card border-2 border-navy/10">
          <CardContent className="py-3 px-4">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Active Model</p>
            <p className="text-sm font-sans font-bold text-navy mt-1.5">{config.provider}/{config.model}</p>
          </CardContent>
        </Card>
        <Card className="bg-card border-2 border-navy/10">
          <CardContent className="py-3 px-4">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Templates</p>
            <p className="text-2xl font-serif font-bold text-forest">{catalog.templates.length}</p>
          </CardContent>
        </Card>
      </div>

      {/* Settings panel */}
      {showSettings && (
        <Card className="mb-6 bg-card border-2 border-gold" data-testid="ai-settings-panel">
          <CardContent className="py-4">
            <p className="font-serif text-navy font-bold mb-3">AI Model Settings</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-muted-foreground mb-1">Provider</label>
                <select
                  data-testid="ai-config-provider"
                  value={config.provider}
                  onChange={(e) => setConfig({ ...config, provider: e.target.value })}
                  className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm"
                >
                  <option value="openai">openai</option>
                  <option value="anthropic">anthropic</option>
                  <option value="gemini">gemini</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-muted-foreground mb-1">Model</label>
                <Input
                  data-testid="ai-config-model"
                  value={config.model}
                  onChange={(e) => setConfig({ ...config, model: e.target.value })}
                  className="border-navy/20"
                  placeholder="gpt-5"
                />
              </div>
              <div className="flex items-end">
                <Button onClick={saveModelConfig} className="bg-gold text-navy hover:bg-gold/90" data-testid="ai-config-save">
                  <Save className="w-4 h-4 mr-1.5" /> Save Model
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Builder */}
        <div className="lg:col-span-1 space-y-4">
          <Section title="Campaign Builder" icon={Wand2} testId="ai-builder">
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-muted-foreground mb-1">Template (optional)</label>
                <select
                  data-testid="ai-template"
                  value={form.template_id}
                  onChange={(e) => selectTemplate(e.target.value)}
                  className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm"
                >
                  <option value="">— Choose template —</option>
                  {templateOptions}
                </select>
              </div>

              <div>
                <label className="block text-xs text-muted-foreground mb-1">Campaign Name *</label>
                <Input
                  data-testid="ai-name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g., Friday Fish Fry"
                  className="border-navy/20"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-muted-foreground mb-1">Goal</label>
                  <select
                    data-testid="ai-goal"
                    value={form.goal}
                    onChange={(e) => setForm({ ...form, goal: e.target.value })}
                    className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm"
                  >
                    {goalOptions}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-muted-foreground mb-1">Platform</label>
                  <select
                    data-testid="ai-platform"
                    value={form.platform}
                    onChange={(e) => setForm({ ...form, platform: e.target.value })}
                    className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm"
                  >
                    {platformOptions}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs text-muted-foreground mb-1">Tone</label>
                <select
                  data-testid="ai-tone"
                  value={form.tone}
                  onChange={(e) => setForm({ ...form, tone: e.target.value })}
                  className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm"
                >
                  {toneOptions}
                </select>
              </div>

              <div>
                <label className="block text-xs text-muted-foreground mb-1">Audience</label>
                <textarea
                  data-testid="ai-audience"
                  value={form.audience}
                  onChange={(e) => setForm({ ...form, audience: e.target.value })}
                  rows={2}
                  placeholder="e.g., NOLA locals 25-65 who love seafood"
                  className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm resize-none"
                />
              </div>

              <div>
                <label className="block text-xs text-muted-foreground mb-1">Offer</label>
                <textarea
                  data-testid="ai-offer"
                  value={form.offer}
                  onChange={(e) => setForm({ ...form, offer: e.target.value })}
                  rows={2}
                  placeholder="e.g., Catfish plate $16.25 every Friday"
                  className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm resize-none"
                />
              </div>

              <div>
                <label className="block text-xs text-muted-foreground mb-1">Budget (optional)</label>
                <Input
                  data-testid="ai-budget"
                  type="number"
                  value={form.budget}
                  onChange={(e) => setForm({ ...form, budget: e.target.value })}
                  placeholder="100"
                  className="border-navy/20"
                />
              </div>

              {error && (
                <p data-testid="ai-error" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-sm p-2">
                  {error}
                </p>
              )}

              <div className="flex flex-wrap gap-2 pt-2">
                <Button
                  data-testid="ai-generate-btn"
                  onClick={() => runGenerate()}
                  disabled={generating}
                  className="bg-gold text-navy hover:bg-gold/90 flex-1 min-w-[140px]"
                >
                  <Sparkles className="w-4 h-4 mr-1.5" />
                  {generating ? "Generating…" : "Generate"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={resetForm}
                  className="border-navy/20"
                  data-testid="ai-reset-btn"
                  title="Reset form"
                >
                  <RotateCcw className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </Section>
        </div>

        {/* Output */}
        <div className="lg:col-span-2">
          {!output && !generating && (
            <Card className="bg-cream border-2 border-dashed border-navy/20">
              <CardContent className="py-16 text-center">
                <Sparkles className="w-12 h-12 mx-auto text-gold mb-4 opacity-60" />
                <p className="font-serif text-lg text-navy mb-2">Ready when you are</p>
                <p className="font-sans text-sm text-muted-foreground max-w-md mx-auto">
                  Pick a template or fill in the brief, then hit Generate. GPT-5 will draft headlines, primary text, CTAs, hashtags, and image concepts.
                </p>
              </CardContent>
            </Card>
          )}

          {generating && (
            <Card className="bg-card border-2 border-gold/30">
              <CardContent className="py-12 text-center">
                <Sparkles className="w-10 h-10 mx-auto text-gold mb-3 animate-pulse" />
                <p className="font-serif text-lg text-navy">Crafting your campaign…</p>
                <p className="text-sm text-muted-foreground mt-1">This usually takes 10–25 seconds.</p>
              </CardContent>
            </Card>
          )}

          {output && (
            <GenerationOutput
              output={output}
              genId={genId}
              variationSeed={variationSeed}
              generating={generating}
              onGenerateMore={generateMore}
              onSave={saveCampaign}
              savedJustNow={savedJustNow}
            />
          )}
        </div>
      </div>

      {/* Saved campaigns */}
      <Section title={`Saved Campaigns (${campaigns.length})`} icon={Save} testId="ai-campaigns-list">
        {campaigns.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-6">No saved campaigns yet.</p>
        ) : (
          <div className="space-y-2">{campaignRows}</div>
        )}
      </Section>
    </section>
  );
};

export default AiAdsTab;
