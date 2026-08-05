import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Phone, ExternalLink } from "lucide-react";
import { trackButtonClick } from "@/lib/analytics";

// Sticky Order Bar - appears when scrolled past hero
const StickyOrderBar = () => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setVisible(window.scrollY > window.innerHeight * 0.8);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  if (!visible) return null;

  return (
    <div
      data-testid="sticky-order-bar"
      className="fixed bottom-0 left-0 right-0 z-50 bg-navy/95 backdrop-blur-md border-t border-gold/30 py-3 px-4 transition-transform duration-300"
      style={{ transform: visible ? "translateY(0)" : "translateY(100%)" }}
    >
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">
        <span className="hidden sm:block font-serif text-cream text-sm">
          Ready to order?
        </span>
        <div className="flex items-center gap-3 w-full sm:w-auto justify-center">
          <Button
            data-testid="sticky-uber-eats-btn"
            asChild
            className="rounded-full bg-forest text-cream hover:bg-forest/90 text-sm px-6 py-2.5 h-auto font-semibold shadow-lg transition-all duration-300 hover:scale-105"
          >
            <a
              href="https://www.ubereats.com/store-browse-uuid/de2b0e6b-0fdf-44bc-92e9-2c223008bd36?diningMode=DELIVERY"
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackButtonClick("uber_eats_sticky")}
            >
              <ExternalLink className="w-4 h-4 mr-1.5" />
              Uber Eats
            </a>
          </Button>
          <Button
            data-testid="sticky-square-btn"
            asChild
            className="rounded-full bg-gold text-navy hover:bg-gold/90 text-sm px-6 py-2.5 h-auto font-semibold shadow-lg transition-all duration-300 hover:scale-105"
          >
            <a
              href="https://lakeview-burgers-seafood.square.site"
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackButtonClick("square_sticky")}
            >
              <ExternalLink className="w-4 h-4 mr-1.5" />
              Square
            </a>
          </Button>
          <Button
            data-testid="sticky-call-btn"
            asChild
            className="rounded-full bg-cream text-navy hover:bg-cream/90 text-sm px-6 py-2.5 h-auto font-semibold shadow-lg transition-all duration-300 hover:scale-105"
          >
            <a
              href="tel:+15042891032"
              onClick={() => trackButtonClick("call_now_sticky")}
            >
              <Phone className="w-4 h-4 mr-1.5" />
              Call Now
            </a>
          </Button>
        </div>
      </div>
    </div>
  );
};

export default StickyOrderBar;
