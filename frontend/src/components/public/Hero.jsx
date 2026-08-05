import React from "react";
import { Button } from "@/components/ui/button";
import { ChevronDown } from "lucide-react";
import { LOGO, HERO_BG } from "@/lib/publicConfig";
import { trackButtonClick } from "@/lib/analytics";

// Hero Section
const Hero = ({ content, titleOverride, bodyOverride }) => {
  const scrollToMenu = () => {
    trackButtonClick("view_menu");
    const element = document.getElementById("menu");
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
  };

  const handleUberEatsClick = () => {
    trackButtonClick("uber_eats");
  };

  const handleSquareClick = () => {
    trackButtonClick("square");
  };

  return (
    <section 
      id="hero" 
      data-testid="hero-section"
      className="relative min-h-[75vh] flex items-center justify-center hero-bg"
      style={{ backgroundImage: `url(${HERO_BG})`, backgroundPosition: "center 40%" }}
    >
      <div className="absolute inset-0 bg-navy/60"></div>
      
      <div className="relative z-10 text-center px-4 max-w-4xl mx-auto pt-16 md:pt-20">
        <div className="animate-fade-in-up">
          <img 
            src={LOGO} 
            alt="Lakeview Burgers & Seafood" 
            data-testid="hero-logo"
            className="w-[280px] md:w-[380px] max-w-full mx-auto mb-2 drop-shadow-2xl"
            fetchPriority="high"
          />
        </div>

        {/* SEO H1 — visually hidden but read by Google + screen readers */}
        <h1 className="sr-only">
          Lakeview Burgers &amp; Seafood — Family-owned restaurant in New Orleans serving the finest burgers and fresh Gulf seafood since 2015
        </h1>
        
        <p className="font-accent text-2xl md:text-3xl text-gold mb-1 md:mb-2 animate-fade-in-up animation-delay-200">
          {titleOverride || content?.tagline || "Lakeview"}
        </p>
        
        <p className="font-sans text-sm md:text-base text-cream/90 mb-4 md:mb-5 max-w-2xl mx-auto animate-fade-in-up animation-delay-400">
          {bodyOverride || content?.subtitle || "Serving the finest burgers and fresh Gulf seafood in the heart of New Orleans since 2015"}
        </p>
        
        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center animate-fade-in-up animation-delay-600">
          <Button
            data-testid="hero-view-menu-btn"
            onClick={scrollToMenu}
            className="rounded-full bg-gold text-navy hover:bg-gold/90 text-base md:text-lg px-8 md:px-12 py-5 md:py-6 h-auto font-semibold shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105"
          >
            View Our Menu
          </Button>
          <Button
            data-testid="hero-uber-eats-btn"
            asChild
            className="rounded-full bg-forest text-cream hover:bg-forest/90 text-base md:text-lg px-8 md:px-12 py-5 md:py-6 h-auto font-semibold shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105"
          >
            <a href="https://www.ubereats.com/store-browse-uuid/de2b0e6b-0fdf-44bc-92e9-2c223008bd36?diningMode=DELIVERY" target="_blank" rel="noopener noreferrer" onClick={handleUberEatsClick}>
              Order on Uber Eats
            </a>
          </Button>
          <Button
            data-testid="hero-square-btn"
            asChild
            className="rounded-full bg-cream text-navy hover:bg-cream/90 text-base md:text-lg px-8 md:px-12 py-5 md:py-6 h-auto font-semibold shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105"
          >
            <a href="https://lakeview-burgers-seafood.square.site" target="_blank" rel="noopener noreferrer" onClick={handleSquareClick}>
              Order on Square
            </a>
          </Button>
        </div>
        
        <div className="absolute bottom-8 left-1/2 transform -translate-x-1/2 animate-bounce">
          <ChevronDown className="w-8 h-8 text-cream/70" />
        </div>
      </div>
    </section>
  );
};

export default Hero;
