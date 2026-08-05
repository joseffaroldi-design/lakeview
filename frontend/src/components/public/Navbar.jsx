import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Phone, Settings, Menu as MenuIcon, X } from "lucide-react";
import { LOGO } from "@/lib/publicConfig";

// Navbar Component
const Navbar = () => {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToSection = (id) => {
    setMobileOpen(false);
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
  };

  const navItems = [
    { id: "about", label: "About", testId: "nav-about" },
    { id: "specials", label: "Specials", testId: "nav-specials" },
    { id: "menu", label: "Menu", testId: "nav-menu" },
    { id: "catering", label: "Catering", testId: "nav-catering" },
    { id: "contact", label: "Contact", testId: "nav-contact" },
  ];

  return (
    <nav 
      data-testid="navbar"
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled || mobileOpen ? "navbar-scrolled py-3" : "bg-transparent py-6"
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          <button 
            data-testid="nav-logo"
            onClick={() => scrollToSection("hero")}
            className="flex items-center space-x-2 transition-transform hover:scale-105"
          >
            <img src={LOGO} alt="Lakeview Burgers & Seafood" className="h-12 w-auto" />
          </button>
          
          <div className="hidden md:flex items-center space-x-12">
            {navItems.map((item) => (
              <button
                key={item.id}
                data-testid={item.testId}
                onClick={() => scrollToSection(item.id)}
                className={`nav-link font-serif text-sm uppercase tracking-widest transition-colors ${
                  scrolled ? "text-navy" : "text-white"
                } hover:text-gold`}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <Button
              data-testid="nav-call-btn"
              variant="outline"
              asChild
              className={`hidden sm:flex items-center gap-2 border-2 ${
                scrolled 
                  ? "border-navy text-navy hover:bg-navy hover:text-cream" 
                  : "border-white text-white hover:bg-white hover:text-navy"
              } transition-all duration-300`}
            >
              <a href="tel:+15042891032">
                <Phone className="w-4 h-4" />
                <span className="font-sans text-sm">Call Us</span>
              </a>
            </Button>
            <Link to="/dashboard" data-testid="nav-dashboard">
              <Button
                variant="ghost"
                size="icon"
                className={`${scrolled || mobileOpen ? "text-navy hover:text-gold" : "text-white hover:text-gold"}`}
              >
                <Settings className="w-5 h-5" />
              </Button>
            </Link>
            {/* Mobile hamburger toggle */}
            <Button
              data-testid="mobile-menu-toggle"
              variant="ghost"
              size="icon"
              onClick={() => setMobileOpen((v) => !v)}
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
              aria-expanded={mobileOpen}
              className={`md:hidden ${scrolled || mobileOpen ? "text-navy hover:text-gold" : "text-white hover:text-gold"}`}
            >
              {mobileOpen ? <X className="w-6 h-6" /> : <MenuIcon className="w-6 h-6" />}
            </Button>
          </div>
        </div>

        {/* Mobile menu drawer */}
        {mobileOpen && (
          <div
            data-testid="mobile-menu-drawer"
            className="md:hidden mt-4 pb-4 border-t border-navy/10 animate-fade-in"
          >
            <div className="flex flex-col space-y-1 pt-4">
              {navItems.map((item) => (
                <button
                  key={item.id}
                  data-testid={`${item.testId}-mobile`}
                  onClick={() => scrollToSection(item.id)}
                  className="text-left font-serif text-base uppercase tracking-widest text-navy hover:text-gold py-3 px-2 transition-colors"
                >
                  {item.label}
                </button>
              ))}
              <a
                data-testid="nav-call-btn-mobile"
                href="tel:+15042891032"
                className="flex items-center gap-2 font-serif text-base uppercase tracking-widest text-navy hover:text-gold py-3 px-2 transition-colors"
              >
                <Phone className="w-4 h-4" />
                Call Us
              </a>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
};

export default Navbar;
