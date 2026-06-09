import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Sparkles, Copy, Save, Wand2, Tag, Image as ImageIcon, Video, Megaphone,
} from "lucide-react";

const Section = ({ title, icon: Icon, children, testId }) => (
  <Card className="bg-card border-2 border-navy/10" data-testid={testId}>
    <CardHeader className="pb-3">
      <CardTitle className="font-serif text-navy text-base flex items-center gap-2">
        {Icon && <Icon className="w-4 h-4 text-gold" />} {title}
      </CardTitle>
    </CardHeader>
    <CardContent>{children}</CardContent>
  </Card>
);

const Pill = ({ children }) => (
  <span className="inline-block text-xs font-sans px-2.5 py-1 mr-1.5 mb-1.5 rounded-full bg-gold/15 text-navy border border-gold/30">
    {children}
  </span>
);

const CopyableItem = ({ text, testId }) => {
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

const renderList = (items, testIdPrefix) => {
  const out = [];
  for (let i = 0; i < (items || []).length; i += 1) {
    out.push(<CopyableItem key={i} text={items[i]} testId={`${testIdPrefix}-${i}`} />);
  }
  return out;
};

const renderPills = (items) => {
  const out = [];
  for (let i = 0; i < (items || []).length; i += 1) {
    out.push(<Pill key={i}>{items[i]}</Pill>);
  }
  return out;
};

export const GenerationOutput = ({ output, genId, variationSeed, generating, onGenerateMore, onSave, savedJustNow }) => {
  const headlines = output.headlines || [];
  const primaryText = output.primary_text || [];
  const ctas = output.ctas || [];
  const hashtags = output.hashtags || [];
  const imageConcepts = output.image_concepts || [];
  const videoConcepts = output.video_concepts || [];
  const videoHooks = output.video_hooks || [];
  const idShort = genId ? genId.substring(0, 8) : "";
  const variationLabel = variationSeed > 0 ? ` · Variation #${variationSeed + 1}` : "";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Generation ID: <code className="text-navy">{idShort}</code>{variationLabel}
        </p>
        <div className="flex gap-2">
          <Button
            onClick={onGenerateMore}
            variant="outline"
            size="sm"
            disabled={generating}
            className="border-navy/20"
            data-testid="ai-generate-more-btn"
          >
            <Sparkles className="w-3.5 h-3.5 mr-1.5" />
            Generate More Variations
          </Button>
          <Button
            onClick={onSave}
            size="sm"
            className="bg-forest text-cream hover:bg-forest/90"
            data-testid="ai-save-btn"
          >
            <Save className="w-3.5 h-3.5 mr-1.5" />
            {savedJustNow ? "Saved ✓" : "Save Campaign"}
          </Button>
        </div>
      </div>

      <Section title={`Headlines (${headlines.length})`} icon={Megaphone} testId="ai-out-headlines">
        {renderList(headlines, "ai-headline")}
      </Section>

      <Section title="Primary Text Variations" icon={Wand2} testId="ai-out-primary">
        {renderList(primaryText, "ai-primary")}
      </Section>

      <Section title="Call-to-Actions" icon={Tag} testId="ai-out-ctas">
        <div className="flex flex-wrap gap-2">{renderList(ctas, "ai-cta")}</div>
      </Section>

      <Section title="Hashtags" icon={Tag} testId="ai-out-hashtags">
        <div className="flex flex-wrap">{renderPills(hashtags)}</div>
      </Section>

      <Section title="Image Concepts" icon={ImageIcon} testId="ai-out-images">
        {renderList(imageConcepts, "ai-image")}
      </Section>

      {(videoConcepts.length > 0 || videoHooks.length > 0) && (
        <Section title="Video Concepts & Hooks" icon={Video} testId="ai-out-videos">
          {renderList(videoConcepts.map((c) => `Concept: ${c}`), "ai-video-concept")}
          {renderList(videoHooks.map((c) => `Hook: ${c}`), "ai-video-hook")}
        </Section>
      )}
    </div>
  );
};

export default GenerationOutput;
