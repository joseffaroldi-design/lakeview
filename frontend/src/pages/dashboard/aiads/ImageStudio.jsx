/**
 * Image Studio — concept generation (Phase 2). Actual image rendering wired later
 * by implementing ai_engine/providers.generate_image() and flipping the flag.
 */
import React from "react";
import { Image as ImageIcon } from "lucide-react";
import { Section, CopyableItem } from "./shared";
import { BriefForm, useSpecialtyRunner, OutputPanel, SaveBtn } from "./BriefForm";

const IMAGE_SUBTYPES = [
  "Marketing Image",
  "Flyer Layout",
  "Social Graphic",
  "Ad Creative",
  "Food Photography",
  "Service Business",
  "Event Graphic",
];

const Result = ({ output, savedJustNow, onSave }) => {
  if (!output) return null;
  return (
    <Section
      title="Art Direction"
      icon={ImageIcon}
      testId="ai-image-result"
      action={<SaveBtn savedJustNow={savedJustNow} onSave={onSave} testId="ai-image-save" />}
    >
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Headline</p>
      <CopyableItem text={output.headline || ""} testId="ai-image-headline" />
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Subheadline</p>
      <CopyableItem text={output.subheadline || ""} testId="ai-image-subheadline" />
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">CTA</p>
      <CopyableItem text={output.cta || ""} testId="ai-image-cta" />
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Layout</p>
      <CopyableItem text={output.layout_direction || ""} testId="ai-image-layout" />
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Photography</p>
      <CopyableItem text={output.photography_direction || ""} testId="ai-image-photo" />
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Graphic Direction</p>
      <CopyableItem text={output.graphic_direction || ""} testId="ai-image-graphic" />
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Brand Direction</p>
      <CopyableItem text={output.brand_direction || ""} testId="ai-image-brand" />
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Generation Prompt (for OpenAI Images / Ideogram / Midjourney / Flux)</p>
      <CopyableItem text={output.generation_prompt || ""} testId="ai-image-genprompt" />
      <p className="text-xs text-muted-foreground italic mt-2">
        Image rendering is a future step. Connect a provider in ai_engine/providers.py to enable in-app generation.
      </p>
    </Section>
  );
};

export const ImageStudio = ({ catalog, getAuthHeader, onSavedCount }) => {
  const { output, busy, error, savedJustNow, run, saveAsAsset, lastBrief } = useSpecialtyRunner("image_concept", getAuthHeader, onSavedCount);

  const onSave = () => {
    const title = `Image · ${(lastBrief && lastBrief.asset_subtype) || "Concept"} · ${(lastBrief && lastBrief.name) || "Untitled"}`;
    saveAsAsset("image_concept", title, output, null);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-1">
        <BriefForm
          catalog={catalog}
          onSubmit={run}
          busy={busy}
          submitLabel="Generate Image Concept"
          testIdPrefix="ai-image"
          briefIcon={ImageIcon}
          showPlatform={false}
          showAssetSubtype
          subtypeOptions={IMAGE_SUBTYPES}
        />
      </div>
      <div className="lg:col-span-2">
        {error && <p data-testid="ai-image-error" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-sm p-3 mb-3">{error}</p>}
        <OutputPanel
          busy={busy}
          EmptyIcon={ImageIcon}
          emptyTitle="Generate image concepts"
          emptyBody="Choose an image type, brief your audience and offer. You'll get a full art direction + a generation prompt ready for any image AI."
        >
          {output ? <Result output={output} savedJustNow={savedJustNow} onSave={onSave} /> : null}
        </OutputPanel>
      </div>
    </div>
  );
};

export default ImageStudio;
