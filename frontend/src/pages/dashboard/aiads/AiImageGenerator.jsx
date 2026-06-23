/**
 * Sprint 15B.8 — AI Image Generator (real AI, via Flux Pro / OpenAI gpt-image-1).
 *
 * Sibling to the Template Designer. Owner workflow:
 *   1. Pick a style pack + aspect ratio
 *   2. Type a prompt
 *   3. Generate → 4 variations stream in
 *   4. Save (already in library), Download, or "Use In Ad" → preloads the
 *      asset back into the Template Designer for price/headline overlays.
 *
 * Reuses ALL existing infrastructure:
 *   * `/api/ai-image/generate` → background job (same pattern as ai_designer)
 *   * `/api/ai-image/job/{id}` polling
 *   * `/api/media/thumb/{id}` for previews — generated images already
 *     live in `media_assets` so the library shows them automatically.
 */
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Sparkles,
  Wand2,
  Download,
  Image as ImageIcon,
  ChevronRight,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ASPECT_OPTIONS = [
  { key: "1:1", label: "Square 1:1", hint: "Instagram feed, menu cards" },
  { key: "4:5", label: "Portrait 4:5", hint: "Instagram portrait, flyers" },
  { key: "9:16", label: "Vertical 9:16", hint: "Reels, Stories, TikTok" },
  { key: "16:9", label: "Wide 16:9", hint: "Banner, web hero" },
];

const POLL_INTERVAL_MS = 2500;
const POLL_TIMEOUT_MS = 90_000;

