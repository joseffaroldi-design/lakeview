/**
 * Campaign Builder sub-tab — Phase 1 master generation. Lives inside the AI Ads tab.
 */
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sparkles, Wand2, Save, RotateCcw, Trash2 } from "lucide-react";
import { API, Section, Field, EmptyState, Spinner } from "./shared";
import GenerationOutput from "@/pages/dashboard/AiAdsOutput";

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
        <Button variant="outline" size="sm" onClick={() => onLoad(campaign)} className="border-navy/20 text-xs">Load</Button>
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

export const CampaignBuilder = ({ catalog, getAuthHeader, onChange }) => {
  const [form, setForm] = useState(INIT_FORM);
  const [generating, setGenerating] = useState(false);
  const [variationSeed, setVariationSeed] = useState(0);
  const [output, setOutput] = useState(null);
  const [genId, setGenId] = useState(null);
  const [error, setError] = useState("");
  const [savedJustNow, setSavedJustNow] = useState(false);
  const [campaigns, setCampaigns] = useState([]);

  const loadCampaigns = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/ai-ads/campaigns`, { headers: getAuthHeader() });
      return res.data.campaigns || [];
    } catch (e) { console.error(e); return []; }
  }, [getAuthHeader]);

  useEffect(() => {
    let mounted = true;
    loadCampaigns().then((list) => { if (mounted) setCampaigns(list); });
    return () => { mounted = false; };
  }, [loadCampaigns]);

  const refresh = useCallback(async () => {
    const list = await loadCampaigns();
    setCampaigns(list);
    if (onChange) onChange();
  }, [loadCampaigns, onChange]);

  const selectTemplate = (id) => {
    if (!id) { setForm((f) => ({ ...f, template_id: "" })); return; }
    const tpl = (catalog.templates || []).find((t) => t.id === id);
    if (!tpl) return;
    setForm((f) => ({ ...f, template_id: id, ...tpl.defaults }));
  };

  const runGenerate = async (extra = {}) => {
    setError("");
    setGenerating(true);
    try {
      const payload = { ...form, ...extra };
      ["audience", "offer", "context", "template_id"].forEach((k) => { if (!payload[k]) delete payload[k]; });
      if (payload.budget === "" || payload.budget == null) delete payload.budget;
      else payload.budget = parseFloat(payload.budget);
      const res = await axios.post(`${API}/ai-ads/generate`, payload, { headers: getAuthHeader() });
      setOutput(res.data.output);
      setGenId(res.data.generation_id);
      refresh();
    } catch (e) {
      const detail = e.response && e.response.data && e.response.data.detail;
      setError(typeof detail === "string" ? detail : "Generation failed.");
    } finally {
      setGenerating(false);
    }
  };

  const generateMore = () => {
    const next = variationSeed + 1;
    setVariationSeed(next);
    runGenerate({ variation_seed: next });
  };

  const saveCampaign = async () => {
    if (!output) return;
    if (!form.name.trim()) { setError("Please give your campaign a name before saving."); return; }
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
      setError("Failed to save campaign.");
    }
  };

  const deleteCampaign = async (id) => {
    if (!window.confirm("Delete this campaign?")) return;
    await axios.delete(`${API}/ai-ads/campaigns/${id}`, { headers: getAuthHeader() });
    refresh();
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

  const resetForm = () => {
    setForm(INIT_FORM);
    setOutput(null);
    setGenId(null);
    setVariationSeed(0);
    setError("");
  };

  // Precomputed option arrays — avoids Babel plugin recursion on member-access in .map
  const tpls = [];
  const all = catalog.templates || [];
  for (let i = 0; i < all.length; i += 1) {
    if (all[i] && all[i].industry === "restaurant") tpls.push(all[i]);
  }
  const templateOptions = [];
  for (let i = 0; i < tpls.length; i += 1) templateOptions.push(<TemplateOption key={tpls[i].id} template={tpls[i]} />);

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
  const campaignRows = [];
  for (let i = 0; i < campaigns.length; i += 1) {
    campaignRows.push(
      <CampaignRow key={campaigns[i].id} campaign={campaigns[i]} onLoad={loadCampaign} onDelete={deleteCampaign} />
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-1 space-y-4">
        <Section title="Campaign Builder" icon={Wand2} testId="ai-builder">
          <div className="space-y-3">
            <Field label="Template (optional)">
              <select data-testid="ai-template" value={form.template_id} onChange={(e) => selectTemplate(e.target.value)} className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm">
                <option value="">— Choose template —</option>
                {templateOptions}
              </select>
            </Field>
            <Field label="Campaign Name *">
              <Input data-testid="ai-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g., Friday Fish Fry" className="border-navy/20" />
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Goal">
                <select data-testid="ai-goal" value={form.goal} onChange={(e) => setForm({ ...form, goal: e.target.value })} className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm">{goalOptions}</select>
              </Field>
              <Field label="Platform">
                <select data-testid="ai-platform" value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })} className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm">{platformOptions}</select>
              </Field>
            </div>
            <Field label="Tone">
              <select data-testid="ai-tone" value={form.tone} onChange={(e) => setForm({ ...form, tone: e.target.value })} className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm">{toneOptions}</select>
            </Field>
            <Field label="Audience">
              <textarea data-testid="ai-audience" value={form.audience} onChange={(e) => setForm({ ...form, audience: e.target.value })} rows={2} className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm resize-none" />
            </Field>
            <Field label="Offer">
              <textarea data-testid="ai-offer" value={form.offer} onChange={(e) => setForm({ ...form, offer: e.target.value })} rows={2} className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm resize-none" />
            </Field>
            <Field label="Budget (optional)">
              <Input data-testid="ai-budget" type="number" value={form.budget} onChange={(e) => setForm({ ...form, budget: e.target.value })} className="border-navy/20" />
            </Field>
            {error && <p data-testid="ai-error" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-sm p-2">{error}</p>}
            <div className="flex flex-wrap gap-2 pt-2">
              <Button data-testid="ai-generate-btn" onClick={() => runGenerate()} disabled={generating} className="bg-gold text-navy hover:bg-gold/90 flex-1 min-w-[140px]">
                <Sparkles className="w-4 h-4 mr-1.5" />
                {generating ? "Generating…" : "Generate"}
              </Button>
              <Button variant="outline" size="sm" onClick={resetForm} className="border-navy/20" data-testid="ai-reset-btn">
                <RotateCcw className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </Section>

        <Section title={`Saved Campaigns (${campaigns.length})`} icon={Save} testId="ai-campaigns-list">
          {campaigns.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">No saved campaigns yet.</p>
          ) : (
            <div className="space-y-2">{campaignRows}</div>
          )}
        </Section>
      </div>

      <div className="lg:col-span-2">
        {!output && !generating && (
          <EmptyState icon={Sparkles} title="Ready when you are" body="Pick a template or fill in the brief, then hit Generate. GPT-5 drafts headlines, primary text, CTAs, hashtags, and image concepts." testId="ai-empty" />
        )}
        {generating && <Spinner label="Crafting your campaign…" />}
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
  );
};

export default CampaignBuilder;
