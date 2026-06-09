/**
 * SMS Generator — 160ch / 300ch / urgency / discount variants.
 */
import React from "react";
import { MessageSquare } from "lucide-react";
import { Section, CopyableItem } from "./shared";
import { BriefForm, useSpecialtyRunner, OutputPanel, SaveBtn } from "./BriefForm";

const VariantBlock = ({ label, text, testId, onSave, savedJustNow }) => (
  <Section
    title={label}
    icon={MessageSquare}
    testId={testId}
    action={<SaveBtn savedJustNow={savedJustNow} onSave={onSave} testId={`${testId}-save`} />}
  >
    <CopyableItem text={text || ""} testId={`${testId}-text`} />
    <p className="text-[10px] text-muted-foreground mt-1">{(text || "").length} chars</p>
  </Section>
);

export const SmsGenerator = ({ catalog, getAuthHeader, onSavedCount }) => {
  const { output, busy, error, savedJustNow, run, saveAsAsset, lastBrief } = useSpecialtyRunner("sms", getAuthHeader, onSavedCount);

  const save = (label, text) => {
    const title = `SMS · ${label} · ${(lastBrief && lastBrief.name) || "Untitled"}`;
    saveAsAsset("sms", title, { variant: label, text }, null);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-1">
        <BriefForm
          catalog={catalog}
          onSubmit={run}
          busy={busy}
          submitLabel="Generate SMS"
          testIdPrefix="ai-sms"
          briefIcon={MessageSquare}
          showPlatform={false}
        />
      </div>
      <div className="lg:col-span-2">
        {error && <p data-testid="ai-sms-error" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-sm p-3 mb-3">{error}</p>}
        <OutputPanel
          busy={busy}
          EmptyIcon={MessageSquare}
          emptyTitle="Generate SMS variants"
          emptyBody="160-char, 300-char, urgency-led, and discount-led versions for the same campaign."
        >
          {output ? (
            <>
              <VariantBlock label="160 Characters" text={output.v160} testId="ai-sms-160" savedJustNow={savedJustNow} onSave={() => save("160", output.v160)} />
              <VariantBlock label="300 Characters" text={output.v300} testId="ai-sms-300" savedJustNow={savedJustNow} onSave={() => save("300", output.v300)} />
              <VariantBlock label="Urgency-led" text={output.urgency} testId="ai-sms-urgency" savedJustNow={savedJustNow} onSave={() => save("Urgency", output.urgency)} />
              <VariantBlock label="Discount-led" text={output.discount} testId="ai-sms-discount" savedJustNow={savedJustNow} onSave={() => save("Discount", output.discount)} />
            </>
          ) : null}
        </OutputPanel>
      </div>
    </div>
  );
};

export default SmsGenerator;
