/**
 * Media Studio — Uploads + AI Images + Library + Video Render in one tab.
 *
 * Keeps existing AI Ads styling (Section, gold/navy palette, no redesign).
 * Drag-drop uploads, multi-file, progress per file, preview thumbs, AI image
 * generation via /api/media/ai-image, video slideshow render via
 * /api/media/video/render (asyncio job — poll /jobs).
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  Upload, Image as ImageIcon, Sparkles, Video, Library as LibraryIcon,
  Trash2, Star, Loader2, Folder, Film, Search, RefreshCcw, Play, Download,
  Sliders, AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API, Section, EmptyState } from "./shared";
import { ImageEditor } from "./ImageEditor";
// SocialExporter removed in Sprint 12B — superseded by PromoteThisItem social formats.
import { StructuredErrorCard, parseAxiosError } from "./StructuredErrorCard";

const FOLDERS = ["Menu Items", "Promotions", "Catering", "Events", "Logos", "Social Media", "Custom"];
const ASPECTS = ["1:1", "4:5", "9:16", "16:9"];
const TEMPLATES = [
  "restaurant_promotion", "daily_special", "menu_item_spotlight",
  "catering_ad", "holiday_promotion", "review_highlight",
];

// --------------- Uploads ---------------
const UploadDropzone = (props) => {
  const { onUpload, folder, setFolder, getAuthHeader } = props;
  const [dragging, setDragging] = useState(false);
  const [items, setItems] = useState([]); // {file, progress, error, asset}
  const inputRef = useRef(null);

  const submitFiles = async (files) => {
    const next = Array.from(files).map((f) => ({ file: f, progress: 0, error: null, asset: null }));
    setItems((prev) => [...next, ...prev]);
    for (let i = 0; i < next.length; i += 1) {
      const it = next[i];
      const form = new FormData();
      form.append("file", it.file);
      form.append("folder", folder);
      try {
        const res = await axios.post(`${API}/media/upload`, form, {
          // NOTE: do NOT set Content-Type — axios + the browser MUST
          // auto-generate `multipart/form-data; boundary=…`. Manual override
          // drops the boundary string and the backend rejects with 400
          // (which Cloudflare surfaces as 520 in production).
          headers: { ...getAuthHeader() },
          onUploadProgress: (e) => {
            const pct = e.total ? Math.round((e.loaded / e.total) * 100) : 0;
            setItems((prev) => prev.map((x) => (x.file === it.file ? { ...x, progress: pct } : x)));
          },
        });
        setItems((prev) => prev.map((x) => (x.file === it.file ? { ...x, asset: res.data, progress: 100 } : x)));
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.detail) || "Upload failed";
        setItems((prev) => prev.map((x) => (x.file === it.file ? { ...x, error: msg } : x)));
      }
    }
    onUpload();
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length > 0) submitFiles(e.dataTransfer.files);
  };

  const rows = [];
  for (let i = 0; i < items.length; i += 1) {
    const it = items[i];
    rows.push(
      <div key={i} className="flex items-center gap-2 p-2 bg-background border border-navy/10 rounded-sm text-xs" data-testid={`upload-item-${i}`}>
        <span className="flex-1 truncate text-navy">{it.file.name}</span>
        <span className="text-muted-foreground font-mono">{(it.file.size / 1024).toFixed(0)} KB</span>
        {it.error ? <span className="text-red-700">{it.error}</span>
          : it.asset ? <span className="text-forest">✓ Saved</span>
          : <div className="w-24 h-2 bg-navy/10 rounded-full overflow-hidden">
              <div className="h-full bg-gold transition-all" style={{ width: `${it.progress}%` }} />
            </div>}
      </div>
    );
  }

  return (
    <Section title="Upload Media" icon={Upload} testId="media-upload">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Folder</label>
          <select value={folder} onChange={(e) => setFolder(e.target.value)} className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm" data-testid="upload-folder">
            {FOLDERS.map((f) => <option key={f}>{f}</option>)}
          </select>
        </div>
      </div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current && inputRef.current.click()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${dragging ? "border-gold bg-gold/10" : "border-navy/20 bg-cream"}`}
        data-testid="upload-dropzone"
      >
        <Upload className="w-10 h-10 text-gold mx-auto mb-2 opacity-70" />
        <p className="font-serif text-navy font-semibold">Drag & drop images or videos</p>
        <p className="text-xs text-muted-foreground mt-1">JPG · PNG · WEBP · MP4 · MOV · WEBM</p>
        <input ref={inputRef} type="file" multiple accept="image/*,video/*" onChange={(e) => e.target.files && submitFiles(e.target.files)} className="hidden" data-testid="upload-file-input" />
      </div>
      {rows.length > 0 ? <div className="space-y-1 mt-3">{rows}</div> : null}
    </Section>
  );
};

// --------------- AI Image Generator (async job + polling) ---------------
// Production uses Cloudflare which kills HTTP requests at ~60s; image gen takes
// up to ~85s. We therefore POST /media/ai-image to enqueue a job (returns in
// <1s with a job_id), then poll GET /media/ai-image/job/{id} every 3s until
// status === "completed" | "failed", with a 3-minute frontend ceiling.
const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 3 * 60 * 1000;

const AiImageGenerator = (props) => {
  const { getAuthHeader, onGenerated } = props;
  const [prompt, setPrompt] = useState("");
  const [headline, setHeadline] = useState("");
  const [style, setStyle] = useState("Food photography, natural light, appetizing, restaurant menu hero shot");
  const [count, setCount] = useState(1);
  const [quality, setQuality] = useState("medium");
  const [folder, setFolder] = useState("Promotions");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [jobStatus, setJobStatus] = useState(null); // pending | processing | completed | failed
  const [progress, setProgress] = useState(0);
  const pollRef = useRef(null);
  const startedAtRef = useRef(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => () => stopPolling(), []);

  const finishWith = ({ err, completed }) => {
    stopPolling();
    setBusy(false);
    setJobStatus(null);
    setProgress(0);
    if (err) setError(err);
    if (completed) onGenerated();
  };

  const pollOnce = async (id) => {
    try {
      const res = await axios.get(`${API}/media/ai-image/job/${id}`, {
        headers: getAuthHeader(),
        timeout: 15000,
      });
      const job = res.data;
      setJobStatus(job.status);
      if (typeof job.progress === "number") setProgress(job.progress);
      if (job.status === "completed") {
        finishWith({ completed: true });
        return;
      }
      if (job.status === "failed") {
        finishWith({
          err: job.error || {
            code: "unknown", retryable: true, retry_action: "retry",
            user_message: "Image generation failed.", technical: "",
          },
        });
        return;
      }
      if (Date.now() - startedAtRef.current > POLL_TIMEOUT_MS) {
        finishWith({
          err: {
            code: "timeout", retryable: true, retry_action: "retry",
            user_message: "Generation took longer than 3 minutes. Try a shorter prompt, lower quality, or fewer images.",
            technical: "frontend poll timeout after 3 min",
          },
        });
      }
    } catch (e) {
      // Transient errors during polling — keep going unless we've exceeded the cap.
      if (Date.now() - startedAtRef.current > POLL_TIMEOUT_MS) {
        finishWith({ err: parseAxiosError(e) });
      }
    }
  };

  const run = async () => {
    setBusy(true); setError(null); setProgress(0); setJobStatus("pending");
    try {
      const res = await axios.post(`${API}/media/ai-image`,
        { prompt, headline: headline || null, style, count, quality, folder },
        { headers: getAuthHeader(), timeout: 15000 });
      const id = res.data && res.data.job_id;
      if (!id) {
        finishWith({
          err: {
            code: "unknown", retryable: true, retry_action: "retry",
            user_message: "The server didn't return a job ID. Please try again.",
            technical: "missing job_id in 202 response",
          },
        });
        return;
      }
      startedAtRef.current = Date.now();
      pollOnce(id);
      pollRef.current = setInterval(() => pollOnce(id), POLL_INTERVAL_MS);
    } catch (e) {
      finishWith({ err: parseAxiosError(e) });
    }
  };

  const focusPrompt = () => {
    const el = document.querySelector('[data-testid="ai-image-prompt"]');
    if (el) el.focus();
  };

  const statusLabel = jobStatus === "pending" ? "Queued…"
    : jobStatus === "processing" ? "Generating image… this can take 60–90 seconds."
    : "Working…";

  return (
    <Section title="AI Image Generator" icon={Sparkles} testId="ai-image-gen">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="md:col-span-2">
          <label className="block text-xs text-muted-foreground mb-1">Prompt</label>
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm" placeholder="e.g. Plate of crawfish étouffée with chunky house roux, white rice, parsley, on rustic wood table." data-testid="ai-image-prompt" />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Headline (optional overlay)</label>
          <Input value={headline} onChange={(e) => setHeadline(e.target.value)} className="border-navy/20 text-sm" placeholder="FRIDAY SPECIAL" data-testid="ai-image-headline" />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Folder</label>
          <select value={folder} onChange={(e) => setFolder(e.target.value)} className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm" data-testid="ai-image-folder">
            {FOLDERS.map((f) => <option key={f}>{f}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Style</label>
          <Input value={style} onChange={(e) => setStyle(e.target.value)} className="border-navy/20 text-sm" data-testid="ai-image-style" />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Count / Quality</label>
          <div className="flex gap-2">
            <select value={count} onChange={(e) => setCount(Number(e.target.value))} className="px-2 py-2 border border-navy/20 rounded-sm text-sm flex-1" data-testid="ai-image-count">
              {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n} image{n > 1 ? "s" : ""}</option>)}
            </select>
            <select value={quality} onChange={(e) => setQuality(e.target.value)} className="px-2 py-2 border border-navy/20 rounded-sm text-sm flex-1" data-testid="ai-image-quality">
              <option value="low">Low (faster)</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
        </div>
      </div>

      {busy ? (
        <div className="mt-3 p-3 bg-cream border border-gold/40 rounded-sm" data-testid="ai-image-progress">
          <div className="flex items-center gap-2 text-sm text-navy">
            <Loader2 className="w-4 h-4 animate-spin text-gold" />
            <span data-testid="ai-image-status-label">{statusLabel}</span>
          </div>
          <div className="mt-2 h-1.5 bg-navy/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-gold transition-all duration-500"
              style={{ width: `${Math.max(5, progress)}%` }}
              data-testid="ai-image-progress-bar"
            />
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="mt-3">
          <StructuredErrorCard error={error} testId="ai-image-error" onRetry={run} onEditSource={focusPrompt} />
        </div>
      ) : null}

      <Button onClick={run} disabled={busy || prompt.length < 3} className="bg-gold text-navy hover:bg-gold/90 mt-3" data-testid="ai-image-run">
        {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
        {busy ? "Generating…" : `Generate ${count} Image${count > 1 ? "s" : ""}`}
      </Button>
    </Section>
  );
};

// --------------- Asset Card ---------------
const AssetCard = (props) => {
  const { asset, onDelete, onFavorite, onEdit } = props;
  const isVideo = asset.kind === "video";
  return (
    <div className="rounded-lg border-2 border-navy/10 bg-card overflow-hidden group" data-testid={`media-asset-${asset.id}`}>
      <div className="relative aspect-square bg-background overflow-hidden">
        <img src={`${API}/media/thumb/${asset.id}`} alt={asset.filename} className="w-full h-full object-cover" loading="lazy" />
        {isVideo ? (
          <div className="absolute inset-0 flex items-center justify-center bg-black/30">
            <Play className="w-10 h-10 text-white drop-shadow-lg" />
          </div>
        ) : null}
        {asset.source === "ai_image" ? <span className="absolute top-1 left-1 text-[9px] bg-gold/90 text-navy px-1.5 py-0.5 rounded font-semibold uppercase">AI</span> : null}
        {asset.source === "video_render" ? <span className="absolute top-1 left-1 text-[9px] bg-forest/90 text-cream px-1.5 py-0.5 rounded font-semibold uppercase">Rendered</span> : null}
        {asset.source === "image_edit" ? <span className="absolute top-1 left-1 text-[9px] bg-navy/90 text-cream px-1.5 py-0.5 rounded font-semibold uppercase">Edited</span> : null}
        {asset.source === "social_export" ? <span className="absolute top-1 left-1 text-[9px] bg-cream/90 text-navy px-1.5 py-0.5 rounded font-semibold uppercase border border-navy/20">Social</span> : null}
      </div>
      <div className="p-2 space-y-1">
        <p className="text-[11px] font-semibold text-navy truncate" title={asset.filename}>{asset.filename}</p>
        <p className="text-[9px] text-muted-foreground">{asset.folder} · {(asset.size_bytes / 1024).toFixed(0)} KB{asset.duration_seconds ? ` · ${asset.duration_seconds}s` : ""}{asset.width ? ` · ${asset.width}×${asset.height}` : ""}</p>
        <div className="flex gap-1">
          <a href={`${API}/media/file/${asset.id}`} target="_blank" rel="noopener noreferrer" className="p-1 text-navy hover:text-gold" title="Download" data-testid={`media-${asset.id}-download`}><Download className="w-3 h-3" /></a>
          {!isVideo && onEdit ? (
            <button onClick={() => onEdit(asset)} className="p-1 text-navy hover:text-gold" title="Edit" data-testid={`media-${asset.id}-edit`}>
              <Sliders className="w-3 h-3" />
            </button>
          ) : null}
          <button onClick={() => onFavorite(asset)} className={`p-1 ${asset.is_favorite ? "text-gold" : "text-navy/60 hover:text-gold"}`} title="Favorite" data-testid={`media-${asset.id}-fav`}>
            <Star className="w-3 h-3" fill={asset.is_favorite ? "currentColor" : "none"} />
          </button>
          <button onClick={() => onDelete(asset)} className="p-1 text-destructive ml-auto" title="Delete" data-testid={`media-${asset.id}-del`}>
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>
    </div>
  );
};

// --------------- Video Render Wizard ---------------
const VideoRenderWizard = (props) => {
  const { getAuthHeader, assets, onStarted, jobs } = props;
  const [picked, setPicked] = useState([]);
  const [duration, setDuration] = useState(30);
  const [aspect, setAspect] = useState("9:16");
  const [title, setTitle] = useState("");
  const [cta, setCta] = useState("Order Now");
  const [template, setTemplate] = useState("menu_item_spotlight");
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  const togglePick = (id) => setPicked((p) => (p.indexOf(id) === -1 ? [...p, id] : p.filter((x) => x !== id)));

  const submit = async () => {
    setBusy(true); setSubmitError(null);
    try {
      await axios.post(`${API}/media/video/render`, {
        asset_ids: picked, duration_seconds: duration, aspect,
        title: title || null, cta: cta || null, template,
      }, { headers: getAuthHeader() });
      setPicked([]); setTitle("");
      onStarted();
    } catch (e) {
      setSubmitError(parseAxiosError(e));
    } finally {
      setBusy(false);
    }
  };

  const pickerCards = [];
  const usable = assets.filter((a) => a.kind === "image" || a.kind === "video");
  for (let i = 0; i < usable.length; i += 1) {
    const a = usable[i];
    const on = picked.indexOf(a.id) !== -1;
    pickerCards.push(
      <button key={a.id} type="button" onClick={() => togglePick(a.id)} className={`relative rounded border-2 overflow-hidden aspect-square ${on ? "border-gold ring-2 ring-gold/40" : "border-navy/10"}`} data-testid={`render-pick-${a.id}`}>
        <img src={`${API}/media/thumb/${a.id}`} alt="" className="w-full h-full object-cover" loading="lazy" />
        {on ? <span className="absolute top-1 left-1 bg-gold text-navy text-[9px] px-1 rounded font-bold">{picked.indexOf(a.id) + 1}</span> : null}
      </button>
    );
  }

  const jobRows = [];
  for (let i = 0; i < jobs.length; i += 1) {
    const j = jobs[i];
    const isFailed = j.status === "failed";
    const isDone = j.status === "completed";
    jobRows.push(
      <div key={j.id}
        className={`flex flex-col gap-1 p-2 border rounded-sm text-xs ${isFailed ? "bg-red-50 border-red-300" : isDone ? "bg-forest/5 border-forest/30" : "bg-background border-navy/10"}`}
        data-testid={`render-job-${j.id}`}>
        <div className="flex items-center gap-2 flex-wrap">
          <Film className="w-3.5 h-3.5 text-gold flex-shrink-0" />
          <span className="font-mono text-[10px] text-muted-foreground">{j.id.slice(0, 8)}</span>
          <span className="text-navy text-[11px]">{j.template} · {j.aspect} · {j.duration_seconds}s</span>
          <span className="ml-auto text-[10px] uppercase tracking-wider font-semibold flex items-center gap-1">
            {isDone ? <span className="text-forest">✓ Done</span>
              : isFailed ? <span className="text-red-700 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> Failed</span>
              : <span className="text-navy flex items-center gap-1"><Loader2 className="w-3 h-3 animate-spin" /> {j.status} {Math.round((j.progress || 0) * 100)}%</span>}
          </span>
        </div>
        {!isDone && !isFailed ? (
          <div className="h-1.5 w-full bg-navy/10 rounded-full overflow-hidden">
            <div className="h-full bg-gold transition-all" style={{ width: `${Math.round((j.progress || 0) * 100)}%` }} />
          </div>
        ) : null}
        {isFailed && j.error ? (
          typeof j.error === "string" ? (
            <p className="text-[11px] text-red-700 bg-red-100 rounded p-1.5 font-mono break-all" data-testid={`render-job-${j.id}-error`}>{j.error}</p>
          ) : (
            <StructuredErrorCard error={j.error} compact testId={`render-job-${j.id}-error`} onRetry={submit} />
          )
        ) : null}
        {isDone && j.output_asset_id ? (
          <a href={`${API}/media/file/${j.output_asset_id}`} target="_blank" rel="noopener noreferrer"
            className="text-[11px] text-gold hover:underline inline-flex items-center gap-1" data-testid={`render-job-${j.id}-link`}>
            <Download className="w-3 h-3" /> View / Download render
          </a>
        ) : null}
      </div>
    );
  }

  return (
    <Section title="Video Studio · Render from Media" icon={Video} testId="video-studio">
      <p className="text-xs text-muted-foreground mb-3">Pick 2-12 images or video clips, set duration + aspect, optionally add a title + CTA, and we&apos;ll render an MP4 you can publish.</p>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Duration</label>
          <select value={duration} onChange={(e) => setDuration(Number(e.target.value))} className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm" data-testid="render-duration">
            {[15, 30, 60].map((s) => <option key={s} value={s}>{s} sec</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Aspect</label>
          <select value={aspect} onChange={(e) => setAspect(e.target.value)} className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm" data-testid="render-aspect">
            {ASPECTS.map((a) => <option key={a}>{a}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Template</label>
          <select value={template} onChange={(e) => setTemplate(e.target.value)} className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm" data-testid="render-template">
            {TEMPLATES.map((t) => <option key={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Title (3s overlay)</label>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} className="border-navy/20 text-sm" placeholder="Friday Special" data-testid="render-title" />
        </div>
        <div className="md:col-span-2">
          <label className="block text-xs text-muted-foreground mb-1">Call-to-Action</label>
          <Input value={cta} onChange={(e) => setCta(e.target.value)} className="border-navy/20 text-sm" data-testid="render-cta" />
        </div>
      </div>
      <p className="text-xs font-semibold text-navy mb-2">Pick your media ({picked.length} selected — click in the order you want them shown):</p>
      {pickerCards.length === 0
        ? <p className="text-xs text-muted-foreground italic py-4">Upload at least one image or video to render a slideshow.</p>
        : <div className="grid grid-cols-3 md:grid-cols-6 lg:grid-cols-8 gap-1.5 mb-3">{pickerCards}</div>}
      <Button onClick={submit} disabled={busy || picked.length < 2} className="bg-gold text-navy hover:bg-gold/90" data-testid="render-start">
        {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Video className="w-4 h-4 mr-2" />} Render Video
      </Button>
      {submitError ? (
        <div className="mt-3">
          <StructuredErrorCard error={submitError} testId="render-submit-error" onRetry={submit} />
        </div>
      ) : null}
      {jobRows.length > 0 ? (
        <div className="mt-4 space-y-2" data-testid="render-jobs">
          <p className="text-xs font-semibold text-navy">Render Queue</p>
          {jobRows}
        </div>
      ) : null}
    </Section>
  );
};

// --------------- Media Studio (orchestrator) ---------------
export const MediaStudio = (props) => {
  const { getAuthHeader } = props;
  const [section, setSection] = useState("uploads");
  const [folder, setFolder] = useState("Custom");
  const [filters, setFilters] = useState({ q: "", kind: "", folder: "" });
  const [assets, setAssets] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState({});
  const [editorAsset, setEditorAsset] = useState(null);

  const loadAssets = useCallback(async () => {
    try {
      const params = {};
      if (filters.q) params.q = filters.q;
      if (filters.kind) params.kind = filters.kind;
      if (filters.folder) params.folder = filters.folder;
      const r = await axios.get(`${API}/media/assets`, { params, headers: getAuthHeader() });
      setAssets(r.data.assets || []);
    } catch (e) { console.error(e); }
  }, [filters, getAuthHeader]);

  const loadJobs = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/media/video/jobs`, { headers: getAuthHeader() });
      setJobs(r.data.jobs || []);
    } catch (e) { /* noop */ }
  }, [getAuthHeader]);

  const loadStats = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/media/stats`, { headers: getAuthHeader() });
      setStats(r.data);
    } catch (e) { /* noop */ }
  }, [getAuthHeader]);

  // Combined initial load + 4s polling for active render jobs / video tab
  const refs = useRef({ jobs, section, loadJobs, loadAssets, loadStats });
  useEffect(() => { refs.current = { jobs, section, loadJobs, loadAssets, loadStats }; });
  useEffect(() => {
    refs.current.loadAssets();
    refs.current.loadStats();
    refs.current.loadJobs();
    const t = setInterval(() => {
      const r = refs.current;
      const hasActive = r.jobs.some((j) => j.status === "queued" || j.status === "processing");
      if (hasActive || r.section === "video") {
        r.loadJobs(); r.loadAssets(); r.loadStats();
      }
    }, 4000);
    return () => clearInterval(t);
  }, []);

  const onFavorite = async (a) => {
    await axios.patch(`${API}/media/assets/${a.id}`, { is_favorite: !a.is_favorite }, { headers: getAuthHeader() });
    loadAssets();
  };
  const onDelete = async (a) => {
    if (!window.confirm(`Delete ${a.filename}?`)) return;
    await axios.delete(`${API}/media/assets/${a.id}`, { headers: getAuthHeader() });
    loadAssets();
  };

  const cards = [];
  for (let i = 0; i < assets.length; i += 1) {
    cards.push(<AssetCard key={assets[i].id} asset={assets[i]} onDelete={onDelete} onFavorite={onFavorite} onEdit={setEditorAsset} />);
  }

  const sectionBtns = [];
  const SECTIONS = [
    { id: "uploads", label: "Uploads", icon: Upload },
    { id: "ai", label: "AI Images", icon: Sparkles },
    { id: "editor", label: "Editor", icon: Sliders },
    { id: "video", label: "Video Studio", icon: Video },
    { id: "library", label: "Asset Library", icon: LibraryIcon },
  ];
  for (let i = 0; i < SECTIONS.length; i += 1) {
    const s = SECTIONS[i]; const on = section === s.id;
    sectionBtns.push(
      <button key={s.id} onClick={() => setSection(s.id)}
        className={`whitespace-nowrap shrink-0 px-3 py-2 rounded-sm text-sm border ${on ? "bg-navy text-cream border-navy" : "border-navy/20 text-navy hover:bg-navy/5"}`}
        data-testid={`media-sub-${s.id}`}>
        <s.icon className="w-3.5 h-3.5 inline mr-1" /> {s.label}
      </button>
    );
  }

  return (
    <div className="space-y-4" data-testid="media-studio">
      <div className="rounded-lg bg-gradient-to-r from-gold/10 to-forest/10 border-2 border-gold/30 p-3 flex flex-wrap gap-4 items-center" data-testid="media-stats">
        <div className="flex items-center gap-2"><ImageIcon className="w-4 h-4 text-gold" /><span className="text-xs text-navy"><strong>{stats.images_uploaded || 0}</strong> uploaded · <strong>{stats.ai_images_generated || 0}</strong> AI</span></div>
        <div className="flex items-center gap-2"><Film className="w-4 h-4 text-forest" /><span className="text-xs text-navy"><strong>{stats.videos_uploaded || 0}</strong> videos · <strong>{stats.videos_rendered || 0}</strong> rendered</span></div>
        {stats.active_render_jobs > 0 ? <span className="text-xs bg-gold/30 text-navy px-2 py-0.5 rounded-full font-semibold">{stats.active_render_jobs} rendering…</span> : null}
      </div>

      <div className="flex gap-2 overflow-x-auto pb-2">{sectionBtns}</div>

      {section === "uploads" && <UploadDropzone onUpload={loadAssets} folder={folder} setFolder={setFolder} getAuthHeader={getAuthHeader} />}
      {section === "ai" && <AiImageGenerator getAuthHeader={getAuthHeader} onGenerated={() => { loadAssets(); loadStats(); }} />}
      {section === "editor" && (
        assets.filter((a) => a.kind === "image").length === 0
          ? <EmptyState icon={Sliders} title="No images yet" body="Upload or generate an image first, then click the editor icon on any thumbnail to refine it." testId="editor-empty" />
          : (
            <Section title="Image Editor" icon={Sliders} testId="editor-launcher">
              <p className="text-xs text-muted-foreground mb-3">Pick an image from your library to crop, resize, adjust brightness/contrast, add text or logo overlays, or remove the background.</p>
              <div className="grid grid-cols-3 md:grid-cols-6 lg:grid-cols-8 gap-1.5">
                {assets.filter((a) => a.kind === "image").slice(0, 32).map((a) => (
                  <button key={a.id} type="button" onClick={() => setEditorAsset(a)}
                    className="relative rounded border-2 border-navy/10 hover:border-gold overflow-hidden aspect-square group"
                    data-testid={`editor-source-${a.id}`}>
                    <img src={`${API}/media/thumb/${a.id}`} alt="" className="w-full h-full object-cover" loading="lazy" />
                    <div className="absolute inset-0 bg-navy/0 group-hover:bg-navy/40 transition-colors flex items-center justify-center">
                      <Sliders className="w-5 h-5 text-cream opacity-0 group-hover:opacity-100" />
                    </div>
                  </button>
                ))}
              </div>
            </Section>
          )
      )}
      {section === "video" && <VideoRenderWizard getAuthHeader={getAuthHeader} assets={assets} onStarted={() => { loadJobs(); loadStats(); }} jobs={jobs} />}

      {(section === "library" || section === "uploads" || section === "ai" || section === "video") ? (
        <Section title={`Asset Library (${assets.length})`} icon={LibraryIcon} testId="media-library"
          action={<Button size="sm" variant="outline" onClick={loadAssets} className="border-navy/20" data-testid="media-library-refresh"><RefreshCcw className="w-3 h-3 mr-1" /> Refresh</Button>}>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
            <Input placeholder="Search filename / tag…" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} className="border-navy/20 text-sm md:col-span-2" data-testid="media-search" />
            <select value={filters.kind} onChange={(e) => setFilters({ ...filters, kind: e.target.value })} className="px-2 py-2 border border-navy/20 rounded-sm text-sm" data-testid="media-filter-kind">
              <option value="">All types</option><option value="image">Images</option><option value="video">Videos</option>
            </select>
            <select value={filters.folder} onChange={(e) => setFilters({ ...filters, folder: e.target.value })} className="px-2 py-2 border border-navy/20 rounded-sm text-sm" data-testid="media-filter-folder">
              <option value="">All folders</option>
              {FOLDERS.map((f) => <option key={f}>{f}</option>)}
            </select>
          </div>
          {cards.length === 0
            ? <EmptyState icon={LibraryIcon} title="No media yet" body="Upload images / videos or generate AI images. Everything you save here can be attached to campaigns." testId="media-empty" />
            : <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">{cards}</div>}
        </Section>
      ) : null}

      <ImageEditor key={editorAsset ? editorAsset.id : "closed"} open={!!editorAsset} source={editorAsset} libraryAssets={assets}
        getAuthHeader={getAuthHeader}
        onClose={() => setEditorAsset(null)}
        onSaved={() => { loadAssets(); loadStats(); }} />
    </div>
  );
};

export default MediaStudio;
