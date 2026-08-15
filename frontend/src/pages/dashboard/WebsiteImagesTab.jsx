/**
 * WebsiteImagesTab — admin control for the 9 public-site photo slots.
 *
 * Each slot card shows the current image (backend override → falls back to
 * hard-coded default) with three actions:
 *   • Change Photo — asset picker modal (Library grid + Upload New)
 *   • Reset        — clears the override, public site falls back to default
 *
 * Reuses the existing media pipeline (/api/media/upload + /api/media/assets)
 * and the site-image mapping layer (/api/site-images). Never duplicates
 * storage — only maps slot → asset.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Loader2, RotateCcw, ImagePlus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/dashboard/primitives";
import { AssetPicker } from "@/components/dashboard/AssetPicker";
import { SITE_IMAGE_SLOTS, DEFAULT_IMAGES } from "@/config/siteImages";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const absolutize = (url) => {
  if (!url) return url;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  if (url.startsWith("/api/")) return `${process.env.REACT_APP_BACKEND_URL}${url}`;
  return url;
};

// --- Slot Card ---
const SlotCard = ({ slot, currentUrl, isOverride, onChange, onReset, resetting }) => (
  <div className="ds-card overflow-hidden flex flex-col" data-testid={`site-image-slot-${slot.key}`}>
    <div className="relative aspect-[4/3] bg-navy/5 border-b border-navy/8">
      {currentUrl ? (
        <img
          src={currentUrl}
          alt={slot.label}
          loading="lazy"
          className="w-full h-full object-cover"
        />
      ) : (
        <div className="w-full h-full flex items-center justify-center text-navy/30">
          <ImagePlus className="w-8 h-8" />
        </div>
      )}
      {isOverride ? (
        <span className="absolute top-3 left-3 text-[10px] uppercase tracking-wider font-semibold bg-gold text-navy px-2 py-1 rounded-full shadow-sm">
          Custom
        </span>
      ) : (
        <span className="absolute top-3 left-3 text-[10px] uppercase tracking-wider font-semibold bg-cream text-navy/60 px-2 py-1 rounded-full border border-navy/10">
          Default
        </span>
      )}
    </div>
    <div className="p-4 flex-1 flex flex-col">
      <div className="flex-1">
        <p className="font-semibold text-navy" style={{ fontFamily: "Oswald, sans-serif", letterSpacing: "0.02em" }}>
          {slot.label}
        </p>
        <p className="text-xs text-navy/55 mt-1">{slot.sub}</p>
        <p className="text-[11px] text-navy/40 mt-2">Recommended: {slot.ratio}</p>
      </div>
      <div className="flex items-center gap-2 mt-4 pt-3 border-t border-gold/25">
        <Button
          size="sm"
          onClick={() => onChange(slot.key)}
          className="flex-1 bg-navy text-cream hover:bg-navy/90"
          data-testid={`site-image-change-${slot.key}`}
        >
          Change Photo
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onReset(slot.key)}
          disabled={!isOverride || resetting}
          title={isOverride ? "Restore the original default photo" : "Already using the default photo"}
          className="text-navy/60 hover:text-navy hover:bg-navy/5 disabled:opacity-30"
          data-testid={`site-image-reset-${slot.key}`}
        >
          {resetting ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
        </Button>
      </div>
    </div>
  </div>
);

// --- Main Tab ---
const WebsiteImagesTab = ({ getAuthHeader }) => {
  const [overrides, setOverrides] = useState({}); // slot → resolved URL from API
  const [loading, setLoading] = useState(true);
  const [pickerFor, setPickerFor] = useState(null);
  const [resetting, setResetting] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/site-images`);
      setOverrides(r.data?.slots || {});
    } catch (e) {
      toast.error("Could not load website images.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const assignSlot = async (assetId) => {
    if (!pickerFor) return;
    try {
      await axios.put(
        `${API}/site-images/${pickerFor}`,
        { asset_id: assetId },
        { headers: getAuthHeader() },
      );
      toast.success("Photo updated on your public site.");
      await refresh();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not update photo.");
      throw e;
    }
  };

  const resetSlot = async (slot) => {
    setResetting(slot);
    try {
      await axios.post(
        `${API}/site-images/${slot}/reset`,
        {},
        { headers: getAuthHeader() },
      );
      toast.success("Restored to the default photo.");
      await refresh();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not reset photo.");
    } finally {
      setResetting(null);
    }
  };

  // The Website Images grid always shows *something* — either the override
  // resolved by the API, or the shared DEFAULT_IMAGES fallback (kept in
  // `frontend/src/config/siteImages.js` so both this tab and the public
  // site read the same source of truth).
  const cards = useMemo(() => SITE_IMAGE_SLOTS, []);

  return (
    <div>
      <PageHeader
        eyebrow="Website"
        title="Website Images"
        subtitle="Change any photo shown on your public site. Custom photos replace the built-in ones — reset any time to restore the original."
        testId="website-images-header"
      />

      {loading ? (
        <div className="py-16 text-center text-navy/50">
          <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> Loading photos…
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="website-images-grid">
          {cards.map((slot) => {
            const overrideUrl = overrides[slot.key];
            const isOverride = Boolean(overrideUrl);
            const previewUrl = overrideUrl
              ? absolutize(overrideUrl)
              : DEFAULT_IMAGES[slot.key];
            return (
              <SlotCard
                key={slot.key}
                slot={slot}
                currentUrl={previewUrl}
                isOverride={isOverride}
                onChange={setPickerFor}
                onReset={resetSlot}
                resetting={resetting === slot.key}
              />
            );
          })}
        </div>
      )}

      {/* When we don't have an override URL, the card shows a "Default" placeholder
          instead of loading the default photo — this keeps the dashboard fast and
          lets admins see at a glance which slots they've customized. */}

      <AssetPicker
        open={Boolean(pickerFor)}
        onClose={() => setPickerFor(null)}
        getAuthHeader={getAuthHeader}
        title={pickerFor ? `Change photo · ${SITE_IMAGE_SLOTS.find((s) => s.key === pickerFor)?.label || pickerFor}` : "Change photo"}
        mode="single"
        onAssign={assignSlot}
      />
    </div>
  );
};

export default WebsiteImagesTab;
