import React, { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { X, Share, Plus, Download } from "lucide-react";

const LOGO = "https://customer-assets.emergentagent.com/job_703dcc6a-aa7a-4633-a18d-a8d37a8eb209/artifacts/y3vh8170_5D695FC6-4513-41E6-8C85-02DA2EA2EF08.png";
const DISMISS_KEY = "lv_pwa_prompt_dismissed_at";
const DISMISS_DAYS = 7;
const ENGAGEMENT_MS = 30000;
const SCROLL_THRESHOLD = 0.6;

const isStandalone = () =>
  window.matchMedia?.("(display-mode: standalone)").matches ||
  window.navigator.standalone === true;

const isIOS = () => /iphone|ipad|ipod/i.test(window.navigator.userAgent);

const wasRecentlyDismissed = () => {
  const ts = localStorage.getItem(DISMISS_KEY);
  if (!ts) return false;
  const ageDays = (Date.now() - parseInt(ts, 10)) / (1000 * 60 * 60 * 24);
  return ageDays < DISMISS_DAYS;
};

export const InstallPrompt = ({ onTrackClick }) => {
  const [visible, setVisible] = useState(false);
  const [showIOS, setShowIOS] = useState(false);
  const deferredPromptRef = useRef(null);

  useEffect(() => {
    if (isStandalone() || wasRecentlyDismissed()) return;

    const ios = isIOS();
    let shown = false;

    const tryShow = () => {
      if (shown || isStandalone() || wasRecentlyDismissed()) return;
      if (ios) {
        shown = true;
        setShowIOS(true);
        setVisible(true);
      } else if (deferredPromptRef.current) {
        shown = true;
        setVisible(true);
      }
    };

    const onBeforeInstall = (e) => {
      e.preventDefault();
      deferredPromptRef.current = e;
    };
    const onInstalled = () => {
      setVisible(false);
      deferredPromptRef.current = null;
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    };
    const onScroll = () => {
      const pct = (window.scrollY + window.innerHeight) / document.body.scrollHeight;
      if (pct > SCROLL_THRESHOLD) tryShow();
    };

    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    window.addEventListener("scroll", onScroll, { passive: true });
    const timer = setTimeout(tryShow, ENGAGEMENT_MS);

    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
      window.removeEventListener("scroll", onScroll);
      clearTimeout(timer);
    };
  }, []);

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
    setVisible(false);
    if (onTrackClick) onTrackClick("pwa_install_dismissed");
  };

  const install = async () => {
    const evt = deferredPromptRef.current;
    if (!evt) return;
    if (onTrackClick) onTrackClick("pwa_install_accepted");
    evt.prompt();
    const choice = await evt.userChoice;
    if (choice?.outcome !== "accepted") {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    }
    deferredPromptRef.current = null;
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      data-testid="pwa-install-prompt"
      className="fixed bottom-20 sm:bottom-24 inset-x-3 mx-auto z-[60] max-w-md animate-fade-in-up"
      role="dialog"
      aria-label="Install Lakeview app"
    >
      <div className="relative bg-cream border-2 border-gold rounded-lg shadow-2xl p-4 sm:p-5 paper-texture">
        <button
          data-testid="pwa-install-dismiss"
          onClick={dismiss}
          aria-label="Dismiss install prompt"
          className="absolute top-2 right-2 text-navy/60 hover:text-navy transition-colors p-1"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-start gap-3 pr-4">
          <img
            src={LOGO}
            alt="Lakeview logo"
            className="w-14 h-14 rounded-md flex-shrink-0 object-contain"
          />
          <div className="flex-1 min-w-0">
            <p className="font-accent text-xl text-gold leading-none mb-1">Get the app</p>
            <h3 className="font-serif text-base sm:text-lg text-navy font-bold leading-tight">
              Install Lakeview for one‑tap ordering
            </h3>
            <p className="font-sans text-xs sm:text-sm text-muted-foreground mt-1">
              Quick access to menu, specials, and Uber Eats — right from your home screen.
            </p>
          </div>
        </div>

        {showIOS ? (
          <div className="mt-3 pt-3 border-t border-navy/10 text-xs sm:text-sm text-navy/80 font-sans space-y-2">
            <p className="font-semibold text-navy">How to install on iPhone:</p>
            <ol className="space-y-1.5 pl-1">
              <li className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-gold text-navy text-[10px] font-bold flex items-center justify-center flex-shrink-0">1</span>
                <span>Tap the <Share className="inline w-3.5 h-3.5 -mt-0.5" /> Share button in Safari</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-gold text-navy text-[10px] font-bold flex items-center justify-center flex-shrink-0">2</span>
                <span>Scroll down &amp; tap <strong>Add to Home Screen</strong> <Plus className="inline w-3.5 h-3.5 -mt-0.5" /></span>
              </li>
            </ol>
          </div>
        ) : (
          <div className="mt-4 flex gap-2">
            <Button
              data-testid="pwa-install-accept-btn"
              onClick={install}
              className="flex-1 rounded-full bg-gold text-navy hover:bg-gold/90 font-semibold"
            >
              <Download className="w-4 h-4 mr-2" />
              Add to Home Screen
            </Button>
            <Button
              data-testid="pwa-install-later-btn"
              onClick={dismiss}
              variant="outline"
              className="rounded-full border-navy/30 text-navy hover:bg-navy/5"
            >
              Later
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default InstallPrompt;
