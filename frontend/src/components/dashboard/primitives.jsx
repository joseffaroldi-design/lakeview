/**
 * Dashboard shared primitives (Sprint 22 — Phase 3).
 *
 * These components consolidate patterns repeated across dashboard tabs and
 * are pure visual wrappers around the `.dashboard-shell` design tokens
 * introduced in Sprint 21. NO new behaviour — these are extract-only.
 *
 * Components:
 *   - PageHeader   — eyebrow + display title + optional subtitle + actions
 *   - StatTile     — small label/value card with optional icon
 *   - EmptyState   — dashed-border placeholder with message + optional icon
 *   - LoadingState — spinner + message inside an ds-empty container
 *
 * Public restaurant site is unaffected — these components rely on the
 * `.dashboard-shell` scope, which only wraps the owner dashboard.
 */
import React from "react";
import { Loader2 } from "lucide-react";

/** PageHeader — used at the top of every dashboard tab. */
export const PageHeader = ({
  eyebrow,
  title,
  subtitle,
  actions,
  testId,
}) => (
  <header
    className="mb-8 flex items-end justify-between gap-4 flex-wrap"
    data-testid={testId}
  >
    <div className="min-w-0">
      {eyebrow ? <p className="ds-eyebrow mb-1">{eyebrow}</p> : null}
      <h2 className="ds-display text-3xl sm:text-4xl leading-tight">{title}</h2>
      {subtitle ? (
        <p className="text-sm text-navy/60 mt-2 max-w-xl">{subtitle}</p>
      ) : null}
    </div>
    {actions ? <div className="shrink-0 flex items-center gap-2">{actions}</div> : null}
  </header>
);

/** StatTile — small KPI card with icon + label + value. */
export const StatTile = ({
  label,
  value,
  icon: Icon,
  tone = "navy",
  testId,
}) => {
  const wrapTone =
    tone === "gold" ? "bg-gold/12 text-gold"
    : tone === "red"  ? "bg-red-50 text-red-700"
    : "bg-navy/8 text-navy";
  const valueTone = tone === "red" ? "text-red-700" : "text-navy";
  return (
    <div className="ds-card p-4 flex items-center gap-3" data-testid={testId}>
      {Icon ? (
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${wrapTone}`}>
          <Icon className="w-5 h-5" />
        </div>
      ) : null}
      <div className="min-w-0">
        <p className="text-[10px] uppercase tracking-wider text-navy/55 font-semibold">{label}</p>
        <p
          className={`text-2xl font-semibold leading-tight ${valueTone}`}
          style={{ fontFamily: "Outfit, system-ui, sans-serif" }}
        >
          {value}
        </p>
      </div>
    </div>
  );
};

/** EmptyState — dashed placeholder with optional icon + CTA. */
export const EmptyState = ({
  icon: Icon,
  title,
  message,
  action,
  testId,
}) => (
  <div className="ds-empty" data-testid={testId}>
    {Icon ? <Icon className="w-7 h-7 text-navy/30 mx-auto mb-3" /> : null}
    {title ? (
      <p className="text-sm font-semibold text-navy mb-1">{title}</p>
    ) : null}
    {message ? <p className="text-sm text-navy/55">{message}</p> : null}
    {action ? <div className="mt-4 inline-flex">{action}</div> : null}
  </div>
);

/** LoadingState — spinner + message inside an ds-empty container. */
export const LoadingState = ({ message = "Loading…", testId }) => (
  <div className="ds-empty" data-testid={testId}>
    <Loader2 className="w-5 h-5 animate-spin inline mr-2 text-navy/40" />
    <span className="text-sm text-navy/55">{message}</span>
  </div>
);
