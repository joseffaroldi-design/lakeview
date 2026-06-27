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
import { Button } from "@/components/ui/button";

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
      className="mb-6 rounded-xl border-2 border-gold/40 bg-gradient-to-br from-gold/10 via-cream to-cream p-5 relative"
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
        <Sparkles className="w-5 h-5 text-gold" />
        <h3 className="font-serif text-lg font-bold text-navy">
          Welcome — promote your first item in 3 steps
        </h3>
      </div>
      <p className="text-xs text-navy/60 mb-4">
        Each step links straight to where you need to go. Skip this guide anytime.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {STEPS.map((s) => {
          const Icon = s.icon;
          return (
            <div
              key={s.n}
              className="bg-white border border-navy/10 rounded-lg p-4 flex flex-col gap-2 hover:border-gold/40 hover:shadow-sm transition"
              data-testid={`onboarding-step-${s.n}`}
            >
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-full bg-gold/15 flex items-center justify-center text-gold font-bold text-sm">
                  {s.n}
                </div>
                <Icon className="w-4 h-4 text-navy/70" />
                <div className="font-semibold text-navy text-sm">{s.title}</div>
              </div>
              <p className="text-xs text-navy/60 flex-1">{s.body}</p>
              <Button
                size="sm"
                className="bg-navy text-cream hover:bg-navy/90 h-8 text-xs mt-1"
                onClick={() => onNavigate && onNavigate(s.target)}
                data-testid={`onboarding-cta-${s.target}`}
              >
                {s.cta}
              </Button>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex items-center justify-between text-[11px] text-navy/50">
        <span className="inline-flex items-center gap-1">
          <CheckCircle2 className="w-3.5 h-3.5 text-gold" />
          This guide hides automatically once you save your first flyer.
        </span>
      </div>
    </div>
  );
};

export default OnboardingGuide;
