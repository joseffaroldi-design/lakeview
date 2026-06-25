/**
 * AI Designer — themed marketing graphics via deterministic PIL composition.
 *
 * Lives inside the Promote tab as an alternative to the standard Marketing Pack.
 * Owner picks a photo, enters item name + bullet features + price, picks ONE
 * theme, and receives exactly 3 designed graphics (different layouts). The
 * uploaded food photo is preserved pixel-for-pixel; designs are free. Optional
 * auto-copy writes a marketing pack (FB / IG / GBP / SMS / Email / hashtags)
 * for ~$0.001 per run. Winners can be saved as templates and reused on future
 * photos via the Recent Designs rail.
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
import {
  markGenerationStarted,
  markGenerationCompleted,
  markGenerationAbandoned,
  checkAndResumeGeneration,
  setupAbandonmentDetection,
  hasActiveGeneration,
} from "./aiDesignerAnalytics";
import { bootAiDesigner } from "./aiDesignerBoot";

const POLL_MS = 4000;
const POLL_TIMEOUT_MS = 6 * 60 * 1000;

// ---------- Step 1: Pick photo --------------------------------------------

const PickPhoto = ({
  getAuthHeader,
  onSelected,
  // Sprint 15B.2: parent may pre-fetch the library to de-burst boot calls.
  prefetchedLibrary,
  prefetchedLibraryLoading,
  prefetchedLibraryError,
  onRetryPrefetch,
}) => {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [library, setLibrary] = useState([]);
  const [libraryLoadingLocal, setLibraryLoadingLocal] = useState(false);
  const [showLibrary, setShowLibrary] = useState(false);
  const fileRef = useRef(null);

  // Pull from parent prefetch when available; lazy-load on click as fallback.
  const usingPrefetch = prefetchedLibrary !== undefined;
  const effectiveLibrary = usingPrefetch ? (prefetchedLibrary || []) : library;
  const effectiveLoading = usingPrefetch ? !!prefetchedLibraryLoading : libraryLoadingLocal;
  const effectiveError = usingPrefetch ? prefetchedLibraryError : null;

  const loadLibrary = async () => {
    if (usingPrefetch) {
      // Show the prefetched data; if it failed, surface inline retry.
      setShowLibrary(true);
      return;
    }
    try {
      setLibraryLoadingLocal(true);
      const r = await axios.get(`${API}/media/assets?kind=image&limit=24`, { headers: getAuthHeader() });
      setLibrary(r.data.assets || r.data || []);
      setShowLibrary(true);
    } catch (e) {
      setError(parseAxiosError(e));
    } finally {
      setLibraryLoadingLocal(false);
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
          We use your photo as the actual hero — your original food photo is preserved
          pixel-for-pixel. Designs are free. Each run creates 3 designs.
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
            disabled={effectiveLoading}
            className="border-2 border-navy/20 hover:border-gold/60 rounded-md p-6 text-center transition-colors disabled:opacity-60"
            data-testid="designer-pick-from-library"
          >
            {effectiveLoading
              ? <Loader2 className="w-6 h-6 mx-auto animate-spin text-navy" />
              : <ImageIcon className="w-6 h-6 mx-auto text-navy" />}
            <p className="text-sm font-semibold text-navy mt-2">{effectiveLoading ? "Loading library…" : "Pick from Library"}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">Reuse any saved image</p>
          </button>
        </div>
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleUpload} data-testid="designer-file-input" />

        {showLibrary && effectiveError ? (
          <div className="border-t border-navy/10 pt-3 text-xs text-muted-foreground flex items-center justify-between gap-2" data-testid="designer-library-error">
            <span>Couldn&apos;t load your photo library. Production may be warming up.</span>
            {onRetryPrefetch ? (
              <button type="button" onClick={onRetryPrefetch} className="text-xs font-semibold text-gold hover:underline" data-testid="designer-library-retry">
                Try again
              </button>
            ) : null}
          </div>
        ) : null}

        {showLibrary && !effectiveError ? (
          <div className="border-t border-navy/10 pt-3" data-testid="designer-library-grid">
            <p className="text-xs font-semibold text-navy mb-2">Recent photos</p>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
              {effectiveLibrary.map((a) => (
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
              {effectiveLibrary.length === 0 && !effectiveLoading ? <p className="col-span-full text-xs text-muted-foreground">No images saved yet.</p> : null}
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
      <div className="flex items-center gap-2 min-w-0">
        {theme.preview_color ? (
          <span
            aria-hidden="true"
            className="w-3 h-3 rounded-full border border-navy/20 shrink-0"
            style={{ backgroundColor: theme.preview_color }}
            data-testid={`designer-theme-swatch-${theme.id}`}
          />
        ) : null}
        <p className="text-sm font-semibold text-navy truncate">{theme.label}</p>
      </div>
      {selected ? <Bookmark className="w-4 h-4 text-gold shrink-0" /> : null}
    </div>
    {(theme.best_use || theme.style) ? (
      <p className="text-[11px] text-muted-foreground mt-1 leading-snug">
        {theme.best_use || theme.style}
      </p>
    ) : null}
  </button>
);

// Sprint 16F.1 — Grouped theme picker. Renders one collapsible section per
// pack so the 22-theme list stays scannable. Falls back to a flat grid when
// the backend doesn't ship `packs[]` metadata (older preview pods).
const PackSection = ({ pack, packThemes, pickedId, onToggle, defaultOpen }) => {
  if (!packThemes || packThemes.length === 0) return null;
  return (
    <details
      open={defaultOpen}
      className="rounded-md border border-navy/10 bg-card/40 px-2.5 py-2 mb-2 last:mb-0 group"
      data-testid={`designer-pack-${pack.id}`}
    >
      <summary
        className="cursor-pointer select-none flex items-center justify-between gap-2 list-none [&::-webkit-details-marker]:hidden"
        data-testid={`designer-pack-summary-${pack.id}`}
      >
        <div className="min-w-0">
          <p className="text-xs font-semibold text-navy uppercase tracking-wide">
            <span className="inline-block w-2 h-2 rounded-full bg-gold mr-2 align-middle" aria-hidden="true" />
            {pack.label}
          </p>
          {pack.description ? (
            <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug truncate">
              {pack.description}
            </p>
          ) : null}
        </div>
        <span
          className="text-[10px] font-medium text-muted-foreground bg-navy/5 rounded-full px-2 py-0.5 shrink-0"
          data-testid={`designer-pack-count-${pack.id}`}
        >
          {packThemes.length} themes
        </span>
      </summary>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
        {packThemes.map((t) => (
          <ThemeCard
            key={t.id}
            theme={t}
            selected={pickedId === t.id}
            onToggle={() => onToggle(t.id)}
          />
        ))}
      </div>
    </details>
  );
};

const Designer = ({
  getAuthHeader, asset, onBack, onJobStarted, templates, initialValues,
  // Sprint 15B.2: parent may prefetch themes during boot
  prefetchedThemes, prefetchedThemesLoading, prefetchedThemesError, onRetryThemes,
  // Sprint 16F.1: parent may also stream the `packs[]` grouped metadata
  prefetchedPacks,
}) => {
  const init = initialValues || {};
  const usingPrefetchThemes = prefetchedThemes !== undefined;
  const [themesLocal, setThemesLocal] = useState([]);
  const [packsLocal, setPacksLocal] = useState([]);
  const [themesLoadingLocal, setThemesLoadingLocal] = useState(!usingPrefetchThemes);
  const themes = usingPrefetchThemes ? (prefetchedThemes || []) : themesLocal;
  const packs = usingPrefetchThemes ? (prefetchedPacks || []) : packsLocal;
  const themesLoading = usingPrefetchThemes ? !!prefetchedThemesLoading : themesLoadingLocal;
  const themesError = usingPrefetchThemes ? prefetchedThemesError : null;
  const [name, setName] = useState(init.item_name || "");
  const [featuresText, setFeaturesText] = useState((init.features || []).join("\n"));
  const [price, setPrice] = useState(init.price || "");
  const [picked, setPicked] = useState(init.themes && init.themes.length ? [init.themes[0]] : ["modern"]);
  const [autoCopy, setAutoCopy] = useState(true);
  // Sprint 15B.3: rembg/background-removal is now opt-in. Default OFF so the
  // single-worker production pod isn't blocked by the ~5-15s rembg call.
  const [removeBackground, setRemoveBackground] = useState(false);
  const [estimate, setEstimate] = useState(null);
  const [estimating, setEstimating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [showConfirm, setShowConfirm] = useState(false);
  // Sprint 15B.3: AbortController for cancelling in-flight generation if the
  // component unmounts mid-request (e.g. user navigates away).
  const submitAbortRef = useRef(null);

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

  // Load themes once on mount IF parent didn't prefetch them. `getAuthHeader`
  // identity may change on each parent render, so we intentionally exclude it
  // from deps to avoid an infinite fetch loop that would keep cancelling itself
  // before the response lands.
  useEffect(() => {
    if (usingPrefetchThemes) return undefined;
    let cancelled = false;
    axios.get(`${API}/ai-designer/themes`, { headers: getAuthHeader() })
      .then((r) => {
        if (cancelled) return;
        setThemesLocal(r.data.themes || []);
        setPacksLocal(r.data.packs || []);
        setThemesLoadingLocal(false);
      })
      .catch((e) => { if (!cancelled) { setError(parseAxiosError(e)); setThemesLoadingLocal(false); } });
    return () => { cancelled = true; };
  }, []);

  // Refresh estimate when theme changes (single theme, always 3 variations,
  // designs are always free — estimate just confirms tier + auto-copy budget).
  useEffect(() => {
    let cancelled = false;
    if (picked.length === 0) { setEstimate(null); return; }
    setEstimating(true);
    axios.post(`${API}/ai-designer/estimate`, { theme: picked[0] }, { headers: getAuthHeader() })
      .then((r) => { if (!cancelled) setEstimate(r.data); })
      .catch(() => { /* non-fatal */ })
      .finally(() => { if (!cancelled) setEstimating(false); });
    return () => { cancelled = true; };
  }, [picked]);

  // Single-select theme. Always exactly 3 variations are produced.
  const togglePick = (themeId) => setPicked([themeId]);

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
    // Sprint 15B.3: hard guard against double-submission. Even if the button
    // is disabled in markup, fast enter-key or programmatic clicks could fire
    // twice; this short-circuits the duplicate.
    if (submitting) return;
    if (!name.trim()) { setError({ user_message: "Add an item name first." }); return; }
    if (picked.length === 0) { setError({ user_message: "Pick at least one theme." }); return; }
    setSubmitting(true); setError(null);
    // Build an AbortController so navigation away cancels the request
    if (submitAbortRef.current) submitAbortRef.current.abort();
    submitAbortRef.current = new AbortController();
    try {
      const r = await axios.post(`${API}/ai-designer/generate`, {
        source_asset_id: asset.id,
        item_name: name.trim(),
        features,
        price: price.trim() || null,
        theme: picked[0],
        auto_copy: autoCopy,
        remove_background: removeBackground,
      }, { headers: getAuthHeader(), timeout: 45000, signal: submitAbortRef.current.signal });
      onJobStarted(r.data.job_id, [picked[0]], {
        item_name: name.trim(),
        theme: picked[0],
        auto_copy: autoCopy,
        remove_background: removeBackground,
      });
    } catch (e) {
      // Sprint 15B.3: friendlier message for AI Designer specifically.
      // The global toast (route-aware) still fires for 5xx so the owner has
      // diagnostic detail, but inline form copy is gentle.
      if (e.code === "ERR_CANCELED" || e.name === "CanceledError" || e.message === "canceled") {
        // User navigated away — silent.
        return;
      }
      const status = (e.response && e.response.status) || 0;
      if (status === 0 || status >= 500 || e.code === "ECONNABORTED") {
        setError({ user_message: "AI Designer is busy. Try again in a moment." });
      } else {
        setError(parseAxiosError(e));
      }
      setShowConfirm(false);
    } finally {
      setSubmitting(false);
    }
  };

  // Sprint 15B.3: cancel any in-flight generation if the user navigates away.
  useEffect(() => () => {
    if (submitAbortRef.current) {
      try { submitAbortRef.current.abort(); } catch (_) { /* noop */ }
    }
  }, []);

  const applyTemplate = (tpl) => {
    setName(tpl.item_name || "");
    setFeaturesText((tpl.features || []).join("\n"));
    setPrice(tpl.price || "");
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
  if (themesError && (!themes || themes.length === 0)) {
    return (
      <Section title="2. Design your graphic" icon={Wand2} testId="designer-step-form">
        <div className="text-sm text-muted-foreground" data-testid="designer-themes-error">
          Couldn&apos;t load design themes. Production may be warming up.
          {onRetryThemes ? (
            <button type="button" onClick={onRetryThemes} className="ml-2 text-xs font-semibold text-gold hover:underline" data-testid="designer-themes-retry">
              Try again
            </button>
          ) : null}
        </div>
      </Section>
    );
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

          <div>
              <label className="block text-xs font-semibold text-navy mb-1">Price</label>
              <Input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="$20.95" className="border-navy/20" data-testid="designer-price" />
            </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-navy">
                Theme <span className="text-muted-foreground font-normal">(pick one — you&apos;ll get 3 variations)</span>
              </label>
              <span className="text-[11px] text-muted-foreground" data-testid="designer-variations-count">
                3 variations × free
              </span>
            </div>
            <div data-testid="designer-themes">
              {packs && packs.length > 0 ? (
                (() => {
                  // Sprint 16F.1: bucket themes by pack (preserves pack ordering).
                  const byPack = new Map();
                  for (let i = 0; i < themes.length; i += 1) {
                    const t = themes[i];
                    const pid = t.pack || "_other";
                    if (!byPack.has(pid)) byPack.set(pid, []);
                    byPack.get(pid).push(t);
                  }
                  // Open the pack that contains the currently picked theme;
                  // if nothing matches, open the first pack.
                  const pickedPack = (themes.find((t) => t.id === picked[0]) || {}).pack;
                  const orderedPacks = packs.slice();
                  const otherThemes = byPack.get("_other") || [];
                  if (otherThemes.length) {
                    orderedPacks.push({ id: "_other", label: "Other", description: "", theme_ids: otherThemes.map((t) => t.id) });
                  }
                  return orderedPacks.map((p, idx) => {
                    const list = byPack.get(p.id) || [];
                    const isPickedPack = pickedPack ? pickedPack === p.id : idx === 0;
                    return (
                      <PackSection
                        key={p.id}
                        pack={p}
                        packThemes={list}
                        pickedId={picked[0]}
                        onToggle={togglePick}
                        defaultOpen={isPickedPack}
                      />
                    );
                  });
                })()
              ) : (
                // Backward-compatible flat grid when /themes payload lacks packs[]
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2" data-testid="designer-themes-flat">
                  {themes.map((t) => (
                    <ThemeCard key={t.id} theme={t} selected={picked[0] === t.id} onToggle={() => togglePick(t.id)} />
                  ))}
                </div>
              )}
            </div>
          </div>

          {estimate && (
            <div
              className="p-2.5 rounded-md text-xs flex items-center justify-between gap-2 bg-cream border border-gold/30 text-navy"
              data-testid="designer-estimate"
            >
              <span>
                <strong>3 designs · FREE</strong>
                <span className="text-muted-foreground ml-1">(PIL composition — no LLM image cost)</span>
              </span>
              {autoCopy ? <span className="text-[11px] font-medium">+ copy ~${estimate.with_copy_cost_usd?.toFixed(3) ?? "0.001"}</span> : null}
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
                Designs are free. Marketing copy uses a small amount of AI credit (~$0.001) to write your
                Facebook / Instagram / GBP / SMS / Email + hashtags.
              </p>
            </div>
          </label>

          {/* Sprint 15B.3: opt-in background removal. Default OFF so the
              normal flow is fast and won't block the production worker. */}
          <label className="flex items-start gap-2 cursor-pointer p-2.5 bg-white border border-navy/15 rounded-md" data-testid="designer-remove-bg-row">
            <input
              type="checkbox"
              checked={removeBackground}
              onChange={(e) => setRemoveBackground(e.target.checked)}
              className="mt-0.5"
              data-testid="designer-remove-bg"
            />
            <div className="flex-1">
              <p className="text-xs font-semibold text-navy">Remove background from food photo <span className="text-muted-foreground font-normal">(slower)</span></p>
              <p className="text-[11px] text-muted-foreground">
                Cleaner cutouts but adds ~5–15 s per generation. Leave off for fast designs that use a rounded crop instead.
              </p>
            </div>
          </label>

          <div className="flex gap-2 pt-2">
            <Button variant="outline" onClick={onBack} disabled={submitting} className="border-navy/20" data-testid="designer-back">
              <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </Button>
            <Button
              onClick={() => { if (!submitting) setShowConfirm(true); }}
              disabled={submitting || picked.length === 0 || !name.trim()}
              className="bg-gold text-navy hover:bg-gold/90 flex-1"
              data-testid="designer-generate-btn"
            >
              {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
              {submitting ? "Generating…" : "Generate 3 designs"}
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
              You&apos;re about to generate <strong>3 design variations</strong> using the <strong>{pickedLabels()}</strong> theme.
              Layouts: <em>centered</em>, <em>side-by-side</em>, and <em>stacked</em>.
              Your original food photo will be preserved pixel-for-pixel.
            </p>
            <div className="bg-card border-2 border-navy/10 rounded-md p-3 mb-4 text-sm">
              <div className="flex justify-between"><span>3 designs (PIL composition)</span><span className="font-mono text-green-700">FREE</span></div>
              {autoCopy ? (
                <div className="flex justify-between text-xs text-muted-foreground"><span>+ marketing copy</span><span className="font-mono">~${estimate.with_copy_cost_usd?.toFixed(3) ?? "0.001"}</span></div>
              ) : null}
              <div className="flex justify-between border-t border-navy/10 pt-2 mt-2 font-semibold">
                <span>Total</span>
                <span className="font-mono">${autoCopy ? (estimate.with_copy_cost_usd?.toFixed(3) ?? "0.001") : "0.000"}</span>
              </div>
            </div>
            <p className="text-[11px] text-muted-foreground mb-4 italic">
              Your uploaded food photo will be preserved pixel-for-pixel. Each variation takes ~3 seconds.
            </p>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setShowConfirm(false)} className="flex-1" data-testid="designer-confirm-cancel">Cancel</Button>
              <Button onClick={submit} disabled={submitting} className="bg-gold text-navy hover:bg-gold/90 flex-1" data-testid="designer-confirm-yes">
                {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                {submitting ? "Generating…" : "Generate now"}
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
          onFailed({ user_message: "Generation took too long. Try again.", retry_action: "retry" });
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

// Full-screen lightbox with zoom (wheel + buttons) + pan (drag) + actions.
const FullPreviewModal = ({ open, assetUrl, theme, variant, onClose, onDownload, onUse, onCopy, useSaved, isSaving }) => {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [drag, setDrag] = useState(null);

  useEffect(() => {
    if (!open) return;
    setZoom(1); setPan({ x: 0, y: 0 });
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "+") setZoom((z) => Math.min(4, z + 0.25));
      else if (e.key === "-") setZoom((z) => Math.max(0.5, z - 0.25));
      else if (e.key === "0") { setZoom(1); setPan({ x: 0, y: 0 }); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const onWheel = (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.15 : 0.15;
    setZoom((z) => Math.min(4, Math.max(0.5, z + delta)));
  };
  const onMouseDown = (e) => {
    if (zoom <= 1) return;
    setDrag({ sx: e.clientX, sy: e.clientY, ox: pan.x, oy: pan.y });
  };
  const onMouseMove = (e) => {
    if (!drag) return;
    setPan({ x: drag.ox + (e.clientX - drag.sx), y: drag.oy + (e.clientY - drag.sy) });
  };
  const stopDrag = () => setDrag(null);

  return (
    <div
      className="fixed inset-0 z-[60] bg-black/90 flex flex-col"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      data-testid="designer-full-preview-modal"
    >
      <div className="flex items-center justify-between p-3 text-white bg-black/40">
        <div>
          <p className="text-sm font-semibold" data-testid="designer-preview-title">{theme} · Variation {variant}</p>
          <p className="text-[11px] text-white/60">Scroll to zoom · Drag to pan · Press 0 to reset</p>
        </div>
        <div className="flex gap-2 items-center">
          <button onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))} className="px-2 py-1 text-xs bg-white/10 hover:bg-white/20 rounded text-white" data-testid="designer-preview-zoom-out">−</button>
          <span className="text-xs text-white/70 w-12 text-center" data-testid="designer-preview-zoom-level">{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom((z) => Math.min(4, z + 0.25))} className="px-2 py-1 text-xs bg-white/10 hover:bg-white/20 rounded text-white" data-testid="designer-preview-zoom-in">+</button>
          <button
            onClick={onClose}
            className="ml-3 inline-flex items-center gap-1 px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded text-xs text-white"
            data-testid="designer-preview-close"
          >
            <X className="w-3 h-3" /> Close
          </button>
        </div>
      </div>
      <div
        className="flex-1 overflow-hidden flex items-center justify-center cursor-grab active:cursor-grabbing select-none"
        onWheel={onWheel}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={stopDrag}
        onMouseLeave={stopDrag}
        data-testid="designer-preview-stage"
      >
        <img
          src={assetUrl}
          alt={`Variation ${variant}`}
          draggable={false}
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transition: drag ? "none" : "transform 0.15s ease-out",
            maxHeight: "100%", maxWidth: "100%",
          }}
        />
      </div>
      <div className="flex flex-wrap gap-2 p-3 bg-black/40 justify-center">
        <a
          href={assetUrl}
          download
          className="inline-flex items-center gap-1 bg-gold text-navy text-xs font-semibold py-2 px-3 rounded hover:bg-gold/90"
          data-testid="designer-preview-download"
        >
          <Download className="w-3.5 h-3.5" /> Download
        </a>
        <button
          onClick={onUse}
          disabled={isSaving || useSaved}
          className="inline-flex items-center gap-1 bg-white/10 hover:bg-white/20 disabled:opacity-50 text-white text-xs font-semibold py-2 px-3 rounded"
          data-testid="designer-preview-use"
        >
          {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : useSaved ? <Check className="w-3.5 h-3.5" /> : <BookmarkPlus className="w-3.5 h-3.5" />}
          {useSaved ? "Saved as winner" : isSaving ? "Saving…" : "Select as Winner"}
        </button>
        <button
          onClick={onCopy}
          className="inline-flex items-center gap-1 bg-white/10 hover:bg-white/20 text-white text-xs font-semibold py-2 px-3 rounded"
          data-testid="designer-preview-copy"
        >
          <Sparkles className="w-3.5 h-3.5" /> Generate Copy
        </button>
      </div>
    </div>
  );
};

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
  // Sprint 14B.3: when reopening a saved job, show existing copy by default
  // — it was already saved with the job, costs zero credits, and is the
  // primary reason the owner is reopening.
  const [showCopy, setShowCopy] = useState(Boolean(job.copy_pack));
  const [previewIdx, setPreviewIdx] = useState(null);
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
      <Section title="Your 3 designs are ready" icon={Wand2} testId="designer-review">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {successes.map((v) => {
            const actualIdx = (job.variations || []).indexOf(v);
            const assetUrl = `${API}/media/file/${v.asset_id}`;
            return (
              <div key={v.asset_id} className="rounded-md overflow-hidden border-2 border-navy/10 bg-card" data-testid={`designer-result-${v.variant || v.theme}`}>
                <button
                  type="button"
                  onClick={() => setPreviewIdx(actualIdx)}
                  className="block w-full focus:outline-none focus:ring-2 focus:ring-gold"
                  data-testid={`designer-thumb-${v.variant || v.theme}`}
                  title="Click for full-screen preview"
                >
                  <img src={assetUrl} alt={`${v.theme_label} variation ${v.variant || ""}`} className="w-full aspect-square object-cover" />
                </button>
                <div className="p-2.5">
                  <p className="text-sm font-semibold text-navy">{v.theme_label} {v.variant ? `· ${v.variant}` : ""}</p>
                  <p className="text-[10px] text-muted-foreground mb-2">{v.layout || "design"} layout · free</p>
                  <div className="grid grid-cols-2 gap-1.5">
                    <button
                      type="button"
                      onClick={() => setPreviewIdx(actualIdx)}
                      className="inline-flex items-center justify-center gap-1 border border-navy/20 text-navy text-xs font-semibold py-1.5 px-2 rounded hover:bg-navy/5"
                      data-testid={`designer-full-preview-${v.variant || v.theme}`}
                    >
                      <ImageIcon className="w-3 h-3" /> Full Preview
                    </button>
                    <a
                      href={assetUrl}
                      download
                      className="inline-flex items-center justify-center gap-1 bg-gold text-navy text-xs font-semibold py-1.5 px-2 rounded hover:bg-gold/90"
                      data-testid={`designer-download-${v.variant || v.theme}`}
                    >
                      <Download className="w-3 h-3" /> Download
                    </a>
                    <button
                      type="button"
                      onClick={() => saveAsTemplate(actualIdx)}
                      disabled={savingIdx === actualIdx || savedIdxs[actualIdx]}
                      className="inline-flex items-center justify-center gap-1 border border-navy/20 text-navy text-xs font-semibold py-1.5 px-2 rounded hover:bg-navy/5 disabled:opacity-50"
                      data-testid={`designer-use-${v.variant || v.theme}`}
                      title="Save as winner / reusable template"
                    >
                      {savedIdxs[actualIdx]
                        ? <><Check className="w-3 h-3" /> Used</>
                        : savingIdx === actualIdx
                        ? <Loader2 className="w-3 h-3 animate-spin" />
                        : <><BookmarkPlus className="w-3 h-3" /> Use Design</>}
                    </button>
                    <button
                      type="button"
                      onClick={() => { if (!copyPack) generateCopy(); setShowCopy(true); setTimeout(() => { document.querySelector('[data-testid="designer-copy-section"]')?.scrollIntoView({ behavior: 'smooth' }); }, 100); }}
                      disabled={generatingCopy}
                      className="inline-flex items-center justify-center gap-1 border border-navy/20 text-navy text-xs font-semibold py-1.5 px-2 rounded hover:bg-navy/5 disabled:opacity-50"
                      data-testid={`designer-card-copy-${v.variant || v.theme}`}
                    >
                      {generatingCopy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />} Copy
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

      {previewIdx !== null && (job.variations || [])[previewIdx] && (
        <FullPreviewModal
          open={previewIdx !== null}
          assetUrl={`${API}/media/file/${(job.variations || [])[previewIdx].asset_id}`}
          theme={(job.variations || [])[previewIdx].theme_label}
          variant={(job.variations || [])[previewIdx].variant || ""}
          onClose={() => setPreviewIdx(null)}
          onDownload={() => {}}
          onUse={() => saveAsTemplate(previewIdx)}
          useSaved={Boolean(savedIdxs[previewIdx])}
          isSaving={savingIdx === previewIdx}
          onCopy={() => { if (!copyPack) generateCopy(); setShowCopy(true); setPreviewIdx(null); setTimeout(() => { document.querySelector('[data-testid="designer-copy-section"]')?.scrollIntoView({ behavior: 'smooth' }); }, 200); }}
        />
      )}
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

const RecentDesignsRail = ({
  getAuthHeader, onOpen, onDuplicate, refreshKey,
  // Sprint 15B.2: parent may prefetch jobs during boot
  prefetchedJobs, prefetchedJobsLoading, prefetchedJobsError, onRetryJobs,
}) => {
  const usingPrefetch = prefetchedJobs !== undefined;
  const [jobsLocal, setJobsLocal] = useState([]);
  const [loadingLocal, setLoadingLocal] = useState(!usingPrefetch);
  const jobs = usingPrefetch ? (prefetchedJobs || []) : jobsLocal;
  const loading = usingPrefetch ? !!prefetchedJobsLoading : loadingLocal;
  const error = usingPrefetch ? prefetchedJobsError : null;
  const [pinningId, setPinningId] = useState(null);

  // `reload` is invoked imperatively (e.g. after pinning) and supports both
  // modes. In prefetch mode we delegate to the parent's retry handle so the
  // shared boot orchestrator can re-fetch /jobs/recent exactly once.
  const reload = useCallback(() => {
    if (usingPrefetch) {
      if (onRetryJobs) onRetryJobs();
      return;
    }
    setLoadingLocal(true);
    axios.get(`${API}/ai-designer/jobs/recent?limit=5`, { headers: getAuthHeader() })
      .then((r) => setJobsLocal(r.data.jobs || []))
      .catch(() => setJobsLocal([]))
      .finally(() => setLoadingLocal(false));
  }, [getAuthHeader, usingPrefetch, onRetryJobs]);

  // Sprint 15B.4: Legacy (non-prefetch) mode — auto-fetch on mount and
  // whenever `refreshKey` changes. When prefetch is active, this effect must
  // do NOTHING: the parent boot orchestrator already streams jobs in via
  // `prefetchedJobs`, and re-triggering on every parent re-render (which
  // happens 4× during the staggered boot as `onRetryJobs` identity flips)
  // cascades into 5–6 redundant /jobs/recent calls.
  useEffect(() => {
    if (usingPrefetch) return;
    reload();
  }, [reload, refreshKey, usingPrefetch]);

  // Sprint 15B.4: Prefetch mode — only ask parent to re-fetch when
  // `refreshKey` actually increments (e.g. after a new generation completes
  // or a pin toggle). Skip the initial mount and ignore identity changes of
  // `onRetryJobs` so the boot sequence isn't amplified.
  const lastRefreshKeyRef = useRef(refreshKey);
  useEffect(() => {
    if (!usingPrefetch) return;
    if (lastRefreshKeyRef.current === refreshKey) return;
    lastRefreshKeyRef.current = refreshKey;
    if (onRetryJobs) onRetryJobs();
  }, [refreshKey, usingPrefetch]);

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

  if (error) {
    return (
      <Section title="Recent AI Designs" icon={Folder} testId="designer-recent-rail">
        <div className="text-xs text-muted-foreground flex items-center justify-between gap-2" data-testid="designer-recent-error">
          <span>Couldn&apos;t load recent designs. Production may be warming up.</span>
          {onRetryJobs ? (
            <button type="button" onClick={onRetryJobs} className="text-xs font-semibold text-gold hover:underline" data-testid="designer-recent-retry">
              Try again
            </button>
          ) : null}
        </div>
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

const HANDOFF_KEY = "lakeview.ai_designer.preload_asset_id";

const AiDesigner = ({ getAuthHeader }) => {
  const [step, setStep] = useState("pick"); // pick | form | progress | review
  const [asset, setAsset] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [expectedCount, setExpectedCount] = useState(1);
  const [completedJob, setCompletedJob] = useState(null);
  const [reopenedFromRail, setReopenedFromRail] = useState(false);
  const [error, setError] = useState(null);
  const [initialValues, setInitialValues] = useState(null);
  const [recentRefreshKey, setRecentRefreshKey] = useState(0);
  const [openingId, setOpeningId] = useState(null);

  // Sprint 15B.8: when AiImageGenerator emits "Use In Ad", it drops the
  // generated asset payload into sessionStorage and switches the parent tab
  // to designer. Read it ONCE on mount, hydrate `asset`, and auto-advance
  // to the form step. Skip silently if nothing is queued.
  useEffect(() => {
    let raw = null;
    try {
      raw = sessionStorage.getItem(HANDOFF_KEY);
      if (raw) sessionStorage.removeItem(HANDOFF_KEY);
    } catch {
      return undefined;
    }
    if (!raw) return undefined;
    try {
      const payload = JSON.parse(raw);
      if (payload?.id) {
        setAsset(payload);
        setStep("form");
      }
    } catch {
      /* malformed handoff — ignore */
    }
    return undefined;
    // Run once on mount only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sprint 15B.2: de-burst boot. Parent owns all 4 datasets and streams them
  // to children with a 200ms stagger to avoid Cloudflare 520s on cold starts.
  const [boot, setBoot] = useState({
    themes:       { data: null, loading: true, error: null, retry: null },
    jobsRecent:   { data: null, loading: true, error: null, retry: null },
    templates:    { data: null, loading: true, error: null, retry: null },
    mediaAssets:  { data: null, loading: true, error: null, retry: null },
  });

  // Stable callbacks to ingest streamed boot results.
  const ingestBoot = useCallback((key) => (result) => {
    setBoot((prev) => ({
      ...prev,
      [key]: {
        data: result.data,
        loading: false,
        error: result.error,
        retry: result.retry,
      },
    }));
  }, []);

  useEffect(() => {
    const handle = bootAiDesigner({
      getAuthHeader,
      onThemes:       ingestBoot("themes"),
      onRecentJobs:   ingestBoot("jobsRecent"),
      onTemplates:    ingestBoot("templates"),
      onMediaAssets:  ingestBoot("mediaAssets"),
    });
    return () => handle.cancel();
    // Boot once per mount. `getAuthHeader` identity may change but the token
    // is read inside bootAiDesigner at call time, so re-running on identity
    // change would double-fire the sequence.
  }, []);

  // Convenience: derive `templates` array from boot state (used by Designer).
  const templates = (boot.templates.data && boot.templates.data.templates) || [];
  const themes = (boot.themes.data && boot.themes.data.themes) || undefined;
  // Sprint 16F.1 — `packs[]` is the grouped index emitted by the new theme-pack
  // backend. May be undefined on older preview pods, in which case Designer
  // falls back to a flat grid automatically.
  const packs = (boot.themes.data && boot.themes.data.packs) || undefined;
  const recentJobs = (boot.jobsRecent.data && boot.jobsRecent.data.jobs) || undefined;
  const mediaAssets = (boot.mediaAssets.data && boot.mediaAssets.data.assets) || undefined;

  // Sprint 14B.1A: Abandonment analytics — measure before optimizing.
  useEffect(() => {
    // Detect any in-flight generation from a previous session and emit a resumed event.
    checkAndResumeGeneration(getAuthHeader);
    // Listen for page unload / tab switch.
    const teardown = setupAbandonmentDetection(getAuthHeader);
    return () => {
      // If the user navigates away from the AI Designer mid-generation, log as abandoned.
      if (hasActiveGeneration()) {
        markGenerationAbandoned("component_unmount", getAuthHeader);
      }
      teardown();
    };
  }, [getAuthHeader]);

  const startOver = () => {
    // If the owner restarts mid-generation, log it as abandonment too.
    if (hasActiveGeneration() && step !== "review") {
      markGenerationAbandoned("start_over", getAuthHeader);
    }
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
            prefetchedJobs={recentJobs}
            prefetchedJobsLoading={boot.jobsRecent.loading}
            prefetchedJobsError={boot.jobsRecent.error}
            onRetryJobs={boot.jobsRecent.retry || undefined}
          />
          {openingId ? (
            <div className="text-xs text-muted-foreground flex items-center gap-2" data-testid="designer-opening-spinner">
              <Loader2 className="w-3 h-3 animate-spin" /> Opening saved design…
            </div>
          ) : null}
          <PickPhoto
            getAuthHeader={getAuthHeader}
            onSelected={(a) => { setAsset(a); setStep("form"); }}
            prefetchedLibrary={mediaAssets}
            prefetchedLibraryLoading={boot.mediaAssets.loading}
            prefetchedLibraryError={boot.mediaAssets.error}
            onRetryPrefetch={boot.mediaAssets.retry || undefined}
          />
        </>
      )}
      {step === "form" && asset && (
        <Designer
          getAuthHeader={getAuthHeader}
          asset={asset}
          templates={templates}
          initialValues={initialValues}
          onBack={() => setStep("pick")}
          prefetchedThemes={themes}
          prefetchedPacks={packs}
          prefetchedThemesLoading={boot.themes.loading}
          prefetchedThemesError={boot.themes.error}
          onRetryThemes={boot.themes.retry || undefined}
          onJobStarted={(jid, themesArg, formContext) => {
            setJobId(jid); setExpectedCount(themesArg.length); setStep("progress");
            markGenerationStarted({ job_id: jid }, formContext || {}, getAuthHeader);
          }}
        />
      )}
      {step === "progress" && jobId && (
        <Progress
          getAuthHeader={getAuthHeader}
          jobId={jobId}
          expectedCount={expectedCount}
          onCompleted={(j) => {
            markGenerationCompleted(j, getAuthHeader);
            setCompletedJob(j); setStep("review");
          }}
          onFailed={(err) => {
            markGenerationAbandoned("generation_failed", getAuthHeader);
            setError(err); setStep("form");
          }}
          onCancel={() => {
            markGenerationAbandoned("user_cancel", getAuthHeader);
            setStep("form");
          }}
        />
      )}
      {step === "review" && completedJob && (
        <Review
          getAuthHeader={getAuthHeader}
          job={completedJob}
          fromRecent={reopenedFromRail}
          onStartOver={startOver}
          onReloadTemplates={boot.templates.retry || (() => {})}
        />
      )}
    </div>
  );
};

export default AiDesigner;
