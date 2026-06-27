/**
 * OnboardingGuide — Launch Cleanup Sprint.
 *
 * 3-step "How to promote a menu item" helper card surfaced at the top of
 * Home for new pilot customers. Auto-dismisses once the owner has any
 * saved flyer in their Library, and stays dismissed across reloads via
 * localStorage.
 *
 * Public path it teaches:
 *   1. Pick a menu item   → Menu tab
 *   2. Upload a food photo → Promote tab (Photo → Flyer)
 *   3. Save & download     → Library tab
 */
import React, { useEffect, useState } from "react";
import axios from "axios";
import { ChefHat, Camera, Download, X, Sparkles, CheckCircle2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const DISMISS_KEY = "lakeview.onboarding.dismissed.v1";

const STEPS = [
  {
    n: 1,
    icon: ChefHat,
    title: "Pick a menu item",
    body: "Open the Menu tab and choose the dish you want to promote.",
    cta: "Open Menu",
    target: "menu",
  },
  {
    n: 2,
    icon: Camera,
    title: "Upload a food photo",
    body: "Drop in a photo — our AI builds a flyer + caption automatically.",
    cta: "Open Promote",
    target: "promotions",
  },
  {
    n: 3,
    icon: Download,
    title: "Generate flyer & video",
    body: "Save your favourite flyer, turn it into a 15-second video, and download for social.",
    cta: "Open Library",
    target: "library",
  },
];

const OnboardingGuide = ({ getAuthHeader, onNavigate }) => {
  const [dismissed, setDismissed] = useState(() => {
    try {
      return localStorage.getItem(DISMISS_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [autoHidden, setAutoHidden] = useState(false);
  const [checked, setChecked] = useState(false);

  // Auto-hide once the owner has any saved flyer in the library.
  useEffect(() => {
    if (dismissed) {
      setChecked(true);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/media/assets`, {
          params: { kind: "image", limit: 1 },
          headers: getAuthHeader(),
        });
        const items = r?.data?.assets || r?.data?.items || r?.data || [];
        if (!cancelled && Array.isArray(items) && items.length > 0) {
          setAutoHidden(true);
        }
      } catch {
        /* network errors are fine — keep the guide visible */
      } finally {
        if (!cancelled) setChecked(true);
      }
    })();
    return () => { cancelled = true; };
  }, [dismissed, getAuthHeader]);

  const handleDismiss = () => {
    try { localStorage.setItem(DISMISS_KEY, "1"); } catch { /* ignore */ }
    setDismissed(true);
  };

  // Don't flash on first paint — wait for the library probe to finish.
  if (!checked) return null;
  if (dismissed || autoHidden) return null;

  return (
    <div
      className="ds-card p-5 relative"
      data-testid="onboarding-guide"
    >
      <button
        type="button"
        onClick={handleDismiss}
        className="absolute top-3 right-3 p-1.5 rounded-full hover:bg-navy/5 text-navy/40 hover:text-navy transition-colors"
        aria-label="Dismiss onboarding"
        data-testid="onboarding-dismiss"
      >
        <X className="w-4 h-4" />
      </button>

      <div className="flex items-center gap-2 mb-1">
        <Sparkles className="w-4 h-4 text-gold" />
        <p className="ds-eyebrow">Getting started</p>
      </div>
      <h3 className="ds-display text-lg text-navy mb-1">Promote your first dish in 3 steps</h3>
      <p className="text-xs text-navy/55 mb-4">
        Each step links straight to where you need to go. Skip this guide anytime.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {STEPS.map((s) => {
          const Icon = s.icon;
          return (
            <button
              key={s.n}
              onClick={() => onNavigate && onNavigate(s.target)}
              className="ds-card ds-card-interactive p-3 flex items-start gap-3 text-left"
              data-testid={`onboarding-step-${s.n}`}
            >
              <div className="w-8 h-8 rounded-lg bg-gold/12 flex items-center justify-center text-gold font-semibold text-xs shrink-0" style={{ fontFamily: 'Outfit, system-ui, sans-serif' }}>
                {s.n}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <Icon className="w-3.5 h-3.5 text-navy/55" />
                  <div className="font-semibold text-navy text-sm truncate" data-testid={`onboarding-cta-${s.target}`}>{s.title}</div>
                </div>
                <p className="text-[11px] text-navy/55 mt-0.5">{s.body}</p>
              </div>
            </button>
          );
        })}
      </div>

      <div className="mt-3 flex items-center gap-1.5 text-[10px] text-navy/45">
        <CheckCircle2 className="w-3 h-3 text-gold" />
        <span>Hides automatically once you save your first flyer.</span>
      </div>
    </div>
  );
};

export default OnboardingGuide;
