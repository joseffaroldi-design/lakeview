/**
 * Image Editor modal — non-destructive, saves output as a NEW media asset.
 *
 * Controls:
 *   - Crop center (percentage box)
 *   - Resize (W × H)
 *   - Rotate (0/90/180/270) + flip
 *   - Brightness / Contrast / Saturation / Sharpness sliders
 *   - Background removal (rembg — first call downloads model, slow)
 *   - Text overlay (text, position, size, color, optional background)
 *   - Logo overlay (pick from library)
 *   - Reset to original • Save as new asset
 *
 * NOTE on imports: we intentionally use plain HTML elements (button / div /
 * input) and avoid cross-file shadcn Card components — keeps the visual-edits
 * Babel plugin happy (see shared.jsx header).
 */
import React, { useMemo, useState } from "react";
import axios from "axios";
import {
  X, RotateCw, FlipHorizontal2, Crop, Type, Image as ImageIcon,
  Sparkles, Save, RefreshCcw, Loader2, Sliders,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API } from "./shared";

const DEFAULTS = {
  brightness: 1.0, contrast: 1.0, saturation: 1.0, sharpness: 1.0,
  rotate: 0, flip_horizontal: false, remove_background: false,
  crop_pct: { x: 0, y: 0, w: 100, h: 100 },  // percentage of source
  resize_w: "", resize_h: "",
  text_overlay: null, logo_overlay: null,
  folder: null, bg_color: "#FFFFFF",
};

const Slider = ({ label, min, max, step, value, onChange, testId, formatter }) => (
  <div>
    <div className="flex justify-between mb-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xs font-mono text-navy">{formatter ? formatter(value) : value}</span>
    </div>
    <input type="range" min={min} max={max} step={step} value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-full accent-gold" data-testid={testId} />
  </div>
);

const TabBtn = ({ id, label, icon: Icon, current, onSelect }) => (
  <button onClick={() => onSelect(id)}
    className={`px-3 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${current === id ? "border-gold text-navy" : "border-transparent text-muted-foreground hover:text-navy"}`}
    data-testid={`editor-tab-${id}`}>
    <Icon className="w-3.5 h-3.5" /> {label}
  </button>
);

