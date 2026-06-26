/**
 * Sprint 17A — CreativeDirectorRecs
 *
 * Renders the top-3 theme recommendations as a compact horizontal strip:
 *   ★★★★★ Best Match   ★★★★ Good Match   ★★★ Alternative
 * Each card shows the theme label, a single-line reason, and a "Use" CTA.
 * Includes a "View All Themes" toggle that delegates to a child render
 * prop so the parent can swap in the full grouped picker.
 *
 * Props:
 *   recs              – array of {id, label, rank, stars, reason, preview_color, pack_label}
 *   context           – { has_memory, memory_theme, category, holiday, ... }
 *   value             – currently-selected theme id
 *   onPick(theme_id)  – called when the owner clicks a recommendation
 *   renderAll         – render-prop returning the full grouped picker
 */
import React, { useState } from "react";
import { Star, Sparkles, ChevronDown, ChevronUp } from "lucide-react";

const Stars = ({ n }) => (
  <span className="inline-flex items-center gap-0.5 text-gold" aria-label={`${n} stars`}>
    {Array.from({ length: 5 }).map((_, i) => (
      <Star
        key={i}
        className={`w-3 h-3 ${i < n ? "fill-gold text-gold" : "text-navy/20"}`}
        strokeWidth={1.5}
      />
    ))}
  </span>
);

const CreativeDirectorRecs = ({ recs, context, value, onPick, renderAll }) => {
  const [showAll, setShowAll] = useState(false);

  if (!recs || recs.length === 0) {
    return (
      <div className="text-xs text-navy/60" data-testid="cd-recs-empty">
        Theme recommendations unavailable — pick one manually below.
      </div>
    );
  }

  return (
    <div className="space-y-2" data-testid="cd-recs">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-navy/70 flex items-center gap-1.5">
          <Sparkles className="w-3 h-3 text-gold" />
          Recommended themes
          {context?.has_memory ? (
            <span
              className="ml-1 inline-block text-[9px] font-semibold uppercase tracking-wider text-gold bg-gold/10 border border-gold/30 rounded-full px-1.5 py-0.5"
              data-testid="cd-recs-memory-pill"
            >
              from saved style
            </span>
          ) : null}
        </p>
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          className="text-[11px] text-gold hover:underline inline-flex items-center gap-1"
          data-testid="cd-recs-toggle-all"
        >
          {showAll ? "Hide all themes" : "View all themes"}
          {showAll ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2" data-testid="cd-recs-grid">
        {recs.map((rec) => {
          const selected = value === rec.id;
          return (
            <button
              key={rec.id}
              type="button"
              onClick={() => onPick(rec.id)}
              aria-pressed={selected}
              className={`text-left rounded-md border p-2.5 transition-colors flex flex-col gap-1 ${
                selected
                  ? "border-gold bg-gold/15 ring-2 ring-gold/40"
                  : "border-navy/15 hover:border-gold/50 bg-white"
              }`}
              data-testid={`cd-rec-${rec.id}`}
            >
              <div className="flex items-center justify-between">
                <span
                  className="inline-block w-4 h-4 rounded-full border border-navy/20 shrink-0"
                  style={{ backgroundColor: rec.preview_color || "#999" }}
                />
                <Stars n={rec.stars || 3} />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider font-semibold text-navy/60">
                  {rec.rank}
                </p>
                <p className="text-sm font-semibold text-navy leading-tight truncate">
                  {rec.label}
                </p>
                {rec.pack_label ? (
                  <p className="text-[10px] text-navy/50 truncate">{rec.pack_label}</p>
                ) : null}
              </div>
              <p
                className="text-[11px] text-navy/70 leading-snug line-clamp-2"
                data-testid={`cd-rec-reason-${rec.id}`}
              >
                {rec.reason}
              </p>
            </button>
          );
        })}
      </div>

      {showAll && renderAll ? (
        <div className="pt-2" data-testid="cd-recs-all-themes">
          {renderAll()}
        </div>
      ) : null}
    </div>
  );
};

export default CreativeDirectorRecs;
