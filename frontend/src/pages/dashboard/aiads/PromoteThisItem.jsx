/**
 * Promote This Item — Marketing Pack 3.0 (video-only, Sprint 16B.4).
 *
 * Flow: pick photo → tweak item → generate (background job + 3-sec polling) →
 * download the 15-second promo video.
 *
 * Caption / SMS / email / GBP / hashtag copy moved to AI Designer's
 * copy_pack — open any AI Designer job and use the "Copy" panel. This
 * surface now exists ONLY to produce the unique 15-second video.
 */
import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import {
  Sparkles, Upload, Image as ImageIcon, Loader2, Download,
  RefreshCw, CheckCircle, ChevronRight, ArrowLeft, Video,
} from "lucide-react";
import { API, Section } from "./shared";
import StructuredErrorCard, { parseAxiosError } from "./StructuredErrorCard";

const POLL_MS = 3000;
const POLL_TIMEOUT_MS = 4 * 60 * 1000;


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
        headers: { ...getAuthHeader() },
        timeout: 60000,
      });
      onSelected({ asset: r.data, menuItem: null });
    } catch (e2) {
      setError(parseAxiosError(e2));
    } finally {
      setUploading(false);
    }
  };

  const pickLibrary = (a) => onSelected({ asset: a, menuItem: null });
  const pickSuggestion = (s) => onSelected({ asset: s.last_used_asset || null, menuItem: s });

  return (
    <div className="space-y-4" data-testid="promote-step-pick">
      <Section title="Pick a photo" icon={ImageIcon} testId="promote-pick-photo">
        <div className="flex gap-2 flex-wrap">
          <Button onClick={() => fileRef.current && fileRef.current.click()} disabled={uploading}
            className="bg-gold text-navy hover:bg-gold/90" data-testid="promote-upload-btn">
            {uploading ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Upload className="w-4 h-4 mr-1.5" />}
            {uploading ? "Uploading…" : "Upload photo"}
          </Button>
          <input ref={fileRef} type="file" accept="image/*" onChange={handleUpload}
            className="hidden" data-testid="promote-upload-input" />
          <Button variant="outline" onClick={loadLibrary} className="border-navy/20" data-testid="promote-pick-library">
            <ImageIcon className="w-4 h-4 mr-1.5" /> Pick from library
          </Button>
        </div>
        {error ? <StructuredErrorCard error={error} testId="promote-pick-error" onRetry={() => setError(null)} /> : null}
      </Section>

      {suggestions.length > 0 ? (
        <Section title="Suggestions — items you haven't promoted lately" icon={Sparkles} testId="promote-suggestions">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {suggestions.map((s) => (
              <button key={s.item_key} type="button" onClick={() => pickSuggestion(s)}
                className="text-left p-3 border border-navy/15 rounded-md hover:border-gold transition-colors"
                data-testid={`promote-suggestion-${s.item_key}`}>
                <p className="text-sm font-semibold text-navy">{s.name}</p>
                <p className="text-[10px] text-muted-foreground capitalize">{s.category}</p>
                {s.last_promoted_at ? (
                  <p className="text-[10px] text-muted-foreground">
                    last promoted: {new Date(s.last_promoted_at).toLocaleDateString()}
                  </p>
                ) : (
                  <p className="text-[10px] text-gold font-semibold">never promoted</p>
                )}
              </button>
            ))}
          </div>
        </Section>
      ) : null}

      {showLibrary && libraryAssets.length > 0 ? (
        <Section title="Pick from library" testId="promote-library">
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 max-h-96 overflow-y-auto">
            {libraryAssets.map((a) => (
              <button key={a.id} type="button" onClick={() => pickLibrary(a)}
                className="aspect-square overflow-hidden border-2 border-transparent hover:border-gold rounded-sm"
                data-testid={`promote-library-${a.id}`}>
                <img src={`${API}/media/thumb/${a.id}`} alt={a.filename} className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        </Section>
      ) : null}
    </div>
  );
};


// ---------- Step 2: Item details -------------------------------------------

const ItemDetailsStep = ({ getAuthHeader, asset, menuItem, onBack, onGenerated }) => {
  const [name, setName] = useState(menuItem?.name || "");
  const [description, setDescription] = useState(menuItem?.description || "");
  const [price, setPrice] = useState(menuItem?.price || "");
  const [headline, setHeadline] = useState("");
  const [cta, setCta] = useState("Order Now");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const submit = async () => {
    setSubmitting(true); setError(null);
    try {
      const r = await axios.post(`${API}/marketing-pack/generate`, {
        source_asset_id: asset.id,
        menu_item_key: menuItem?.item_key || null,
        name: name || null, description: description || null,
        price: price || null, headline: headline || null, cta: cta || null,
      }, { headers: getAuthHeader(), timeout: 30000 });
      onGenerated(r.data.job_id);
    } catch (e) {
      setError(parseAxiosError(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="promote-step-details">
      <Section title="Make a 15-second promo video" icon={Video} testId="promote-details">
        <div className="grid grid-cols-1 sm:grid-cols-[180px,1fr] gap-4">
          {asset ? (
            <img src={`${API}/media/thumb/${asset.id}`} alt={asset.filename}
              className="w-full h-44 object-cover rounded-md border-2 border-navy/10" />
          ) : (
            <div className="w-full h-44 bg-navy/5 rounded-md flex items-center justify-center text-xs text-muted-foreground">
              No photo selected
            </div>
          )}
          <div className="space-y-2">
            <div>
              <label className="text-xs font-semibold text-navy">Item name</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="(we'll infer one if blank)"
                className="border-navy/20" data-testid="promote-name" />
            </div>
            <div>
              <label className="text-xs font-semibold text-navy">Description</label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="(we'll infer one if blank)"
                className="border-navy/20" data-testid="promote-description" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold text-navy">Price</label>
                <Input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="$14"
                  className="border-navy/20" data-testid="promote-price" />
              </div>
              <div>
                <label className="text-xs font-semibold text-navy">CTA</label>
                <Input value={cta} onChange={(e) => setCta(e.target.value)} placeholder="Order Now"
                  className="border-navy/20" data-testid="promote-cta" />
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold text-navy">Headline (optional)</label>
              <Input value={headline} onChange={(e) => setHeadline(e.target.value)} placeholder="Weekend Special"
                className="border-navy/20" data-testid="promote-headline" />
            </div>
          </div>
        </div>
        {error ? <StructuredErrorCard error={error} testId="promote-details-error" onRetry={() => setError(null)} /> : null}
      </Section>

      <div className="flex gap-2">
        <Button variant="outline" onClick={onBack} className="border-navy/20" data-testid="promote-details-back">
          <ArrowLeft className="w-4 h-4 mr-1.5" /> Back
        </Button>
        <div className="flex-1" />
        <Button onClick={submit} disabled={submitting || !asset}
          className="bg-gold text-navy hover:bg-gold/90" data-testid="promote-generate">
          {submitting ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1.5" />}
          Make the video
        </Button>
      </div>
    </div>
  );
};


// ---------- Step 3: Progress ----------------------------------------------

const ProgressStep = ({ getAuthHeader, jobId, onCompleted, onFailed, onCancel }) => {
  const [progress, setProgress] = useState(5);
  const [currentStep, setCurrentStep] = useState("queued");
  const startedAt = useRef(Date.now());

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      if (Date.now() - startedAt.current > POLL_TIMEOUT_MS) {
        onFailed({ user_message: "Took too long — try again with a smaller photo.", code: "timeout" });
        return;
      }
      try {
        const r = await axios.get(`${API}/marketing-pack/job/${jobId}`, { headers: getAuthHeader(), timeout: 15000 });
        const job = r.data;
        setProgress(job.progress || 0);
        setCurrentStep(job.current_step || job.status);
        if (job.status === "completed") {
          onCompleted(job);
          return;
        }
        if (job.status === "failed") {
          onFailed(job.error || { user_message: "Something went wrong." });
          return;
        }
        setTimeout(tick, POLL_MS);
      } catch (e) {
        setTimeout(tick, POLL_MS * 2);
      }
    };
    tick();
    return () => { cancelled = true; };
  }, [jobId, getAuthHeader, onCompleted, onFailed]);

  const STEP_LABEL = {
    queued: "Queued…",
    pending: "Queued…",
    inferring: "Reading the menu item…",
    rendering_images: "Cropping the photo for the video…",
    rendering_video: "Rendering the 15-second video…",
    saving: "Finishing up…",
    done: "Done!",
    processing: "Working…",
  };

  return (
    <div className="space-y-4" data-testid="promote-step-progress">
      <Section title="Making your video" icon={Loader2} testId="promote-progress">
        <div className="space-y-3">
          <div className="h-2 bg-navy/10 rounded-full overflow-hidden">
            <div className="h-full bg-gold transition-all duration-500" style={{ width: `${progress}%` }} data-testid="promote-progress-bar" />
          </div>
          <p className="text-sm text-navy" data-testid="promote-progress-step">{STEP_LABEL[currentStep] || currentStep}</p>
          <p className="text-[10px] text-muted-foreground">This takes about 30–60 seconds.</p>
          <Button variant="outline" onClick={onCancel} className="border-navy/20 text-xs" data-testid="promote-cancel">
            Cancel
          </Button>
        </div>
      </Section>
    </div>
  );
};


// ---------- Step 4: Review (video only) -----------------------------------

const ReviewStep = ({ pack, onRegenerate, onStartOver }) => {
  const r = pack.result || {};
  const videoUrl = r.video_asset_id ? `${API}/media/file/${r.video_asset_id}` : null;

  return (
    <div className="space-y-6" data-testid="promote-step-review">
      <Section title="Your 15-second promo video is ready" icon={CheckCircle} testId="promote-review-video">
        {videoUrl ? (
          <div className="space-y-3">
            <video
              src={videoUrl}
              controls
              className="w-full max-w-md rounded-md border-2 border-navy/10"
              data-testid="promote-video"
            />
            <a href={videoUrl} download
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-gold hover:underline"
              data-testid="promote-download-video">
              <Download className="w-4 h-4" /> Download video
            </a>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground" data-testid="promote-no-video">
            Video rendering was skipped or failed. Try regenerating, or open AI Designer for static graphics + copy.
          </p>
        )}
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
        <span className={step === "review" ? "text-gold font-semibold" : ""}>4. Download</span>
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
        <ReviewStep pack={completedPack}
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
