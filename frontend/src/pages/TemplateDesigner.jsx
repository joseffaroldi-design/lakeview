import React, { useState, useCallback, useEffect, useRef } from "react";
import axios from "axios";
import { Link } from "react-router-dom";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Sprint 20A — Template Designer
// Live preview of the HTML/CSS flyer engine. Designer picks a theme,
// edits the item payload, hits "Render" and sees the resulting PNG in
// ~1.5s. Front-end-only — backend code is unchanged.

const DEFAULT_FEATURES = ["Smash Patty", "American Cheese", "House Pickles"];

const PRESETS = {
  cajun:   { name: "Smash Burger",       price: "$11.00", cta: "Order Now · Mon-Sat 11-9",
             features: ["Smash Patty", "American Cheese", "House Pickles"] },
  seafood: { name: "Shrimp Po-Boy",      price: "$14.50", cta: "Catch of the Day · Til 9pm",
             features: ["Fried Gulf Shrimp", "House Remoulade", "Pickled Slaw"] },
  luxury:  { name: "Wagyu Filet Mignon", price: "$48.00", cta: "Chef's Selection · Reserve a Table",
             features: ["8oz Prime Cut", "House Demi-Glace", "Roasted Shallots"] },
};

export default function TemplateDesigner() {
  const [themes, setThemes] = useState(["cajun", "seafood", "luxury"]);
  const [theme, setTheme] = useState("luxury");
  const [itemName, setItemName] = useState(PRESETS.luxury.name);
  const [price, setPrice] = useState(PRESETS.luxury.price);
  const [cta, setCta] = useState(PRESETS.luxury.cta);
  const [features, setFeatures] = useState(PRESETS.luxury.features);
  const [imageUrl, setImageUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [renderMs, setRenderMs] = useState(null);
  const lastBlobUrl = useRef(null);

  // Fetch supported themes on mount
  useEffect(() => {
    axios.get(`${API}/html-template/themes`).then((r) => {
      if (r.data?.themes?.length) {
        const visible = Array.from(new Set(
          r.data.themes.map((t) => {
            const k = t.toLowerCase();
            if (k.startsWith("cajun")) return "cajun";
            if (k.startsWith("luxury")) return "luxury";
            if (k.startsWith("seafood")) return "seafood";
            return t;
          })
        ));
        setThemes(visible);
      }
    }).catch(() => {});
  }, []);

  // When the theme changes, hydrate the preset.
  const switchTheme = (t) => {
    setTheme(t);
    const p = PRESETS[t];
    if (p) {
      setItemName(p.name);
      setPrice(p.price);
      setCta(p.cta);
      setFeatures(p.features);
    }
  };

  const render = useCallback(async () => {
    setLoading(true);
    setError(null);
    const t0 = performance.now();
    try {
      const resp = await axios.post(`${API}/html-template/preview`, {
        theme,
        item_name: itemName,
        features: features.filter((f) => f && f.trim()),
        price,
        cta,
        output_size: 1024,
        render_size: 2048,
      }, { responseType: "blob" });
      if (lastBlobUrl.current) URL.revokeObjectURL(lastBlobUrl.current);
      const url = URL.createObjectURL(resp.data);
      lastBlobUrl.current = url;
      setImageUrl(url);
      setRenderMs(Math.round(performance.now() - t0));
    } catch (e) {
      setError(
        e?.response?.data?.detail
        || e?.message
        || "Render failed. Check backend logs."
      );
    } finally {
      setLoading(false);
    }
  }, [theme, itemName, price, cta, features]);

  // Render once on first mount.
  useEffect(() => { render(); /* eslint-disable-next-line */ }, []);

  // Clean up blob on unmount
  useEffect(() => () => {
    if (lastBlobUrl.current) URL.revokeObjectURL(lastBlobUrl.current);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100" data-testid="template-designer-page">
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-amber-400 text-2xl font-serif font-bold tracking-widest">
              LAKEVIEW
            </span>
            <span className="text-slate-500 text-xs uppercase tracking-widest pl-2 border-l border-slate-700">
              Template Designer
            </span>
          </div>
          <Link to="/dashboard" className="text-sm text-slate-400 hover:text-amber-400 transition" data-testid="back-to-dashboard">
            ← Back to Dashboard
          </Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-[400px_1fr] gap-8">
        {/* ----- Control panel ----- */}
        <aside className="space-y-5">
          <Field label="Theme">
            <div className="flex gap-2 flex-wrap" data-testid="theme-picker">
              {themes.map((t) => (
                <button
                  key={t}
                  onClick={() => switchTheme(t)}
                  data-testid={`theme-${t}`}
                  className={`px-4 py-2 rounded-full border text-sm uppercase tracking-wider transition ${
                    theme === t
                      ? "bg-amber-400 text-slate-950 border-amber-400 font-semibold"
                      : "bg-slate-900 text-slate-300 border-slate-700 hover:border-amber-400"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </Field>

          <Field label="Item name">
            <input
              value={itemName}
              onChange={(e) => setItemName(e.target.value)}
              data-testid="item-name-input"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-base focus:border-amber-400 focus:outline-none"
            />
          </Field>

          <Field label="Price">
            <input
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              data-testid="price-input"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-base focus:border-amber-400 focus:outline-none"
            />
          </Field>

          <Field label="CTA">
            <input
              value={cta}
              onChange={(e) => setCta(e.target.value)}
              data-testid="cta-input"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-base focus:border-amber-400 focus:outline-none"
            />
          </Field>

          <Field label="Features (up to 4)">
            <div className="space-y-2">
              {[0, 1, 2, 3].map((i) => (
                <input
                  key={i}
                  value={features[i] || ""}
                  onChange={(e) => {
                    const next = features.slice();
                    next[i] = e.target.value;
                    setFeatures(next);
                  }}
                  data-testid={`feature-input-${i}`}
                  placeholder={i === 0 ? "First chip" : `Chip ${i + 1}`}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:border-amber-400 focus:outline-none"
                />
              ))}
            </div>
          </Field>

          <button
            onClick={render}
            disabled={loading}
            data-testid="render-button"
            className="w-full py-3 rounded-full bg-amber-400 text-slate-950 font-bold uppercase tracking-widest text-sm hover:bg-amber-300 disabled:opacity-50 disabled:cursor-wait transition"
          >
            {loading ? "Rendering…" : "Render Flyer"}
          </button>

          {renderMs !== null && (
            <p className="text-xs text-slate-500" data-testid="render-time">
              Last render: <span className="text-amber-400">{renderMs}&nbsp;ms</span>
            </p>
          )}

          {error && (
            <div className="text-sm text-rose-400 bg-rose-950/40 border border-rose-900 rounded-lg p-3" data-testid="render-error">
              {error}
            </div>
          )}

          <p className="text-xs text-slate-500 leading-relaxed pt-4 border-t border-slate-800">
            Live previews use the HTML/CSS engine
            (<code className="text-amber-400">html_renderer</code>).
            Each render produces a 2048×2048 internal canvas downscaled to
            1024×1024 PNG. Edit the source template at
            <br />
            <code className="text-slate-400">
              backend/html_renderer/templates/&lt;theme&gt;.html
            </code>
            <br />and the next render reflects your changes (no restart).
          </p>
        </aside>

        {/* ----- Preview panel ----- */}
        <section className="rounded-2xl bg-slate-900/40 border border-slate-800 p-6 flex items-center justify-center min-h-[640px]">
          {imageUrl ? (
            <img
              src={imageUrl}
              alt="Flyer preview"
              data-testid="flyer-preview"
              className="max-w-full max-h-[840px] rounded-xl shadow-2xl"
            />
          ) : (
            <div className="text-slate-500 text-center">
              {loading ? "Rendering first preview…" : "Click Render Flyer to begin."}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <div className="text-[11px] uppercase tracking-widest text-slate-400 mb-2">
        {label}
      </div>
      {children}
    </label>
  );
}
