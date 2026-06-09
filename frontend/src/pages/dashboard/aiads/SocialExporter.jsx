/**
 * Social Exporter — pick a source image and bulk-generate platform-sized copies.
 *
 * Outputs land in the Asset Library tagged with the platform key
 * (ig_post_1_1, ig_reel_9_16, fb_post, fb_story, tiktok_9_16, gbp_image,
 * flyer_8_5_11). Uses /api/media/export-social.
 */
import React, { useState } from "react";
import axios from "axios";
import { Share2, Loader2, Check, ImageIcon as Img, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { API, Section, EmptyState } from "./shared";

const PRESETS = [
  { id: "ig_post_1_1",     label: "Instagram Post",        ratio: "1:1",  size: "1080×1080" },
  { id: "ig_portrait_4_5", label: "Instagram Portrait",    ratio: "4:5",  size: "1080×1350" },
  { id: "ig_reel_9_16",    label: "Instagram Reel/Story",  ratio: "9:16", size: "1080×1920" },
  { id: "fb_post",         label: "Facebook Post",         ratio: "1.9:1", size: "1200×630" },
  { id: "fb_story",        label: "Facebook Story",        ratio: "9:16", size: "1080×1920" },
  { id: "tiktok_9_16",     label: "TikTok Vertical",       ratio: "9:16", size: "1080×1920" },
  { id: "gbp_image",       label: "Google Business",       ratio: "4:3",  size: "1200×900" },
  { id: "flyer_8_5_11",    label: "Flyer (Print 8.5×11)",  ratio: "Letter", size: "2550×3300" },
];

export const SocialExporter = ({ assets, getAuthHeader, onExported }) => {
  const [sourceId, setSourceId] = useState("");
  const [picked, setPicked] = useState(new Set(["ig_post_1_1", "ig_reel_9_16", "fb_post"]));
  const [fit, setFit] = useState("cover");
  const [bgColor, setBgColor] = useState("#FFFFFF");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);   // {count, formats}
  const [error, setError] = useState("");

  const images = (assets || []).filter((a) => a.kind === "image");
  // Effective source: explicit pick, otherwise first available image.
  const effectiveSourceId = sourceId || (images[0] && images[0].id) || "";

  const togglePreset = (id) => {
    const next = new Set(picked);
    if (next.has(id)) next.delete(id); else next.add(id);
    setPicked(next);
  };

  const submit = async () => {
    setBusy(true); setError(""); setDone(null);
    try {
      const r = await axios.post(`${API}/media/export-social`, {
        source_asset_id: effectiveSourceId,
        formats: Array.from(picked),
        fit, bg_color: bgColor,
      }, { headers: getAuthHeader(), timeout: 90000 });
      setDone({ count: r.data.count, formats: Array.from(picked) });
      onExported && onExported();
    } catch (e) {
      const d = e.response && e.response.data && e.response.data.detail;
      setError(typeof d === "string" ? d : "Export failed");
    } finally {
      setBusy(false);
    }
  };

  if (images.length === 0) {
    return (
      <Section title="Social Exports" icon={Share2} testId="social-exporter">
        <EmptyState icon={Img} title="No images yet" body="Upload or generate an image first, then come back to export to Instagram/Facebook/TikTok formats." testId="social-empty" />
      </Section>
    );
  }

  return (
    <Section title="Social Exports — one image → every platform" icon={Share2} testId="social-exporter">
      <p className="text-xs text-muted-foreground mb-3">Pick one source image, choose the platforms you publish on, and we&apos;ll save correctly sized copies into your Asset Library.</p>

      {/* Source picker */}
      <p className="text-xs font-semibold text-navy mb-2">1. Source image</p>
      <div className="grid grid-cols-4 md:grid-cols-8 gap-1.5 max-h-32 overflow-y-auto mb-4 p-1 bg-background border border-navy/10 rounded">
        {images.slice(0, 40).map((a) => {
          const on = effectiveSourceId === a.id;
          return (
            <button key={a.id} type="button" onClick={() => setSourceId(a.id)}
              className={`relative aspect-square rounded border-2 overflow-hidden ${on ? "border-gold ring-2 ring-gold/40" : "border-navy/10 hover:border-navy/30"}`}
              data-testid={`social-source-${a.id}`}>
              <img src={`${API}/media/thumb/${a.id}`} alt="" className="w-full h-full object-cover" loading="lazy" />
              {on ? <Check className="absolute top-1 right-1 w-3 h-3 text-gold drop-shadow" /> : null}
            </button>
          );
        })}
      </div>

      {/* Presets */}
      <p className="text-xs font-semibold text-navy mb-2">2. Output formats ({picked.size} selected)</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 mb-4">
        {PRESETS.map((p) => {
          const on = picked.has(p.id);
          return (
            <button key={p.id} type="button" onClick={() => togglePreset(p.id)}
              className={`text-left p-2 rounded border-2 transition-colors ${on ? "border-gold bg-gold/10" : "border-navy/10 hover:border-navy/30"}`}
              data-testid={`social-preset-${p.id}`}>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-navy">{p.label}</span>
                {on ? <Check className="w-3 h-3 text-gold" /> : null}
              </div>
              <div className="text-[9px] text-muted-foreground font-mono">{p.size} · {p.ratio}</div>
            </button>
          );
        })}
      </div>

      {/* Fit */}
      <p className="text-xs font-semibold text-navy mb-2">3. Resize behavior</p>
      <div className="flex gap-3 items-center mb-4 flex-wrap">
        <label className="flex items-center gap-1.5 text-xs cursor-pointer">
          <input type="radio" checked={fit === "cover"} onChange={() => setFit("cover")} className="accent-gold" data-testid="fit-cover" />
          <span>Cover (crop to fill)</span>
        </label>
        <label className="flex items-center gap-1.5 text-xs cursor-pointer">
          <input type="radio" checked={fit === "contain"} onChange={() => setFit("contain")} className="accent-gold" data-testid="fit-contain" />
          <span>Contain (pad with color)</span>
        </label>
        {fit === "contain" ? (
          <span className="flex items-center gap-1 text-xs">
            <span className="text-muted-foreground">Padding</span>
            <input type="color" value={bgColor} onChange={(e) => setBgColor(e.target.value)}
              className="w-8 h-6 border border-navy/20 rounded cursor-pointer" data-testid="fit-bg-color" />
          </span>
        ) : null}
      </div>

      {error ? (
        <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2 mb-3 flex items-start gap-2" data-testid="social-error">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" /><span>{error}</span>
        </div>
      ) : null}
      {done ? (
        <div className="text-xs text-forest bg-forest/10 border border-forest/30 rounded p-2 mb-3" data-testid="social-success">
          ✓ Exported {done.count} sized copies into Asset Library (folder: Social Media).
        </div>
      ) : null}

      <Button onClick={submit} disabled={busy || !effectiveSourceId || picked.size === 0}
        className="bg-gold text-navy hover:bg-gold/90" data-testid="social-export-run">
        {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Share2 className="w-4 h-4 mr-2" />}
        {busy ? `Exporting ${picked.size}…` : `Export ${picked.size} format${picked.size === 1 ? "" : "s"}`}
      </Button>
    </Section>
  );
};

export default SocialExporter;