export const ImageEditor = ({ open, source, libraryAssets, getAuthHeader, onClose, onSaved }) => {
  const [state, setState] = useState(DEFAULTS);
  const [tab, setTab] = useState("adjust");
  const [previewKey, setPreviewKey] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [text, setText] = useState({
    enabled: false, text: "", x_pct: 0.5, y_pct: 0.85, size_pct: 0.08,
    color: "#FFFFFF", background: "", background_opacity: 0.55, align: "center",
  });
  const [logo, setLogo] = useState({
    enabled: false, logo_asset_id: "", x_pct: 0.05, y_pct: 0.05, width_pct: 0.18, opacity: 1.0,
  });

  // Reset is handled by the parent re-mounting this component via `key={source.id}`.
  // No effect needed — keeps the hook ESLint plugin happy.

  // Live CSS preview for adjustments — exact match to server PIL is close enough
  const previewFilter = useMemo(() => {
    const parts = [];
    parts.push(`brightness(${state.brightness})`);
    parts.push(`contrast(${state.contrast})`);
    parts.push(`saturate(${state.saturation})`);
    return parts.join(" ");
  }, [state.brightness, state.contrast, state.saturation]);

  const previewTransform = useMemo(() => {
    const parts = [];
    if (state.rotate) parts.push(`rotate(${state.rotate}deg)`);
    if (state.flip_horizontal) parts.push("scaleX(-1)");
    return parts.join(" ");
  }, [state.rotate, state.flip_horizontal]);

  const logoChoices = (libraryAssets || []).filter((a) => a.kind === "image" && a.id !== (source && source.id));

  if (!open || !source) return null;

  const submit = async () => {
    setSaving(true); setError("");
    const body = {
      source_asset_id: source.id,
      brightness: state.brightness, contrast: state.contrast,
      saturation: state.saturation, sharpness: state.sharpness,
      rotate: state.rotate, flip_horizontal: state.flip_horizontal,
      remove_background: state.remove_background,
    };
    if (state.remove_background && state.bg_color) body.bg_color = state.bg_color;

    // Crop: percentages → pixels (use source W/H from asset)
    const c = state.crop_pct;
    if (c.x !== 0 || c.y !== 0 || c.w !== 100 || c.h !== 100) {
      const sw = source.width || 1080;
      const sh = source.height || 1080;
      body.crop = {
        x: Math.max(0, Math.floor((c.x / 100) * sw)),
        y: Math.max(0, Math.floor((c.y / 100) * sh)),
        w: Math.max(10, Math.floor((c.w / 100) * sw)),
        h: Math.max(10, Math.floor((c.h / 100) * sh)),
      };
    }
    if (state.resize_w || state.resize_h) {
      if (state.resize_w) body.resize_w = Number(state.resize_w);
      if (state.resize_h) body.resize_h = Number(state.resize_h);
    }
    if (text.enabled && text.text.trim().length > 0) {
      body.text_overlay = {
        text: text.text, x_pct: text.x_pct, y_pct: text.y_pct,
        size_pct: text.size_pct, color: text.color, align: text.align,
      };
      if (text.background) {
        body.text_overlay.background = text.background;
        body.text_overlay.background_opacity = text.background_opacity;
      }
    }
    if (logo.enabled && logo.logo_asset_id) {
      body.logo_overlay = {
        logo_asset_id: logo.logo_asset_id,
        x_pct: logo.x_pct, y_pct: logo.y_pct,
        width_pct: logo.width_pct, opacity: logo.opacity,
      };
    }
    try {
      const r = await axios.post(`${API}/media/edit`, body, {
        headers: getAuthHeader(),
        timeout: state.remove_background ? 180000 : 60000,
      });
      onSaved && onSaved(r.data);
      onClose && onClose();
    } catch (e) {
      const d = e.response && e.response.data && e.response.data.detail;
      setError(typeof d === "string" ? d : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    setState(DEFAULTS);
    setText({ ...text, enabled: false, text: "" });
    setLogo({ ...logo, enabled: false, logo_asset_id: "" });
    setError("");
    setPreviewKey((k) => k + 1);
  };

  // local helper closes over `tab` and `setTab`
  const tabBtn = (id, label, icon) => (
    <TabBtn id={id} label={label} icon={icon} current={tab} onSelect={setTab} />
  );

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-2 sm:p-4" data-testid="image-editor-modal" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="bg-card text-card-foreground rounded-lg w-full max-w-5xl max-h-[95vh] overflow-hidden flex flex-col shadow-2xl border-2 border-gold/30">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-navy/10 bg-cream">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-gold" />
            <h3 className="font-serif text-navy font-semibold">Image Editor</h3>
            <span className="text-xs text-muted-foreground truncate max-w-[200px] hidden sm:inline">· {source.filename}</span>
          </div>
          <button onClick={onClose} className="text-navy hover:text-red-700 p-1" data-testid="editor-close"><X className="w-5 h-5" /></button>
        </div>

        {/* Body */}
        <div className="flex flex-col md:flex-row flex-1 overflow-hidden">
          {/* Preview */}
          <div className="flex-1 bg-navy/5 flex items-center justify-center p-4 min-h-[300px] overflow-auto">
            <div className="relative max-w-full max-h-full">
              <img
                key={previewKey}
                src={`${API}/media/file/${source.id}`}
                alt="preview"
                className="max-w-full max-h-[60vh] object-contain rounded shadow-lg"
                style={{ filter: previewFilter, transform: previewTransform }}
                data-testid="editor-preview"
              />
              {text.enabled && text.text ? (
                <div className="absolute pointer-events-none"
                  style={{
                    left: `${text.x_pct * 100}%`, top: `${text.y_pct * 100}%`,
                    transform: "translate(-50%,-50%)",
                    fontSize: `${text.size_pct * 100}%`,
                    color: text.color,
                    background: text.background ? `${text.background}${Math.round(text.background_opacity*255).toString(16).padStart(2,'0')}` : "transparent",
                    padding: text.background ? "0.2em 0.4em" : 0,
                    fontWeight: "bold", textShadow: "0 0 4px rgba(0,0,0,0.6)",
                    whiteSpace: "nowrap",
                  }}>
                  {text.text}
                </div>
              ) : null}
            </div>
          </div>

          {/* Controls */}
          <div className="w-full md:w-80 flex-shrink-0 border-l border-navy/10 flex flex-col overflow-hidden">
            <div className="flex border-b border-navy/10">
              {tabBtn("adjust", "Adjust", Sliders)}
              {tabBtn("crop", "Crop", Crop)}
              {tabBtn("text", "Text", Type)}
              {tabBtn("logo", "Logo", ImageIcon)}
              {tabBtn("bg", "BG", Sparkles)}
            </div>
            <div className="overflow-y-auto p-4 space-y-4 flex-1">
              {tab === "adjust" && (
                <>
                  <Slider label="Brightness" min={0.3} max={2.0} step={0.05}
                    value={state.brightness} onChange={(v) => setState({ ...state, brightness: v })}
                    testId="slider-brightness" formatter={(v) => v.toFixed(2)} />
                  <Slider label="Contrast" min={0.3} max={2.0} step={0.05}
                    value={state.contrast} onChange={(v) => setState({ ...state, contrast: v })}
                    testId="slider-contrast" formatter={(v) => v.toFixed(2)} />
                  <Slider label="Saturation" min={0.0} max={2.0} step={0.05}
                    value={state.saturation} onChange={(v) => setState({ ...state, saturation: v })}
                    testId="slider-saturation" formatter={(v) => v.toFixed(2)} />
                  <Slider label="Sharpness" min={0.0} max={3.0} step={0.1}
                    value={state.sharpness} onChange={(v) => setState({ ...state, sharpness: v })}
                    testId="slider-sharpness" formatter={(v) => v.toFixed(2)} />
                  <div className="pt-2 border-t border-navy/10">
                    <div className="flex gap-2 flex-wrap">
                      {[0, 90, 180, 270].map((deg) => (
                        <button key={deg} onClick={() => setState({ ...state, rotate: deg })}
                          className={`px-3 py-1.5 text-xs border rounded ${state.rotate === deg ? "bg-gold text-navy border-gold" : "border-navy/20 text-navy hover:bg-navy/5"}`}
                          data-testid={`rotate-${deg}`}>
                          <RotateCw className="w-3 h-3 inline mr-1" />{deg}°
                        </button>
                      ))}
                      <button onClick={() => setState({ ...state, flip_horizontal: !state.flip_horizontal })}
                        className={`px-3 py-1.5 text-xs border rounded ${state.flip_horizontal ? "bg-gold text-navy border-gold" : "border-navy/20 text-navy hover:bg-navy/5"}`}
                        data-testid="flip-horizontal">
                        <FlipHorizontal2 className="w-3 h-3 inline mr-1" />Flip
                      </button>
                    </div>
                  </div>
                </>
              )}

              {tab === "crop" && (
                <div className="space-y-3">
                  <p className="text-xs text-muted-foreground">Crop is in percent of source ({source.width || "?"}×{source.height || "?"}). 0=top-left.</p>
                  {[
                    ["x", "X start", 0, 99],
                    ["y", "Y start", 0, 99],
                    ["w", "Width", 1, 100],
                    ["h", "Height", 1, 100],
                  ].map(([k, label, mn, mx]) => (
                    <Slider key={k} label={`${label} (%)`} min={mn} max={mx} step={1}
                      value={state.crop_pct[k]}
                      onChange={(v) => setState({ ...state, crop_pct: { ...state.crop_pct, [k]: v } })}
                      testId={`crop-${k}`} />
                  ))}
                  <div className="flex gap-2 flex-wrap pt-2 border-t border-navy/10">
                    <button onClick={() => setState({ ...state, crop_pct: { x: 0, y: 0, w: 100, h: 100 } })}
                      className="px-2 py-1 text-[11px] border border-navy/20 rounded hover:bg-navy/5" data-testid="crop-preset-full">Full</button>
                    <button onClick={() => setState({ ...state, crop_pct: { x: 10, y: 10, w: 80, h: 80 } })}
                      className="px-2 py-1 text-[11px] border border-navy/20 rounded hover:bg-navy/5" data-testid="crop-preset-center">Center 80%</button>
                    <button onClick={() => setState({ ...state, crop_pct: { x: 0, y: 12, w: 100, h: 76 } })}
                      className="px-2 py-1 text-[11px] border border-navy/20 rounded hover:bg-navy/5" data-testid="crop-preset-wide">Wide 16:9</button>
                  </div>
                  <div className="pt-2 border-t border-navy/10 space-y-2">
                    <p className="text-xs font-semibold text-navy">Resize output (optional)</p>
                    <div className="flex gap-2">
                      <Input value={state.resize_w} onChange={(e) => setState({ ...state, resize_w: e.target.value.replace(/\D/g, "") })}
                        placeholder="Width" className="border-navy/20 text-sm" data-testid="resize-w" />
                      <Input value={state.resize_h} onChange={(e) => setState({ ...state, resize_h: e.target.value.replace(/\D/g, "") })}
                        placeholder="Height" className="border-navy/20 text-sm" data-testid="resize-h" />
                    </div>
                  </div>
                </div>
              )}

              {tab === "text" && (
                <div className="space-y-3">
                  <label className="flex items-center gap-2 text-xs">
                    <input type="checkbox" checked={text.enabled} onChange={(e) => setText({ ...text, enabled: e.target.checked })} data-testid="text-toggle" />
                    Enable text overlay
                  </label>
                  <Input value={text.text} onChange={(e) => setText({ ...text, text: e.target.value })}
                    placeholder="FRIDAY SPECIAL" className="border-navy/20 text-sm" data-testid="text-content" />
                  <Slider label="X position" min={0} max={1} step={0.01} value={text.x_pct}
                    onChange={(v) => setText({ ...text, x_pct: v })} testId="text-x" formatter={(v) => `${Math.round(v*100)}%`} />
                  <Slider label="Y position" min={0} max={1} step={0.01} value={text.y_pct}
                    onChange={(v) => setText({ ...text, y_pct: v })} testId="text-y" formatter={(v) => `${Math.round(v*100)}%`} />
                  <Slider label="Size" min={0.02} max={0.25} step={0.005} value={text.size_pct}
                    onChange={(v) => setText({ ...text, size_pct: v })} testId="text-size" formatter={(v) => `${Math.round(v*100)}%`} />
                  <div className="flex gap-2 items-center">
                    <label className="text-xs text-muted-foreground">Color</label>
                    <input type="color" value={text.color} onChange={(e) => setText({ ...text, color: e.target.value })}
                      className="w-12 h-7 border border-navy/20 rounded cursor-pointer" data-testid="text-color" />
                    <label className="text-xs text-muted-foreground ml-2">BG</label>
                    <input type="color" value={text.background || "#000000"}
                      onChange={(e) => setText({ ...text, background: e.target.value })}
                      className="w-12 h-7 border border-navy/20 rounded cursor-pointer" data-testid="text-bg" />
                    <button onClick={() => setText({ ...text, background: "" })}
                      className="text-[10px] text-muted-foreground hover:text-red-700 underline">no bg</button>
                  </div>
                </div>
              )}

              {tab === "logo" && (
                <div className="space-y-3">
                  <label className="flex items-center gap-2 text-xs">
                    <input type="checkbox" checked={logo.enabled} onChange={(e) => setLogo({ ...logo, enabled: e.target.checked })} data-testid="logo-toggle" />
                    Enable logo overlay
                  </label>
                  <p className="text-xs text-muted-foreground">Pick a logo from your Asset Library:</p>
                  {logoChoices.length === 0
                    ? <p className="text-xs italic text-muted-foreground">No images available. Upload your logo first.</p>
                    : (
                      <div className="grid grid-cols-3 gap-1.5 max-h-40 overflow-y-auto">
                        {logoChoices.slice(0, 24).map((a) => (
                          <button key={a.id} type="button" onClick={() => setLogo({ ...logo, logo_asset_id: a.id })}
                            className={`relative aspect-square rounded border-2 overflow-hidden ${logo.logo_asset_id === a.id ? "border-gold ring-2 ring-gold/40" : "border-navy/10"}`}
                            data-testid={`logo-pick-${a.id}`}>
                            <img src={`${API}/media/thumb/${a.id}`} alt="" className="w-full h-full object-cover" loading="lazy" />
                          </button>
                        ))}
                      </div>
                    )}
                  <Slider label="X position" min={0} max={0.85} step={0.01} value={logo.x_pct}
                    onChange={(v) => setLogo({ ...logo, x_pct: v })} testId="logo-x" formatter={(v) => `${Math.round(v*100)}%`} />
                  <Slider label="Y position" min={0} max={0.85} step={0.01} value={logo.y_pct}
                    onChange={(v) => setLogo({ ...logo, y_pct: v })} testId="logo-y" formatter={(v) => `${Math.round(v*100)}%`} />
                  <Slider label="Width" min={0.05} max={0.6} step={0.01} value={logo.width_pct}
                    onChange={(v) => setLogo({ ...logo, width_pct: v })} testId="logo-w" formatter={(v) => `${Math.round(v*100)}%`} />
                  <Slider label="Opacity" min={0.2} max={1.0} step={0.05} value={logo.opacity}
                    onChange={(v) => setLogo({ ...logo, opacity: v })} testId="logo-opacity" formatter={(v) => v.toFixed(2)} />
                </div>
              )}

              {tab === "bg" && (
                <div className="space-y-3">
                  <label className="flex items-center gap-2 text-xs">
                    <input type="checkbox" checked={state.remove_background}
                      onChange={(e) => setState({ ...state, remove_background: e.target.checked })}
                      data-testid="remove-bg-toggle" />
                    Remove background (AI)
                  </label>
                  <p className="text-xs text-muted-foreground">First call may take 30–90 seconds while the AI model is downloaded. Subsequent calls are fast.</p>
                  {state.remove_background ? (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">Replace BG with</span>
                      <input type="color" value={state.bg_color} onChange={(e) => setState({ ...state, bg_color: e.target.value })}
                        className="w-12 h-7 border border-navy/20 rounded cursor-pointer" data-testid="bg-color" />
                      <button onClick={() => setState({ ...state, bg_color: "" })}
                        className="text-[10px] text-muted-foreground hover:text-red-700 underline">transparent PNG</button>
                    </div>
                  ) : null}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="border-t border-navy/10 p-3 space-y-2 bg-cream">
              {error ? <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2" data-testid="editor-error">{error}</div> : null}
              <div className="flex gap-2">
                <Button variant="outline" onClick={reset} className="border-navy/20 flex-1" data-testid="editor-reset">
                  <RefreshCcw className="w-3.5 h-3.5 mr-1" /> Reset
                </Button>
                <Button onClick={submit} disabled={saving} className="bg-gold text-navy hover:bg-gold/90 flex-1" data-testid="editor-save">
                  {saving ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Save className="w-3.5 h-3.5 mr-1" />}
                  {saving ? (state.remove_background ? "Removing BG…" : "Saving…") : "Save as new"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImageEditor;
