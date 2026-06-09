/**
 * Social Media Generator — Short / Medium / Long captions per platform.
 */
import React from "react";
import { Share2, Hash } from "lucide-react";
import { Section, CopyableItem, Pill } from "./shared";
import { BriefForm, useSpecialtyRunner, OutputPanel, SaveBtn } from "./BriefForm";

const Variant = ({ title, data, savedJustNow, onSave, testId }) => {
  if (!data) return null;
  const hashtags = data.hashtags || [];
  const tagPills = [];
  for (let i = 0; i < hashtags.length; i += 1) tagPills.push(<Pill key={i}>{hashtags[i]}</Pill>);
  return (
    <Section
      title={title}
      icon={Share2}
      testId={testId}
      action={<SaveBtn savedJustNow={savedJustNow} onSave={onSave} testId={`${testId}-save`} />}
    >
      <div className="mb-2">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Headline</p>
        <CopyableItem text={data.headline || ""} testId={`${testId}-headline`} />
      </div>
      <div className="mb-2">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Caption</p>
        <CopyableItem text={data.caption || ""} testId={`${testId}-caption`} />
      </div>
      <div className="mb-2">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">CTA</p>
        <CopyableItem text={data.cta || ""} testId={`${testId}-cta`} />
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1 flex items-center gap-1">
          <Hash className="w-3 h-3" /> Hashtags
        </p>
        <div className="flex flex-wrap">{tagPills}</div>
      </div>
    </Section>
  );
};

export const SocialGenerator = ({ catalog, getAuthHeader, onSavedCount }) => {
  const { output, busy, error, savedJustNow, run, saveAsAsset, lastBrief } = useSpecialtyRunner("social", getAuthHeader, onSavedCount);
  const platform = lastBrief && lastBrief.platform;

  const saveVariant = (lengthLabel, data) => {
    const title = `${platform || "Social"} · ${lengthLabel} · ${(lastBrief && lastBrief.name) || "Untitled"}`;
    saveAsAsset("social_post", title, { length: lengthLabel, ...data }, platform);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-1">
        <BriefForm
          catalog={catalog}
          onSubmit={run}
          busy={busy}
          submitLabel="Generate Social Posts"
          testIdPrefix="ai-social"
          briefIcon={Share2}
        />
      </div>
      <div className="lg:col-span-2">
        {error && <p data-testid="ai-social-error" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-sm p-3 mb-3">{error}</p>}
        <OutputPanel
          busy={busy}
          EmptyIcon={Share2}
          emptyTitle="Generate social posts"
          emptyBody="Pick a platform and brief. You'll get Short / Medium / Long variants with captions, headlines, hashtags and CTAs."
        >
          {output ? (
            <>
              <Variant title="Short" data={output.short} savedJustNow={savedJustNow} onSave={() => saveVariant("Short", output.short)} testId="ai-social-short" />
              <Variant title="Medium" data={output.medium} savedJustNow={savedJustNow} onSave={() => saveVariant("Medium", output.medium)} testId="ai-social-medium" />
              <Variant title="Long" data={output.long} savedJustNow={savedJustNow} onSave={() => saveVariant("Long", output.long)} testId="ai-social-long" />
            </>
          ) : null}
        </OutputPanel>
      </div>
    </div>
  );
};

export default SocialGenerator;
