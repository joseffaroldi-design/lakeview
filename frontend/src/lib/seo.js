// Lightweight per-route SEO helper for a CRA/React SPA.
//
// Root index.html ships strong default metadata (title, description, canonical,
// OG, Twitter, JSON-LD) — those handle first-paint SEO for Google's rendering
// crawler and any bot that doesn't execute JS. This hook only *updates* those
// tags per public route so /menu doesn't inherit /'s title/canonical.
//
// No dependencies. No react-helmet. Pure DOM.

import { useEffect } from "react";

const CANONICAL_ORIGIN = "https://lakeview-grill.emergent.host";

const setAttr = (selector, attr, value) => {
  const el = document.head.querySelector(selector);
  if (el && value != null) el.setAttribute(attr, value);
};

const setText = (selector, value) => {
  const el = document.head.querySelector(selector);
  if (el && value != null) el.textContent = value;
};

/**
 * Update <title>, meta description, canonical, and social-share tags for the
 * current route. Falls back silently if a tag doesn't exist in index.html.
 *
 * @param {Object} opts
 * @param {string} opts.title       Full <title> content
 * @param {string} opts.description meta description content (< 160 chars ideal)
 * @param {string} opts.path        Route path (leading slash), used to build canonical + og:url
 * @param {string} [opts.ogImage]   Absolute image URL (defaults to the one in index.html)
 */
export const useSeo = ({ title, description, path, ogImage }) => {
  useEffect(() => {
    const url = `${CANONICAL_ORIGIN}${path || "/"}`;

    if (title) document.title = title;

    setAttr('meta[name="description"]', "content", description);
    setAttr('link[rel="canonical"]', "href", url);

    // Open Graph
    setAttr('meta[property="og:title"]', "content", title);
    setAttr('meta[property="og:description"]', "content", description);
    setAttr('meta[property="og:url"]', "content", url);
    if (ogImage) setAttr('meta[property="og:image"]', "content", ogImage);

    // Twitter
    setAttr('meta[name="twitter:title"]', "content", title);
    setAttr('meta[name="twitter:description"]', "content", description);
    if (ogImage) setAttr('meta[name="twitter:image"]', "content", ogImage);
  }, [title, description, path, ogImage]);
};
