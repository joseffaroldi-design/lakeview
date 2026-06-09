/**
 * Shared primitives for AI Ads sub-modules. Extracted to keep individual
 * tab files small, and to avoid the Emergent visual-edits Babel plugin
 * recursion bug we hit on large files with nested .map(item => item.x).
 */
import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Copy } from "lucide-react";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const Section = ({ title, icon: Icon, children, testId, action }) => (
  <Card className="bg-card border-2 border-navy/10" data-testid={testId}>
    <CardHeader className="pb-3 flex flex-row items-center justify-between space-y-0">
      <CardTitle className="font-serif text-navy text-base flex items-center gap-2">
        {Icon && <Icon className="w-4 h-4 text-gold" />} {title}
      </CardTitle>
      {action}
    </CardHeader>
    <CardContent>{children}</CardContent>
  </Card>
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
    } catch (_) { /* ignore */ }
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
        {copied && <span className="text-[10px] ml-1">✓</span>}
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
  <Card className="bg-cream border-2 border-dashed border-navy/20" data-testid={testId}>
    <CardContent className="py-16 text-center">
      {Icon && <Icon className="w-12 h-12 mx-auto text-gold mb-4 opacity-60" />}
      <p className="font-serif text-lg text-navy mb-2">{title}</p>
      {body && <p className="font-sans text-sm text-muted-foreground max-w-md mx-auto">{body}</p>}
    </CardContent>
  </Card>
);

export const Spinner = ({ label = "Working…" }) => (
  <Card className="bg-card border-2 border-gold/30">
    <CardContent className="py-12 text-center">
      <div className="w-10 h-10 mx-auto border-4 border-gold/30 border-t-gold rounded-full animate-spin mb-3" />
      <p className="font-serif text-base text-navy">{label}</p>
    </CardContent>
  </Card>
);
