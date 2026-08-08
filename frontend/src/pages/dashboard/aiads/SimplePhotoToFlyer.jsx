import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { ArrowLeft, CheckCircle, Copy, Download, Image as ImageIcon, Loader2, RefreshCw, Sparkles, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const PREFILL_KEY = "lakeview.photo_flyer.prefill";
const REMIX_KEY = "lakeview.photo_flyer.remix";
const POLL_MS = 1200;

const DEFAULT_TEMPLATES = [
  { id: "luxury", name: "Luxury" },
  { id: "luxury_dark", name: "Luxury Dark" },
  { id: "cajun", name: "Cajun" },
  { id: "cajun_blackened", name: "Blackened Cajun" },
  { id: "seafood", name: "Seafood" },
  { id: "seafood_coastal", name: "Coastal Seafood" },
  { id: "seafood_lagoon", name: "Seafood Lagoon" },
];

const readSessionJson = (key) => {
  try { const raw = sessionStorage.getItem(key); return raw ? JSON.parse(raw) : null; }
  catch { return null; }
};

const LibraryPicker = ({ getAuthHeader, selected, onSelect }) => {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    axios.get(`${API}/media/assets?kind=image&limit=200`, { headers: getAuthHeader() })
      .then(r => {
        if (cancelled) return;
        setAssets((r.data.assets || []).filter(a => {
          const tags = a.tags || [];
          const source = a.source || "";
          return !tags.includes("flyer") && !tags.includes("logo")
            && source !== "logo" && source !== "marketing_template" && !source.startsWith("ai_designer");
        }));
      })
      .catch(() => { if (!cancelled) setAssets([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [getAuthHeader]);

  if (loading) return <div className="py-8 text-center text-sm text-navy/50"><Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />Loading photos…</div>;
  if (!assets.length) return <div className="py-8 text-center text-sm text-navy/50 border border-dashed border-navy/20 rounded-lg">No reusable food photos yet.</div>;

  return <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 max-h-72 overflow-y-auto">
    {assets.map(a => <button key={a.id} onClick={() => onSelect(a)} type="button"
      className={`relative aspect-square overflow-hidden rounded-md border-2 ${selected?.id === a.id ? "border-gold" : "border-navy/10"}`}>
      <img src={`${API}/media/thumb/${a.id}`} alt={a.filename || "food"} className="w-full h-full object-cover" />
      {selected?.id === a.id ? <CheckCircle className="absolute top-1 right-1 w-5 h-5 text-gold bg-white rounded-full" /> : null}
    </button>)}
  </div>;
};

const SimplePhotoToFlyer = ({ getAuthHeader }) => {
  const prefill = useMemo(() => readSessionJson(PREFILL_KEY), []);
  const remix = useMemo(() => readSessionJson(REMIX_KEY), []);
  const [step, setStep] = useState(remix?.source_asset_id ? "edit" : "source");
  const [sourceMode, setSourceMode] = useState("upload");
  const [file, setFile] = useState(null);
  const [libraryAsset, setLibraryAsset] = useState(null);
  const [analysis, setAnalysis] = useState(remix?.source_asset_id ? {
    enhanced_asset_id: remix.source_asset_id,
    food_type: remix.food_type || remix.menu_item?.name || "",
    features: remix.features || [],
    menu_match: { matched: false },
  } : null);
  const [templates, setTemplates] = useState(DEFAULT_TEMPLATES);
  const [name, setName] = useState(remix?.menu_item?.name || prefill?.name || "");
  const [features, setFeatures] = useState((remix?.features || prefill?.features || []).join(", "));
  const [price, setPrice] = useState(remix?.menu_item?.price || prefill?.price || "");
  const [templateId, setTemplateId] = useState(remix?.theme || "luxury");
  const [platform, setPlatform] = useState("instagram_square");
  const [cta, setCta] = useState("Order Now");
  const [variations, setVariations] = useState(1);
  const [job, setJob] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (prefill) sessionStorage.removeItem(PREFILL_KEY);
    if (remix) sessionStorage.removeItem(REMIX_KEY);
  }, [prefill, remix]);

  useEffect(() => {
    axios.get(`${API}/marketing/flyers/templates`, { headers: getAuthHeader() })
      .then(r => setTemplates(r.data.templates || DEFAULT_TEMPLATES)).catch(() => {});
  }, [getAuthHeader]);

  const analyze = async () => {
    setBusy(true); setError("");
    try {
      let r;
      if (sourceMode === "upload") {
        if (!file) throw new Error("Choose a photo first.");
        const fd = new FormData(); fd.append("file", file); fd.append("folder", "Custom");
        r = await axios.post(`${API}/photo-flyer/analyze`, fd, { headers: getAuthHeader(), timeout: 90000 });
      } else {
        if (!libraryAsset) throw new Error("Choose a library photo first.");
        r = await axios.post(`${API}/photo-flyer/analyze-existing`, { asset_id: libraryAsset.id }, { headers: getAuthHeader(), timeout: 60000 });
      }
      const a = r.data; setAnalysis(a);
      const match = a.menu_match || {};
      if (!name) setName(prefill?.name || (match.matched && match.name) || a.food_type || "Featured Dish");
      if (!features) setFeatures((prefill?.features || a.features || []).join(", "));
      if (!price) setPrice(prefill?.price || (match.matched && match.price) || "");
      setStep("edit");
    } catch (e) { setError(e.response?.data?.detail || e.message || "Could not analyze photo."); }
    finally { setBusy(false); }
  };

  const generate = async () => {
    setBusy(true); setError("");
    try {
      const r = await axios.post(`${API}/marketing/flyers/generate`, {
        source_asset_id: analysis.enhanced_asset_id,
        item_name: name.trim() || "Featured Dish",
        features: features.split(",").map(x => x.trim()).filter(Boolean),
        price: price || null,
        template_id: templateId,
        platform,
        cta: cta || null,
        variations,
      }, { headers: getAuthHeader(), timeout: 30000 });
      setJobId(r.data.job_id); setStep("generating");
    } catch (e) { setError(e.response?.data?.detail || "Could not start flyer render."); }
    finally { setBusy(false); }
  };

  useEffect(() => {
    if (step !== "generating" || !jobId) return;
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        const r = await axios.get(`${API}/marketing/flyers/job/${jobId}`, { headers: getAuthHeader(), timeout: 15000 });
        if (r.data.status === "completed") { setJob(r.data); setStep("done"); return; }
        if (r.data.status === "failed") { setError(r.data.error?.user_message || "Render failed."); setStep("edit"); return; }
      } catch { /* transient poll failure */ }
      setTimeout(poll, POLL_MS);
    };
    poll(); return () => { cancelled = true; };
  }, [step, jobId, getAuthHeader]);

  const restart = () => {
    setStep("source"); setAnalysis(null); setFile(null); setLibraryAsset(null); setJob(null); setJobId(null); setError("");
  };

  return <div className="space-y-6" data-testid="simple-photo-flyer">
    {error ? <div className="p-3 rounded-md bg-red-50 border border-red-200 text-sm text-red-800">{error}</div> : null}

    {step === "source" ? <section className="bg-white border border-navy/10 rounded-lg p-5 space-y-5">
      <div><p className="text-xs uppercase tracking-wider text-gold font-semibold">Step 1</p><h3 className="font-serif text-2xl text-navy">Choose a food photo</h3></div>
      <div className="flex gap-2">
        <Button variant={sourceMode === "upload" ? "default" : "outline"} onClick={() => setSourceMode("upload")}><Upload className="w-4 h-4 mr-2" />Upload</Button>
        <Button variant={sourceMode === "library" ? "default" : "outline"} onClick={() => setSourceMode("library")}><ImageIcon className="w-4 h-4 mr-2" />Library</Button>
      </div>
      {sourceMode === "upload" ? <label className="block border-2 border-dashed border-navy/20 rounded-lg p-8 text-center cursor-pointer hover:border-gold/60">
        <Upload className="w-8 h-8 text-gold mx-auto mb-2" /><span className="text-sm font-semibold text-navy">{file ? file.name : "Choose a food photo"}</span>
        <input type="file" accept="image/*" className="hidden" onChange={e => setFile(e.target.files?.[0] || null)} />
      </label> : <LibraryPicker getAuthHeader={getAuthHeader} selected={libraryAsset} onSelect={setLibraryAsset} />}
      <Button onClick={analyze} disabled={busy || (sourceMode === "upload" ? !file : !libraryAsset)} className="bg-gold text-navy hover:bg-gold/90">
        {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}Continue
      </Button>
    </section> : null}

    {step === "edit" ? <section className="bg-white border border-navy/10 rounded-lg p-5 space-y-5">
      <div><p className="text-xs uppercase tracking-wider text-gold font-semibold">Step 2</p><h3 className="font-serif text-2xl text-navy">Build the flyer</h3><p className="text-sm text-navy/60 mt-1">Edit exactly what should appear, then choose a template and size.</p></div>
      <div className="grid md:grid-cols-2 gap-4">
        <label className="space-y-1"><span className="text-xs font-semibold text-navy">Item name</span><Input value={name} onChange={e => setName(e.target.value)} /></label>
        <label className="space-y-1"><span className="text-xs font-semibold text-navy">Price</span><Input value={price} onChange={e => setPrice(e.target.value)} placeholder="$12.95" /></label>
        <label className="md:col-span-2 space-y-1"><span className="text-xs font-semibold text-navy">Features (comma separated)</span><Input value={features} onChange={e => setFeatures(e.target.value)} /></label>
        <label className="space-y-1"><span className="text-xs font-semibold text-navy">Template</span><select value={templateId} onChange={e => setTemplateId(e.target.value)} className="w-full border border-navy/20 rounded-md px-3 py-2 text-sm bg-white">{templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
        <label className="space-y-1"><span className="text-xs font-semibold text-navy">Size</span><select value={platform} onChange={e => setPlatform(e.target.value)} className="w-full border border-navy/20 rounded-md px-3 py-2 text-sm bg-white"><option value="instagram_square">Instagram Square</option><option value="facebook_post">Facebook Post</option><option value="instagram_story">Story</option></select></label>
        <label className="space-y-1"><span className="text-xs font-semibold text-navy">Call to action</span><Input value={cta} onChange={e => setCta(e.target.value)} /></label>
        <label className="space-y-1"><span className="text-xs font-semibold text-navy">Designs</span><select value={variations} onChange={e => setVariations(Number(e.target.value))} className="w-full border border-navy/20 rounded-md px-3 py-2 text-sm bg-white"><option value={1}>1</option><option value={2}>2</option><option value={3}>3</option></select></label>
      </div>
      <div className="flex gap-2"><Button variant="outline" onClick={() => setStep("source")}><ArrowLeft className="w-4 h-4 mr-2" />Back</Button><Button onClick={generate} disabled={busy} className="bg-gold text-navy hover:bg-gold/90"><Sparkles className="w-4 h-4 mr-2" />Render flyer</Button></div>
    </section> : null}

    {step === "generating" ? <section className="bg-white border border-navy/10 rounded-lg p-8 text-center"><Loader2 className="w-8 h-8 text-gold animate-spin mx-auto mb-3" /><h3 className="font-serif text-2xl text-navy">Rendering your flyer</h3><p className="text-sm text-navy/60">Using the selected template—no design agent or hidden theme logic.</p></section> : null}

    {step === "done" && job ? <section className="bg-white border border-navy/10 rounded-lg p-5 space-y-5">
      <div><p className="text-xs uppercase tracking-wider text-gold font-semibold">Done</p><h3 className="font-serif text-2xl text-navy">Your flyer is ready</h3></div>
      <div className="grid md:grid-cols-3 gap-4">{(job.variations || []).map(v => <div key={v.asset_id} className="space-y-2"><img src={`${API}/media/file/${v.asset_id}`} alt="flyer" className="w-full rounded-lg border border-navy/10" /><a href={`${API}/media/file/${v.asset_id}`} download className="inline-flex items-center gap-2 text-sm font-semibold text-gold"><Download className="w-4 h-4" />Download</a></div>)}</div>
      {job.copy_pack ? <div className="grid md:grid-cols-2 gap-3">{[["Facebook", job.copy_pack.fb_post],["Instagram",job.copy_pack.ig_post]].map(([label,text]) => text ? <div key={label} className="border border-navy/10 rounded-lg p-4"><div className="flex justify-between mb-2"><strong className="text-sm text-navy">{label}</strong><button className="text-xs text-gold inline-flex gap-1" onClick={() => navigator.clipboard?.writeText(text)}><Copy className="w-3 h-3" />Copy</button></div><p className="text-sm text-navy/70 whitespace-pre-wrap">{text}</p></div> : null)}</div> : null}
      <div className="flex gap-2"><Button variant="outline" onClick={() => setStep("edit")}><RefreshCw className="w-4 h-4 mr-2" />Change template</Button><Button onClick={restart} className="bg-gold text-navy hover:bg-gold/90">New photo</Button></div>
    </section> : null}
  </div>;
};

export default SimplePhotoToFlyer;
