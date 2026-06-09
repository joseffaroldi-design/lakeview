/**
 * Shared brief form + generic specialty runner.
 * Posts to /api/ai-ads/generate/{kind} and returns the structured output.
 */
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sparkles, Save } from "lucide-react";
import { API, Field, Section, Spinner, EmptyState } from "./shared";

export const BriefForm = ({
  catalog,
  defaults,
  showPlatform = true,
  showAudience = true,
  showOffer = true,
  showEmailType = false,
  showAssetSubtype = false,
  showDuration = false,
  subtypeOptions = [],
  durationOptions = [15, 30, 60],
  briefIcon: BriefIcon = Sparkles,
  onSubmit,
  submitLabel = "Generate",
  busy = false,
  testIdPrefix = "ai-brief",
}) => {
  const [form, setForm] = useState({
    name: "",
    goal: "Increase Sales",
    platform: "Facebook",
    tone: "Local New Orleans Style",
    audience: "",
    offer: "",
    email_type: "Promotion",
    asset_subtype: subtypeOptions[0] || "Ad Creative",
    duration_seconds: durationOptions[1] || 30,
    industry: "restaurant",
    ...defaults,
  });

  useEffect(() => {
    if (defaults) setForm((f) => ({ ...f, ...defaults }));
  }, [JSON.stringify(defaults)]);

  const goalOpts = [];
  for (let i = 0; i < (catalog.goals || []).length; i += 1) {
    const g = catalog.goals[i];
    goalOpts.push(<option key={g}>{g}</option>);
  }
  const platOpts = [];
  for (let i = 0; i < (catalog.platforms || []).length; i += 1) {
    const p = catalog.platforms[i];
    platOpts.push(<option key={p}>{p}</option>);
  }
  const toneOpts = [];
  for (let i = 0; i < (catalog.tones || []).length; i += 1) {
    const tn = catalog.tones[i];
    toneOpts.push(<option key={tn}>{tn}</option>);
  }
  const emailOpts = [];
  const emailKinds = ["Welcome", "Promotion", "Holiday", "Winback"];
  for (let i = 0; i < emailKinds.length; i += 1) emailOpts.push(<option key={emailKinds[i]}>{emailKinds[i]}</option>);
  const subtypeOpts = [];
  for (let i = 0; i < subtypeOptions.length; i += 1) subtypeOpts.push(<option key={subtypeOptions[i]}>{subtypeOptions[i]}</option>);
  const durOpts = [];
  for (let i = 0; i < durationOptions.length; i += 1) durOpts.push(<option key={durationOptions[i]} value={durationOptions[i]}>{durationOptions[i]}s</option>);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <Section title="Brief" icon={BriefIcon} testId={`${testIdPrefix}-form`}>
      <div className="space-y-3">
        <Field label="Campaign Name (optional)">
          <Input data-testid={`${testIdPrefix}-name`} value={form.name} onChange={(e) => set("name", e.target.value)} className="border-navy/20" />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Goal">
            <select data-testid={`${testIdPrefix}-goal`} value={form.goal} onChange={(e) => set("goal", e.target.value)} className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm">{goalOpts}</select>
          </Field>
          <Field label="Tone">
            <select data-testid={`${testIdPrefix}-tone`} value={form.tone} onChange={(e) => set("tone", e.target.value)} className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm">{toneOpts}</select>
          </Field>
        </div>
        {showPlatform && (
          <Field label="Platform">
            <select data-testid={`${testIdPrefix}-platform`} value={form.platform} onChange={(e) => set("platform", e.target.value)} className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm">{platOpts}</select>
          </Field>
        )}
        {showEmailType && (
          <Field label="Email Type">
            <select data-testid={`${testIdPrefix}-email-type`} value={form.email_type} onChange={(e) => set("email_type", e.target.value)} className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm">{emailOpts}</select>
          </Field>
        )}
        {showAssetSubtype && (
          <Field label="Image Type">
            <select data-testid={`${testIdPrefix}-asset-subtype`} value={form.asset_subtype} onChange={(e) => set("asset_subtype", e.target.value)} className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm">{subtypeOpts}</select>
          </Field>
        )}
        {showDuration && (
          <Field label="Duration">
            <select data-testid={`${testIdPrefix}-duration`} value={form.duration_seconds} onChange={(e) => set("duration_seconds", parseInt(e.target.value, 10))} className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm">{durOpts}</select>
          </Field>
        )}
        {showAudience && (
          <Field label="Audience">
            <textarea data-testid={`${testIdPrefix}-audience`} value={form.audience} onChange={(e) => set("audience", e.target.value)} rows={2} className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm resize-none" />
          </Field>
        )}
        {showOffer && (
          <Field label="Offer">
            <textarea data-testid={`${testIdPrefix}-offer`} value={form.offer} onChange={(e) => set("offer", e.target.value)} rows={2} className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm resize-none" />
          </Field>
        )}
        <Button
          data-testid={`${testIdPrefix}-submit`}
          onClick={() => onSubmit(form)}
          disabled={busy}
          className="bg-gold text-navy hover:bg-gold/90 w-full"
        >
          <Sparkles className="w-4 h-4 mr-2" />
          {busy ? "Generating…" : submitLabel}
        </Button>
      </div>
    </Section>
  );
};

export const useSpecialtyRunner = (kind, getAuthHeader, onSavedCount) => {
  const [output, setOutput] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [lastBrief, setLastBrief] = useState(null);
  const [savedJustNow, setSavedJustNow] = useState(false);

  const run = useCallback(async (brief) => {
    setError("");
    setBusy(true);
    try {
      const res = await axios.post(`${API}/ai-ads/generate/${kind}`, brief, { headers: getAuthHeader() });
      setOutput(res.data.output);
      setLastBrief(brief);
    } catch (e) {
      const detail = e.response && e.response.data && e.response.data.detail;
      setError(typeof detail === "string" ? detail : "Generation failed.");
    } finally {
      setBusy(false);
    }
  }, [kind, getAuthHeader]);

  const saveAsAsset = useCallback(async (assetKind, title, payload, platform) => {
    try {
      await axios.post(`${API}/ai-ads/assets`, {
        kind: assetKind,
        title,
        platform: platform || null,
        industry: (lastBrief && lastBrief.industry) || "restaurant",
        payload,
      }, { headers: getAuthHeader() });
      setSavedJustNow(true);
      setTimeout(() => setSavedJustNow(false), 2000);
      if (onSavedCount) onSavedCount();
    } catch (e) {
      console.error("save asset failed:", e);
    }
  }, [getAuthHeader, lastBrief, onSavedCount]);

  return { output, busy, error, savedJustNow, run, saveAsAsset, lastBrief };
};

export const OutputPanel = ({ children, EmptyIcon, emptyTitle, emptyBody, busy }) => {
  if (busy) return <Spinner label="Crafting…" />;
  if (!children) return <EmptyState icon={EmptyIcon} title={emptyTitle} body={emptyBody} />;
  return <div className="space-y-4">{children}</div>;
};

export const SaveBtn = ({ savedJustNow, onSave, testId }) => (
  <Button onClick={onSave} size="sm" className="bg-forest text-cream hover:bg-forest/90" data-testid={testId}>
    <Save className="w-3.5 h-3.5 mr-1.5" />
    {savedJustNow ? "Saved ✓" : "Save to Library"}
  </Button>
);
