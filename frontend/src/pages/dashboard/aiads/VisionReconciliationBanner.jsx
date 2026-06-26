/**
 * Sprint 17B — VisionReconciliationBanner
 *
 * Explicit Menu-vs-AI-Vision reconciliation. Shows up only when:
 *   – the owner picked a menu item AND
 *   – the AI vision detected a different food type AND
 *   – the AI confidence is high enough (> 0.7) to be worth a question.
 *
 * Three choices:
 *   – Use Menu Item  (we honor the owner's pick — silent default)
 *   – Use AI Detection (let the vision label win)
 *   – Merge Both       (keep both — best of both worlds)
 *
 * The choice is remembered against the menu item via `design_memory.vision_choice`
 * so the banner never nags twice for the same dish.
 *
 * Props:
 *   menuItemName  – string, the picked menu item label
 *   detectedName  – string, AI-vision detected food type
 *   confidence    – 0..1
 *   savedChoice   – "menu" | "ai" | "merge" | null
 *   onChoose(choice) – callback with the picked choice
 */
import React from "react";
import { Eye, BookOpen, GitMerge, Sparkles, Check } from "lucide-react";

const VisionReconciliationBanner = ({
  menuItemName, detectedName, confidence,
  savedChoice, onChoose,
}) => {
  const same = (menuItemName || "").trim().toLowerCase() === (detectedName || "").trim().toLowerCase();
  if (same || !menuItemName || !detectedName) return null;
  if ((confidence || 0) < 0.7) return null;

  return (
    <div className="rounded-md border border-amber-300 bg-amber-50/60 p-3"
         data-testid="vision-reconciliation-banner">
      <div className="flex items-start gap-2 mb-2">
        <Sparkles className="w-4 h-4 text-amber-700 flex-shrink-0 mt-0.5" />
        <div className="text-xs leading-snug">
          <p className="font-semibold text-navy">
            We think this is <span className="text-gold">{menuItemName}</span>{" "}
            <span className="text-navy/60 font-normal">
              (AI detected <em>{detectedName}</em> · {Math.round(confidence * 100)}% confidence)
            </span>
          </p>
          <p className="text-navy/70 mt-0.5">
            Choose how we should label this flyer.
            {savedChoice ? <> (You picked <strong>{savedChoice}</strong> last time.)</> : null}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onChoose("menu")}
          className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-semibold border ${
            savedChoice === "menu"
              ? "border-gold bg-gold text-navy"
              : "border-navy/20 bg-white text-navy hover:border-gold/50"
          }`}
          data-testid="vision-recon-use-menu"
        >
          <BookOpen className="w-3 h-3" />
          {savedChoice === "menu" ? <Check className="w-3 h-3" /> : null}
          Use Menu Item
        </button>
        <button
          type="button"
          onClick={() => onChoose("ai")}
          className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-semibold border ${
            savedChoice === "ai"
              ? "border-gold bg-gold text-navy"
              : "border-navy/20 bg-white text-navy hover:border-gold/50"
          }`}
          data-testid="vision-recon-use-ai"
        >
          <Eye className="w-3 h-3" />
          {savedChoice === "ai" ? <Check className="w-3 h-3" /> : null}
          Use AI Detection
        </button>
        <button
          type="button"
          onClick={() => onChoose("merge")}
          className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-semibold border ${
            savedChoice === "merge"
              ? "border-gold bg-gold text-navy"
              : "border-navy/20 bg-white text-navy hover:border-gold/50"
          }`}
          data-testid="vision-recon-merge"
        >
          <GitMerge className="w-3 h-3" />
          {savedChoice === "merge" ? <Check className="w-3 h-3" /> : null}
          Merge Both
        </button>
      </div>
    </div>
  );
};

export default VisionReconciliationBanner;
