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
  ArrowLeft, BookmarkPlus, Bookmark, Wand2, Plus, X,
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

const Designer = ({ getAuthHeader, asset, onBack, onJobStarted, templates }) => {
  const [themes, setThemes] = useState([]);
  const [themesLoading, setThemesLoading] = useState(true);
  const [name, setName] = useState("");
  const [featuresText, setFeaturesText] = useState("");
  const [price, setPrice] = useState("");
  const [quality, setQuality] = useState("medium");
  const [picked, setPicked] = useState(["luxury", "modern"]);
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

const Review = ({ getAuthHeader, job, onStartOver, onReloadTemplates }) => {
  const [savingIdx, setSavingIdx] = useState(null);
  const [savedIdxs, setSavedIdxs] = useState({});

  const successes = (job.variations || []).filter((v) => v.status === "completed");
  const failures = (job.variations || []).filter((v) => v.status === "failed");

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

  return (
    <div className="space-y-4" data-testid="designer-step-review">
      <Section title="Your designs are ready" icon={Wand2} testId="designer-review">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {successes.map((v, i) => {
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
        <div className="flex gap-2 mt-4">
          <Button variant="outline" onClick={onStartOver} className="border-navy/20" data-testid="designer-start-over">
            <RefreshCw className="w-4 h-4 mr-1" /> Design another
          </Button>
        </div>
      </Section>
    </div>
  );
};


// ---------- Top-level -----------------------------------------------------

const AiDesigner = ({ getAuthHeader }) => {
  const [step, setStep] = useState("pick"); // pick | form | progress | review
  const [asset, setAsset] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [expectedCount, setExpectedCount] = useState(1);
  const [completedJob, setCompletedJob] = useState(null);
  const [error, setError] = useState(null);
  const [templates, setTemplates] = useState([]);

  const loadTemplates = useCallback(() => {
    axios.get(`${API}/ai-designer/templates`, { headers: getAuthHeader() })
      .then((r) => setTemplates(r.data.templates || []))
      .catch(() => {});
  }, [getAuthHeader]);

  useEffect(() => { loadTemplates(); }, [loadTemplates]);

  const startOver = () => {
    setStep("pick"); setAsset(null); setJobId(null); setCompletedJob(null); setError(null);
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

      {step === "pick" && <PickPhoto getAuthHeader={getAuthHeader} onSelected={(a) => { setAsset(a); setStep("form"); }} />}
      {step === "form" && asset && (
        <Designer
          getAuthHeader={getAuthHeader}
          asset={asset}
          templates={templates}
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
          onStartOver={startOver}
          onReloadTemplates={loadTemplates}
        />
      )}
    </div>
  );
};

export default AiDesigner;
