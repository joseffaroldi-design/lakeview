import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  ArrowLeft,
  CheckCircle,
  Copy,
  Download,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  Share2,
  Sparkles,
  Upload,
} from "lucide-react";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { API, Section } from "./shared";
import StructuredErrorCard, { parseAxiosError } from "./StructuredErrorCard";

const POLL_MS = 2500;
const POLL_TIMEOUT_MS = 4 * 60 * 1000;
const PREFILL_KEY = "lakeview.photo_flyer.prefill";

const FALLBACK_THEMES = [
  { id: "modern", label: "Modern" },
  { id: "comic_pop", label: "Comic Pop" },
  { id: "vintage_diner", label: "Vintage Diner" },
];

function readPrefill() {
  try {
    const raw = sessionStorage.getItem(PREFILL_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && parsed.name ? parsed : null;
  } catch {
    return null;
  }
}

function clearPrefill() {
  try { sessionStorage.removeItem(PREFILL_KEY); } catch { /* noop */ }
}

function copyText(text) {
  if (!text) return;
  navigator.clipboard?.writeText(text).catch(() => {});
}

export default function PhotoToFlyer({ getAuthHeader }) {
  const fileRef = useRef(null);
  const pollStarted = useRef(0);
  const [step, setStep] = useState("photo");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [themes, setThemes] = useState(FALLBACK_THEMES);
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [progress, setProgress] = useState(0);
  const [prefill] = useState(() => readPrefill());

  const [form, setForm] = useState({
    itemName: prefill?.name || "",
    price: prefill?.price || "",
    features: Array.isArray(prefill?.features) ? prefill.features.join(", ") : "",
    theme: "modern",
  });

  useEffect(() => {
    let cancelled = false;
    axios.get(`${API}/photo-flyer/themes`, { headers: getAuthHeader(), timeout: 10000 })
      .then((r) => {
        if (cancelled) return;
        const visible = (r.data?.themes || []).filter((t) => !t.hidden);
        if (visible.length) setThemes(visible);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [getAuthHeader]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const analyzeFile = async (file) => {
    if (!file) return;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(file));
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await axios.post(`${API}/photo-flyer/analyze`, fd, {
        headers: { ...getAuthHeader() },
        timeout: 90000,
      });
      const data = r.data;
      setAnalysis(data);
      setForm((old) => ({
        ...old,
        itemName: old.itemName || data.menu_match?.item?.name || data.food_type || "Featured Dish",
        price: old.price || data.menu_match?.item?.price || "",
        features: old.features || (data.features || []).slice(0, 4).join(", "),
        theme: data.suggested_theme || old.theme || "modern",
      }));
      clearPrefill();
      setStep("details");
    } catch (e) {
      setError(parseAxiosError(e));
    } finally {
      setBusy(false);
    }
  };

  const generate = async () => {
    if (!analysis || !form.itemName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const r = await axios.post(`${API}/photo-flyer/generate`, {
        source_asset_id: analysis.enhanced_asset_id,
        item_name: form.itemName.trim(),
        features: form.features.split(",").map((s) => s.trim()).filter(Boolean).slice(0, 6),
        price: form.price.trim() || null,
        theme: form.theme,
        auto_copy: true,
        remove_background: false,
        variations: 3,
        platform: "instagram_post",
        include_price: true,
        include_description: true,
      }, { headers: getAuthHeader(), timeout: 30000 });
      setJobId(r.data.job_id);
      setJob(null);
      setProgress(5);
      pollStarted.current = Date.now();
      setStep("generating");
    } catch (e) {
      setError(parseAxiosError(e));
    } finally {
      setBusy(false);
    }
  };

  const poll = useCallback(async () => {
    if (!jobId) return;
    if (Date.now() - pollStarted.current > POLL_TIMEOUT_MS) {
      setError({ user_message: "Generation took too long. Please try again.", code: "timeout" });
      setStep("details");
      return;
    }
    try {
      const r = await axios.get(`${API}/photo-flyer/job/${jobId}`, {
        headers: getAuthHeader(),
        timeout: 15000,
      });
      const current = r.data;
      setProgress(current.progress || 0);
      if (current.status === "completed") {
        setJob(current);
        setStep("done");
        return;
      }
      if (current.status === "failed") {
        setError(current.error || { user_message: "Generation failed." });
        setStep("details");
        return;
      }
      window.setTimeout(poll, POLL_MS);
    } catch {
      window.setTimeout(poll, POLL_MS * 2);
    }
  }, [jobId, getAuthHeader]);

  useEffect(() => {
    if (step === "generating" && jobId) poll();
  }, [step, jobId, poll]);

  const startOver = () => {
    setStep("photo");
    setAnalysis(null);
    setJobId(null);
    setJob(null);
    setProgress(0);
    setError(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl("");
  };

  const variations = job?.variations || [];
  const finished = variations.filter((v) => v.status === "completed" && v.asset_id);
  const [selected, setSelected] = useState(0);
  const active = finished[selected] || finished[0] || null;
  const activeUrl = active?.asset_id ? `${API}/media/file/${active.asset_id}` : "";
  const fb = job?.copy_pack?.fb_post || "";
  const ig = job?.copy_pack?.ig_post || "";

  useEffect(() => { setSelected(0); }, [jobId]);

  const shareFlyer = async () => {
    if (!activeUrl) return;
    if (navigator.share) {
      try {
        await navigator.share({ title: form.itemName, text: ig || fb || form.itemName, url: activeUrl });
        return;
      } catch { /* use copy fallback */ }
    }
    copyText(activeUrl);
  };

  return (
    <div className="space-y-6" data-testid="photo-flyer">
      <div>
        <p className="text-xs uppercase tracking-[0.16em] font-semibold text-gold">Marketing</p>
        <h2 className="text-2xl font-bold text-navy">Photo to Flyer</h2>
        <p className="text-sm text-navy/60 mt-1">Upload a food photo, confirm the details, choose a style, and generate.</p>
      </div>

      {error ? (
        <StructuredErrorCard error={error} testId="photo-flyer-top-error" onRetry={() => setError(null)} />
      ) : null}

      {step === "photo" ? (
        <Section title="1. Choose a photo" icon={ImageIcon} testId="photo-upload">
          <div className="space-y-4">
            {previewUrl ? <img src={previewUrl} alt="Preview" className="w-full max-w-sm rounded-lg border border-navy/10" /> : null}
            <Button
              onClick={() => fileRef.current?.click()}
              disabled={busy}
              className="bg-gold text-navy hover:bg-gold/90"
              data-testid="photo-flyer-upload-btn"
            >
              {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
              {busy ? "Analyzing photo…" : "Upload food photo"}
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(e) => analyzeFile(e.target.files?.[0])}
              data-testid="photo-flyer-upload-input"
            />
          </div>
        </Section>
      ) : null}

      {step === "details" && analysis ? (
        <div className="space-y-4">
          <Section title="2. Flyer details" icon={Sparkles} testId="photo-flyer-details">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-semibold text-navy">Item name</label>
                <Input value={form.itemName} onChange={(e) => setForm({ ...form, itemName: e.target.value })} data-testid="photo-flyer-item-name" />
              </div>
              <div>
                <label className="text-xs font-semibold text-navy">Price</label>
                <Input value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} placeholder="$14.99" data-testid="photo-flyer-price" />
              </div>
              <div className="md:col-span-2">
                <label className="text-xs font-semibold text-navy">Features</label>
                <Input value={form.features} onChange={(e) => setForm({ ...form, features: e.target.value })} placeholder="Cheddar, bacon, pickles" data-testid="photo-flyer-features" />
                <p className="text-[11px] text-navy/50 mt-1">Separate features with commas.</p>
              </div>
            </div>
          </Section>

          <Section title="3. Choose a style" testId="photo-flyer-themes">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              {themes.map((theme) => (
                <button
                  key={theme.id}
                  type="button"
                  onClick={() => setForm({ ...form, theme: theme.id })}
                  className={`rounded-md border px-3 py-3 text-sm text-left transition-colors ${form.theme === theme.id ? "border-gold bg-gold/10 font-semibold text-navy" : "border-navy/15 text-navy/70 hover:border-gold/50"}`}
                  data-testid={`photo-flyer-theme-${theme.id}`}
                >
                  {theme.label || theme.id}
                </button>
              ))}
            </div>
          </Section>

          <div className="flex gap-2">
            <Button variant="outline" onClick={startOver} className="border-navy/20"><ArrowLeft className="w-4 h-4 mr-1.5" /> Back</Button>
            <Button onClick={generate} disabled={busy || !form.itemName.trim()} className="bg-gold text-navy hover:bg-gold/90" data-testid="photo-flyer-generate">
              {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1.5" />}
              Generate flyer
            </Button>
          </div>
        </div>
      ) : null}

      {step === "generating" ? (
        <Section title="Generating your flyer" icon={Loader2} testId="photo-flyer-progress">
          <div className="space-y-3">
            <div className="h-2 rounded-full bg-navy/10 overflow-hidden"><div className="h-full bg-gold transition-all" style={{ width: `${Math.max(5, progress)}%` }} /></div>
            <p className="text-sm text-navy/70">Creating three designs and captions…</p>
          </div>
        </Section>
      ) : null}

      {step === "done" && active ? (
        <div className="space-y-4" data-testid="photo-flyer-step-review-done">
          <Section title="Your flyer is ready" icon={CheckCircle} testId="photo-flyer-review-flyer">
            {finished.length > 1 ? (
              <div className="grid grid-cols-3 gap-2 mb-4">
                {finished.map((v, idx) => (
                  <button key={v.asset_id} onClick={() => setSelected(idx)} className={`rounded-md overflow-hidden border-2 ${selected === idx ? "border-gold" : "border-transparent"}`}>
                    <img src={`${API}/media/thumb/${v.asset_id}`} alt={`Design ${idx + 1}`} className="w-full aspect-square object-cover" />
                  </button>
                ))}
              </div>
            ) : null}

            <img src={activeUrl} alt="Generated flyer" className="w-full max-w-md mx-auto rounded-lg border border-navy/10" data-testid="photo-flyer-flyer-img" />

            <div className="flex flex-wrap gap-2 mt-4">
              <a href={activeUrl} download className="inline-flex items-center gap-1.5 text-sm font-semibold text-gold hover:underline" data-testid="photo-flyer-download-flyer">
                <Download className="w-4 h-4" /> Download
              </a>
              <button type="button" onClick={shareFlyer} className="inline-flex items-center gap-1.5 text-sm font-semibold text-navy hover:text-gold" data-testid="flyer-share-btn">
                <Share2 className="w-4 h-4" /> Share
              </button>
              <button type="button" onClick={() => setStep("details")} className="inline-flex items-center gap-1.5 text-sm text-navy hover:underline" data-testid="photo-flyer-regenerate">
                <RefreshCw className="w-4 h-4" /> Change style
              </button>
            </div>
          </Section>

          {(fb || ig) ? (
            <Section title="Captions" icon={Copy} testId="photo-flyer-review-copy">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {fb ? <CaptionCard title="Facebook" text={fb} /> : null}
                {ig ? <CaptionCard title="Instagram" text={ig} /> : null}
              </div>
            </Section>
          ) : null}

          <Button variant="outline" onClick={startOver} className="border-navy/20">Make another flyer</Button>
        </div>
      ) : null}
    </div>
  );
}

function CaptionCard({ title, text }) {
  return (
    <div className="rounded-md border border-navy/15 p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-navy">{title}</p>
        <button type="button" onClick={() => copyText(text)} className="text-xs text-gold hover:underline inline-flex items-center gap-1"><Copy className="w-3 h-3" /> Copy</button>
      </div>
      <p className="text-sm text-navy whitespace-pre-wrap">{text}</p>
    </div>
  );
}
