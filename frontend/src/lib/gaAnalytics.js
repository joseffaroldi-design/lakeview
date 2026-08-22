// Google Analytics 4 (GA4) — lightweight loader + event helpers.
// Reads the Measurement ID from REACT_APP_GA_MEASUREMENT_ID. If the ID is
// missing (any environment where analytics isn't configured), every function
// in this module becomes a silent no-op: no script tag is injected, no
// `dataLayer` is created, no console noise. This is intentional so builds
// stay clean and preview/local runs don't pollute a real GA4 property.

const MEASUREMENT_ID = process.env.REACT_APP_GA_MEASUREMENT_ID || "";

let initialized = false;

const hasWindow = () => typeof window !== "undefined";

const isEnabled = () => Boolean(MEASUREMENT_ID) && hasWindow();

// Inject the gtag.js loader exactly once. Safe to call multiple times.
export const initGA = () => {
  if (!isEnabled() || initialized) return;
  initialized = true;

  // Standard GA4 bootstrap (matches Google's official snippet). We disable
  // automatic page_view so SPA navigations don't double-fire alongside our
  // manual pageview() calls on route change.
  window.dataLayer = window.dataLayer || [];
  window.gtag = function gtag() { window.dataLayer.push(arguments); };
  window.gtag("js", new Date());
  window.gtag("config", MEASUREMENT_ID, {
    send_page_view: false,
    anonymize_ip: true,
  });

  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(MEASUREMENT_ID)}`;
  document.head.appendChild(script);
};

export const pageview = (path, title) => {
  if (!isEnabled() || !initialized || !window.gtag) return;
  window.gtag("event", "page_view", {
    page_path: path,
    page_location: window.location.href,
    page_title: title || document.title,
  });
};

export const event = (name, params = {}) => {
  if (!isEnabled() || !initialized || !window.gtag || !name) return;
  window.gtag("event", name, params);
};

export const isGAConfigured = () => Boolean(MEASUREMENT_ID);
