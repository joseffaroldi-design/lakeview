/**
 * AI Designer — themed marketing graphic variations via gpt-image-1 image-edit.
 *
 * Lives inside the Promote tab as an alternative to the standard Marketing Pack.
 * Owner uploads (or picks) a photo, types item name + bullet features + price,
 * picks 1–5 themes, sees an estimated cost, confirms, and gets one designed
 * graphic per theme. Winning variations can be saved as templates and re-run on
 * future photos.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  Sparkles, Upload, Image as ImageIcon, Loader2, Download, RefreshCw,
  ArrowLeft, BookmarkPlus, Bookmark, Wand2, X, Check, Mail, MessageSquare, FileText, Hash,
  Pin, Copy as CopyIcon, Folder,
} from "lucide-react";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { API, Section } from "./shared";
import StructuredErrorCard, { parseAxiosError } from "./StructuredErrorCard";

const POLL_MS = 4000;
const POLL_TIMEOUT_MS = 6 * 60 * 1000;

const QUALITY_LABEL = { low: "Low (fast, ~$0.01/img)", medium: "Medium (recommended, ~$0.04/img)", high: "High (best, ~$0.08/img)" };

// ---------- Step 1: Pick photo --------------------------------------------

const PickPhoto = ({ getAuthHeader, onSelected }) => {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [library, setLibrary] = useState([]);
  const [showLibrary, setShowLibrary] = useState(false);
  const fileRef = useRef(null);

  const loadLibrary = async () => {
    try {
      const r = await axios.get(`${API}/media/assets?kind=image&limit=24`, { headers: getAuthHeader() });
      setLibrary(r.data.assets || r.data || []);
      setShowLibrary(true);
    } catch (e) {
      setError(parseAxiosError(e));
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    setUploading(true); setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("folder", "AI Designer");
      fd.append("tags", "ai-designer-source");
      const r = await axios.post(`${API}/media/upload`, fd, {
        headers: { ...getAuthHeader() },
        timeout: 60000,
      });
      onSelected(r.data);
    } catch (e2) {
      setError(parseAxiosError(e2));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <Section title="1. Pick the food photo" icon={ImageIcon} testId="designer-step-pick">
      <div className="space-y-3">
        <p className="text-xs text-muted-foreground">
          We&apos;ll use your photo as the actual hero — the AI only redesigns the background,
          text, and badges around it.
        </p>
        {error ? <StructuredErrorCard error={error} testId="designer-pick-error" onRetry={() => setError(null)} /> : null}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => fileRef.current && fileRef.current.click()}
            disabled={uploading}
            className="border-2 border-dashed border-gold/40 hover:border-gold bg-cream rounded-md p-6 text-center transition-colors disabled:opacity-50"
            data-testid="designer-upload-btn"
          >
            {uploading
              ? <Loader2 className="w-6 h-6 mx-auto animate-spin text-gold" />
              : <Upload className="w-6 h-6 mx-auto text-gold" />}
            <p className="text-sm font-semibold text-navy mt-2">{uploading ? "Uploading…" : "Upload a new photo"}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">JPG, PNG or WebP up to 15 MB</p>
          </button>
          <button
            type="button"
            onClick={loadLibrary}
            className="border-2 border-navy/20 hover:border-gold/60 rounded-md p-6 text-center transition-colors"
            data-testid="designer-pick-from-library"
          >
            <ImageIcon className="w-6 h-6 mx-auto text-navy" />
            <p className="text-sm font-semibold text-navy mt-2">Pick from Library</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">Reuse any saved image</p>
          </button>
        </div>
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleUpload} data-testid="designer-file-input" />

        {showLibrary ? (
          <div className="border-t border-navy/10 pt-3" data-testid="designer-library-grid">
            <p className="text-xs font-semibold text-navy mb-2">Recent photos</p>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
              {library.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => onSelected(a)}
                  className="rounded-sm overflow-hidden border-2 border-transparent hover:border-gold focus:outline-none focus:border-gold"
                  data-testid={`designer-lib-${a.id}`}
                >
                  <img src={`${API}/media/thumb/${a.id}`} alt="" className="w-full h-20 object-cover" />
                </button>
              ))}
              {library.length === 0 ? <p className="col-span-full text-xs text-muted-foreground">No images saved yet.</p> : null}
            </div>
          </div>
        ) : null}
      </div>
    </Section>
  );
};


// ---------- Step 2: Designer form ----------------------------------------

const ThemeCard = ({ theme, selected, onToggle }) => (
  <button
    type="button"
    onClick={onToggle}
    className={`text-left rounded-md p-3 border-2 transition-colors ${
      selected ? "border-gold bg-gold/10" : "border-navy/15 hover:border-gold/50 bg-card"
    }`}
    data-testid={`designer-theme-${theme.id}`}
    aria-pressed={selected}
  >
    <div className="flex items-center justify-between gap-2">
      <p className="text-sm font-semibold text-navy">{theme.label}</p>
      {selected ? <Bookmark className="w-4 h-4 text-gold" /> : null}
    </div>
    <p className="text-[11px] text-muted-foreground mt-1 leading-snug">{theme.style}</p>
  </button>
);

const Designer = ({ getAuthHeader, asset, onBack, onJobStarted, templates, initialValues }) => {
  const init = initialValues || {};
  const [themes, setThemes] = useState([]);
  const [themesLoading, setThemesLoading] = useState(true);
  const [name, setName] = useState(init.item_name || "");
  const [featuresText, setFeaturesText] = useState((init.features || []).join("\n"));
  const [price, setPrice] = useState(init.price || "");
  const [quality, setQuality] = useState(init.quality || "medium");
  const [picked, setPicked] = useState(init.themes && init.themes.length ? init.themes : ["luxury", "modern"]);
  const [autoCopy, setAutoCopy] = useState(true);
  const [estimate, setEstimate] = useState(null);
  const [estimating, setEstimating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [showConfirm, setShowConfirm] = useState(false);

  // Parse features (one per line, auto-split commas)
  const parseFeatures = (text) => {
    const out = [];
    const lines = (text || "").split(/\n+/);
    for (let i = 0; i < lines.length; i += 1) {
      const parts = lines[i].split(/,\s*/);
      for (let j = 0; j < parts.length; j += 1) {
        const t = parts[j].trim();
        if (t) out.push(t);
        if (out.length >= 5) return out;
      }
    }
    return out;
  };
  const features = parseFeatures(featuresText);

  // Load themes
  useEffect(() => {
    let cancelled = false;
    axios.get(`${API}/ai-designer/themes`, { headers: getAuthHeader() })
      .then((r) => { if (!cancelled) { setThemes(r.data.themes || []); setThemesLoading(false); } })
      .catch((e) => { if (!cancelled) { setError(parseAxiosError(e)); setThemesLoading(false); } });
    return () => { cancelled = true; };
  }, [getAuthHeader]);

  // Refresh estimate when themes or quality change
  useEffect(() => {
    let cancelled = false;
    if (picked.length === 0) { setEstimate(null); return; }
    setEstimating(true);
    axios.post(`${API}/ai-designer/estimate`, { themes: picked, quality }, { headers: getAuthHeader() })
      .then((r) => { if (!cancelled) setEstimate(r.data); })
      .catch(() => { /* non-fatal */ })
      .finally(() => { if (!cancelled) setEstimating(false); });
    return () => { cancelled = true; };
  }, [picked, quality, getAuthHeader]);

  const togglePick = (themeId) => {
    setPicked((prev) => {
      if (prev.includes(themeId)) return prev.filter((t) => t !== themeId);
      if (prev.length >= 5) return prev;
      return [...prev, themeId];
    });
  };

  // Auto-convert pasted text into bullets
  const handleFeaturesChange = (val) => {
    // If user pastes a comma-separated string with no newlines, split it
    if (val.indexOf(",") !== -1 && val.indexOf("\n") === -1) {
      const rawParts = val.split(/,\s*/);
      const cleaned = [];
      for (let i = 0; i < rawParts.length; i += 1) {
        const t = rawParts[i].trim();
        if (t) cleaned.push(t);
      }
      if (cleaned.length > 1) {
        setFeaturesText(cleaned.join("\n"));
        return;
      }
    }
    setFeaturesText(val);
  };

  const submit = async () => {
    if (!name.trim()) { setError({ user_message: "Add an item name first." }); return; }
    if (picked.length === 0) { setError({ user_message: "Pick at least one theme." }); return; }
    setSubmitting(true); setError(null);
    try {
      const r = await axios.post(`${API}/ai-designer/generate`, {
        source_asset_id: asset.id,
        item_name: name.trim(),
        features,
        price: price.trim() || null,
        themes: picked,
        quality,
        auto_copy: autoCopy,
      }, { headers: getAuthHeader(), timeout: 30000 });
      onJobStarted(r.data.job_id, picked);
    } catch (e) {
      setError(parseAxiosError(e));
      setShowConfirm(false);
    } finally {
      setSubmitting(false);
    }
  };

  const applyTemplate = (tpl) => {
    setName(tpl.item_name || "");
    setFeaturesText((tpl.features || []).join("\n"));
    setPrice(tpl.price || "");
    setQuality(tpl.quality || "medium");
    setPicked([tpl.theme]);
  };

  const pickedLabels = () => {
    const out = [];
    for (let i = 0; i < picked.length; i += 1) {
      const found = themes.find((x) => x.id === picked[i]);
      out.push(found ? found.label : picked[i]);
    }
    return out.join(", ");
  };

  if (themesLoading) {
    return <Section title="Loading…" icon={Loader2} testId="designer-loading"><Loader2 className="w-5 h-5 animate-spin text-gold" /></Section>;
  }

  return (
    <Section title="2. Design your graphic" icon={Wand2} testId="designer-step-form">
      <div className="grid grid-cols-1 md:grid-cols-[280px,1fr] gap-4">
        <div>
          <div className="rounded-md overflow-hidden border-2 border-gold">
            <img src={`${API}/media/thumb/${asset.id}`} alt="" className="w-full h-44 object-cover" data-testid="designer-preview" />
            <button onClick={onBack} className="w-full text-xs py-1.5 bg-navy/5 hover:bg-navy/10 text-navy" data-testid="designer-change-photo">
              Change photo
            </button>
          </div>

          {templates && templates.length > 0 ? (
            <div className="mt-4 border-t border-navy/10 pt-3">
              <p className="text-xs font-semibold text-navy mb-2 flex items-center gap-1"><Bookmark className="w-3 h-3 text-gold" /> Reuse a winner</p>
              <div className="space-y-1.5" data-testid="designer-templates">
                {templates.slice(0, 5).map((tpl) => (
                  <button
                    key={tpl.id}
                    type="button"
                    onClick={() => applyTemplate(tpl)}
                    className="w-full text-left text-[11px] border border-navy/10 hover:border-gold/50 rounded p-2 bg-cream"
                    data-testid={`designer-template-${tpl.id}`}
                  >
                    <p className="font-semibold text-navy">{tpl.item_name}</p>
                    <p className="text-muted-foreground">{tpl.theme_label} · used {tpl.uses}x</p>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-semibold text-navy mb-1">Item name *</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Smash Burger" className="border-navy/20" data-testid="designer-name" />
          </div>

          <div>
            <label className="block text-xs font-semibold text-navy mb-1">
              Features <span className="text-muted-foreground font-normal">(one per line — up to 5)</span>
            </label>
            <textarea
              value={featuresText}
              onChange={(e) => handleFeaturesChange(e.target.value)}
              rows={5}
              className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm font-mono"
              placeholder={"2 Burger Patties\nAmerican Cheese\nGarlic Aioli\nPickled & Fried Onions\nComes With Fries"}
              data-testid="designer-features"
            />
            <p className="text-[10px] text-muted-foreground mt-0.5">
              {features.length}/5 features detected. Comma-separated text will auto-split into lines.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs font-semibold text-navy mb-1">Price</label>
              <Input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="$20.95" className="border-navy/20" data-testid="designer-price" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-navy mb-1">Quality</label>
              <select
                value={quality}
                onChange={(e) => setQuality(e.target.value)}
                className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm bg-card"
                data-testid="designer-quality"
              >
                <option value="low">{QUALITY_LABEL.low}</option>
                <option value="medium">{QUALITY_LABEL.medium}</option>
                <option value="high">{QUALITY_LABEL.high}</option>
              </select>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-navy">Themes <span className="text-muted-foreground font-normal">(pick 1–5)</span></label>
              <span className="text-[11px] text-muted-foreground">{picked.length} of 5 selected</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2" data-testid="designer-themes">
              {themes.map((t) => (
                <ThemeCard key={t.id} theme={t} selected={picked.includes(t.id)} onToggle={() => togglePick(t.id)} />
              ))}
            </div>
          </div>

          {estimate && (
            <div
              className={`p-2.5 rounded-md text-xs flex items-center justify-between gap-2 ${
                estimate.would_exceed_balance
                  ? "bg-red-50 border border-red-200 text-red-800"
                  : estimate.tier === "low" || estimate.tier === "critical"
                  ? "bg-amber-50 border border-amber-200 text-amber-800"
                  : "bg-cream border border-gold/30 text-navy"
              }`}
              data-testid="designer-estimate"
            >
              <span>
                <strong>Est. cost: ${estimate.total_cost_usd.toFixed(3)}</strong>
                <span className="text-muted-foreground ml-1">
                  ({picked.length} × ${estimate.per_image_cost_usd.toFixed(3)})
                </span>
                {estimating ? <Loader2 className="inline w-3 h-3 ml-1 animate-spin" /> : null}
              </span>
              <span className="text-[11px] font-medium">Balance: ${estimate.current_balance_usd.toFixed(2)}</span>
            </div>
          )}

          {error ? <StructuredErrorCard error={error} testId="designer-form-error" onRetry={() => setError(null)} /> : null}

          <label className="flex items-start gap-2 cursor-pointer p-2.5 bg-cream border border-gold/30 rounded-md" data-testid="designer-auto-copy-row">
            <input
              type="checkbox"
              checked={autoCopy}
              onChange={(e) => setAutoCopy(e.target.checked)}
              className="mt-0.5"
              data-testid="designer-auto-copy"
            />
            <div className="flex-1">
              <p className="text-xs font-semibold text-navy">Also write marketing copy <span className="text-muted-foreground font-normal">(recommended)</span></p>
              <p className="text-[11px] text-muted-foreground">
                Auto-generates Facebook / Instagram / GBP / SMS / Email + hashtags right after the design.
                Adds ~$0.001 — uses your virtual balance.
              </p>
            </div>
          </label>

          <div className="flex gap-2 pt-2">
            <Button variant="outline" onClick={onBack} className="border-navy/20" data-testid="designer-back">
              <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </Button>
            <Button
              onClick={() => setShowConfirm(true)}
              disabled={submitting || picked.length === 0 || !name.trim() || (estimate && estimate.would_exceed_balance)}
              className="bg-gold text-navy hover:bg-gold/90 flex-1"
              data-testid="designer-generate-btn"
            >
              {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
              {estimate && estimate.would_exceed_balance
                ? "Not enough balance — top up"
                : `Generate ${picked.length} design${picked.length === 1 ? "" : "s"}`}
            </Button>
          </div>
        </div>
      </div>

      {/* Confirm dialog */}
      {showConfirm && estimate ? (
        <div
          className="fixed inset-0 z-50 bg-navy/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={(e) => e.target === e.currentTarget && setShowConfirm(false)}
          data-testid="designer-confirm-modal"
        >
          <div className="bg-cream rounded-lg shadow-2xl max-w-md w-full p-6 border-2 border-gold/40">
            <h3 className="font-serif text-xl text-navy font-bold mb-2 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-gold" /> Confirm generation
            </h3>
            <p className="text-sm text-muted-foreground mb-4">
              You&apos;re about to generate <strong>{picked.length}</strong> design{picked.length === 1 ? "" : "s"} ({pickedLabels()})
              at <strong>{quality}</strong> quality.
            </p>
            <div className="bg-card border-2 border-navy/10 rounded-md p-3 mb-4 text-sm">
              <div className="flex justify-between"><span>Per image</span><span className="font-mono">${estimate.per_image_cost_usd.toFixed(3)}</span></div>
              <div className="flex justify-between"><span>Variations</span><span className="font-mono">× {picked.length}</span></div>
              <div className="flex justify-between border-t border-navy/10 pt-2 mt-2 font-semibold"><span>Total</span><span className="font-mono">${estimate.total_cost_usd.toFixed(3)}</span></div>
              <div className="flex justify-between text-xs text-muted-foreground mt-1"><span>Balance after</span><span>${(estimate.current_balance_usd - estimate.total_cost_usd).toFixed(2)}</span></div>
            </div>
            <p className="text-[11px] text-muted-foreground mb-4 italic">
              Each design takes ~30–90 seconds. You can leave this page; results land in your Library when done.
            </p>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setShowConfirm(false)} className="flex-1" data-testid="designer-confirm-cancel">Cancel</Button>
              <Button onClick={submit} disabled={submitting} className="bg-gold text-navy hover:bg-gold/90 flex-1" data-testid="designer-confirm-yes">
                {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                Generate now
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </Section>
  );
};


// ---------- Step 3: Progress ---------------------------------------------

const Progress = ({ getAuthHeader, jobId, onCompleted, onFailed, onCancel, expectedCount }) => {
  const [job, setJob] = useState({ status: "pending", progress: 0, variations: [] });
  const [elapsed, setElapsed] = useState(0);
  const startedRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => {
    startedRef.current = Date.now();
    const tick = async () => {
      try {
        const r = await axios.get(`${API}/ai-designer/job/${jobId}`, { headers: getAuthHeader(), timeout: 15000 });
        setJob(r.data);
        setElapsed(Math.floor((Date.now() - startedRef.current) / 1000));
        if (r.data.status === "completed") {
          if (pollRef.current) clearInterval(pollRef.current);
          onCompleted(r.data);
        } else if (r.data.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          onFailed(r.data.error || { user_message: "Design generation failed.", retry_action: "retry" });
        } else if (Date.now() - startedRef.current > POLL_TIMEOUT_MS) {
          if (pollRef.current) clearInterval(pollRef.current);
          onFailed({ user_message: "Generation took too long. Try fewer themes or lower quality.", retry_action: "retry" });
        }
      } catch (e) { /* keep polling */ }
    };
    tick();
    pollRef.current = setInterval(tick, POLL_MS);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [jobId, getAuthHeader, onCompleted, onFailed]);

  const completed = (job.variations || []).filter((v) => v.status === "completed").length;
  const failed = (job.variations || []).filter((v) => v.status === "failed").length;
  const variations = job.variations || [];

  return (
    <Section title="Designing your graphics" icon={Wand2} testId="designer-step-progress">
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-gold" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-navy" data-testid="designer-progress-label">
              {completed} of {expectedCount} ready · {failed > 0 ? `${failed} failed · ` : ""}elapsed {elapsed}s
            </p>
            <p className="text-xs text-muted-foreground">Each design takes about 30–90 seconds. Hang tight.</p>
          </div>
        </div>
        <div className="h-2 bg-navy/10 rounded-full overflow-hidden">
          <div className="h-full bg-gold transition-all duration-500" style={{ width: `${Math.max(5, job.progress || 0)}%` }} data-testid="designer-progress-bar" />
        </div>
        {variations.length > 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2" data-testid="designer-progress-variations">
            {variations.map((v, i) => (
              <div key={i} className={`rounded border-2 overflow-hidden ${v.status === "completed" ? "border-gold" : v.status === "failed" ? "border-red-300" : "border-navy/10"}`}>
                {v.status === "completed" && v.asset_id ? (
                  <img src={`${API}/media/thumb/${v.asset_id}`} alt="" className="w-full h-20 object-cover" />
                ) : (
                  <div className="h-20 flex items-center justify-center bg-cream">
                    {v.status === "failed"
                      ? <X className="w-5 h-5 text-red-500" />
                      : <Loader2 className="w-4 h-4 animate-spin text-navy/40" />}
                  </div>
                )}
                <p className="text-[10px] text-center py-1 px-1 bg-cream truncate">{v.theme_label || v.theme}</p>
              </div>
            ))}
          </div>
        ) : null}
        <Button variant="outline" onClick={onCancel} size="sm" data-testid="designer-progress-cancel">Cancel</Button>
      </div>
    </Section>
  );
};


// ---------- Step 4: Review ------------------------------------------------

// Small helper: copy a string to clipboard and flash "Copied!" state.
const useCopier = () => {
  const [copiedKey, setCopiedKey] = useState(null);
  const copy = useCallback(async (key, text) => {
    try {
      await navigator.clipboard.writeText(text || "");
      setCopiedKey(key);
      setTimeout(() => setCopiedKey((k) => (k === key ? null : k)), 1500);
    } catch (e) { /* ignore */ }
  }, []);
  return { copiedKey, copy };
};

const CopyButton = ({ id, text, label, icon: Icon, copiedKey, copy, testId }) => {
  const isCopied = copiedKey === id;
  return (
    <button
      type="button"
      onClick={() => copy(id, text)}
      className={`inline-flex items-center gap-1 text-xs font-semibold py-1.5 px-2.5 rounded border transition-colors ${
        isCopied ? "bg-green-50 border-green-300 text-green-800" : "bg-card border-navy/20 text-navy hover:bg-navy/5"
      }`}
      data-testid={testId}
    >
      {isCopied ? <Check className="w-3 h-3" /> : Icon ? <Icon className="w-3 h-3" /> : null}
      {isCopied ? "Copied!" : label}
    </button>
  );
};

const CopyPackPanel = ({ copyPack }) => {
  const { copiedKey, copy } = useCopier();
  const cp = copyPack || {};
  const hashtagText = (cp.hashtags || []).map((h) => `#${h}`).join(" ");
  const emailFull = `Subject: ${cp.email?.subject || ""}\n\n${cp.email?.body || ""}`;
  const igFull = `${cp.ig_post || ""}\n\n${hashtagText}`;

  return (
    <div className="space-y-3" data-testid="designer-copy-pack">
      {/* Facebook */}
      <div className="border border-navy/15 rounded-md overflow-hidden">
        <div className="flex items-center justify-between bg-navy/5 px-3 py-1.5">
          <span className="text-xs font-semibold text-navy flex items-center gap-1.5"><FileText className="w-3.5 h-3.5" /> Facebook post</span>
          <div className="flex gap-1.5">
            <CopyButton id="fb" text={cp.fb_post} label="Copy Caption" icon={Check} copiedKey={copiedKey} copy={copy} testId="copy-fb" />
            <a href="https://www.facebook.com/" target="_blank" rel="noopener noreferrer" className="text-xs underline text-navy/70 hover:text-navy" data-testid="open-fb">Open Facebook</a>
          </div>
        </div>
        <p className="text-sm text-navy whitespace-pre-line p-3" data-testid="fb-post-text">{cp.fb_post || "—"}</p>
      </div>

      {/* Instagram */}
      <div className="border border-navy/15 rounded-md overflow-hidden">
        <div className="flex items-center justify-between bg-navy/5 px-3 py-1.5">
          <span className="text-xs font-semibold text-navy flex items-center gap-1.5"><FileText className="w-3.5 h-3.5" /> Instagram post</span>
          <div className="flex gap-1.5">
            <CopyButton id="ig" text={igFull} label="Copy Caption + Tags" icon={Check} copiedKey={copiedKey} copy={copy} testId="copy-ig" />
            <a href="https://www.instagram.com/" target="_blank" rel="noopener noreferrer" className="text-xs underline text-navy/70 hover:text-navy" data-testid="open-ig">Open Instagram</a>
          </div>
        </div>
        <p className="text-sm text-navy whitespace-pre-line p-3" data-testid="ig-post-text">{cp.ig_post || "—"}</p>
      </div>

      {/* GBP */}
      <div className="border border-navy/15 rounded-md overflow-hidden">
        <div className="flex items-center justify-between bg-navy/5 px-3 py-1.5">
          <span className="text-xs font-semibold text-navy flex items-center gap-1.5"><FileText className="w-3.5 h-3.5" /> Google Business Profile</span>
          <CopyButton id="gbp" text={cp.gbp} label="Copy" icon={Check} copiedKey={copiedKey} copy={copy} testId="copy-gbp" />
        </div>
        <p className="text-sm text-navy whitespace-pre-line p-3" data-testid="gbp-text">{cp.gbp || "—"}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* SMS */}
        <div className="border border-navy/15 rounded-md overflow-hidden">
          <div className="flex items-center justify-between bg-navy/5 px-3 py-1.5">
            <span className="text-xs font-semibold text-navy flex items-center gap-1.5"><MessageSquare className="w-3.5 h-3.5" /> SMS</span>
            <CopyButton id="sms" text={cp.sms} label="Copy SMS" icon={Check} copiedKey={copiedKey} copy={copy} testId="copy-sms" />
          </div>
          <p className="text-sm text-navy whitespace-pre-line p-3" data-testid="sms-text">{cp.sms || "—"}</p>
          <p className="text-[10px] text-muted-foreground px-3 pb-2">{(cp.sms || "").length}/160 chars</p>
        </div>

        {/* Email */}
        <div className="border border-navy/15 rounded-md overflow-hidden">
          <div className="flex items-center justify-between bg-navy/5 px-3 py-1.5">
            <span className="text-xs font-semibold text-navy flex items-center gap-1.5"><Mail className="w-3.5 h-3.5" /> Email</span>
            <CopyButton id="email" text={emailFull} label="Copy Email" icon={Check} copiedKey={copiedKey} copy={copy} testId="copy-email" />
          </div>
          <div className="p-3">
            <p className="text-xs font-semibold text-navy mb-1" data-testid="email-subject">Subject: {cp.email?.subject || "—"}</p>
            <p className="text-sm text-navy whitespace-pre-line" data-testid="email-body">{cp.email?.body || "—"}</p>
          </div>
        </div>
      </div>

      {/* Hashtags */}
      <div className="border border-navy/15 rounded-md overflow-hidden">
        <div className="flex items-center justify-between bg-navy/5 px-3 py-1.5">
          <span className="text-xs font-semibold text-navy flex items-center gap-1.5"><Hash className="w-3.5 h-3.5" /> Hashtags</span>
          <CopyButton id="tags" text={hashtagText} label="Copy Hashtags" icon={Check} copiedKey={copiedKey} copy={copy} testId="copy-hashtags" />
        </div>
        <p className="text-sm text-navy p-3 font-mono leading-relaxed" data-testid="hashtags-text">{hashtagText || "—"}</p>
      </div>
    </div>
  );
};

const Review = ({ getAuthHeader, job, onStartOver, onReloadTemplates, fromRecent = false }) => {
  const [savingIdx, setSavingIdx] = useState(null);
  const [savedIdxs, setSavedIdxs] = useState({});
  const [copyPack, setCopyPack] = useState(job.copy_pack || null);
  // Default-show copy panel only on fresh jobs (auto-copy users expect to see results
  // immediately). When reopened from the Recent rail, show the "View Existing Copy"
  // button instead — matches the Sprint 13C spec.
  const [showCopy, setShowCopy] = useState(Boolean(job.copy_pack) && !fromRecent);
  const [generatingCopy, setGeneratingCopy] = useState(false);
  const [copyError, setCopyError] = useState(null);

  const successes = (job.variations || []).filter((v) => v.status === "completed");
  const failures = (job.variations || []).filter((v) => v.status === "failed");
  const hasCopy = Boolean(copyPack);

  // If autoCopy was on but the job-poll responded BEFORE the copy_pack saved, fetch once.
  useEffect(() => {
    if (hasCopy) return;
    let cancelled = false;
    axios.get(`${API}/ai-designer/jobs/${job.id}/copy`, { headers: getAuthHeader() })
      .then((r) => {
        if (cancelled) return;
        if (r.data.has_copy && r.data.copy_pack) {
          setCopyPack(r.data.copy_pack);
          setShowCopy(true);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [job.id, getAuthHeader, hasCopy]);

  const saveAsTemplate = async (idx) => {
    setSavingIdx(idx);
    try {
      await axios.post(`${API}/ai-designer/jobs/${job.id}/save-template`, { variation_index: idx }, { headers: getAuthHeader() });
      setSavedIdxs((p) => ({ ...p, [idx]: true }));
      if (onReloadTemplates) onReloadTemplates();
    } catch (e) {
      // swallow — non-fatal
    } finally {
      setSavingIdx(null);
    }
  };

  const generateCopy = async () => {
    setGeneratingCopy(true); setCopyError(null);
    try {
      const r = await axios.post(`${API}/ai-designer/jobs/${job.id}/copy`, {}, { headers: getAuthHeader(), timeout: 60000 });
      setCopyPack(r.data.copy_pack);
      setShowCopy(true);
    } catch (e) {
      setCopyError(parseAxiosError(e));
    } finally {
      setGeneratingCopy(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="designer-step-review">
      <Section title="Your designs are ready" icon={Wand2} testId="designer-review">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {successes.map((v) => {
            const actualIdx = (job.variations || []).indexOf(v);
            return (
              <div key={v.asset_id} className="rounded-md overflow-hidden border-2 border-navy/10 bg-card" data-testid={`designer-result-${v.theme}`}>
                <img src={`${API}/media/file/${v.asset_id}`} alt={v.theme_label} className="w-full aspect-square object-cover" />
                <div className="p-2.5">
                  <p className="text-sm font-semibold text-navy">{v.theme_label}</p>
                  <p className="text-[10px] text-muted-foreground mb-2">${(v.cost_usd || 0).toFixed(3)}</p>
                  <div className="flex gap-1.5">
                    <a
                      href={`${API}/media/file/${v.asset_id}`}
                      download
                      className="flex-1 inline-flex items-center justify-center gap-1 bg-gold text-navy text-xs font-semibold py-1.5 px-2 rounded hover:bg-gold/90"
                      data-testid={`designer-download-${v.theme}`}
                    >
                      <Download className="w-3 h-3" /> Download
                    </a>
                    <button
                      type="button"
                      onClick={() => saveAsTemplate(actualIdx)}
                      disabled={savingIdx === actualIdx || savedIdxs[actualIdx]}
                      className="inline-flex items-center justify-center gap-1 border border-navy/20 text-navy text-xs font-semibold py-1.5 px-2 rounded hover:bg-navy/5 disabled:opacity-50"
                      data-testid={`designer-save-template-${v.theme}`}
                      title="Save as reusable template"
                    >
                      {savedIdxs[actualIdx]
                        ? <><Bookmark className="w-3 h-3" /> Saved</>
                        : savingIdx === actualIdx
                        ? <Loader2 className="w-3 h-3 animate-spin" />
                        : <><BookmarkPlus className="w-3 h-3" /> Save</>}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        {failures.length > 0 ? (
          <div className="mt-3 p-2.5 rounded-md bg-amber-50 border border-amber-200 text-xs text-amber-800">
            {failures.length} variation{failures.length === 1 ? "" : "s"} failed ({failures.map((f) => f.theme).join(", ")}). You weren&apos;t charged for failures.
          </div>
        ) : null}
        <div className="flex flex-wrap gap-2 mt-4 items-center">
          <Button variant="outline" onClick={onStartOver} className="border-navy/20" data-testid="designer-start-over">
            <RefreshCw className="w-4 h-4 mr-1" /> Design another
          </Button>
          {hasCopy ? (
            <Button
              onClick={() => setShowCopy((s) => !s)}
              className="bg-navy text-cream hover:bg-navy/90"
              data-testid="designer-view-copy"
            >
              <FileText className="w-4 h-4 mr-1" /> {showCopy ? "Hide" : "View"} Existing Copy
            </Button>
          ) : (
            <Button
              onClick={generateCopy}
              disabled={generatingCopy}
              className="bg-gold text-navy hover:bg-gold/90"
              data-testid="designer-generate-copy"
            >
              {generatingCopy ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1" />}
              {generatingCopy ? "Writing copy…" : "Generate Marketing Pack Copy"}
            </Button>
          )}
        </div>
        {copyError ? <div className="mt-3"><StructuredErrorCard error={copyError} testId="designer-copy-error" onRetry={() => setCopyError(null)} /></div> : null}
      </Section>

      {showCopy && hasCopy ? (
        <Section title="Marketing copy" icon={FileText} testId="designer-copy-section">
          <CopyPackPanel copyPack={copyPack} />
        </Section>
      ) : null}
    </div>
  );
};


// ---------- Recent designs rail (Sprint 13C) ------------------------------

const formatRelative = (iso) => {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 3600) return `${Math.max(1, Math.round(diff / 60))}m ago`;
    if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
    if (diff < 86400 * 7) return `${Math.round(diff / 86400)}d ago`;
    return d.toLocaleDateString();
  } catch (e) { return ""; }
};

const RecentDesignsRail = ({ getAuthHeader, onOpen, onDuplicate, refreshKey }) => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pinningId, setPinningId] = useState(null);

  const reload = useCallback(() => {
    setLoading(true);
    axios.get(`${API}/ai-designer/jobs/recent?limit=5`, { headers: getAuthHeader() })
      .then((r) => setJobs(r.data.jobs || []))
      .catch(() => setJobs([]))
      .finally(() => setLoading(false));
  }, [getAuthHeader]);

  useEffect(() => { reload(); }, [reload, refreshKey]);

  const togglePin = async (jobId) => {
    setPinningId(jobId);
    try {
      await axios.post(`${API}/ai-designer/jobs/${jobId}/pin`, {}, { headers: getAuthHeader() });
      reload();
    } catch (e) { /* swallow — non-fatal */ }
    finally { setPinningId(null); }
  };

  if (loading) {
    return (
      <Section title="Recent AI Designs" icon={Folder} testId="designer-recent-rail">
        <Loader2 className="w-4 h-4 animate-spin text-gold" />
      </Section>
    );
  }

  if (jobs.length === 0) {
    return (
      <Section title="Recent AI Designs" icon={Folder} testId="designer-recent-rail">
        <div className="text-center py-6" data-testid="designer-recent-empty">
          <Folder className="w-8 h-8 mx-auto text-navy/30 mb-2" />
          <p className="text-sm font-semibold text-navy">No AI Designs yet</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Generate your first design below — it&apos;ll show up here for one-tap reuse.
          </p>
        </div>
      </Section>
    );
  }

  return (
    <Section title="Recent AI Designs" icon={Folder} testId="designer-recent-rail">
      <p className="text-[11px] text-muted-foreground mb-3 flex items-center gap-1" data-testid="designer-recent-cost-label">
        <Check className="w-3 h-3 text-green-600" />
        Reopen without spending credits — copy is already saved.
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3" data-testid="designer-recent-grid">
        {jobs.map((j) => (
          <div
            key={j.id}
            className={`rounded-md overflow-hidden border-2 bg-card hover:shadow-md transition-shadow ${j.is_pinned ? "border-gold" : "border-navy/15"}`}
            data-testid={`designer-recent-card-${j.id}`}
          >
            <div className="relative">
              {j.thumb_asset_id ? (
                <img
                  src={`${API}/media/thumb/${j.thumb_asset_id}`}
                  alt={j.item_name}
                  loading="lazy"
                  className="w-full aspect-square object-cover bg-cream"
                />
              ) : (
                <div className="w-full aspect-square bg-cream flex items-center justify-center"><ImageIcon className="w-6 h-6 text-navy/30" /></div>
              )}
              <button
                type="button"
                onClick={() => togglePin(j.id)}
                disabled={pinningId === j.id}
                title={j.is_pinned ? "Unpin" : "Pin (max 3)"}
                className={`absolute top-1 right-1 p-1 rounded ${j.is_pinned ? "bg-gold text-navy" : "bg-card/90 text-navy/60 hover:text-navy"}`}
                data-testid={`designer-recent-pin-${j.id}`}
              >
                {pinningId === j.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Pin className={`w-3 h-3 ${j.is_pinned ? "fill-current" : ""}`} />}
              </button>
              {j.is_pinned ? (
                <span className="absolute top-1 left-1 text-[9px] font-bold uppercase bg-gold text-navy px-1 py-0.5 rounded">Pinned</span>
              ) : null}
            </div>
            <div className="p-2">
              <p className="text-xs font-semibold text-navy truncate" title={j.item_name}>{j.item_name}</p>
              <p className="text-[10px] text-muted-foreground truncate">{j.primary_theme_label || j.primary_theme}</p>
              <div className="flex items-center justify-between mt-1">
                <span className="text-[10px] text-muted-foreground">{formatRelative(j.created_at)}</span>
                <span
                  className={`text-[9px] font-bold uppercase px-1 py-0.5 rounded ${j.has_copy ? "bg-green-100 text-green-800" : "bg-navy/10 text-navy/70"}`}
                  data-testid={`designer-recent-copy-badge-${j.id}`}
                >
                  {j.has_copy ? "Copy Ready" : "No Copy"}
                </span>
              </div>
              <p className="text-[10px] text-muted-foreground mt-0.5">{j.variation_count} variation{j.variation_count === 1 ? "" : "s"}</p>
              <div className="flex gap-1 mt-2">
                <button
                  type="button"
                  onClick={() => onOpen(j.id)}
                  className="flex-1 bg-gold text-navy text-[11px] font-semibold py-1 px-1 rounded hover:bg-gold/90"
                  data-testid={`designer-recent-open-${j.id}`}
                >
                  Open
                </button>
                <button
                  type="button"
                  onClick={() => onDuplicate(j)}
                  title="Use this name/features/price/theme on a new photo"
                  className="inline-flex items-center justify-center border border-navy/20 text-navy text-[11px] font-semibold py-1 px-1.5 rounded hover:bg-navy/5"
                  data-testid={`designer-recent-duplicate-${j.id}`}
                >
                  <CopyIcon className="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
};


// ---------- Top-level -----------------------------------------------------

const AiDesigner = ({ getAuthHeader }) => {
  const [step, setStep] = useState("pick"); // pick | form | progress | review
  const [asset, setAsset] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [expectedCount, setExpectedCount] = useState(1);
  const [completedJob, setCompletedJob] = useState(null);
  const [reopenedFromRail, setReopenedFromRail] = useState(false);
  const [error, setError] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [initialValues, setInitialValues] = useState(null);
  const [recentRefreshKey, setRecentRefreshKey] = useState(0);
  const [openingId, setOpeningId] = useState(null);

  const loadTemplates = useCallback(() => {
    axios.get(`${API}/ai-designer/templates`, { headers: getAuthHeader() })
      .then((r) => setTemplates(r.data.templates || []))
      .catch(() => {});
  }, [getAuthHeader]);

  useEffect(() => { loadTemplates(); }, [loadTemplates]);

  const startOver = () => {
    setStep("pick"); setAsset(null); setJobId(null); setCompletedJob(null); setError(null);
    setInitialValues(null);
    setReopenedFromRail(false);
    setRecentRefreshKey((k) => k + 1);
  };

  // Sprint 13C: Open a previously completed job — read-only, no credits spent.
  const openExisting = async (id) => {
    setOpeningId(id);
    try {
      const r = await axios.get(`${API}/ai-designer/job/${id}`, { headers: getAuthHeader() });
      setCompletedJob(r.data);
      setReopenedFromRail(true);
      setStep("review");
      setError(null);
    } catch (e) {
      setError(parseAxiosError(e));
    } finally {
      setOpeningId(null);
    }
  };

  // Sprint 13C: Duplicate — pre-fill form values, owner uploads a new photo.
  const duplicateJob = (recentJob) => {
    setInitialValues({
      item_name: recentJob.item_name,
      features: recentJob.features || [],
      price: recentJob.price || "",
      themes: recentJob.primary_theme ? [recentJob.primary_theme] : [],
      quality: recentJob.quality || "medium",
    });
    setAsset(null);
    setStep("pick");
    setError(null);
  };

  return (
    <div className="space-y-4" data-testid="ai-designer">
      <div className="flex items-center gap-1 text-xs text-muted-foreground" data-testid="designer-stepper">
        <span className={step === "pick" ? "text-gold font-semibold" : ""}>1. Pick photo</span>
        <span>·</span>
        <span className={step === "form" ? "text-gold font-semibold" : ""}>2. Design</span>
        <span>·</span>
        <span className={step === "progress" ? "text-gold font-semibold" : ""}>3. Generate</span>
        <span>·</span>
        <span className={step === "review" ? "text-gold font-semibold" : ""}>4. Review</span>
      </div>

      {error && step !== "progress" ? (
        <StructuredErrorCard error={error} testId="designer-top-error" onRetry={() => setError(null)} />
      ) : null}

      {step === "pick" && (
        <>
          <RecentDesignsRail
            getAuthHeader={getAuthHeader}
            onOpen={openExisting}
            onDuplicate={duplicateJob}
            refreshKey={recentRefreshKey}
          />
          {openingId ? (
            <div className="text-xs text-muted-foreground flex items-center gap-2" data-testid="designer-opening-spinner">
              <Loader2 className="w-3 h-3 animate-spin" /> Opening saved design…
            </div>
          ) : null}
          <PickPhoto getAuthHeader={getAuthHeader} onSelected={(a) => { setAsset(a); setStep("form"); }} />
        </>
      )}
      {step === "form" && asset && (
        <Designer
          getAuthHeader={getAuthHeader}
          asset={asset}
          templates={templates}
          initialValues={initialValues}
          onBack={() => setStep("pick")}
          onJobStarted={(jid, themes) => { setJobId(jid); setExpectedCount(themes.length); setStep("progress"); }}
        />
      )}
      {step === "progress" && jobId && (
        <Progress
          getAuthHeader={getAuthHeader}
          jobId={jobId}
          expectedCount={expectedCount}
          onCompleted={(j) => { setCompletedJob(j); setStep("review"); }}
          onFailed={(err) => { setError(err); setStep("form"); }}
          onCancel={() => setStep("form")}
        />
      )}
      {step === "review" && completedJob && (
        <Review
          getAuthHeader={getAuthHeader}
          job={completedJob}
          fromRecent={reopenedFromRail}
          onStartOver={startOver}
          onReloadTemplates={loadTemplates}
        />
      )}
    </div>
  );
};

export default AiDesigner;
