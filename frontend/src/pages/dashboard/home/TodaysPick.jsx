/**
 * TodaysPick — Full-width hero card for the Home screen
 * 
 * Sprint 13A: Displays the daily auto-selected menu item with pre-drafted marketing copy.
 * Owner can accept, reject, or pick a different item.
 */
import React, { useState } from "react";
import { Sparkles, Copy, CheckCircle2, X, RefreshCw, Calendar } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

// Extracted CopyButton to avoid nested component definition
const CopyButton = ({ text, field, label, copiedField, onCopy }) => (
  <button
    onClick={() => onCopy(text, field)}
    className="flex items-center gap-2 px-3 py-2 bg-white border-2 border-navy/10 hover:border-gold/40 rounded-lg transition-colors text-left flex-1"
  >
    <div className="flex-1 min-w-0">
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="text-sm text-navy font-medium truncate">{text.substring(0, 60)}...</p>
    </div>
    {copiedField === field ? (
      <CheckCircle2 className="w-4 h-4 text-forest flex-shrink-0" />
    ) : (
      <Copy className="w-4 h-4 text-navy/40 flex-shrink-0" />
    )}
  </button>
);

const TodaysPick = ({ pick, onRefresh, onAccept, onReject, onPickDifferent }) => {
  const [showCopyModal, setShowCopyModal] = useState(false);
  const [copiedField, setCopiedField] = useState(null);

  if (!pick) {
    return (
      <Card className="bg-gradient-to-br from-gold/10 via-cream to-white border-2 border-gold/30 mb-6">
        <CardContent className="py-6 px-6 text-center">
          <Sparkles className="w-8 h-8 text-gold mx-auto mb-3" />
          <p className="text-navy font-semibold">Loading Today&apos;s Pick...</p>
        </CardContent>
      </Card>
    );
  }

  const { item, copy, metrics } = pick;

  const copyToClipboard = (text, field) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  return (
    <>
      {/* Hero Card */}
      <Card className="bg-gradient-to-br from-gold/10 via-cream to-white border-2 border-gold/30 mb-6 overflow-hidden">
        <div className="px-6 py-4 border-b border-gold/20 bg-gold/5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-gold" />
            <h3 className="font-serif text-lg text-navy font-bold">Today&apos;s Pick</h3>
          </div>
          <button
            onClick={onRefresh}
            className="p-2 hover:bg-gold/10 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4 text-navy/60" />
          </button>
        </div>

        <CardContent className="p-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Item Info */}
            <div className="lg:col-span-2">
              <div className="flex items-start justify-between gap-4 mb-4">
                <div className="flex-1">
                  <h4 className="font-serif text-2xl text-navy font-bold mb-1">{item.name}</h4>
                  <p className="text-sm text-muted-foreground mb-2">{item.category}</p>
                  {item.description && (
                    <p className="text-sm text-navy/80 mb-3">{item.description}</p>
                  )}
                  <div className="flex items-center gap-4">
                    <span className="text-2xl font-bold text-gold">${item.price}</span>
                    {item.days_since_promoted !== null && (
                      <span className="text-xs px-3 py-1.5 bg-navy/10 text-navy rounded-full flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {item.days_since_promoted === 999
                          ? "Never promoted"
                          : `${item.days_since_promoted} days since last promo`}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Caption Preview */}
              <div className="bg-white border-2 border-navy/10 rounded-lg p-4 mb-4">
                <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Caption Preview</p>
                <p className="text-sm text-navy leading-relaxed">{copy.caption}</p>
                <div className="flex flex-wrap gap-1 mt-3">
                  {copy.hashtags.slice(0, 5).map((tag, idx) => (
                    <span key={idx} className="text-xs text-gold">#{tag}</span>
                  ))}
                  {copy.hashtags.length > 5 && (
                    <span className="text-xs text-muted-foreground">+{copy.hashtags.length - 5} more</span>
                  )}
                </div>
              </div>

              {/* CTAs */}
              <div className="flex flex-wrap gap-3">
                <Button
                  onClick={() => setShowCopyModal(true)}
                  className="bg-gold text-navy hover:bg-gold/90 flex-1 min-w-[200px]"
                  disabled={metrics.accepted}
                >
                  <Copy className="w-4 h-4 mr-2" />
                  {metrics.accepted ? "Already Used" : "Use This Post"}
                </Button>
                <Button
                  onClick={onPickDifferent}
                  variant="outline"
                  className="border-navy/20 flex-1 min-w-[180px]"
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Pick Different Item
                </Button>
              </div>
            </div>

            {/* Placeholder for photo (future) */}
            <div className="lg:col-span-1">
              <div className="aspect-square bg-navy/5 rounded-lg flex items-center justify-center border-2 border-dashed border-navy/10">
                <div className="text-center p-4">
                  <Sparkles className="w-8 h-8 text-navy/20 mx-auto mb-2" />
                  <p className="text-xs text-muted-foreground">Photo placeholder</p>
                  <p className="text-xs text-muted-foreground mt-1">(Use existing item photo)</p>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Copy Modal */}
      {showCopyModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-card rounded-lg max-w-3xl w-full my-8 shadow-2xl border-2 border-gold/30">
            <div className="px-6 py-4 border-b border-navy/10 bg-cream flex items-center justify-between sticky top-0 z-10">
              <div className="flex items-center gap-2">
                <Copy className="w-5 h-5 text-gold" />
                <h3 className="font-serif text-navy font-semibold">Marketing Copy — {item.name}</h3>
              </div>
              <button
                onClick={() => setShowCopyModal(false)}
                className="p-2 hover:bg-navy/10 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-navy" />
              </button>
            </div>

            <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
              {/* Caption */}
              <div>
                <CopyButton
                  text={copy.caption}
                  field="caption"
                  label="Social Caption"
                  copiedField={copiedField}
                  onCopy={copyToClipboard}
                />
              </div>

              {/* Hashtags */}
              <div>
                <CopyButton
                  text={copy.hashtags.map(t => `#${t}`).join(" ")}
                  field="hashtags"
                  label="Hashtags"
                  copiedField={copiedField}
                  onCopy={copyToClipboard}
                />
              </div>

              {/* SMS */}
              <div>
                <CopyButton
                  text={copy.sms}
                  field="sms"
                  label="SMS"
                  copiedField={copiedField}
                  onCopy={copyToClipboard}
                />
              </div>

              {/* Email Subject */}
              <div>
                <CopyButton
                  text={copy.email.subject}
                  field="email_subject"
                  label="Email Subject"
                  copiedField={copiedField}
                  onCopy={copyToClipboard}
                />
              </div>

              {/* Email Body */}
              <div>
                <button
                  onClick={() => copyToClipboard(copy.email.body, "email_body")}
                  className="w-full flex items-start gap-2 px-3 py-2 bg-white border-2 border-navy/10 hover:border-gold/40 rounded-lg transition-colors text-left"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Email Body</p>
                    <p className="text-sm text-navy leading-relaxed">{copy.email.body}</p>
                  </div>
                  {copiedField === "email_body" ? (
                    <CheckCircle2 className="w-4 h-4 text-forest flex-shrink-0 mt-1" />
                  ) : (
                    <Copy className="w-4 h-4 text-navy/40 flex-shrink-0 mt-1" />
                  )}
                </button>
              </div>

              {/* Google Business Post */}
              <div>
                <button
                  onClick={() => copyToClipboard(copy.gbp, "gbp")}
                  className="w-full flex items-start gap-2 px-3 py-2 bg-white border-2 border-navy/10 hover:border-gold/40 rounded-lg transition-colors text-left"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Google Business Post</p>
                    <p className="text-sm text-navy leading-relaxed">{copy.gbp}</p>
                  </div>
                  {copiedField === "gbp" ? (
                    <CheckCircle2 className="w-4 h-4 text-forest flex-shrink-0 mt-1" />
                  ) : (
                    <Copy className="w-4 h-4 text-navy/40 flex-shrink-0 mt-1" />
                  )}
                </button>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-navy/10 bg-cream flex items-center justify-between sticky bottom-0">
              <p className="text-xs text-muted-foreground">Click any section to copy to clipboard</p>
              <div className="flex gap-2">
                <Button
                  onClick={() => {
                    setShowCopyModal(false);
                    onAccept();
                  }}
                  className="bg-forest text-white hover:bg-forest/90"
                >
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  Mark as Used
                </Button>
                <Button
                  onClick={() => setShowCopyModal(false)}
                  variant="outline"
                  className="border-navy/20"
                >
                  Close
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default TodaysPick;
