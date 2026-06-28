import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import {
  ArrowDown, ArrowUp, Eye, EyeOff, GripVertical, Loader2,
  Pencil, RotateCcw, Save,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Sprint 22C — Homepage Layout Editor.
 *
 * Lets the admin reorder, show/hide, and override the title/body of
 * every public-homepage section. Nothing ships to visitors until
 * "Save layout" is clicked — the local working copy lives in state
 * until then.
 */
export default function LayoutTab({ getAuthHeader }) {
  const [sections, setSections] = useState([]);
  const [savedSections, setSavedSections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);
  const [expandedKey, setExpandedKey] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await axios.get(`${API}/homepage/layout`);
      setSections(r.data.sections);
      setSavedSections(JSON.parse(JSON.stringify(r.data.sections)));
    } catch (e) {
      console.error("[LayoutTab] load failed", e);
      setError("Couldn't load the homepage layout. Refresh and try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const dirty = JSON.stringify(sections) !== JSON.stringify(savedSections);

  const move = (idx, direction) => {
    const next = [...sections];
    const target = idx + direction;
    if (target < 0 || target >= next.length) return;
    [next[idx], next[target]] = [next[target], next[idx]];
    setSections(next);
  };

  const toggleVisible = (idx) => {
    const next = [...sections];
    next[idx] = { ...next[idx], visible: !next[idx].visible };
    setSections(next);
  };

  const updateField = (idx, field, value) => {
    const next = [...sections];
    next[idx] = { ...next[idx], [field]: value };
    setSections(next);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        sections: sections.map((s) => ({
          key: s.key,
          visible: s.visible,
          title: s.title || "",
          body: s.body || "",
        })),
      };
      const r = await axios.put(`${API}/homepage/layout`, payload, {
        headers: getAuthHeader(),
      });
      setSections(r.data.sections);
      setSavedSections(JSON.parse(JSON.stringify(r.data.sections)));
      setToast({ type: "success", message: "Layout saved. Public site updates instantly." });
      setTimeout(() => setToast(null), 4000);
    } catch (e) {
      console.error("[LayoutTab] save failed", e);
      const msg = e?.response?.data?.detail || "Couldn't save. Try again.";
      setError(typeof msg === "string" ? msg : "Couldn't save.");
    } finally {
      setSaving(false);
    }
  };

  const handleDiscard = () => {
    setSections(JSON.parse(JSON.stringify(savedSections)));
    setExpandedKey(null);
  };

  const handleReset = async () => {
    if (!window.confirm("Reset to the default layout? This clears every title/body override and restores the original order.")) return;
    setSaving(true);
    setError(null);
    try {
      const r = await axios.post(`${API}/homepage/layout/reset`, {}, {
        headers: getAuthHeader(),
      });
      setSections(r.data.sections);
      setSavedSections(JSON.parse(JSON.stringify(r.data.sections)));
      setToast({ type: "success", message: "Layout reset to defaults." });
      setTimeout(() => setToast(null), 4000);
    } catch (e) {
      console.error("[LayoutTab] reset failed", e);
      setError("Couldn't reset. Try again.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="py-16 text-center text-sm text-navy/50" data-testid="layout-tab-loading">
        <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
        Loading layout…
      </div>
    );
  }

  return (
    <section data-testid="layout-tab" className="space-y-6">
      <header>
        <p className="ds-eyebrow mb-1">Public site</p>
        <h2 className="ds-display text-3xl sm:text-4xl">Homepage Layout</h2>
        <p className="text-sm text-navy/60 mt-2 max-w-2xl">
          Reorder, show/hide, or rewrite the title and intro paragraph
          for any section on your public homepage. Visitors see nothing
          until you click <strong>Save layout</strong>.
        </p>
      </header>

      {error ? (
        <div
          data-testid="layout-error"
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {error}
        </div>
      ) : null}

      {toast ? (
        <div
          data-testid="layout-toast"
          className={`rounded-md border px-4 py-3 text-sm ${
            toast.type === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-red-200 bg-red-50 text-red-800"
          }`}
        >
          {toast.message}
        </div>
      ) : null}

      <ol data-testid="layout-section-list" className="space-y-2">
        {sections.map((s, idx) => {
          const isExpanded = expandedKey === s.key;
          const hidden = s.visible === false;
          const hasOverride = (s.title && s.title.length) || (s.body && s.body.length);

          return (
            <li
              key={s.key}
              data-testid={`layout-row-${s.key}`}
              className={`rounded-md border bg-card transition-colors ${
                hidden ? "border-dashed border-navy/15 opacity-60" : "border-navy/10"
              }`}
            >
              <div className="flex items-center gap-2 p-3">
                <GripVertical className="w-4 h-4 text-navy/30 shrink-0" />

                <div className="flex flex-col gap-0.5 shrink-0">
                  <button
                    data-testid={`layout-row-${s.key}-up`}
                    type="button"
                    onClick={() => move(idx, -1)}
                    disabled={idx === 0}
                    className="p-1 rounded hover:bg-navy/5 disabled:opacity-25 disabled:cursor-not-allowed"
                    aria-label={`Move ${s.label} up`}
                  >
                    <ArrowUp className="w-3.5 h-3.5 text-navy/70" />
                  </button>
                  <button
                    data-testid={`layout-row-${s.key}-down`}
                    type="button"
                    onClick={() => move(idx, +1)}
                    disabled={idx === sections.length - 1}
                    className="p-1 rounded hover:bg-navy/5 disabled:opacity-25 disabled:cursor-not-allowed"
                    aria-label={`Move ${s.label} down`}
                  >
                    <ArrowDown className="w-3.5 h-3.5 text-navy/70" />
                  </button>
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-sans font-semibold text-navy text-sm truncate">
                      {s.label}
                    </span>
                    {hasOverride ? (
                      <span className="text-[10px] uppercase tracking-wider bg-gold/15 text-gold-foreground rounded-full px-2 py-0.5 border border-gold/30" style={{ color: "#8a7d3a" }}>
                        Custom copy
                      </span>
                    ) : null}
                    {hidden ? (
                      <span className="text-[10px] uppercase tracking-wider bg-navy/10 text-navy/60 rounded-full px-2 py-0.5">
                        Hidden
                      </span>
                    ) : null}
                  </div>
                  {s.note ? (
                    <p className="text-xs text-navy/50 mt-0.5 truncate">{s.note}</p>
                  ) : null}
                </div>

                <button
                  data-testid={`layout-row-${s.key}-toggle-visible`}
                  type="button"
                  onClick={() => toggleVisible(idx)}
                  className="ds-btn-secondary !py-1.5 !px-3 text-xs"
                  aria-label={hidden ? `Show ${s.label}` : `Hide ${s.label}`}
                >
                  {hidden ? (
                    <>
                      <EyeOff className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Hidden</span>
                    </>
                  ) : (
                    <>
                      <Eye className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Visible</span>
                    </>
                  )}
                </button>

                <button
                  data-testid={`layout-row-${s.key}-edit-toggle`}
                  type="button"
                  onClick={() => setExpandedKey(isExpanded ? null : s.key)}
                  className="ds-btn-secondary !py-1.5 !px-3 text-xs"
                  aria-expanded={isExpanded}
                >
                  <Pencil className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">{isExpanded ? "Close" : "Edit copy"}</span>
                </button>
              </div>

              {isExpanded ? (
                <div className="border-t border-navy/10 p-4 space-y-3 bg-navy/[0.02]">
                  {s.supports_title ? (
                    <div>
                      <label className="block text-xs font-semibold text-navy/70 uppercase tracking-wider mb-1">
                        Section title override
                      </label>
                      <input
                        data-testid={`layout-row-${s.key}-title-input`}
                        type="text"
                        value={s.title || ""}
                        onChange={(e) => updateField(idx, "title", e.target.value)}
                        placeholder="Leave blank to use the default"
                        className="w-full px-3 py-2 border border-navy/15 rounded-md text-sm font-sans focus:outline-none focus:ring-2 focus:ring-gold/40"
                      />
                    </div>
                  ) : null}

                  {s.supports_body ? (
                    <div>
                      <label className="block text-xs font-semibold text-navy/70 uppercase tracking-wider mb-1">
                        Intro paragraph override
                      </label>
                      <textarea
                        data-testid={`layout-row-${s.key}-body-input`}
                        rows={3}
                        value={s.body || ""}
                        onChange={(e) => updateField(idx, "body", e.target.value)}
                        placeholder="Leave blank to use the default"
                        className="w-full px-3 py-2 border border-navy/15 rounded-md text-sm font-sans focus:outline-none focus:ring-2 focus:ring-gold/40"
                      />
                    </div>
                  ) : null}

                  <p className="text-xs text-navy/50">
                    Tip: keep the title short (3–6 words). The intro paragraph appears just under the heading.
                  </p>
                </div>
              ) : null}
            </li>
          );
        })}
      </ol>

      <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-navy/10">
        <button
          data-testid="layout-reset-btn"
          type="button"
          onClick={handleReset}
          disabled={saving}
          className="ds-btn-secondary text-xs"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          Reset to defaults
        </button>

        <div className="flex items-center gap-2 ml-auto">
          {dirty ? (
            <span data-testid="layout-dirty-flag" className="text-xs text-navy/60">
              You have unsaved changes
            </span>
          ) : (
            <span className="text-xs text-navy/40">All changes saved</span>
          )}

          <button
            data-testid="layout-discard-btn"
            type="button"
            onClick={handleDiscard}
            disabled={!dirty || saving}
            className="ds-btn-secondary text-xs"
          >
            Discard
          </button>

          <button
            data-testid="layout-save-btn"
            type="button"
            onClick={handleSave}
            disabled={!dirty || saving}
            className="ds-btn-primary text-xs"
          >
            {saving ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Saving…
              </>
            ) : (
              <>
                <Save className="w-3.5 h-3.5" />
                Save layout
              </>
            )}
          </button>
        </div>
      </div>
    </section>
  );
}
