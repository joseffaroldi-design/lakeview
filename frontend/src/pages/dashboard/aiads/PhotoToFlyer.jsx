/**
 * Photo → Flyer (Sprint 16D)
 *
 * Primary front-end entry point for the marketing workflow. Upload a
 * food photo → AI vision analysis → auto-filled flyer + caption in one
 * click. Video is opt-in from the review screen ("Turn this into a 15s
 * video").
 *
 * Sprint 16F.2 additions:
 *   * Reads sessionStorage key `lakeview.photo_flyer.prefill` (set by
 *     MenuEditor sparkle ✨) so menu items deep-link in with name /
 *     features / price already populated.
 *   * Theme picker upgraded from a flat <select> to the same grouped
 *     pack picker the Template Designer ships, with a flat-select fall
 *     back when /api/ai-designer/themes doesn't expose packs[].
 *
 * Pipelines reused (NOT duplicated):
 *   POST /api/photo-flyer/analyze    (new orchestrator: upload+enhance+vision+menu)
 *   POST /api/ai-designer/generate   (flyer + auto_copy) — existing
 *   POST /api/marketing-pack/generate (15-s video, opt-in) — existing
 */
import React, { useEffect, useRef, useState, useCallback } from "react";
import axios from "axios";
import {
  Sparkles, Upload, Loader2, Download, RefreshCw, CheckCircle,
  ArrowLeft, Wand2, Image as ImageIcon, Video, ChevronRight, Copy,
  AlertTriangle, BookOpen, Save, X,
} from "lucide-react";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { API, Section } from "./shared";
import StructuredErrorCard, { parseAxiosError } from "./StructuredErrorCard";
import MenuItemPicker from "./MenuItemPicker";
import CreativeDirectorRecs from "./CreativeDirectorRecs";
import RecommendedStyleCard from "./RecommendedStyleCard";
import VisionReconciliationBanner from "./VisionReconciliationBanner";

const POLL_MS = 3000;
const POLL_TIMEOUT_MS = 4 * 60 * 1000;

// Sprint 16F.2 — must match the key written by ContentEditor.MenuEditor.
const PREFILL_KEY = "lakeview.photo_flyer.prefill";
const REMIX_KEY = "lakeview.photo_flyer.remix";

// Fallback theme list for when /api/ai-designer/themes is unreachable —
// kept short on purpose so the picker still renders something.
const FALLBACK_THEMES = [
  { value: "comic_pop",         label: "Comic Pop" },
  { value: "vintage_diner",     label: "Vintage Diner" },
  { value: "bold_purple_pop",   label: "Bold Purple Pop" },
  { value: "casual_teal",       label: "Casual Teal" },
  { value: "distressed_orange", label: "Distressed Orange" },
];

