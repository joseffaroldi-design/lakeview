/**
 * AssetPicker — shared modal for selecting/uploading Library images.
 *
 * Extracted from Sprint (Website Images) so it can be reused across the
 * dashboard (Website Images, Menu item photo galleries, etc.).
 *
 * Modes:
 *   - `single`   : one asset can be selected; onAssign is called with a
 *                  single asset_id.
 *   - `multiple` : any number of assets can be selected; onAssign is called
 *                  with an array of asset_ids. Uploading multiple files at
 *                  once is also supported in this mode.
 *
 * Uses the existing /api/media/upload + /api/media/assets endpoints — never
 * duplicates storage.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { Loader2, Upload, Check } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const AssetPicker = ({
  open,
  onClose,
  getAuthHeader,
  onAssign,
  title = "Change photo",
  subtitle = "Pick a photo already in your Library, or upload a new one.",
  mode = "single",       // "single" | "multiple"
  disabledIds = [],      // ids that appear greyed out and can't be selected
}) => {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const fileRef = useRef(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/media/assets?limit=200&kind=image`, { headers: getAuthHeader() });
      setAssets(r.data?.assets || []);
    } catch (e) {
      toast.error("Could not load Library assets.");
    } finally {
      setLoading(false);
    }
  }, [getAuthHeader]);

  useEffect(() => {
    if (open) {
      setSelectedIds([]);
      refresh();
    }
  }, [open, refresh]);

  const handleUpload = async (files) => {
    const list = Array.from(files || []);
    if (list.length === 0) return;
    setUploading(true);
    const newlyUploaded = [];
    try {
      // Upload sequentially so we don't hammer the storage layer if the
      // owner drops in 20 files at once; toast progress lets them see it
      // moving. Failures on individual files are surfaced but don't halt.
      for (const f of list) {
        try {
          const fd = new FormData();
          fd.append("file", f);
          fd.append("folder", "Custom");
          const r = await axios.post(`${API}/media/upload`, fd, { headers: getAuthHeader() });
          if (r.data?.id) newlyUploaded.push(r.data.id);
        } catch (_) {
          toast.error(`Upload failed: ${f.name}`);
        }
      }
      if (newlyUploaded.length) toast.success(`Uploaded ${newlyUploaded.length} photo${newlyUploaded.length === 1 ? "" : "s"}.`);
      await refresh();
      // Auto-select the newly uploaded assets so the admin can confirm.
      setSelectedIds(mode === "single" ? newlyUploaded.slice(0, 1) : newlyUploaded);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const toggle = (id) => {
    if (disabledIds.includes(id)) return;
    setSelectedIds((prev) => {
      if (mode === "single") return prev[0] === id ? [] : [id];
      return prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
    });
  };

  const handleAssign = async () => {
    if (selectedIds.length === 0) return;
    setAssigning(true);
    try {
      if (mode === "single") await onAssign(selectedIds[0]);
      else await onAssign(selectedIds);
      onClose();
    } finally {
      setAssigning(false);
    }
  };

  const count = selectedIds.length;
  const cta = mode === "single"
    ? "Use this photo"
    : count === 0 ? "Add photos" : `Add ${count} photo${count === 1 ? "" : "s"}`;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-4xl bg-cream border-navy/10 p-0 overflow-hidden">
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-navy/8 bg-cream">
          <DialogTitle className="ds-display text-2xl text-navy">{title}</DialogTitle>
          <p className="text-sm text-navy/60 mt-1">{subtitle}</p>
        </DialogHeader>

        <div className="px-6 py-5 max-h-[60vh] overflow-y-auto bg-cream">
          <div className="mb-5">
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              multiple={mode === "multiple"}
              className="hidden"
              data-testid="asset-picker-upload-input"
              onChange={(e) => handleUpload(e.target.files)}
            />
            <Button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="bg-navy text-cream hover:bg-navy/90"
              data-testid="asset-picker-upload-btn"
            >
              {uploading
                ? (<><Loader2 className="w-4 h-4 mr-2 animate-spin" />Uploading…</>)
                : (<><Upload className="w-4 h-4 mr-2" />{mode === "multiple" ? "Upload New Photos" : "Upload New Photo"}</>)}
            </Button>
            <span className="text-xs text-navy/50 ml-3">
              JPG, PNG or WEBP · up to 20 MB{mode === "multiple" ? " each · select multiple files" : ""}
            </span>
          </div>

          <div className="border-t border-navy/10 pt-5">
            <div className="flex items-baseline justify-between mb-3">
              <p className="ds-eyebrow">From your Library</p>
              <p className="text-xs text-navy/45">
                {assets.length} photo{assets.length === 1 ? "" : "s"}
                {mode === "multiple" && count > 0 ? ` · ${count} selected` : ""}
              </p>
            </div>
            {loading ? (
              <div className="py-14 flex items-center justify-center text-navy/50">
                <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading Library…
              </div>
            ) : assets.length === 0 ? (
              <div className="py-14 text-center text-sm text-navy/50 border-2 border-dashed border-navy/12 rounded-xl">
                Your Library is empty. Upload {mode === "multiple" ? "photos" : "a photo"} above to get started.
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3" data-testid="asset-picker-grid">
                {assets.map((a) => {
                  const url = `${process.env.REACT_APP_BACKEND_URL}/api/media/file/${a.id}`;
                  const active = selectedIds.includes(a.id);
                  const disabled = disabledIds.includes(a.id);
                  return (
                    <button
                      key={a.id}
                      type="button"
                      onClick={() => toggle(a.id)}
                      disabled={disabled}
                      data-testid={`asset-picker-thumb-${a.id}`}
                      className={`relative aspect-square rounded-xl overflow-hidden border-2 transition-all ${disabled ? "opacity-40 cursor-not-allowed" : ""} ${active ? "border-gold ring-2 ring-gold/40" : "border-transparent hover:border-navy/20"}`}
                    >
                      <img src={url} alt={a.filename || ""} loading="lazy" className="w-full h-full object-cover" />
                      {active ? (
                        <span className="absolute top-2 right-2 w-6 h-6 rounded-full bg-gold text-navy flex items-center justify-center shadow">
                          <Check className="w-3.5 h-3.5" />
                        </span>
                      ) : null}
                      {disabled ? (
                        <span className="absolute bottom-2 left-2 text-[10px] uppercase tracking-wider font-semibold bg-navy/80 text-cream px-2 py-0.5 rounded-full">
                          Already added
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="px-6 py-4 border-t border-navy/8 bg-cream flex items-center justify-between gap-3">
          <Button
            variant="ghost"
            onClick={onClose}
            className="text-navy/60 hover:text-navy hover:bg-navy/5"
            data-testid="asset-picker-cancel"
          >
            Cancel
          </Button>
          <Button
            onClick={handleAssign}
            disabled={count === 0 || assigning}
            className="bg-gold text-navy hover:bg-gold/90 disabled:opacity-50"
            data-testid="asset-picker-assign"
          >
            {assigning
              ? (<><Loader2 className="w-4 h-4 mr-2 animate-spin" />Applying…</>)
              : (<><Check className="w-4 h-4 mr-2" />{cta}</>)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AssetPicker;
