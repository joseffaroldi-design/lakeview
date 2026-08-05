import React from "react";
import { LOGO } from "@/lib/publicConfig";

// Footer
const Footer = () => {
  return (
    <footer data-testid="footer" className="bg-navy border-t border-gold/20 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <img src={LOGO} alt="Lakeview" className="h-10 w-auto" loading="lazy" decoding="async" />
          </div>
          <p className="font-sans text-sm text-cream/60 text-center">
            © {new Date().getFullYear()} Lakeview Burgers & Seafood. All rights reserved.
          </p>
          <div className="flex items-center space-x-3">
            <a
              href="https://www.facebook.com/lakeviewburgers"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Lakeview on Facebook"
              data-testid="footer-facebook"
              className="text-cream/70 hover:text-gold transition-colors p-2 rounded-full border border-gold/20 hover:border-gold"
            >
              <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor" aria-hidden="true">
                <path d="M22 12.07C22 6.5 17.52 2 12 2S2 6.5 2 12.07c0 5 3.66 9.13 8.44 9.93v-7.03H7.9v-2.9h2.54V9.85c0-2.51 1.49-3.89 3.77-3.89 1.09 0 2.24.19 2.24.19v2.46h-1.26c-1.24 0-1.63.77-1.63 1.56v1.87h2.77l-.44 2.9h-2.33V22c4.78-.8 8.44-4.93 8.44-9.93z" />
              </svg>
            </a>
            <a
              href="https://www.instagram.com/lakeviewburgers"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Lakeview on Instagram"
              data-testid="footer-instagram"
              className="text-cream/70 hover:text-gold transition-colors p-2 rounded-full border border-gold/20 hover:border-gold"
            >
              <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <rect x="3" y="3" width="18" height="18" rx="5" ry="5" />
                <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
              </svg>
            </a>
            <span className="text-gold mx-1">⚜</span>
            <span className="font-serif text-xs sm:text-sm text-cream/60 italic">New Orleans, LA</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
