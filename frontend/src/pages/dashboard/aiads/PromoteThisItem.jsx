/**
 * Promote This Item 2.0 — owner-facing one-click marketing pack generator.
 *
 * Flow: pick photo → tweak item → generate (background job + 3-sec polling) →
 * review + edit text inline → download.  See backend `routers/marketing_pack.py`.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import {
  Sparkles, Upload, Image as ImageIcon, Loader2, Download, Copy as CopyIcon,
  RefreshCw, CheckCircle, ChevronRight, ArrowLeft,
} from "lucide-react";
import { API, Section } from "./shared";
import StructuredErrorCard, { parseAxiosError } from "./StructuredErrorCard";

const POLL_MS = 3000;
const POLL_TIMEOUT_MS = 4 * 60 * 1000;

const fmtLabel = {
  ig_post: "Instagram Post (1:1)",
  ig_story: "Instagram Story / TikTok / Reel (9:16)",
  fb_post: "Facebook Post (1.91:1)",
  hero: "Website Hero (16:9)",
};

const copyToClipboard = (text) => {
  try { navigator.clipboard.writeText(text || ""); } catch (e) { /* noop */ }
};


// ---------- Step 1: Pick photo + suggestion strip ---------------------------

const PickPhotoStep = ({ getAuthHeader, onSelected }) => {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [libraryAssets, setLibraryAssets] = useState([]);
  const [showLibrary, setShowLibrary] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    axios.get(`${API}/marketing-pack/items-not-promoted-recently?limit=3`, { headers: getAuthHeader() })
      .then((r) => { if (mounted) setSuggestions(r.data.items || []); })
      .catch(() => { /* non-fatal */ });
    return () => { mounted = false; };
  }, [getAuthHeader]);

  const loadLibrary = async () => {
    try {
      const r = await axios.get(`${API}/media/assets?kind=image&limit=24`, { headers: getAuthHeader() });
      setLibraryAssets(r.data.assets || r.data || []);
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
      fd.append("folder", "Marketing Packs");
      fd.append("tags", "promote-this-item");
      const r = await axios.post(`${API}/media/upload`, fd, {
        headers: { ...getAuthHeader(), "Content-Type": "multipart/form-data" },
        timeout: 60000,
      });
      onSelected({ asset: r.data, menuItem: null });
    } catch (e2) {
      setError(parseAxiosError(e2));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="promote-step-pick">
      <Section title="Promote This Item" icon={Sparkles} testId="promote-section-pick">
        <p className="text-sm text-muted-foreground mb-4">
          Pick a photo and we&apos;ll create everything you need to promote it —
          Instagram, Facebook, website hero, captions, hashtags, SMS, email,
          Google Business Profile, and a 15-second vertical video.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
          <Button
            onClick={() => fileRef.current && fileRef.current.click()}
            disabled={uploading}
            className="bg-gold text-navy hover:bg-gold/90 h-auto py-4 flex-col gap-1"
            data-testid="promote-upload-btn"
          >
            {uploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Upload className="w-5 h-5" />}
            <span className="font-semibold">{uploading ? "Uploading…" : "Upload Photo"}</span>
            <span className="text-xs opacity-80">jpg, png — max 15 MB</span>
          </Button>
          <Button
            onClick={loadLibrary}
            variant="outline"
            className="border-navy/20 text-navy hover:bg-navy/5 h-auto py-4 flex-col gap-1"
            data-testid="promote-library-btn"
          >
            <ImageIcon className="w-5 h-5 text-gold" />
            <span className="font-semibold">Choose from Library</span>
            <span className="text-xs opacity-70">Pick an existing image</span>
          </Button>
        </div>
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleUpload} data-testid="promote-file-input" />

        {error ? <StructuredErrorCard error={error} testId="promote-pick-error" onRetry={() => setError(null)} /> : null}
      </Section>

      {showLibrary ? (
        <Section title="Choose from Library" icon={ImageIcon} testId="promote-library-grid">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {libraryAssets.map((a) => (
              <button
                key={a.id}
                onClick={() => onSelected({ asset: a, menuItem: null })}
                className="block group relative overflow-hidden rounded-md border border-navy/10 hover:border-gold transition-all"
                data-testid={`promote-library-asset-${a.id}`}
              >
                <img
                  src={`${API}/media/thumb/${a.id}`}
                  alt={a.filename}
                  className="w-full h-32 object-cover group-hover:scale-105 transition-transform"
                  loading="lazy"
                />
                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-navy/80 to-transparent p-2 text-cream text-[10px] truncate">
                  {a.filename}
                </div>
              </button>
            ))}
            {libraryAssets.length === 0 ? (
              <p className="col-span-full text-xs text-muted-foreground text-center py-6">
                No images in library yet — upload one above.
              </p>
            ) : null}
          </div>
        </Section>
      ) : null}

      {suggestions.length > 0 ? (
        <Section title="Items not promoted recently" icon={Sparkles} testId="promote-suggestions">
          <p className="text-xs text-muted-foreground mb-3">
            Tap one to pre-fill the item details — you&apos;ll still pick a photo.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {suggestions.map((it) => (
              <button
                key={it.item_key}
                onClick={() => onSelected({ asset: null, menuItem: it })}
                className="text-left rounded-md border border-navy/10 p-3 hover:border-gold hover:bg-cream transition-colors"
                data-testid={`promote-suggestion-${it.item_key}`}
              >
                <p className="font-semibold text-navy text-sm">{it.name}</p>
                <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">{it.description || it.category_display_name}</p>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs text-gold font-medium">${it.price}</span>
                  <span className="text-[10px] text-muted-foreground">
                    {it.last_promoted_at ? "Promoted" : "Never promoted"}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </Section>
      ) : null}
    </div>
  );
};


// ---------- Step 2: Item details + Generate --------------------------------

const ItemDetailsStep = ({ getAuthHeader, asset, menuItem, onBack, onGenerated }) => {
  const [name, setName] = useState((menuItem && menuItem.name) || "");
  const [description, setDescription] = useState((menuItem && menuItem.description) || "");
  const [price, setPrice] = useState((menuItem && menuItem.price) ? `$${menuItem.price}` : "");
  const [headline, setHeadline] = useState("");
  const [cta, setCta] = useState("Order Now");
  const [needAsset, setNeedAsset] = useState(!asset);
  const [pickedAsset, setPickedAsset] = useState(asset);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const generate = async () => {
    if (!pickedAsset) { setNeedAsset(true); return; }
    setBusy(true); setError(null);
    try {
      const r = await axios.post(`${API}/marketing-pack/generate`, {
        source_asset_id: pickedAsset.id,
        menu_item_key: (menuItem && menuItem.item_key) || null,
        name: name || null, description: description || null,
        price: price || null, headline: headline || null, cta: cta || null,
      }, { headers: getAuthHeader(), timeout: 15000 });
      onGenerated(r.data.job_id);
    } catch (e) {
      setError(parseAxiosError(e));
      setBusy(false);
    }
  };

  return (
    <Section title="Item details" icon={Sparkles} testId="promote-step-details">
      <div className="grid grid-cols-1 md:grid-cols-[280px,1fr] gap-4">
        <div>
          {pickedAsset ? (
            <div className="rounded-md overflow-hidden border-2 border-gold">
              <img src={`${API}/media/thumb/${pickedAsset.id}`} alt="" className="w-full h-44 object-cover" data-testid="promote-preview" />
              <button onClick={() => setPickedAsset(null)} className="w-full text-xs py-1.5 bg-navy/5 hover:bg-navy/10 text-navy" data-testid="promote-change-photo">
                Change photo
              </button>
            </div>
          ) : (
            <div className="border-2 border-dashed border-navy/20 rounded-md p-4 text-center text-xs text-muted-foreground">
              {needAsset ? "Pick a photo first — go back and upload or choose from library." : "No photo selected"}
              <Button variant="outline" size="sm" onClick={onBack} className="mt-2 w-full" data-testid="promote-back-to-pick">
                <ArrowLeft className="w-3 h-3 mr-1" /> Pick photo
              </Button>
            </div>
          )}
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Item name <span className="text-muted-foreground">(optional — AI will infer)</span></label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Smash Burger Special" className="border-navy/20" data-testid="promote-name" />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Description <span className="text-muted-foreground">(optional)</span></label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2}
              className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm"
              placeholder="e.g. Two beef patties, melted cheddar, house sauce, brioche bun"
              data-testid="promote-description" />
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Price</label>
              <Input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="$14" className="border-navy/20" data-testid="promote-price" />
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Headline overlay</label>
              <Input value={headline} onChange={(e) => setHeadline(e.target.value)} placeholder="FRIDAY SPECIAL" className="border-navy/20" data-testid="promote-headline" />
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">CTA</label>
              <Input value={cta} onChange={(e) => setCta(e.target.value)} placeholder="Order Now" className="border-navy/20" data-testid="promote-cta" />
            </div>
          </div>

          <div className="mt-2 p-3 rounded-md bg-cream border border-gold/30">
            <p className="text-xs font-semibold text-navy mb-1.5">Sample pack you&apos;ll get:</p>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              ✓ Instagram Post (1:1) &nbsp;·&nbsp; ✓ IG Story / TikTok / Reel (9:16) &nbsp;·&nbsp; ✓ Facebook Post &nbsp;·&nbsp; ✓ Website Hero<br />
              ✓ Caption + hashtags &nbsp;·&nbsp; ✓ SMS &nbsp;·&nbsp; ✓ Email subject + body &nbsp;·&nbsp; ✓ Google Business Profile post &nbsp;·&nbsp; ✓ 15-sec promo video
            </p>
          </div>

          {error ? <StructuredErrorCard error={error} testId="promote-details-error" onRetry={generate} /> : null}

          <div className="flex gap-2 pt-2">
            <Button variant="outline" onClick={onBack} className="border-navy/20" data-testid="promote-back">
              <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </Button>
            <Button
              onClick={generate}
              disabled={busy || !pickedAsset}
              className="bg-gold text-navy hover:bg-gold/90 flex-1"
              data-testid="promote-generate-btn"
            >
              {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
              {busy ? "Starting…" : "Generate Marketing Pack →"}
            </Button>
          </div>
        </div>
      </div>
    </Section>
  );
};


// ---------- Step 3: Progress ---------------------------------------------

const stepLabels = {
  queued: "Queued…",
  inferring: "Reading your photo and writing item details…",
  writing_copy: "Writing captions, SMS, email, and Google copy…",
  rendering_images: "Rendering your 4 social formats…",
  rendering_video: "Building your 15-second promo video…",
  saving: "Saving everything to your library…",
};

const ProgressStep = ({ getAuthHeader, jobId, onCompleted, onFailed, onCancel }) => {
  const [job, setJob] = useState({ status: "pending", progress: 0, current_step: "queued" });
  const [elapsed, setElapsed] = useState(0);
  const startedRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => {
    startedRef.current = Date.now();
    const tick = async () => {
      try {
        const r = await axios.get(`${API}/marketing-pack/job/${jobId}`, { headers: getAuthHeader(), timeout: 15000 });
        setJob(r.data);
        setElapsed(Math.floor((Date.now() - startedRef.current) / 1000));
        if (r.data.status === "completed") {
          if (pollRef.current) clearInterval(pollRef.current);
          onCompleted(r.data);
        } else if (r.data.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          onFailed(r.data.error || { code: "unknown", retryable: true, retry_action: "retry", user_message: "Pack generation failed.", technical: "" });
        } else if (Date.now() - startedRef.current > POLL_TIMEOUT_MS) {
          if (pollRef.current) clearInterval(pollRef.current);
          onFailed({ code: "timeout", retryable: true, retry_action: "retry",
                     user_message: "Generation took longer than 4 minutes. Try again or pick a different photo.",
                     technical: "frontend poll timeout after 4 min" });
        }
      } catch (e) { /* keep polling */ }
    };
    tick();
    pollRef.current = setInterval(tick, POLL_MS);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [jobId, getAuthHeader, onCompleted, onFailed]);

  const etaText = job.progress >= 70 ? "About 30 more seconds" : job.progress >= 45 ? "About a minute left" : "Roughly a minute and a half left";

  return (
    <Section title="Creating your marketing pack" icon={Sparkles} testId="promote-step-progress">
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-gold" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-navy" data-testid="promote-progress-step">
              {stepLabels[job.current_step] || stepLabels.queued}
            </p>
            <p className="text-xs text-muted-foreground" data-testid="promote-progress-eta">
              {etaText} · elapsed {elapsed}s
            </p>
          </div>
        </div>
        <div className="h-2 bg-navy/10 rounded-full overflow-hidden">
          <div className="h-full bg-gold transition-all duration-500" style={{ width: `${Math.max(5, job.progress || 0)}%` }} data-testid="promote-progress-bar" />
        </div>
        <p className="text-[11px] text-muted-foreground italic">
          You can leave this page — your pack will keep building in the background and you&apos;ll find it in the Library when it&apos;s done.
        </p>
        <div>
          <Button variant="outline" onClick={onCancel} size="sm" data-testid="promote-progress-cancel">Cancel</Button>
        </div>
      </div>
    </Section>
  );
};


// ---------- Step 4: Review ----------------------------------------------

const EditableField = ({ label, value, onChange, testId, rows = 1, hint }) => (
  <div>
    <div className="flex items-center justify-between mb-1">
      <label className="text-xs font-semibold text-navy">{label}</label>
      <button
        onClick={() => copyToClipboard(value)}
        className="text-[10px] text-muted-foreground hover:text-gold flex items-center gap-1"
        data-testid={`${testId}-copy`}
      >
        <CopyIcon className="w-3 h-3" /> Copy
      </button>
    </div>
    {rows > 1 ? (
      <textarea value={value || ""} onChange={(e) => onChange(e.target.value)} rows={rows}
        className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm" data-testid={testId} />
    ) : (
      <Input value={value || ""} onChange={(e) => onChange(e.target.value)} className="border-navy/20 text-sm" data-testid={testId} />
    )}
    {hint ? <p className="text-[10px] text-muted-foreground mt-0.5">{hint}</p> : null}
  </div>
);

const ReviewStep = ({ getAuthHeader, pack, onRegenerate, onStartOver }) => {
  const [r, setR] = useState(pack.result || {});
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);

  const patch = async (partial) => {
    setSaving(true);
    try {
      const body = {};
      if (partial.caption !== undefined) body.caption = partial.caption;
      if (partial.sms !== undefined) body.sms = partial.sms;
      if (partial.gbp !== undefined) body.gbp = partial.gbp;
      if (partial.hashtags !== undefined) body.hashtags = partial.hashtags;
      if (partial.email_subject !== undefined) body.email_subject = partial.email_subject;
      if (partial.email_body !== undefined) body.email_body = partial.email_body;
      const resp = await axios.patch(`${API}/marketing-pack/${pack.id}`, body, { headers: getAuthHeader() });
      setR(resp.data.result);
      setSavedAt(new Date());
    } catch (e) { /* swallow — keep UI editable */ }
    finally { setSaving(false); }
  };

  // Debounced save on text changes
  const debounceRef = useRef(null);
  const scheduleSave = useCallback((partial) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => patch(partial), 800);
  }, [pack.id]);

  const setField = (key, value) => {
    setR((prev) => {
      const next = { ...prev };
      if (key === "email_subject" || key === "email_body") {
        const k = key === "email_subject" ? "subject" : "body";
        next.email = { ...(prev.email || {}), [k]: value };
      } else if (key === "hashtags_string") {
        next.hashtags = value.split(/[\s,]+/).map((s) => s.replace(/^#/, "").trim()).filter(Boolean);
      } else {
        next[key] = value;
      }
      return next;
    });
    if (key === "hashtags_string") {
      scheduleSave({ hashtags: value.split(/[\s,]+/).map((s) => s.replace(/^#/, "").trim()).filter(Boolean) });
    } else {
      scheduleSave({ [key]: value });
    }
  };

  const imgCards = [
    { key: "ig_post_asset_id", label: fmtLabel.ig_post },
    { key: "ig_story_asset_id", label: fmtLabel.ig_story },
    { key: "fb_post_asset_id", label: fmtLabel.fb_post },
    { key: "hero_asset_id", label: fmtLabel.hero },
  ];

  return (
    <div className="space-y-6" data-testid="promote-step-review">
      <Section title="Your marketing pack is ready" icon={CheckCircle} testId="promote-review-images">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {imgCards.map((c) => r[c.key] ? (
            <div key={c.key} className="rounded-md overflow-hidden border-2 border-navy/10" data-testid={`promote-asset-${c.key}`}>
              <img src={`${API}/media/thumb/${r[c.key]}`} alt={c.label} className="w-full h-36 object-cover" />
              <div className="p-2 bg-cream">
                <p className="text-[10px] font-semibold text-navy">{c.label}</p>
                <a
                  href={`${API}/media/file/${r[c.key]}`}
                  download
                  className="text-[10px] text-gold hover:underline flex items-center gap-1 mt-0.5"
                  data-testid={`promote-download-${c.key}`}
                >
                  <Download className="w-3 h-3" /> Download
                </a>
              </div>
            </div>
          ) : null)}
        </div>

        {r.video_asset_id ? (
          <div className="mt-4">
            <p className="text-xs font-semibold text-navy mb-1.5">15-second promo video</p>
            <video src={`${API}/media/file/${r.video_asset_id}`} controls className="w-full max-w-md rounded-md border-2 border-navy/10" data-testid="promote-video" />
            <a href={`${API}/media/file/${r.video_asset_id}`} download className="text-xs text-gold hover:underline flex items-center gap-1 mt-1" data-testid="promote-download-video">
              <Download className="w-3 h-3" /> Download video
            </a>
          </div>
        ) : null}
      </Section>

      <Section title="Copy — edit anything, we save as you type" icon={Sparkles} testId="promote-review-copy" action={
        <span className="text-[10px] text-muted-foreground" data-testid="promote-save-indicator">
          {saving ? "Saving…" : savedAt ? "Saved ✓" : ""}
        </span>
      }>
        <div className="grid grid-cols-1 gap-3">
          <EditableField label="Caption (Instagram + Facebook)" value={r.caption} onChange={(v) => setField("caption", v)} rows={4} testId="promote-caption" />
          <EditableField label="Hashtags" value={(r.hashtags || []).map((h) => `#${h}`).join(" ")} onChange={(v) => setField("hashtags_string", v)} rows={2} hint="Space- or comma-separated." testId="promote-hashtags" />
          <EditableField label="SMS (under 160 chars)" value={r.sms} onChange={(v) => setField("sms", v)} rows={2} testId="promote-sms" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="md:col-span-1">
              <EditableField label="Email subject" value={(r.email || {}).subject} onChange={(v) => setField("email_subject", v)} testId="promote-email-subject" />
            </div>
            <div className="md:col-span-2">
              <EditableField label="Email body" value={(r.email || {}).body} onChange={(v) => setField("email_body", v)} rows={5} testId="promote-email-body" />
            </div>
          </div>
          <EditableField label="Google Business Profile post" value={r.gbp} onChange={(v) => setField("gbp", v)} rows={4} testId="promote-gbp" />
        </div>
      </Section>

      <div className="flex gap-2 sticky bottom-0 bg-cream/95 backdrop-blur-sm border-t border-navy/10 p-3 -mx-6 -mb-6 px-6">
        <Button variant="outline" onClick={onStartOver} className="border-navy/20" data-testid="promote-start-over">
          Start Over
        </Button>
        <Button variant="outline" onClick={onRegenerate} className="border-navy/20" data-testid="promote-regenerate">
          <RefreshCw className="w-4 h-4 mr-1.5" /> Regenerate
        </Button>
        <div className="flex-1" />
        <Button className="bg-gold text-navy hover:bg-gold/90" data-testid="promote-done" onClick={onStartOver}>
          <CheckCircle className="w-4 h-4 mr-1.5" /> Done
        </Button>
      </div>
    </div>
  );
};


// ---------- Top-level orchestrator -----------------------------------------

const PromoteThisItem = ({ getAuthHeader, mode = "page", initialMenuItem = null, onClose }) => {
  const [step, setStep] = useState(initialMenuItem ? "details" : "pick"); // pick | details | progress | review
  const [asset, setAsset] = useState(null);
  const [menuItem, setMenuItem] = useState(initialMenuItem);
  const [jobId, setJobId] = useState(null);
  const [completedPack, setCompletedPack] = useState(null);
  const [topError, setTopError] = useState(null);

  const onSelected = ({ asset, menuItem }) => {
    setAsset(asset); setMenuItem(menuItem); setStep("details");
  };
  const onGenerated = (jid) => { setJobId(jid); setStep("progress"); };
  const onCompleted = (pack) => { setCompletedPack(pack); setStep("review"); };
  const onFailed = (err) => { setTopError(err); setStep("details"); };
  const startOver = () => {
    if (mode === "modal" && onClose) { onClose(); return; }
    setStep("pick"); setAsset(null); setMenuItem(null); setJobId(null); setCompletedPack(null); setTopError(null);
  };
  const regenerate = async () => {
    if (!completedPack) return;
    try {
      const r = await axios.post(`${API}/marketing-pack/${completedPack.id}/regenerate`, {}, { headers: getAuthHeader() });
      setJobId(r.data.job_id); setStep("progress");
    } catch (e) { setTopError(parseAxiosError(e)); }
  };

  const body = (
    <div className="space-y-6" data-testid="promote-this-item">
      {/* Stepper */}
      <div className="flex items-center gap-1 text-xs text-muted-foreground" data-testid="promote-stepper">
        <span className={step === "pick" ? "text-gold font-semibold" : ""}>1. Pick photo</span>
        <ChevronRight className="w-3 h-3 opacity-50" />
        <span className={step === "details" ? "text-gold font-semibold" : ""}>2. Item details</span>
        <ChevronRight className="w-3 h-3 opacity-50" />
        <span className={step === "progress" ? "text-gold font-semibold" : ""}>3. Generate</span>
        <ChevronRight className="w-3 h-3 opacity-50" />
        <span className={step === "review" ? "text-gold font-semibold" : ""}>4. Review</span>
      </div>

      {topError && step !== "progress" ? (
        <StructuredErrorCard error={topError} testId="promote-top-error" onRetry={() => setTopError(null)} />
      ) : null}

      {step === "pick" && <PickPhotoStep getAuthHeader={getAuthHeader} onSelected={onSelected} />}
      {step === "details" && (
        <ItemDetailsStep getAuthHeader={getAuthHeader} asset={asset} menuItem={menuItem}
          onBack={mode === "modal" && !asset ? (onClose || (() => setStep("pick"))) : () => setStep("pick")} onGenerated={onGenerated} />
      )}
      {step === "progress" && jobId && (
        <ProgressStep getAuthHeader={getAuthHeader} jobId={jobId}
          onCompleted={onCompleted} onFailed={onFailed} onCancel={() => setStep("details")} />
      )}
      {step === "review" && completedPack && (
        <ReviewStep getAuthHeader={getAuthHeader} pack={completedPack}
          onRegenerate={regenerate} onStartOver={startOver} />
      )}
    </div>
  );

  if (mode === "modal") {
    return (
      <div
        className="fixed inset-0 z-50 flex items-start justify-center bg-navy/60 backdrop-blur-sm overflow-y-auto p-4"
        data-testid="promote-modal"
        onClick={(e) => { if (e.target === e.currentTarget && onClose) onClose(); }}
      >
        <div className="bg-cream w-full max-w-3xl rounded-lg shadow-2xl my-8 p-6 relative" onClick={(e) => e.stopPropagation()}>
          {onClose ? (
            <button
              onClick={onClose}
              className="absolute top-3 right-3 w-8 h-8 rounded-full bg-navy/10 hover:bg-navy/20 flex items-center justify-center text-navy"
              data-testid="promote-modal-close"
              aria-label="Close"
            >×</button>
          ) : null}
          {body}
        </div>
      </div>
    );
  }
  return body;
};

export default PromoteThisItem;
