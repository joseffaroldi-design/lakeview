/**
 * Email Campaign Generator — Welcome / Promotion / Holiday / Winback.
 */
import React from "react";
import { Mail } from "lucide-react";
import { Section, CopyableItem } from "./shared";
import { BriefForm, useSpecialtyRunner, OutputPanel, SaveBtn } from "./BriefForm";

const Result = ({ output, savedJustNow, onSave }) => {
  if (!output) return null;
  return (
    <Section
      title={`${output.campaign_type || "Email"} Campaign`}
      icon={Mail}
      testId="ai-email-result"
      action={<SaveBtn savedJustNow={savedJustNow} onSave={onSave} testId="ai-email-save" />}
    >
      <div className="mb-2">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Subject Line</p>
        <CopyableItem text={output.subject_line || ""} testId="ai-email-subject" />
      </div>
      <div className="mb-2">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Preview Text</p>
        <CopyableItem text={output.preview_text || ""} testId="ai-email-preview" />
      </div>
      <div className="mb-2">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Email Body</p>
        <CopyableItem text={output.email_body || ""} testId="ai-email-body" />
      </div>
      <div className="mb-2">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">CTA Button</p>
        <CopyableItem text={output.cta_label || ""} testId="ai-email-cta" />
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">CTA Link Target</p>
        <CopyableItem text={output.cta_link_suggestion || ""} testId="ai-email-link" />
      </div>
    </Section>
  );
};

export const EmailGenerator = ({ catalog, getAuthHeader, onSavedCount }) => {
  const { output, busy, error, savedJustNow, run, saveAsAsset, lastBrief } = useSpecialtyRunner("email", getAuthHeader, onSavedCount);

  const onSave = () => {
    const title = `Email · ${(output && output.campaign_type) || "Promo"} · ${(lastBrief && lastBrief.name) || "Untitled"}`;
    saveAsAsset("email", title, output, null);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-1">
        <BriefForm
          catalog={catalog}
          onSubmit={run}
          busy={busy}
          submitLabel="Generate Email"
          testIdPrefix="ai-email"
          briefIcon={Mail}
          showPlatform={false}
          showEmailType
        />
      </div>
      <div className="lg:col-span-2">
        {error && <p data-testid="ai-email-error" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-sm p-3 mb-3">{error}</p>}
        <OutputPanel
          busy={busy}
          EmptyIcon={Mail}
          emptyTitle="Generate email campaigns"
          emptyBody="Choose Welcome, Promotion, Holiday or Winback. You'll get subject line, preview text, full body and CTA."
        >
          {output ? <Result output={output} savedJustNow={savedJustNow} onSave={onSave} /> : null}
        </OutputPanel>
      </div>
    </div>
  );
};

export default EmailGenerator;
