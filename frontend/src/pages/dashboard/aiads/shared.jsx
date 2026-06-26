/**
 * Shared primitives for AI Ads sub-modules.
 *
 * IMPORTANT: This file MUST NOT import cross-file React components that are
 * later rendered with JSX expression props (e.g. shadcn Card / CardHeader /
 * CardContent / CardTitle). The Emergent visual-edits Babel plugin has a bug
 * in `lazyEvaluatePropSource` (babel-metadata-plugin.js:865) where it tries
 * to call `.traverse(...)` on a null parentPath when looking up cross-file
 * prop sources. Using plain intrinsic HTML elements (div, span, button)
 * keeps that code path from being triggered, so we re-implement the visual
 * "Card" shell inline with Tailwind classes.
 *
 * Visual parity goal: identical look-and-feel to shadcn Card used elsewhere
 * in the admin dashboard (cream/navy/gold palette).
 */
import React, { useState } from "react";
import { Copy } from "lucide-react";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const Section = ({ title, icon: Icon, children, testId, action }) => (
  <div
    className="rounded-lg border-2 border-navy/10 bg-card text-card-foreground shadow-sm"
    data-testid={testId}
  >
    <div className="flex flex-row items-center justify-between space-y-0 pb-3 p-6">
      <h3 className="font-serif text-navy text-base flex items-center gap-2 font-semibold leading-none tracking-tight">
        {Icon ? <Icon className="w-4 h-4 text-gold" /> : null} {title}
      </h3>
      {action}
    </div>
    <div className="p-6 pt-0">{children}</div>
  </div>
);

export const Pill = ({ children }) => (
  <span className="inline-block text-xs font-sans px-2.5 py-1 mr-1.5 mb-1.5 rounded-full bg-gold/15 text-navy border border-gold/30">
    {children}
  </span>
);

export const CopyableItem = ({ text, testId }) => {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (e) {
      if (process.env.NODE_ENV !== "production") console.warn("[shared.CopyableItem] clipboard.writeText failed:", e);
    }
  };
  return (
    <div
      className="group flex items-start gap-2 p-3 mb-2 bg-background border border-navy/5 rounded-sm hover:border-gold/40 transition-colors"
      data-testid={testId}
    >
      <p className="font-sans text-sm text-navy flex-1 whitespace-pre-wrap">{text}</p>
      <button
        onClick={onCopy}
        className="opacity-60 group-hover:opacity-100 text-navy hover:text-gold transition-opacity flex-shrink-0"
        title="Copy"
      >
        <Copy className="w-3.5 h-3.5" />
        {copied ? <span className="text-[10px] ml-1">✓</span> : null}
      </button>
    </div>
  );
};

export const Field = ({ label, children }) => (
  <div>
    <label className="block text-xs text-muted-foreground mb-1">{label}</label>
    {children}
  </div>
);

export const EmptyState = ({ icon: Icon, title, body, testId }) => (
  <div
    className="rounded-lg border-2 border-dashed border-navy/20 bg-cream"
    data-testid={testId}
  >
    <div className="py-16 text-center p-6">
      {Icon ? <Icon className="w-12 h-12 mx-auto text-gold mb-4 opacity-60" /> : null}
      <p className="font-serif text-lg text-navy mb-2">{title}</p>
      {body ? (
        <p className="font-sans text-sm text-muted-foreground max-w-md mx-auto">{body}</p>
      ) : null}
    </div>
  </div>
);

export const Spinner = ({ label = "Working…" }) => (
  <div className="rounded-lg border-2 border-gold/30 bg-card">
    <div className="py-12 text-center p-6">
      <div className="w-10 h-10 mx-auto border-4 border-gold/30 border-t-gold rounded-full animate-spin mb-3" />
      <p className="font-serif text-base text-navy">{label}</p>
    </div>
  </div>
);
