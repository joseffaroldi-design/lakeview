import React, { useEffect, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Sprint 20A — Today's Special hero band.
// Surfaces the daily-rotated bulk-rendered flyer to the homepage.
// Renders nothing if there are no bulk flyers in the library yet.
export default function TodaysFeatured({ titleOverride, bodyOverride }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    axios.get(`${API}/html-template/featured`).then((r) => {
      if (!cancelled) setData(r.data);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (!data || !data.image_url) return null;

  const fullUrl = `${process.env.REACT_APP_BACKEND_URL}${data.image_url}`;

  return (
    <section
      data-testid="todays-featured-section"
      className="relative py-12 md:py-16 bg-gradient-to-b from-navy via-navy/95 to-cream"
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-8 md:gap-12 items-center">
          {/* Left — copy block */}
          <div className="text-center md:text-left">
            <p className="font-accent text-gold text-base tracking-[0.4em] uppercase mb-3">
              {titleOverride || "Today's Special"}
            </p>
            <h2
              data-testid="todays-featured-name"
              className="font-display text-4xl md:text-5xl lg:text-6xl text-cream mb-4 leading-tight"
            >
              {data.item_name}
            </h2>
            <p className="text-cream/80 text-base md:text-lg max-w-md mx-auto md:mx-0 mb-6">
              {bodyOverride || "Hand-picked from the kitchen — fresh today, gone tomorrow. Visit the menu for tonight's full lineup."}
            </p>
            <a
              href="#menu"
              data-testid="todays-featured-cta"
              className="inline-block rounded-full bg-gold text-navy px-8 py-3 font-semibold tracking-wider uppercase text-sm hover:bg-gold/90 shadow-lg hover:shadow-xl transition-all hover:scale-105"
            >
              See the Menu
            </a>
          </div>

          {/* Right — flyer */}
          <div className="relative">
            <div className="absolute -inset-4 rounded-3xl bg-gold/20 blur-2xl"></div>
            <img
              src={fullUrl}
              alt={`Today's Special — ${data.item_name}`}
              loading="lazy"
              data-testid="todays-featured-image"
              className="relative w-[280px] md:w-[360px] aspect-square rounded-2xl shadow-2xl border-4 border-gold/40 bg-navy/40"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
