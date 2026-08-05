import React, { useState, useEffect } from "react";
import axios from "axios";
import { API } from "@/lib/publicConfig";

// Specials Section
const Specials = ({ titleOverride, bodyOverride }) => {
  const [specials, setSpecials] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSpecials = async () => {
      try {
        const response = await axios.get(`${API}/specials?active_only=true`);
        setSpecials(response.data);
      } catch (error) {
        console.error("Error fetching specials:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchSpecials();
  }, []);

  if (loading || specials.length === 0) {
    return null;
  }

  return (
    <section 
      id="specials" 
      data-testid="specials-section"
      className="py-24 md:py-32 bg-navy"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <p className="font-accent text-3xl text-gold mb-2">Don&apos;t Miss</p>
          <h2 className="font-serif text-4xl md:text-5xl text-cream font-bold tracking-tight mb-4">
            {titleOverride || "Today\u2019s Specials"}
          </h2>
          {bodyOverride ? (
            <p className="font-sans text-cream/80 max-w-2xl mx-auto mb-4 text-sm md:text-base">{bodyOverride}</p>
          ) : null}
          <div className="w-24 h-1 mx-auto" style={{ background: 'linear-gradient(90deg, transparent, #a5935b, transparent)' }}></div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {specials.map((special) => (
            <div 
              key={special.id}
              className="bg-cream rounded-sm overflow-hidden vintage-shadow transition-transform hover:scale-105"
              data-testid={`special-display-${special.id}`}
            >
              {special.image_url && (
                <div className="h-48 overflow-hidden">
                  <img 
                    src={special.image_url} 
                    alt={special.title}
                    className="w-full h-full object-cover"
                    loading="lazy"
                    decoding="async"
                  />
                </div>
              )}
              <div className="p-6">
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-serif text-xl text-navy font-bold">{special.title}</h3>
                  {special.price && (
                    <span className="font-sans font-bold text-forest text-lg">{special.price}</span>
                  )}
                </div>
                <p className="font-sans text-muted-foreground">{special.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Specials;