const readPrefill = () => {
  try {
    const raw = sessionStorage.getItem(PREFILL_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && parsed.name ? parsed : null;
  } catch {
    return null;
  }
};

const clearPrefill = () => {
  try { sessionStorage.removeItem(PREFILL_KEY); } catch { /* ignore */ }
};

// Sprint 17B — Remix prefill. Library writes this when the owner clicks
// the 🔁 Remix button on a flyer; we read it here on mount to pre-load
// the source photo + menu item + last-used theme.
const readRemix = () => {
  try {
    const raw = sessionStorage.getItem(REMIX_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && parsed.source_asset_id ? parsed : null;
  } catch {
    return null;
  }
};
const clearRemix = () => {
  try { sessionStorage.removeItem(REMIX_KEY); } catch { /* ignore */ }
};



// ============================== Step 1 — Upload ==========================

const UploadStep = ({
  onAnalyzed,
  getAuthHeader,
  prefill,
  onDiscardPrefill,
  menuItem,
  onPickMenuItem,
  onClearMenuItem,
  savedMemory,
  onUseSavedStyle,
  onStartFresh,
  generationOptions,
  onOptionsChange,
  themesData,
}) => {
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const fileRef = useRef(null);

  const handlePick = async (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    await processFile(f);
  };

  const processFile = async (file) => {
    setBusy(true); setError(null); setProgress("Uploading photo…");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("folder", "Custom");
      setProgress("Enhancing and analyzing your photo (≈8s)…");
      const r = await axios.post(`${API}/photo-flyer/analyze`, fd, {
        headers: { ...getAuthHeader() },
        timeout: 90000,
      });
      onAnalyzed(r.data);
    } catch (e2) {
      setError(parseAxiosError(e2));
    } finally {
      setBusy(false); setProgress("");
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (busy) return;
    const files = e.dataTransfer?.files;
    if (files && files[0]) {
      await processFile(files[0]);
    }
  };

  return (
    <div className="space-y-4" data-testid="photo-flyer-step-upload">
      {prefill ? (
        <div
          className="flex items-start justify-between gap-3 rounded-md border border-gold/40 bg-gold/10 p-3"
          data-testid="photo-flyer-prefill-banner"
        >
          <div className="flex items-start gap-2">
            <Sparkles className="w-4 h-4 text-gold mt-0.5 flex-shrink-0" />
            <div className="text-xs leading-snug">
              <p className="font-semibold text-navy">
                Promoting from menu: <span className="text-gold">{prefill.name}</span>
              </p>
              <p className="text-navy/70">
                Item name, features and price will be pre-filled after you upload a photo.
                {prefill.price ? <> Detected price: <strong>{prefill.price}</strong>.</> : null}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onDiscardPrefill}
            className="text-[11px] font-semibold text-navy/60 hover:text-navy underline shrink-0"
            data-testid="photo-flyer-prefill-clear"
          >
            Clear
          </button>
        </div>
      ) : null}

      <Section title="Start with a food photo" icon={Wand2} testId="photo-upload">
        {/* Sprint 17A — Menu item dropdown. Reuses /api/menu (no new endpoint). */}
        <div className="mb-4">
          <MenuItemPicker
            getAuthHeader={getAuthHeader}
            value={menuItem?.item_key || ""}
            onSelect={onPickMenuItem}
            onClear={onClearMenuItem}
          />
        </div>

        {/* Sprint 17A / 19 — Saved style auto-applied. The owner can still
            opt out via "Start Fresh" (or expand "View options" to pick
            manually on the next step). Renders only when memory exists. */}
        {menuItem && savedMemory ? (
          <div
            className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-md border border-gold/50 bg-gold/10 px-3 py-2"
            data-testid="photo-flyer-saved-style-banner"
          >
            <div className="flex items-start gap-2 min-w-0">
              <BookOpen className="w-4 h-4 text-gold mt-0.5 flex-shrink-0" />
              <div className="text-xs leading-snug min-w-0">
                <p className="font-semibold text-navy truncate">
                  Using your saved style for <span className="text-gold">{menuItem.name}</span>
                </p>
                <p className="text-navy/70 truncate">
                  Saved theme: <strong>{savedMemory.theme}</strong>
                  {savedMemory.use_count ? <> · used {savedMemory.use_count}×</> : null}
                  {" · "}
                  <button
                    type="button"
                    onClick={onStartFresh}
                    className="underline hover:text-navy"
                    data-testid="photo-flyer-start-fresh"
                  >
                    Start Fresh
                  </button>
                </p>
              </div>
            </div>
          </div>
        ) : null}

        <p className="text-sm text-navy/70 mb-3">
          Upload a photo of any dish. We&apos;ll detect the food, enhance the
          lighting, auto-fill the design fields, and you&apos;ll have a
          shareable flyer + captions in under 60 seconds.
          {menuItem ? <> Name, price and features have been pre-filled from <strong>{menuItem.name}</strong>.</> : null}
        </p>

        {/* Drag-and-drop upload zone */}
        <div
          className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
            dragActive
              ? "border-gold bg-gold/10"
              : "border-navy/20 hover:border-gold/50 bg-white"
          } ${busy ? "opacity-50 pointer-events-none" : ""}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          data-testid="photo-flyer-dropzone"
        >
          <Upload className={`w-12 h-12 mx-auto mb-3 ${dragActive ? "text-gold" : "text-navy/40"}`} />
          <p className="text-sm font-semibold text-navy mb-1">
            {dragActive ? "Drop your photo here" : "Drag & drop your food photo"}
          </p>
          <p className="text-xs text-navy/60 mb-3">or</p>
          <Button
            onClick={() => fileRef.current && fileRef.current.click()}
            disabled={busy}
            className="bg-gold text-navy hover:bg-gold/90"
            data-testid="photo-flyer-upload-btn"
          >
            {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                  : <ImageIcon className="w-4 h-4 mr-1.5" />}
            {busy ? "Working…" : "Browse files"}
          </Button>
          <input
            ref={fileRef} type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handlePick}
            className="hidden"
            data-testid="photo-flyer-upload-input"
          />
          <p className="text-[10px] text-navy/50 mt-2">
            Supports JPG, PNG, WebP
          </p>
        </div>
        {busy && progress ? (
          <p className="text-xs text-muted-foreground mt-2"
             data-testid="photo-flyer-progress-text">{progress}</p>
        ) : null}
        {error ? (
          <div className="mt-3">
            <StructuredErrorCard error={error}
              testId="photo-flyer-upload-error"
              onRetry={() => setError(null)} />
          </div>
        ) : null}

        {/* Generation Options */}
        <details className="mt-6 border border-navy/10 rounded-lg overflow-hidden"
                 data-testid="photo-flyer-generation-options">
          <summary className="cursor-pointer select-none px-4 py-3 bg-navy/5 hover:bg-navy/10 transition-colors font-semibold text-sm text-navy flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-gold" />
              Generation Options
            </span>
            <span className="text-xs text-navy/60 font-normal">
              Customize your design upfront
            </span>
          </summary>
          <div className="p-4 space-y-4 bg-white">
            
            {/* Variant Count */}
            <div>
              <label className="block text-xs font-semibold text-navy mb-2">
                Number of designs to generate
              </label>
              <div className="flex gap-2">
                {[1, 3, 5].map((count) => (
                  <button
                    key={count}
                    type="button"
                    onClick={() => onOptionsChange({ ...generationOptions, variantCount: count })}
                    className={`flex-1 px-4 py-2 rounded-md border text-sm font-semibold transition-colors ${
                      generationOptions.variantCount === count
                        ? "border-gold bg-gold/15 text-navy"
                        : "border-navy/20 hover:border-gold/50 text-navy/70"
                    }`}
                    data-testid={`photo-flyer-variant-${count}`}
                  >
                    {count} {count === 1 ? "Design" : "Designs"}
                  </button>
                ))}
              </div>
            </div>

            {/* Tone Selector */}
            <div>
              <label className="block text-xs font-semibold text-navy mb-2">
                Tone
              </label>
              <select
                value={generationOptions.tone}
                onChange={(e) => onOptionsChange({ ...generationOptions, tone: e.target.value })}
                className="w-full border border-navy/20 rounded-md px-3 py-2 text-sm bg-white"
                data-testid="photo-flyer-tone"
              >
                <option value="professional">Professional</option>
                <option value="casual">Casual</option>
                <option value="luxury">Luxury</option>
                <option value="bold">Bold</option>
                <option value="playful">Playful</option>
              </select>
            </div>

            {/* Marketing Goal */}
            <div>
              <label className="block text-xs font-semibold text-navy mb-2">
                Marketing Goal
              </label>
              <select
                value={generationOptions.marketingGoal}
                onChange={(e) => onOptionsChange({ ...generationOptions, marketingGoal: e.target.value })}
                className="w-full border border-navy/20 rounded-md px-3 py-2 text-sm bg-white"
                data-testid="photo-flyer-marketing-goal"
              >
                <option value="drive_traffic">Drive Traffic</option>
                <option value="promote_item">Promote New Item</option>
                <option value="limited_offer">Limited Time Offer</option>
                <option value="seasonal">Seasonal Campaign</option>
                <option value="daily_special">Daily Special</option>
                <option value="brand_awareness">Build Brand Awareness</option>
              </select>
            </div>

            {/* Caption Length */}
            <div>
              <label className="block text-xs font-semibold text-navy mb-2">
                Caption Length: <span className="text-gold">{generationOptions.captionLength}</span>
              </label>
              <div className="flex gap-2 items-center">
                <span className="text-[10px] text-navy/60 font-medium">Short</span>
                <input
                  type="range"
                  min="1"
                  max="3"
                  value={generationOptions.captionLength === "short" ? 1 : generationOptions.captionLength === "medium" ? 2 : 3}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    const length = val === 1 ? "short" : val === 2 ? "medium" : "long";
                    onOptionsChange({ ...generationOptions, captionLength: length });
                  }}
                  className="flex-1 h-2 bg-navy/10 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-gold [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-gold [&::-moz-range-thumb]:border-0"
                  data-testid="photo-flyer-caption-length"
                />
                <span className="text-[10px] text-navy/60 font-medium">Long</span>
              </div>
              <p className="text-[10px] text-navy/50 mt-1">
                {generationOptions.captionLength === "short" ? "1-2 sentences" :
                 generationOptions.captionLength === "medium" ? "3-4 sentences" : "5+ sentences"}
              </p>
            </div>

            {/* Platform / Export Size */}
            <div>
              <label className="block text-xs font-semibold text-navy mb-2">
                Platform / Export Size
              </label>
              <select
                value={generationOptions.platform}
                onChange={(e) => onOptionsChange({ ...generationOptions, platform: e.target.value })}
                className="w-full border border-navy/20 rounded-md px-3 py-2 text-sm bg-white"
                data-testid="photo-flyer-platform"
              >
                <option value="instagram_post">Instagram Post (1024×1024)</option>
                <option value="instagram_story">Instagram Story (1080×1920)</option>
                <option value="facebook_post">Facebook Post / Link (1200×630)</option>
                <option value="facebook_feed">Facebook Feed Square (1200×1200)</option>
                <option value="tiktok">TikTok (1080×1920)</option>
                <option value="twitter">Twitter/X (1200×675)</option>
                <option value="email">Email Campaign (600×600)</option>
              </select>
            </div>

            {/* Optional CTA */}
            <div>
              <label className="block text-xs font-semibold text-navy mb-2">
                Call-to-Action (Optional)
              </label>
              <select
                value={generationOptions.cta}
                onChange={(e) => onOptionsChange({ ...generationOptions, cta: e.target.value })}
                className="w-full border border-navy/20 rounded-md px-3 py-2 text-sm bg-white"
                data-testid="photo-flyer-cta"
              >
                <option value="">None</option>
                <option value="Order Today">Order Today</option>
                <option value="Limited Time">Limited Time</option>
                <option value="Chef Special">Chef Special</option>
                <option value="Available Now">Available Now</option>
                <option value="Today's Feature">Today&apos;s Feature</option>
                <option value="Order Now">Order Now</option>
              </select>
            </div>

            {/* Include Price */}
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-navy">
                Include Price
              </label>
              <button
                type="button"
                role="switch"
                aria-checked={generationOptions.includePrice}
                onClick={() => onOptionsChange({ ...generationOptions, includePrice: !generationOptions.includePrice })}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  generationOptions.includePrice ? "bg-gold" : "bg-navy/20"
                }`}
                data-testid="photo-flyer-include-price"
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    generationOptions.includePrice ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>

            {/* Include Description */}
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-navy">
                Include Description
              </label>
              <button
                type="button"
                role="switch"
                aria-checked={generationOptions.includeDescription}
                onClick={() => onOptionsChange({ ...generationOptions, includeDescription: !generationOptions.includeDescription })}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  generationOptions.includeDescription ? "bg-gold" : "bg-navy/20"
                }`}
                data-testid="photo-flyer-include-description"
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    generationOptions.includeDescription ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>

            {/* Divider */}
            <div className="border-t border-navy/10 my-2"></div>
            
            {/* Logo Section */}
            <div className="space-y-3">
              <p className="text-xs font-bold text-navy uppercase tracking-wide">Logo Options</p>
              
              {/* Logo Upload */}
              <div>
                <label className="block text-xs font-semibold text-navy mb-2">
                  Logo URL (optional)
                </label>
                <input
                  type="url"
                  value={generationOptions.logoUrl}
                  onChange={(e) => onOptionsChange({ ...generationOptions, logoUrl: e.target.value })}
                  placeholder="https://example.com/logo.png"
                  className="w-full border border-navy/20 rounded-md px-3 py-2 text-sm"
                  data-testid="photo-flyer-logo-url"
                />
                <p className="text-[10px] text-navy/50 mt-1">
                  Paste URL to your restaurant logo
                </p>
              </div>

              {/* Logo Placement */}
              <div>
                <label className="block text-xs font-semibold text-navy mb-2">
                  Logo Placement
                </label>
                <select
                  value={generationOptions.logoPlacement}
                  onChange={(e) => onOptionsChange({ ...generationOptions, logoPlacement: e.target.value })}
                  className="w-full border border-navy/20 rounded-md px-3 py-2 text-sm bg-white"
                  data-testid="photo-flyer-logo-placement"
                >
                  <option value="none">No Logo</option>
                  <option value="top_left">Top Left</option>
                  <option value="top_center">Top Center</option>
                  <option value="top_right">Top Right</option>
                  <option value="bottom_left">Bottom Left</option>
                  <option value="bottom_center">Bottom Center</option>
                  <option value="bottom_right">Bottom Right</option>
                  <option value="watermark">Watermark (Centered, Transparent)</option>
                </select>
              </div>

              {/* Logo Size */}
              <div>
                <label className="block text-xs font-semibold text-navy mb-2">
                  Logo Size
                </label>
                <div className="flex gap-2">
                  {['small', 'medium', 'large'].map((logoSize) => (
                    <button
                      key={logoSize}
                      type="button"
                      onClick={() => onOptionsChange({ ...generationOptions, logoSize })}
                      className={`flex-1 px-4 py-2 rounded-md border text-xs font-semibold transition-colors capitalize ${
                        generationOptions.logoSize === logoSize
                          ? "border-gold bg-gold/15 text-navy"
                          : "border-navy/20 hover:border-gold/50 text-navy/70"
                      }`}
                      data-testid={`photo-flyer-logo-size-${logoSize}`}
                    >
                      {logoSize}
                    </button>
                  ))}
                </div>
              </div>
            </div>

          </div>
        </details>
      </Section>
    </div>
  );
};