const AiImageGenerator = ({ getAuthHeader, onUseInAd }) => {
  const [presets, setPresets] = useState([]);
  const [providerInfo, setProviderInfo] = useState(null);

  // form state
  const [prompt, setPrompt] = useState("");
  const [stylePack, setStylePack] = useState("restaurant_food_photography");
  const [aspectRatio, setAspectRatio] = useState("1:1");

  // job state
  const [generating, setGenerating] = useState(false);
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);

  // Boot — load presets + provider info once on mount.
  useEffect(() => {
    let alive = true;
    Promise.all([
      axios.get(`${API}/ai-image/style-presets`, { headers: getAuthHeader() }),
      axios.get(`${API}/ai-image/providers`, { headers: getAuthHeader() }),
    ])
      .then(([presetsRes, providersRes]) => {
        if (!alive) return;
        setPresets(presetsRes.data.presets || []);
        setProviderInfo(providersRes.data);
      })
      .catch((e) => {
        if (!alive) return;
        setError("Couldn't load style packs. Refresh the page.");
        console.error("[ai-image] boot failed", e);
      });
    return () => {
      alive = false;
    };
  }, [getAuthHeader]);

  const generate = useCallback(async () => {
    if (!prompt.trim() || prompt.trim().length < 4) {
      toast.error("Prompt needs at least a few words.");
      return;
    }
    setError(null);
    setJob(null);
    setGenerating(true);
    try {
      const res = await axios.post(
        `${API}/ai-image/generate`,
        {
          prompt: prompt.trim(),
          style_pack: stylePack,
          aspect_ratio: aspectRatio,
        },
        { headers: getAuthHeader() },
      );
      const jobId = res.data.job_id;
      setJob({ id: jobId, status: "pending", variations: [] });

      // Poll until done or timeout.
      const startedAt = Date.now();
      let finalJob = null;
      while (Date.now() - startedAt < POLL_TIMEOUT_MS) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
        const poll = await axios.get(`${API}/ai-image/job/${jobId}`, {
          headers: getAuthHeader(),
        });
        const j = poll.data;
        setJob(j);
        if (j.status === "completed" || j.status === "failed") {
          finalJob = j;
          break;
        }
      }
      if (!finalJob) {
        setError("Generation took longer than 90 s. Try again or pick a shorter prompt.");
      } else if (finalJob.status === "failed") {
        setError(finalJob.error?.user_message || "Generation failed. Try again.");
      } else {
        toast.success("4 images generated and saved to your library.");
      }
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const msg =
        (typeof detail === "object" && detail?.user_message) ||
        (typeof detail === "string" && detail) ||
        "Generate request failed. Try again.";
      setError(msg);
    } finally {
      setGenerating(false);
    }
  }, [aspectRatio, getAuthHeader, prompt, stylePack]);

  const downloadVariation = async (asset_id) => {
    try {
      const res = await axios.get(`${API}/media/file/${asset_id}`, {
        headers: getAuthHeader(),
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `lakeview-ai-${asset_id.slice(0, 8)}.png`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error("Could not download. Try again.");
    }
  };

  const handleUseInAd = (asset) => {
    if (!onUseInAd) {
      toast.error("Use In Ad isn't available right now.");
      return;
    }
    onUseInAd(asset);
    toast.success(`Loaded into Template Designer.`);
  };

  const activeProviderLabel =
    providerInfo?.active === "flux"
      ? "Flux Pro (fal.ai)"
      : providerInfo?.active === "openai"
        ? "OpenAI gpt-image-1"
        : "No provider configured";

  return (
    <div className="space-y-6" data-testid="ai-image-generator">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-serif text-navy">AI Image Generator</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Generate brand-new marketing imagery from a prompt — straight into
            your library.
          </p>
        </div>
        <span
          className="text-xs px-2 py-1 rounded-sm bg-navy/5 text-navy/70 font-mono"
          data-testid="ai-image-provider-badge"
        >
          Engine: {activeProviderLabel}
        </span>
      </div>

      {/* Style pack */}
      <div>
        <label className="block text-xs font-semibold uppercase tracking-wide text-navy/70 mb-2">
          Style Pack
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          {presets.map((p) => (
            <button
              key={p.key}
              type="button"
              onClick={() => setStylePack(p.key)}
              disabled={generating}
              className={`text-left text-xs px-3 py-2 rounded-sm border transition-colors ${
                stylePack === p.key
                  ? "border-gold bg-gold/10 text-navy font-semibold"
                  : "border-navy/15 hover:border-navy/30 text-navy/80"
              }`}
              data-testid={`ai-image-style-${p.key}`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Aspect ratio */}
      <div>
        <label className="block text-xs font-semibold uppercase tracking-wide text-navy/70 mb-2">
          Aspect Ratio
        </label>
        <div className="flex flex-wrap gap-2">
          {ASPECT_OPTIONS.map((a) => (
            <button
              key={a.key}
              type="button"
              onClick={() => setAspectRatio(a.key)}
              disabled={generating}
              className={`text-xs px-3 py-2 rounded-sm border transition-colors ${
                aspectRatio === a.key
                  ? "border-gold bg-gold/10 text-navy font-semibold"
                  : "border-navy/15 hover:border-navy/30 text-navy/80"
              }`}
              data-testid={`ai-image-aspect-${a.key}`}
            >
              <span className="font-mono">{a.label}</span>
              <span className="block text-[10px] text-navy/50 mt-0.5">
                {a.hint}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Prompt */}
      <div>
        <label
          className="block text-xs font-semibold uppercase tracking-wide text-navy/70 mb-2"
          htmlFor="ai-image-prompt"
        >
          Prompt
        </label>
        <textarea
          id="ai-image-prompt"
          data-testid="ai-image-prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={generating}
          rows={3}
          placeholder='e.g. "Loaded smash burger with double cheddar, crispy onions and house sauce on a charred brioche bun"'
          className="w-full text-sm border border-navy/20 rounded-sm px-3 py-2 font-sans focus:outline-none focus:ring-2 focus:ring-gold"
          maxLength={500}
        />
        <div className="text-[10px] text-navy/50 mt-1 text-right">
          {prompt.length}/500
        </div>
      </div>

      {/* Generate */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={generate}
          disabled={generating || !providerInfo?.active}
          className="inline-flex items-center gap-2 bg-navy text-white hover:bg-navy/90 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-sm text-sm font-semibold transition-colors"
          data-testid="ai-image-generate-btn"
        >
          {generating ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" /> Generating…
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" /> Generate 4 variations
            </>
          )}
        </button>
        {job?.status === "processing" ? (
          <span
            className="text-xs text-navy/60"
            data-testid="ai-image-progress"
          >
            {job.progress || 0}% · {job.provider || ""}
          </span>
        ) : null}
      </div>

      {/* Error */}
      {error ? (
        <div
          className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-sm text-sm"
          data-testid="ai-image-error"
        >
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      {/* Variations */}
      {(() => {
        if (!(job?.status === "completed")) return null;
        const variations = job.variations || [];
        if (!variations.length) return null;
        return (
        <div data-testid="ai-image-variations">
          <h3 className="text-sm font-semibold text-navy mb-3 flex items-center gap-2">
            <ImageIcon className="w-4 h-4" /> 4 variations · saved to library
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {variations.map((v) => {
              if (v.status !== "completed") {
                return (
                  <div
                    key={v.variant}
                    className="aspect-square bg-red-50 border border-red-200 rounded-sm flex items-center justify-center text-[11px] text-red-700 p-2 text-center"
                    data-testid={`ai-image-variant-failed-${v.variant}`}
                  >
                    Variation {v.variant} failed
                  </div>
                );
              }
              return (
                <div
                  key={v.variant}
                  className="space-y-2"
                  data-testid={`ai-image-variant-${v.variant}`}
                >
                  <div className="aspect-square overflow-hidden bg-navy/5 rounded-sm border border-navy/10">
                    <img
                      src={`${API}/media/thumb/${v.asset_id}`}
                      alt={`Variation ${v.variant}`}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <button
                      type="button"
                      onClick={() => handleUseInAd(v.asset)}
                      className="inline-flex items-center justify-center gap-1 text-[11px] bg-gold text-navy hover:bg-gold/90 px-2 py-1 rounded-sm font-semibold"
                      data-testid={`ai-image-useinad-${v.variant}`}
                    >
                      <ChevronRight className="w-3 h-3" /> Use In Ad
                    </button>
                    <button
                      type="button"
                      onClick={() => downloadVariation(v.asset_id)}
                      className="inline-flex items-center justify-center gap-1 text-[11px] border border-navy/20 hover:bg-navy/5 text-navy px-2 py-1 rounded-sm"
                      data-testid={`ai-image-download-${v.variant}`}
                    >
                      <Download className="w-3 h-3" /> Download
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-4 flex items-center gap-2">
            <button
              type="button"
              onClick={generate}
              disabled={generating}
              className="inline-flex items-center gap-1.5 text-xs border border-navy/20 hover:bg-navy/5 text-navy px-3 py-1.5 rounded-sm"
              data-testid="ai-image-regenerate"
            >
              <Wand2 className="w-3.5 h-3.5" /> Regenerate
            </button>
            <span className="text-[10px] text-navy/50">
              Already saved — these are in your library now.
            </span>
          </div>
        </div>
        );
      })()}
    </div>
  );
};

export default AiImageGenerator;
