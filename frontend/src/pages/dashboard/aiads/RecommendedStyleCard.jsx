/**
 * Sprint 17B — RecommendedStyleCard
 *
 * ONE compact card that bundles the top style recommendation across
 * theme + layout + typography + badge + overlay, with a single
 * "Apply Recommended Style" CTA. Everything else (other themes, manual
 * picker) lives behind a collapsible "View other themes" toggle so the
 * owner sees a single decision instead of 22.
 *
 * Props:
 *   rec               – the top recommendation object supplied by the parent
 *   context           – the same context block (has_memory, holiday, ...)
 *   isSelected        – true when the parent has already accepted this rec
 *   onApply()         – apply the top recommendation (pick its theme_id)
 *   onShowOther()     – expand the "other themes" panel
 *   showingOther      – whether the other-themes panel is currently expanded
 */
import React from "react";
import { Star, Sparkles, BookOpen, ChevronRight } from "lucide-react";

const Stars = ({ n }) => (
  <span className="inline-flex items-center gap-0.5 text-gold" aria-label={`${n} stars`}>
    {Array.from({ length: 5 }).map((_, i) => (
      <Star
        key={i}
        className={`w-3.5 h-3.5 ${i < n ? "fill-gold text-gold" : "text-navy/20"}`}
        strokeWidth={1.5}
      />
    ))}
  </span>
);

const TRAIT_ROWS = [
  { key: "theme",      label: "Theme" },
  { key: "layout",     label: "Layout" },
  { key: "typography", label: "Typography" },
  { key: "badge",      label: "Badge" },
  { key: "overlay",    label: "Overlay" },
];

const RecommendedStyleCard = ({
  rec, context, isSelected,
  onApply, onShowOther, showingOther,
}) => {
  if (!rec) {
    return (
      <div className="rounded-md border border-navy/15 bg-white p-3 text-xs text-navy/60"
           data-testid="rec-style-card-empty">
        Recommendation unavailable — pick a theme manually below.
      </div>
    );
  }

  const traits = rec.style_traits || {};
  const rows = TRAIT_ROWS.map((r) => ({
    label: r.label,
    value: r.key === "theme" ? rec.label : traits[r.key],
  })).filter((r) => r.value);

  return (
    <div
      className={`rounded-lg border p-4 transition-colors ${
        isSelected
          ? "border-gold bg-gold/10 ring-2 ring-gold/30"
          : "border-navy/20 bg-white"
      }`}
      data-testid="rec-style-card"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-gold" />
          <p className="text-[11px] font-semibold uppercase tracking-wider text-navy/70">
            Recommended Style
          </p>
          {context?.has_memory ? (
            <span
              className="inline-block text-[9px] font-semibold uppercase tracking-wider text-gold bg-gold/15 border border-gold/30 rounded-full px-1.5 py-0.5"
              data-testid="rec-style-memory-pill"
            >
              <BookOpen className="w-3 h-3 inline mr-1" />
              from saved style
            </span>
          ) : null}
        </div>
        <Stars n={rec.stars || 5} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 mb-3">
        {rows.map((row) => (
          <div key={row.label}
               className="flex items-baseline gap-2"
               data-testid={`rec-trait-${row.label.toLowerCase()}`}>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-navy/60 w-[78px] shrink-0">
              {row.label}
            </span>
            <span className="text-sm text-navy font-semibold truncate">{row.value}</span>
          </div>
        ))}
      </div>

      <div className="rounded bg-navy/5 px-3 py-2 mb-3">
        <p className="text-[11px] text-navy/70 leading-snug"
           data-testid="rec-style-reason">
          <span className="font-semibold text-navy/80">Reason: </span>
          {rec.reason}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {isSelected ? (
          /* Sprint 19 — passive confirmation. The recommended theme is
             already the default selection on the Review step, so the
             owner doesn't have to click anything to use it. Click
             "Generate" below to ship it as-is. */
          <span
            className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-semibold bg-gold/15 text-navy border border-gold/40"
            data-testid="rec-style-applied-chip"
          >
            <Sparkles className="w-3.5 h-3.5 text-gold" />
            Using this style — click Generate when ready
          </span>
        ) : (
          <button
            type="button"
            onClick={onApply}
            className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-semibold transition-colors bg-gold text-navy hover:bg-gold/90"
            data-testid="rec-style-apply"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Apply Recommended Style
          </button>
        )}
        <button
          type="button"
          onClick={onShowOther}
          className="text-[11px] text-navy/70 hover:underline inline-flex items-center gap-1"
          data-testid="rec-style-view-others"
        >
          {showingOther ? "Hide other themes" : "View other themes"}
          <ChevronRight className={`w-3 h-3 transition-transform ${showingOther ? "rotate-90" : ""}`} />
        </button>
      </div>
    </div>
  );
};

export default RecommendedStyleCard;