// ============================== Step 2 — Review & Edit ==================

// Sprint 16F.2 — compact grouped theme picker. When `packs[]` is present
// renders one <details> per pack; otherwise falls back to a flat <select>.
const InlineThemePicker = ({ themes, packs, value, onChange }) => {
  if (!packs || packs.length === 0) {
    return (
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="w-full border border-navy/20 rounded-md px-2 py-1.5 text-sm bg-white"
        data-testid="photo-flyer-theme">
        {themes.map((t) => (
          <option key={t.id} value={t.id}>{t.label}</option>
        ))}
      </select>
    );
  }

  // Bucket themes by pack, preserve packs[] ordering.
  const byPack = new Map();
  for (const t of themes) {
    const pid = t.pack || "_other";
    if (!byPack.has(pid)) byPack.set(pid, []);
    byPack.get(pid).push(t);
  }
  const selectedPack = (themes.find((t) => t.id === value) || {}).pack;

  return (
    <div className="border border-navy/20 rounded-md bg-white max-h-72 overflow-y-auto"
         data-testid="photo-flyer-theme">
      {packs.map((p, idx) => {
        const list = byPack.get(p.id) || [];
        if (list.length === 0) return null;
        const open = selectedPack ? selectedPack === p.id : idx === 0;
        return (
          <details
            key={p.id}
            open={open}
            className="border-b border-navy/10 last:border-b-0"
            data-testid={`photo-flyer-pack-${p.id}`}
          >
            <summary className="cursor-pointer select-none flex items-center justify-between px-2.5 py-1.5 list-none [&::-webkit-details-marker]:hidden hover:bg-navy/5">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-navy">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-gold mr-1.5 align-middle" />
                {p.label}
              </span>
              <span className="text-[10px] font-medium text-muted-foreground bg-navy/5 rounded-full px-2 py-0.5"
                    data-testid={`photo-flyer-pack-count-${p.id}`}>
                {list.length}
              </span>
            </summary>
            <div className="px-1 pb-1.5 grid grid-cols-2 gap-1">
              {list.map((t) => {
                const selected = value === t.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => onChange(t.id)}
                    aria-pressed={selected}
                    className={`text-left text-[11px] rounded px-2 py-1.5 border transition-colors ${
                      selected
                        ? "border-gold bg-gold/15 text-navy font-semibold"
                        : "border-navy/10 hover:border-gold/50 text-navy/80"
                    }`}
                    data-testid={`photo-flyer-theme-${t.id}`}
                  >
                    <span className="flex items-center gap-1.5">
                      {t.preview_color ? (
                        <span className="inline-block w-2.5 h-2.5 rounded-full border border-navy/20 shrink-0"
                              style={{ backgroundColor: t.preview_color }} />
                      ) : null}
                      <span className="truncate">{t.label}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </details>
        );
      })}
    </div>
  );
};

const AnalysisReviewStep = ({
  analysis, prefill, themes, packs,
  menuItem, recs, recsContext, useSaved,
  savedMemory, onPersistVisionChoice,
  onBack, onGenerate, busy,
}) => {
  const [visionChoice, setVisionChoice] = useState(
    (savedMemory && savedMemory.vision_choice) || (menuItem ? "menu" : null)
  );
  const [showOtherThemes, setShowOtherThemes] = useState(false);

  // Sprint 17B — derive effective name from the vision choice.
  // "menu" wins → menu item name; "ai" wins → AI detection; "merge" → "Menu (also AI)".
  const aiName = analysis.food_type || "";
  const menuName = (menuItem && menuItem.name) || "";
  const effectiveName = (() => {
    if (!menuItem) return aiName || prefill?.name || "";
    if (visionChoice === "ai")   return aiName || menuName;
    if (visionChoice === "merge") return aiName && aiName.toLowerCase() !== menuName.toLowerCase()
      ? `${menuName} (${aiName})` : menuName;
    return menuName;  // "menu" or default
  })();

  const seedFeatures = (
    (menuItem && menuItem.features && menuItem.features.length)
      ? menuItem.features
      : (prefill && prefill.features && prefill.features.length)
        ? prefill.features
        : (analysis.features || [])
  ).join(", ");
  const seedPrice = (() => {
    const raw = (menuItem && menuItem.price)
      || (prefill && prefill.price)
      || analysis.menu_match?.price
      || "";
    if (!raw) return "";
    return raw.toString().startsWith("$") ? raw : `$${raw}`;
  })();

  const [name, setName] = useState(effectiveName || "");
  // Keep `name` in sync when the user flips vision choice.
  useEffect(() => { setName(effectiveName || ""); }, [visionChoice]);

  const [features, setFeatures] = useState(seedFeatures);
  const [price, setPrice] = useState(seedPrice);
  const [headline, setHeadline] = useState((prefill && prefill.headline) || "");
  // Sprint 17A — when "Use Saved Style" was clicked, prefer the saved theme.
  const [theme, setTheme] = useState(
    (useSaved && useSaved.theme)
    || (recs && recs[0]?.id)
    || analysis.suggested_theme
    || "comic_pop"
  );

  const topRec = recs && recs[0];
  const isRecApplied = !!(topRec && theme === topRec.id);

  const submit = () => {
    const feats = features.split(",").map(s => s.trim()).filter(Boolean);
    onGenerate({
      enhanced_asset_id: analysis.enhanced_asset_id,
      item_name: name.trim() || "Featured Dish",
      features: feats,
      price: price.trim(),
      headline: headline.trim() || null,
      theme,
      item_key: menuItem?.item_key || null,
    });
  };

  const onVisionChoice = (choice) => {
    setVisionChoice(choice);
    if (menuItem && onPersistVisionChoice) {
      onPersistVisionChoice(menuItem.item_key, choice);
    }
  };

  return (
    <div className="space-y-4" data-testid="photo-flyer-step-review">
      {!analysis.vision_ok ? (
        <div className="flex gap-2 items-start p-3 rounded-md bg-amber-50 border border-amber-300 text-xs"
             data-testid="photo-flyer-vision-warning">
          <AlertTriangle className="w-4 h-4 text-amber-700 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-amber-800">
              AI vision unavailable — fill the fields manually and continue.
            </p>
            <p className="text-amber-700/80">
              ({analysis.vision_error || "no detail"}) — your photo was still
              enhanced and you can still generate the flyer below.
            </p>
          </div>
        </div>
      ) : null}

      {/* Sprint 17B — Menu vs Vision reconciliation. Only renders when both
          a menu item and a high-confidence vision label are present and
          they disagree. */}
      <VisionReconciliationBanner
        menuItemName={menuName}
        detectedName={aiName}
        confidence={analysis.confidence || 0}
        savedChoice={visionChoice}
        onChoose={onVisionChoice}
      />

      <Section title="We analyzed your photo" icon={Sparkles} testId="photo-flyer-analysis">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Before / after */}
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <p className="text-[10px] uppercase tracking-wider font-semibold text-navy/60 mb-1">Original</p>
                <img src={`${API}/media/thumb/${analysis.original_asset_id}`}
                  alt="original" className="w-full aspect-square object-cover rounded border-2 border-navy/10"
                  data-testid="photo-flyer-original-img" />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider font-semibold text-gold mb-1">Enhanced</p>
                <img src={`${API}/media/thumb/${analysis.enhanced_asset_id}`}
                  alt="enhanced" className="w-full aspect-square object-cover rounded border-2 border-gold"
                  data-testid="photo-flyer-enhanced-img" />
              </div>
            </div>
            {analysis.vision_ok ? (
              <div className="text-[11px] text-muted-foreground space-y-0.5 mt-1">
                <p>Detected: <span className="font-semibold text-navy">{analysis.food_type}</span>
                  {" "}({Math.round((analysis.confidence || 0) * 100)}% confidence)</p>
                {menuItem ? (
                  <p data-testid="photo-flyer-menu-pick">
                    Menu pick: <span className="text-gold font-semibold">{menuItem.name}</span>
                    {" "}— name, price, features pre-filled.
                  </p>
                ) : analysis.menu_match?.matched ? (
                  <p data-testid="photo-flyer-menu-match">
                    Menu match: <span className="text-gold font-semibold">{analysis.menu_match.name}</span>
                    {" "}— price autofilled.
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>

          {/* Editable fields */}
          <div className="space-y-2">
            <div>
              <label className="text-xs font-semibold text-navy">Item name</label>
              <Input value={name} onChange={e => setName(e.target.value)}
                className="border-navy/20" data-testid="photo-flyer-name" />
            </div>
            <div>
              <label className="text-xs font-semibold text-navy">Features (comma-separated)</label>
              <Input value={features} onChange={e => setFeatures(e.target.value)}
                placeholder="Cheese, Bacon, Pickled Onions"
                className="border-navy/20" data-testid="photo-flyer-features" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold text-navy">Price</label>
                <Input value={price} onChange={e => setPrice(e.target.value)}
                  placeholder="$12.95"
                  className="border-navy/20" data-testid="photo-flyer-price" />
              </div>
              <div>
                <label className="text-xs font-semibold text-navy">Headline (opt.)</label>
                <Input value={headline} onChange={e => setHeadline(e.target.value)}
                  placeholder="Weekend Special"
                  className="border-navy/20" data-testid="photo-flyer-headline" />
              </div>
            </div>
          </div>
        </div>
      </Section>

      {/* Sprint 17B — Single Recommended Style card. Other themes are
          collapsible behind "View other themes" so the owner sees ONE
          decision instead of 22. */}
      <Section title="Choose a style" icon={Sparkles} testId="photo-flyer-theme-section">
        <RecommendedStyleCard
          rec={topRec}
          context={recsContext}
          isSelected={isRecApplied}
          onApply={() => topRec && setTheme(topRec.id)}
          onShowOther={() => setShowOtherThemes((v) => !v)}
          showingOther={showOtherThemes}
        />
        {showOtherThemes ? (
          <div className="mt-3 space-y-3" data-testid="photo-flyer-other-themes">
            <CreativeDirectorRecs
              recs={recs}
              context={recsContext}
              value={theme}
              onPick={setTheme}
              renderAll={() => (
                <InlineThemePicker themes={themes} packs={packs}
                  value={theme} onChange={setTheme} />
              )}
            />
          </div>
        ) : null}
      </Section>

      <div className="flex gap-2">
        <Button variant="outline" onClick={onBack} className="border-navy/20"
          data-testid="photo-flyer-back">
          <ArrowLeft className="w-4 h-4 mr-1.5" /> Back
        </Button>
        <div className="flex-1" />
        <Button onClick={submit} disabled={busy}
          className="bg-gold text-navy hover:bg-gold/90"
          data-testid="photo-flyer-generate">
          {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                : <Sparkles className="w-4 h-4 mr-1.5" />}
          Generate flyer + caption
        </Button>
      </div>
    </div>
  );
};


// ============================== Step 3 — Generating =====================

const GeneratingStep = ({ getAuthHeader, designerJobId, onCompleted, onFailed }) => {
  const [step, setStep] = useState("queued");
  const [pct, setPct] = useState(5);
  const started = useRef(Date.now());

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      if (Date.now() - started.current > POLL_TIMEOUT_MS) {
        onFailed({ user_message: "Took too long — try again.", code: "timeout" });
        return;
      }
      try {
        const r = await axios.get(`${API}/ai-designer/job/${designerJobId}`,
          { headers: getAuthHeader(), timeout: 15000 });
        const job = r.data;
        setPct(job.progress || 0);
        setStep(job.current_step || job.status);
        if (job.status === "completed") { onCompleted(job); return; }
        if (job.status === "failed") {
          onFailed(job.error || { user_message: "Generation failed." });
          return;
        }
        setTimeout(tick, POLL_MS);
      } catch {
        setTimeout(tick, POLL_MS * 2);
      }
    };
    tick();
    return () => { cancelled = true; };
  }, [designerJobId, getAuthHeader, onCompleted, onFailed]);

  return (
    <div className="space-y-4" data-testid="photo-flyer-step-generating">
      <Section title="Generating your flyer" icon={Loader2} testId="photo-flyer-progress">
        <div className="space-y-3">
          <div className="h-2 bg-navy/10 rounded-full overflow-hidden">
            <div className="h-full bg-gold transition-all duration-500"
              style={{ width: `${pct}%` }}
              data-testid="photo-flyer-progress-bar" />
          </div>
          <p className="text-sm text-navy" data-testid="photo-flyer-progress-step">
            {{
              queued: "Queued…",
              pending: "Queued…",
              composing: "Composing the flyer…",
              writing_copy: "Writing captions…",
              saving: "Finishing up…",
              done: "Done!",
              processing: "Working…",
            }[step] || step}
          </p>
          <p className="text-[10px] text-muted-foreground">≈ 30–60 seconds.</p>
        </div>
      </Section>
    </div>
  );
};


// ============================== Step 4 — Review (flyer + copy + opt-in video)

const ReviewStep = ({
  job, analysis, getAuthHeader,
  menuItem, themeUsed, onSavePreferredStyle,
  onRegenerate, onStartOver,
}) => {
  const vars = job.variations || [];
  const [selectedIdx, setSelectedIdx] = useState(0);
  const flyer = vars[selectedIdx] || vars[0] || {};
  const flyerUrl = flyer.asset_id ? `${API}/media/file/${flyer.asset_id}` : null;
  const copy = job.copy_pack || {};
  const fb = copy.fb_post || "";
  const ig = copy.ig_post || "";

  // Sprint 17A — Learning loop: fire the save-style prompt the first time
  // the owner hits Download. We trigger the download programmatically
  // (via a synthetic <a download>) so the modal paint isn't racing against
  // the browser's file-save handling. Skipped if no menuItem (we'd have no
  // item_key to save against) or if the current theme already matches what's
  // saved.
  const [askedToSave, setAskedToSave] = useState(false);
  const triggerDownload = () => {
    if (!flyerUrl) return;
    const a = document.createElement("a");
    a.href = flyerUrl;
    a.download = "";  // hint the browser to download instead of navigate
    document.body.appendChild(a);
    a.click();
    a.remove();
    // Sprint 17B — bump the smart-sort signal so favorites + recent-use
    // surface this flyer at the top of the Library next time.
    if (flyer.asset_id) {
      axios.post(`${API}/media/assets/${flyer.asset_id}/used`, null,
        { headers: getAuthHeader(), timeout: 10000 }).catch(() => {});
    }
  };
  const onDownloadClick = () => {
    const eligible = !askedToSave && menuItem && themeUsed && onSavePreferredStyle;
    triggerDownload();
    if (eligible) {
      setAskedToSave(true);
      // Defer one tick so React commits the modal's state before we
      // surrender focus to the file-save dialog.
      setTimeout(() => {
        onSavePreferredStyle({
          item_key: menuItem.item_key,
          item_name: menuItem.name,
          theme: themeUsed,
          favorite_flyer_id: flyer.asset_id || null,
        });
      }, 0);
    }
  };

  // Opt-in video state
  const [videoState, setVideoState] = useState("idle"); // idle|running|done|failed
  const [videoJobId, setVideoJobId] = useState(null);
  const [videoAssetId, setVideoAssetId] = useState(null);
  const [videoErr, setVideoErr] = useState(null);
  const [videoPct, setVideoPct] = useState(0);

  const kickVideo = async () => {
    setVideoState("running"); setVideoErr(null); setVideoPct(5);
    try {
      const r = await axios.post(`${API}/marketing-pack/generate`, {
        source_asset_id: analysis.enhanced_asset_id,
        name: analysis.food_type || flyer.headline || "Featured Dish",
        price: job.price || "",
        headline: flyer.headline || null,
        cta: "Order Now",
      }, { headers: getAuthHeader(), timeout: 30000 });
      setVideoJobId(r.data.job_id);
    } catch (e) {
      setVideoState("failed"); setVideoErr(parseAxiosError(e));
    }
  };

  useEffect(() => {
    if (videoState !== "running" || !videoJobId) return;
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      try {
        const r = await axios.get(`${API}/marketing-pack/job/${videoJobId}`,
          { headers: getAuthHeader(), timeout: 15000 });
        const j = r.data;
        setVideoPct(j.progress || 0);
        if (j.status === "completed") {
          setVideoAssetId((j.result || {}).video_asset_id);
          setVideoState("done");
          return;
        }
        if (j.status === "failed") {
          setVideoState("failed");
          setVideoErr(j.error || { user_message: "Video render failed." });
          return;
        }
        setTimeout(tick, POLL_MS);
      } catch (e) {
        if (process.env.NODE_ENV !== "production") console.warn("[PhotoToFlyer] video poll error (will retry):", e);
        setTimeout(tick, POLL_MS * 2);
      }
    };
    tick();
    return () => { cancelled = true; };
  }, [videoState, videoJobId, getAuthHeader]);

  const copyToClip = (text, label) => {
    navigator.clipboard?.writeText(text || "").then(() => {
      // Toast handled at the parent level; keep minimal here
      const el = document.createElement("div");
      el.textContent = `${label} copied`;
      el.style.cssText = "position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#0a2540;color:#fff;padding:8px 16px;border-radius:6px;font-size:12px;z-index:9999";
      document.body.appendChild(el);
      setTimeout(() => el.remove(), 1400);
    });
  };

  return (
    <div className="space-y-6" data-testid="photo-flyer-step-review-done">
      {/* Flyer */}
      <Section title={`Your ${vars.length > 1 ? `${vars.length} designs are` : "design is"} ready`} icon={CheckCircle} testId="photo-flyer-review-flyer">
        {flyerUrl ? (
          <div className="space-y-4">
            {/* Variant gallery - only show if multiple variants */}
            {vars.length > 1 ? (
              <div className="mb-4">
                <p className="text-xs font-semibold text-navy mb-2">
                  Choose your favorite design:
                </p>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                  {vars.map((v, idx) => {
                    const url = v.asset_id ? `${API}/media/thumb/${v.asset_id}` : null;
                    if (!url) return null;
                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setSelectedIdx(idx)}
                        className={`relative rounded-lg overflow-hidden border-2 transition-all ${
                          selectedIdx === idx
                            ? "border-gold ring-2 ring-gold/30"
                            : "border-navy/10 hover:border-gold/50"
                        }`}
                        data-testid={`photo-flyer-variant-${idx}`}
                      >
                        <img
                          src={url}
                          alt={`Variant ${v.variant || idx + 1}`}
                          className="w-full aspect-square object-cover"
                        />
                        {selectedIdx === idx ? (
                          <div className="absolute top-1 right-1 bg-gold text-navy rounded-full p-1">
                            <CheckCircle className="w-4 h-4" />
                          </div>
                        ) : null}
                        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-navy/80 to-transparent p-2">
                          <p className="text-[10px] font-bold text-white text-center">
                            Design {v.variant || String.fromCharCode(65 + idx)}
                          </p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {/* Selected flyer preview */}
            <img src={flyerUrl} alt="generated flyer"
              className="w-full max-w-md mx-auto rounded-md border-2 border-navy/10"
              data-testid="photo-flyer-flyer-img" />
            {/* Sprint 18 — design quality label (small dev signal — not a big 8.6/10 badge). */}
            {flyer.quality_label ? (
              <div className="flex justify-center"
                   data-testid="photo-flyer-quality-label">
                <span className={`inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border ${
                  flyer.quality_label === "Excellent"     ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                  flyer.quality_label === "Very Good"     ? "bg-sky-50 text-sky-700 border-sky-200" :
                                                            "bg-amber-50 text-amber-700 border-amber-200"
                }`}>
                  <Sparkles className="w-3 h-3" />
                  Design Quality: {flyer.quality_label}
                  {typeof flyer.quality_score === "number" ? (
                    <span className="opacity-70 normal-case">
                      · {flyer.quality_score.toFixed(0)}/100
                    </span>
                  ) : null}
                </span>
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onDownloadClick}
                className="inline-flex items-center gap-1.5 text-sm font-semibold text-gold hover:underline"
                data-testid="photo-flyer-download-flyer">
                <Download className="w-4 h-4" /> Download flyer
              </button>
              <button onClick={onRegenerate}
                className="inline-flex items-center gap-1.5 text-sm text-navy hover:underline"
                data-testid="photo-flyer-regenerate">
                <RefreshCw className="w-4 h-4" /> Regenerate / different theme
              </button>
            </div>
          </div>
        ) : null}
      </Section>

      {/* Copy */}
      {(fb || ig) ? (
        <Section title="Social captions" icon={Sparkles} testId="photo-flyer-review-copy">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {fb ? (
              <div className="border border-navy/15 rounded-md p-3 space-y-2"
                   data-testid="photo-flyer-fb-copy">
                <div className="flex items-center justify-between">
                  <p className="text-[11px] uppercase tracking-wider font-semibold text-navy">Facebook</p>
                  <button onClick={() => copyToClip(fb, "Facebook caption")}
                    className="text-[11px] text-gold hover:underline flex items-center gap-1"
                    data-testid="photo-flyer-copy-fb">
                    <Copy className="w-3 h-3" /> Copy
                  </button>
                </div>
                <p className="text-sm text-navy whitespace-pre-wrap">{fb}</p>
              </div>
            ) : null}
            {ig ? (
              <div className="border border-navy/15 rounded-md p-3 space-y-2"
                   data-testid="photo-flyer-ig-copy">
                <div className="flex items-center justify-between">
                  <p className="text-[11px] uppercase tracking-wider font-semibold text-navy">Instagram</p>
                  <button onClick={() => copyToClip(ig, "Instagram caption")}
                    className="text-[11px] text-gold hover:underline flex items-center gap-1"
                    data-testid="photo-flyer-copy-ig">
                    <Copy className="w-3 h-3" /> Copy
                  </button>
                </div>
                <p className="text-sm text-navy whitespace-pre-wrap">{ig}</p>
              </div>
            ) : null}
          </div>
        </Section>
      ) : job.copy_error ? (
        <div className="text-xs text-amber-700 p-3 rounded-md bg-amber-50 border border-amber-300"
             data-testid="photo-flyer-copy-error">
          Captions unavailable: {job.copy_error.slice(0, 200)}.
          You can paste your own and still share the flyer.
        </div>
      ) : null}

      {/* Opt-in video */}
      <Section title="Optional — 15-second promo video" icon={Video} testId="photo-flyer-video-section">
        {videoState === "idle" ? (
          <div className="space-y-2">
            <p className="text-sm text-navy/70">
              Want a vertical 15-second video built from this photo for
              Reels / TikTok / Stories? Costs about a minute.
            </p>
            <Button onClick={kickVideo}
              className="bg-navy text-cream hover:bg-navy/90"
              data-testid="photo-flyer-video-kick">
              <Video className="w-4 h-4 mr-1.5" /> Turn this into a 15s video
            </Button>
          </div>
        ) : null}
        {videoState === "running" ? (
          <div className="space-y-2">
            <div className="h-2 bg-navy/10 rounded-full overflow-hidden">
              <div className="h-full bg-navy transition-all duration-500"
                style={{ width: `${videoPct}%` }}
                data-testid="photo-flyer-video-progress" />
            </div>
            <p className="text-xs text-muted-foreground">Rendering video… ≈ 60s</p>
          </div>
        ) : null}
        {videoState === "done" && videoAssetId ? (
          <div className="space-y-2" data-testid="photo-flyer-video-done">
            <video src={`${API}/media/file/${videoAssetId}`} controls
              className="w-full max-w-sm rounded-md border-2 border-navy/10"
              data-testid="photo-flyer-video-player" />
            <a href={`${API}/media/file/${videoAssetId}`} download
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-gold hover:underline"
              data-testid="photo-flyer-download-video">
              <Download className="w-4 h-4" /> Download video
            </a>
          </div>
        ) : null}
        {videoState === "failed" ? (
          <StructuredErrorCard error={videoErr}
            testId="photo-flyer-video-error"
            onRetry={() => setVideoState("idle")} />
        ) : null}
      </Section>

      {/* Bottom actions */}
      <div className="flex gap-2 sticky bottom-0 bg-cream/95 backdrop-blur-sm border-t border-navy/10 p-3 -mx-6 -mb-6 px-6">
        <Button variant="outline" onClick={onStartOver}
          className="border-navy/20" data-testid="photo-flyer-start-over">
          New photo
        </Button>
        <div className="flex-1" />
        <Button className="bg-gold text-navy hover:bg-gold/90"
          onClick={onStartOver} data-testid="photo-flyer-done">
          <CheckCircle className="w-4 h-4 mr-1.5" /> Done
        </Button>
      </div>
    </div>
  );
};


// ============================== Save-Style Modal (Sprint 17A) ==========

const SavePreferredStyleModal = ({ open, item_name, theme, onConfirm, onDismiss, busy }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy/40 backdrop-blur-sm"
         data-testid="save-style-modal">
      <div className="bg-white rounded-lg border-2 border-gold/40 shadow-xl max-w-sm w-[92%] p-5">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <Save className="w-5 h-5 text-gold" />
            <h3 className="font-serif text-navy text-base font-semibold">
              Save as preferred style?
            </h3>
          </div>
          <button onClick={onDismiss} className="text-navy/50 hover:text-navy"
                  aria-label="Dismiss" data-testid="save-style-dismiss">
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-sm text-navy/80 leading-snug mb-4">
          Save <strong>{theme}</strong> as your preferred design style for{" "}
          <strong>{item_name}</strong>? Next time you promote this item, we&apos;ll
          suggest it first. You can always pick a different theme manually.
        </p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onDismiss}
            disabled={busy}
            className="flex-1 border-navy/20"
            data-testid="save-style-skip">
            Not now
          </Button>
          <Button onClick={onConfirm}
            disabled={busy}
            className="flex-1 bg-gold text-navy hover:bg-gold/90"
            data-testid="save-style-confirm">
            {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                  : <Save className="w-4 h-4 mr-1.5" />}
            Save preferred style
          </Button>
        </div>
      </div>
    </div>
  );
};


// ============================== Top-level ==============================

const PhotoToFlyer = ({ getAuthHeader }) => {
  const [step, setStep] = useState("upload"); // upload | review | generating | done
  const [analysis, setAnalysis] = useState(null);
  const [genBusy, setGenBusy] = useState(false);
  const [designerJobId, setDesignerJobId] = useState(null);
  const [designerJob, setDesignerJob] = useState(null);
  const [topError, setTopError] = useState(null);
  // Sprint 16F.2 — menu-item prefill from MenuEditor sparkle ✨ deep-link.
  const [prefill, setPrefill] = useState(() => readPrefill());
  // Sprint 16F.2 — themes + packs[] payload used by the grouped picker.
  const [themesData, setThemesData] = useState({ themes: null, packs: null });

  // Sprint 17A — Menu item picker state + design memory + recommendations.
  const [menuItem, setMenuItem] = useState(null);              // {item_key, name, price, features, category}
  const [savedMemory, setSavedMemory] = useState(null);        // design_memory doc | null
  const [useSaved, setUseSaved] = useState(null);              // {theme} when "Use Saved Style" clicked
  const [recs, setRecs] = useState([]);                        // top-3 recommendations
  const [recsContext, setRecsContext] = useState(null);
  // Learning-loop save modal state
  const [saveModal, setSaveModal] = useState(null);            // {item_key, item_name, theme, favorite_flyer_id} | null
  const [savingStyle, setSavingStyle] = useState(false);
  // Last generated theme (so the save modal knows what to save).
  const [lastTheme, setLastTheme] = useState(null);

  // Priority 2 & 3 — Generation options state
  const [generationOptions, setGenerationOptions] = useState({
    variantCount: 3,
    tone: "professional",
    marketingGoal: "promote_item",
    captionLength: "medium",
    platform: "instagram_post",
    cta: "",
    includePrice: true,
    includeDescription: true,
    // Priority 4.1: Logo options
    logoUrl: "",
    logoPlacement: "none",
    logoSize: "medium",
  });

  useEffect(() => {
    let cancelled = false;
    axios.get(`${API}/ai-designer/themes`, { headers: getAuthHeader() })
      .then((r) => {
        if (cancelled) return;
        setThemesData({
          themes: r.data.themes || null,
          packs: r.data.packs || null,
        });
      })
      .catch(() => { /* non-fatal — UI falls back to FALLBACK_THEMES */ });
    return () => { cancelled = true; };
  }, [getAuthHeader]);

  // Sprint 17B — Remix prefill from the Library. When present, pre-load
  // the original photo + menu item + last-used theme so the owner only
  // changes one thing and regenerates. We synthesize an "analysis"-shaped
  // object from the asset id (no new vision call) so the Review step
  // renders straight away.
  useEffect(() => {
    const r = readRemix();
    if (!r) return;
    clearRemix();
    setMenuItem(r.menu_item || null);
    setUseSaved(r.theme ? { theme: r.theme } : null);
    setAnalysis({
      original_asset_id: r.source_asset_id,
      enhanced_asset_id: r.source_asset_id,
      food_type: r.food_type || (r.menu_item && r.menu_item.name) || "",
      features: r.features || [],
      confidence: 1.0,
      vision_ok: true,
      menu_match: { matched: false },
      suggested_theme: r.theme || null,
    });
    setLastTheme(r.theme || null);
    setStep("review");
  }, []);

  // Sprint 19 — auto-apply the saved style as soon as we know about it.
  // The saved style is the OWNER's explicit prior decision (not the AI
  // choosing), so applying it without an extra click is the right call.
  // The "Start Fresh" button still lets them opt out.
  useEffect(() => {
    if (menuItem && savedMemory && savedMemory.theme && !useSaved) {
      setUseSaved({ theme: savedMemory.theme });
    }
  }, [menuItem, savedMemory]);

  const discardPrefill = () => { clearPrefill(); setPrefill(null); };

  // Sprint 17A — Load design memory + recommendations whenever the menu
  // selection (or analysis) changes. Recommendations always run; memory
  // is optional (404 == "no saved style yet").
  const refreshRecs = useCallback(async ({ item, an }) => {
    const item_key = item?.item_key || null;
    // Memory: only when we have an item_key.
    let memory = null;
    if (item_key) {
      try {
        const rm = await axios.get(`${API}/design-memory/${encodeURIComponent(item_key)}`,
          { headers: getAuthHeader(), timeout: 10000 });
        memory = rm.data;
      } catch (e) {
        memory = null; // 404 is expected
      }
    }
    setSavedMemory(memory);

    // Recommendations: ask the Creative Director.
    try {
      const rr = await axios.post(`${API}/creative-director/recommend`, {
        item_key,
        food_type: (an && an.food_type) || (item && item.name) || "",
        features: (an && an.features) || (item && item.features) || [],
        dominant_colors: (an && an.dominant_colors) || [],
      }, { headers: getAuthHeader(), timeout: 15000 });
      setRecs(rr.data.recommendations || []);
      setRecsContext(rr.data.context || null);
    } catch (e) {
      setRecs([]); setRecsContext(null);
    }
  }, [getAuthHeader]);

  // Refresh recs on menu pick (pre-photo).
  useEffect(() => {
    if (step !== "upload") return;
    refreshRecs({ item: menuItem, an: analysis });
  }, [menuItem, step, analysis, refreshRecs]);

  const onPickMenuItem = (item) => { setMenuItem(item); setUseSaved(null); };
  const onClearMenuItem = () => { setMenuItem(null); setSavedMemory(null); setUseSaved(null); };
  const onUseSavedStyle = () => {
    if (savedMemory) setUseSaved({ theme: savedMemory.theme });
  };
  const onStartFresh = () => setUseSaved(null);

  const onAnalyzed = async (data) => {
    setAnalysis(data); setStep("review"); setTopError(null);
    // Recompute recommendations now that we have vision signals.
    await refreshRecs({ item: menuItem, an: data });
  };

  const onGenerate = async (params) => {
    setGenBusy(true); setTopError(null);
    try {
      const r = await axios.post(`${API}/ai-designer/generate`, {
        source_asset_id: params.enhanced_asset_id,
        item_name: params.item_name,
        features: params.features,
        price: params.price,
        theme: params.theme,
        headline: params.headline,
        item_key: params.item_key || null,
        variations: generationOptions.variantCount,
        auto_copy: true,
        remove_background: false,
        // Pass generation options to backend
        tone: generationOptions.tone,
        marketing_goal: generationOptions.marketingGoal,
        caption_length: generationOptions.captionLength,
        platform: generationOptions.platform,
        cta: generationOptions.cta || null,
        include_price: generationOptions.includePrice,
        include_description: generationOptions.includeDescription,
        // Priority 4.1: Logo options
        logo_url: generationOptions.logoUrl || null,
        logo_placement: generationOptions.logoPlacement,
        logo_size: generationOptions.logoSize,
      }, { headers: getAuthHeader(), timeout: 30000 });
      setDesignerJobId(r.data.job_id);
      setDesignerJob({ price: params.price });
      setLastTheme(params.theme);
      setStep("generating");
    } catch (e) {
      setTopError(parseAxiosError(e));
    } finally {
      setGenBusy(false);
    }
  };

  const onCompleted = (job) => {
    setDesignerJob(prev => ({ ...(prev || {}), ...job }));
    setStep("done");
  };
  const onFailed = (err) => { setTopError(err); setStep("review"); };

  const startOver = () => {
    setStep("upload"); setAnalysis(null);
    setDesignerJobId(null); setDesignerJob(null);
    setTopError(null);
    setUseSaved(null);
    setLastTheme(null);
  };
  const regenerate = () => { setStep("review"); };

  // Learning loop — fired when the owner clicks Download (first time only).
  const promptSavePreferredStyle = (payload) => {
    // Skip if the saved theme already equals what they just used (no change).
    if (savedMemory && savedMemory.theme && savedMemory.theme === payload.theme) return;
    setSaveModal(payload);
  };

  const confirmSaveStyle = async () => {
    if (!saveModal) return;
    setSavingStyle(true);
    try {
      const body = { theme: saveModal.theme };
      if (saveModal.favorite_flyer_id) body.favorite_flyer_id = saveModal.favorite_flyer_id;
      const r = await axios.put(
        `${API}/design-memory/${encodeURIComponent(saveModal.item_key)}`,
        body,
        { headers: getAuthHeader(), timeout: 10000 },
      );
      setSavedMemory(r.data);
      setSaveModal(null);
    } catch (e) {
      // Silent on failure — owner can retry; we don't want to block download.
      setSaveModal(null);
    } finally {
      setSavingStyle(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="photo-flyer">
      <div className="flex items-center gap-1 text-xs text-muted-foreground"
           data-testid="photo-flyer-stepper">
        <span className={step === "upload" ? "text-gold font-semibold" : ""}>
          1. Upload
        </span>
        <ChevronRight className="w-3 h-3 opacity-50" />
        <span className={step === "review" ? "text-gold font-semibold" : ""}>
          2. Review &amp; Edit
        </span>
        <ChevronRight className="w-3 h-3 opacity-50" />
        <span className={step === "generating" ? "text-gold font-semibold" : ""}>
          3. Generate
        </span>
        <ChevronRight className="w-3 h-3 opacity-50" />
        <span className={step === "done" ? "text-gold font-semibold" : ""}>
          4. Done
        </span>
      </div>

      {topError && step !== "generating" ? (
        <StructuredErrorCard error={topError}
          testId="photo-flyer-top-error"
          onRetry={() => setTopError(null)} />
      ) : null}

      {step === "upload" && (
        <UploadStep
          onAnalyzed={onAnalyzed}
          getAuthHeader={getAuthHeader}
          prefill={prefill}
          onDiscardPrefill={discardPrefill}
          menuItem={menuItem}
          onPickMenuItem={onPickMenuItem}
          onClearMenuItem={onClearMenuItem}
          savedMemory={savedMemory}
          onUseSavedStyle={onUseSavedStyle}
          onStartFresh={onStartFresh}
          generationOptions={generationOptions}
          onOptionsChange={setGenerationOptions}
          themesData={themesData}
        />
      )}
      {step === "review" && analysis && (
        <AnalysisReviewStep
          analysis={analysis}
          prefill={prefill}
          themes={themesData.themes || FALLBACK_THEMES.map(t => ({
            id: t.value, label: t.label, pack: "",
          }))}
          packs={themesData.packs}
          menuItem={menuItem}
          recs={recs}
          recsContext={recsContext}
          useSaved={useSaved}
          savedMemory={savedMemory}
          onPersistVisionChoice={(item_key, choice) =>
            axios.put(`${API}/design-memory/${encodeURIComponent(item_key)}`,
              { vision_choice: choice },
              { headers: getAuthHeader(), timeout: 10000 }).catch(() => {})}
          onBack={startOver}
          onGenerate={onGenerate}
          busy={genBusy}
        />
      )}
      {step === "generating" && designerJobId && (
        <GeneratingStep getAuthHeader={getAuthHeader}
          designerJobId={designerJobId}
          onCompleted={onCompleted} onFailed={onFailed} />
      )}
      {step === "done" && designerJob && (
        <ReviewStep
          job={designerJob}
          analysis={analysis}
          getAuthHeader={getAuthHeader}
          menuItem={menuItem}
          themeUsed={lastTheme}
          onSavePreferredStyle={promptSavePreferredStyle}
          onRegenerate={regenerate}
          onStartOver={startOver}
        />
      )}

      <SavePreferredStyleModal
        open={!!saveModal}
        item_name={saveModal?.item_name || ""}
        theme={saveModal?.theme || ""}
        onConfirm={confirmSaveStyle}
        onDismiss={() => setSaveModal(null)}
        busy={savingStyle}
      />
    </div>
  );
};

export default PhotoToFlyer;
