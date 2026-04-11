import React, { useState, useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Phone, MapPin, Clock, ChevronDown, Settings, Mail, ExternalLink, Users, CalendarDays, MessageSquare } from "lucide-react";
import axios from "axios";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import SpinWheel from "@/pages/SpinWheel";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Generate or get session ID
const getSessionId = () => {
  let sessionId = sessionStorage.getItem("visitor_session");
  if (!sessionId) {
    sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    sessionStorage.setItem("visitor_session", sessionId);
  }
  return sessionId;
};

// Logo and Images
const LOGO = "https://customer-assets.emergentagent.com/job_703dcc6a-aa7a-4633-a18d-a8d37a8eb209/artifacts/y3vh8170_5D695FC6-4513-41E6-8C85-02DA2EA2EF08.png";
const HERO_BG = "https://images.unsplash.com/photo-1660882089809-9fe922300699?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMzl8MHwxfHNlYXJjaHw0fHxOZXclMjBPcmxlYW5zJTIwbGFrZWZyb250JTIwc3Vuc2V0JTIwd2F0ZXJ8ZW58MHx8fHwxNzcwMjc4MDg2fDA&ixlib=rb-4.1.0&q=85";
const ABOUT_IMG = "https://customer-assets.emergentagent.com/job_lakeview-grill/artifacts/11ja5k21_IMG_1894.jpeg";

// Track page view with enhanced data
const trackPageView = async (page) => {
  try {
    await axios.post(`${API}/analytics/track`, {
      page,
      user_agent: navigator.userAgent,
      referrer: document.referrer || null,
      session_id: getSessionId(),
      screen_width: window.screen.width,
      screen_height: window.screen.height
    });
  } catch (error) {
    console.error("Error tracking page view:", error);
  }
};

// Track button clicks
const trackButtonClick = async (buttonName) => {
  try {
    await axios.post(`${API}/analytics/button-click`, {
      button_name: buttonName,
      session_id: getSessionId()
    });
  } catch (error) {
    console.error("Error tracking button click:", error);
  }
};

// Navbar Component
const Navbar = () => {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToSection = (id) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <nav 
      data-testid="navbar"
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled ? "navbar-scrolled py-3" : "bg-transparent py-6"
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
            <button
              data-testid="nav-about"
              onClick={() => scrollToSection("about")}
              className={`nav-link font-serif text-sm uppercase tracking-widest transition-colors ${
                scrolled ? "text-navy" : "text-white"
              } hover:text-gold`}
            >
              About
            </button>
            <button
              data-testid="nav-specials"
              onClick={() => scrollToSection("specials")}
              className={`nav-link font-serif text-sm uppercase tracking-widest transition-colors ${
                scrolled ? "text-navy" : "text-white"
              } hover:text-gold`}
            >
              Specials
            </button>
            <button
              data-testid="nav-menu"
              onClick={() => scrollToSection("menu")}
              className={`nav-link font-serif text-sm uppercase tracking-widest transition-colors ${
                scrolled ? "text-navy" : "text-white"
              } hover:text-gold`}
            >
              Menu
            </button>
            <button
              data-testid="nav-contact"
              onClick={() => scrollToSection("contact")}
              className={`nav-link font-serif text-sm uppercase tracking-widest transition-colors ${
                scrolled ? "text-navy" : "text-white"
              } hover:text-gold`}
            >
              Contact
            </button>
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
                className={`${scrolled ? "text-navy hover:text-gold" : "text-white hover:text-gold"}`}
              >
                <Settings className="w-5 h-5" />
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
};

// Hero Section
const Hero = ({ content }) => {
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
      className="relative min-h-screen flex items-center justify-center hero-bg"
      style={{ backgroundImage: `url(${HERO_BG})` }}
    >
      <div className="absolute inset-0 bg-navy/60"></div>
      
      <div className="relative z-10 text-center px-4 max-w-4xl mx-auto pt-16 md:pt-20">
        <div className="animate-fade-in-up">
          <img 
            src={LOGO} 
            alt="Lakeview Burgers & Seafood" 
            data-testid="hero-logo"
            className="w-[280px] md:w-[380px] max-w-full mx-auto mb-2 drop-shadow-2xl"
          />
        </div>
        
        <p className="font-accent text-2xl md:text-3xl text-gold mb-1 md:mb-2 animate-fade-in-up animation-delay-200">
          {content?.tagline || "Lakeview"}
        </p>
        
        <p className="font-sans text-sm md:text-base text-cream/90 mb-4 md:mb-5 max-w-2xl mx-auto animate-fade-in-up animation-delay-400">
          {content?.subtitle || "Serving the finest burgers and fresh Gulf seafood in the heart of New Orleans since 2015"}
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

// About Section
const About = ({ content }) => {
  return (
    <section 
      id="about" 
      data-testid="about-section"
      className="py-24 md:py-32 paper-texture"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          <div className="order-2 lg:order-1">
            <div className="img-zoom decorative-border p-2 vintage-shadow">
              <img 
                src={ABOUT_IMG} 
                alt="Lakeview Burgers & Seafood Restaurant"
                data-testid="about-image" 
                className="w-full h-[400px] object-cover"
              />
            </div>
          </div>
          
          <div className="order-1 lg:order-2 space-y-8">
            <div>
              <p className="font-accent text-3xl text-gold mb-2">{content?.accent_text || "Our Story"}</p>
              <h2 className="font-serif text-4xl md:text-5xl text-navy font-bold tracking-tight">
                {content?.heading || "A New Orleans Tradition"}
              </h2>
            </div>
            
            <div className="section-divider !mx-0"></div>
            
            <div className="space-y-6 font-sans text-muted-foreground leading-relaxed">
              <p>{content?.paragraph1 || "Founded by Chef Joseph Faroldi in 2015, Lakeview Burgers & Seafood has become a beloved fixture in the charming Lakeview neighborhood. What started as a dream to bring quality burgers and fresh Gulf seafood to the community has grown into a true family affair."}</p>
              <p>{content?.paragraph2 || "Today, Chef Joseph works alongside his son Josef, passing down culinary traditions and a passion for great food to the next generation. Together, they take pride in sourcing the freshest Gulf seafood daily and crafting each dish with care and expertise."}</p>
              <p>{content?.paragraph3 || "Whether you're craving a perfectly charred burger or authentic Louisiana seafood, the Faroldi family invites you to experience the taste of the Crescent City at Lakeview Burgers & Seafood."}</p>
            </div>
            
            <div className="flex items-center space-x-4 pt-4">
              <span className="text-gold text-2xl">⚜</span>
              <span className="font-serif italic text-navy text-lg">{content?.established_text || "Est. 2015 \u2022 New Orleans, LA"}</span>
              <span className="text-gold text-2xl">⚜</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

// Specials Section
const Specials = () => {
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
          <p className="font-accent text-3xl text-gold mb-2">Don't Miss</p>
          <h2 className="font-serif text-4xl md:text-5xl text-cream font-bold tracking-tight mb-4">
            Today's Specials
          </h2>
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

// Menu Item Component
const MenuItem = ({ name, description, price, index }) => (
  <div className="menu-item py-4 px-2 rounded-sm" data-testid={`menu-item-${index}`}>
    <div className="flex items-baseline">
      <h4 className="font-serif text-lg text-navy font-semibold">{name}</h4>
      <span className="dotted-leader"></span>
      <span className="font-sans font-bold text-forest text-lg">${price}</span>
    </div>
    {description && (
      <p className="font-sans text-sm text-muted-foreground mt-1">{description}</p>
    )}
  </div>
);

// Menu Section
const Menu = ({ categories }) => {
  const getGridCols = (cols) => {
    if (cols === 4) return "grid-cols-2 md:grid-cols-4 gap-x-12";
    if (cols === 3) return "grid-cols-1 md:grid-cols-3 gap-x-12";
    return "grid-cols-1 md:grid-cols-2 gap-x-16";
  };

  return (
    <section 
      id="menu" 
      data-testid="menu-section"
      className="py-24 md:py-32 bg-cream"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <p className="font-accent text-3xl text-gold mb-2">Delicious</p>
          <h2 className="font-serif text-4xl md:text-5xl text-navy font-bold tracking-tight mb-4">
            Our Menu
          </h2>
          <div className="section-divider"></div>
        </div>
        
        <div className="decorative-border p-8 md:p-12 bg-card paper-texture vintage-shadow">
          {categories.map((cat, catIdx) => (
            <div key={cat.id || catIdx} className={catIdx < categories.length - 1 ? "mb-12" : ""}>
              <div className="flex items-center justify-center mb-8">
                <span className="text-gold">⚜</span>
                <h3 className="font-serif text-2xl md:text-3xl text-navy font-bold mx-4 uppercase tracking-wider">
                  {cat.display_name}
                </h3>
                <span className="text-gold">⚜</span>
              </div>
              {cat.subtitle && (
                <p className="text-center text-muted-foreground mb-6 font-sans text-sm">{cat.subtitle}</p>
              )}
              <div className={`grid ${getGridCols(cat.columns)}`}>
                {(cat.items || []).map((item, idx) => (
                  <MenuItem key={idx} index={`${cat.slug}-${idx}`} name={item.name} description={item.description} price={item.price} />
                ))}
              </div>
            </div>
          ))}
        </div>
        
        <p className="text-center font-sans text-sm text-muted-foreground mt-8 italic">
          * Consuming raw or undercooked meats, poultry, seafood, shellfish or eggs may increase your risk of foodborne illness
        </p>
      </div>
    </section>
  );
};

// Contact Section
const Contact = ({ content }) => {
  const phone = content?.phone || "(504) 289-1032";
  const phoneHref = `tel:+1${phone.replace(/\D/g, '')}`;
  
  return (
    <section 
      id="contact" 
      data-testid="contact-section"
      className="bg-navy text-cream py-24 md:py-32"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <p className="font-accent text-3xl text-gold mb-2">Get in Touch</p>
          <h2 className="font-serif text-4xl md:text-5xl font-bold tracking-tight mb-4">
            Visit Us Today
          </h2>
          <div className="w-24 h-1 mx-auto" style={{ background: 'linear-gradient(90deg, transparent, #a5935b, transparent)' }}></div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-12 md:gap-8">
          <div className="text-center group">
            <div className="w-16 h-16 mx-auto mb-6 border-2 border-gold rounded-full flex items-center justify-center transition-transform group-hover:scale-110">
              <MapPin className="w-8 h-8 text-gold" />
            </div>
            <h3 className="font-serif text-xl font-bold mb-4 uppercase tracking-wider">Location</h3>
            <p className="font-sans text-cream/80 leading-relaxed">
              {content?.address_line1 || "872 Harrison Ave"}<br />
              {content?.address_line2 || "New Orleans, LA 70124"}
            </p>
          </div>
          
          <div className="text-center group">
            <div className="w-16 h-16 mx-auto mb-6 border-2 border-gold rounded-full flex items-center justify-center transition-transform group-hover:scale-110">
              <Clock className="w-8 h-8 text-gold" />
            </div>
            <h3 className="font-serif text-xl font-bold mb-4 uppercase tracking-wider">Hours</h3>
            <div className="font-sans text-cream/80 space-y-1">
              <p>{content?.hours_weekday || "Monday - Saturday: 11:30am - 11pm"}</p>
              <p>{content?.hours_weekend || "Sunday: Closed"}</p>
            </div>
          </div>
          
          <div className="text-center group">
            <div className="w-16 h-16 mx-auto mb-6 border-2 border-gold rounded-full flex items-center justify-center transition-transform group-hover:scale-110">
              <Phone className="w-8 h-8 text-gold" />
            </div>
            <h3 className="font-serif text-xl font-bold mb-4 uppercase tracking-wider">Contact</h3>
            <p className="font-sans text-cream/80 leading-relaxed">
              <a href={phoneHref} className="hover:text-gold transition-colors" data-testid="contact-phone">
                {phone}
              </a>
              <br />
              <a href={`mailto:${content?.email || "info@lakeviewburgers.com"}`} className="hover:text-gold transition-colors" data-testid="contact-email">
                {content?.email || "info@lakeviewburgers.com"}
              </a>
            </p>
          </div>
        </div>
        
        <div className="text-center mt-16">
          <p className="font-sans text-cream/70 mb-6">
            {content?.catering_text || "Catering available for private events and parties"}
          </p>
          <Button
            data-testid="contact-call-btn"
            asChild
            className="btn-vintage bg-transparent border-gold text-gold hover:bg-gold hover:text-navy"
          >
            <a href={phoneHref}>
              <Phone className="w-4 h-4 mr-2" />
              Call for Reservations
            </a>
          </Button>
        </div>

        {/* Google Maps Embed */}
        <div className="mt-16 rounded-sm overflow-hidden vintage-shadow" data-testid="google-maps-embed">
          <iframe
            title="Lakeview Burgers & Seafood Location"
            src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3456.123!2d-90.1005!3d30.0075!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x8620a5e4a7a0dd87%3A0x3e8a1e2f1c2b3d4e!2s872%20Harrison%20Ave%2C%20New%20Orleans%2C%20LA%2070124!5e0!3m2!1sen!2sus!4v1700000000000"
            width="100%"
            height="350"
            style={{ border: 0 }}
            allowFullScreen=""
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
            className="w-full"
          />
        </div>
      </div>
    </section>
  );
};

// Footer
const Footer = () => {
  return (
    <footer data-testid="footer" className="bg-navy border-t border-gold/20 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <img src={LOGO} alt="Lakeview" className="h-10 w-auto" />
          </div>
          <p className="font-sans text-sm text-cream/60 text-center">
            © {new Date().getFullYear()} Lakeview Burgers & Seafood. All rights reserved.
          </p>
          <div className="flex items-center space-x-2">
            <span className="text-gold">⚜</span>
            <span className="font-serif text-sm text-cream/60 italic">New Orleans, Louisiana</span>
            <span className="text-gold">⚜</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

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
        </div>
      </div>
    </div>
  );
};

// Email Signup Section
const EmailSignup = () => {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState(null); // 'success' | 'already' | 'error'
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setSubmitting(true);
    setStatus(null);
    try {
      trackButtonClick("newsletter_signup");
      const res = await axios.post(`${API}/newsletter/subscribe`, { email });
      setStatus(res.data.already_subscribed ? "already" : "success");
      if (!res.data.already_subscribed) setEmail("");
    } catch {
      setStatus("error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section data-testid="email-signup-section" className="py-20 md:py-24 bg-forest relative overflow-hidden">
      <div className="absolute inset-0 opacity-10" style={{ backgroundImage: "url('https://www.transparenttextures.com/patterns/cream-paper.png')" }} />
      <div className="relative max-w-2xl mx-auto px-4 sm:px-6 text-center">
        <span className="text-gold text-2xl">⚜</span>
        <h2 className="font-serif text-3xl md:text-4xl text-cream font-bold mt-3 mb-3">
          Join the Lakeview Family
        </h2>
        <p className="font-sans text-cream/80 mb-8 text-sm md:text-base">
          Get exclusive deals, new menu items, and event invites delivered straight to your inbox.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-lg mx-auto">
          <div className="flex-1 relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-navy/40" />
            <input
              data-testid="email-signup-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              required
              className="w-full pl-10 pr-4 py-3 rounded-full bg-cream text-navy font-sans text-sm focus:outline-none focus:ring-2 focus:ring-gold"
            />
          </div>
          <Button
            data-testid="email-signup-btn"
            type="submit"
            disabled={submitting}
            className="rounded-full bg-gold text-navy hover:bg-gold/90 px-8 py-3 h-auto font-semibold transition-all duration-300 hover:scale-105 disabled:opacity-60"
          >
            {submitting ? "Joining..." : "Join the List"}
          </Button>
        </form>

        {status === "success" && (
          <p data-testid="signup-success-msg" className="mt-4 font-sans text-gold text-sm animate-fade-in">
            Welcome to the Lakeview family! Watch your inbox for exclusive deals.
          </p>
        )}
        {status === "already" && (
          <p data-testid="signup-already-msg" className="mt-4 font-sans text-cream/80 text-sm animate-fade-in">
            You're already on our list — stay tuned for great things!
          </p>
        )}
        {status === "error" && (
          <p data-testid="signup-error-msg" className="mt-4 font-sans text-red-300 text-sm animate-fade-in">
            Something went wrong. Please try again.
          </p>
        )}

        <p className="mt-6 font-sans text-cream/50 text-xs">
          No spam, ever. Unsubscribe anytime.
        </p>
      </div>
    </section>
  );
};

// Loyalty Punch Card Section
const LoyaltyCard = () => {
  const [step, setStep] = useState("join"); // join | lookup | result
  const [formData, setFormData] = useState({ name: "", phone: "" });
  const [lookupPhone, setLookupPhone] = useState("");
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleJoin = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      trackButtonClick("loyalty_join");
      const res = await axios.post(`${API}/loyalty/join`, formData);
      setResult(res.data);
      setStep("result");
    } catch { setResult({ message: "Something went wrong" }); setStep("result"); }
    finally { setSubmitting(false); }
  };

  const handleLookup = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await axios.get(`${API}/loyalty/lookup?phone=${lookupPhone.trim()}`);
      setResult({ ...res.data, already_member: true });
      setStep("result");
    } catch { setResult({ message: "Phone not found. Join below!" }); setStep("join"); }
    finally { setSubmitting(false); }
  };

  const visits = result?.visits || 0;
  const dots = Array.from({ length: 10 }, (_, i) => i < visits);

  return (
    <section data-testid="loyalty-section" className="py-20 md:py-24 bg-navy">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 text-center">
        <span className="text-gold text-2xl">⚜</span>
        <h2 className="font-serif text-3xl md:text-4xl text-cream font-bold mt-3 mb-2">
          Lakeview Loyalty Club
        </h2>
        <p className="font-sans text-cream/80 mb-8 text-sm md:text-base">
          Earn a <strong className="text-gold">free meal</strong> after 10 visits. Sign up with your phone number!
        </p>

        {step === "result" && result ? (
          <div data-testid="loyalty-result" className="bg-cream rounded-lg p-8 text-left max-w-sm mx-auto">
            <h3 className="font-serif text-xl text-navy font-bold text-center mb-4">
              {result.already_member ? `Welcome back, ${result.name || ""}!` : "You're in!"}
            </h3>
            {result.already_member && (
              <>
                <div className="flex justify-center gap-2 mb-4 flex-wrap">
                  {dots.map((filled, i) => (
                    <div key={i} className={`w-8 h-8 rounded-full border-2 flex items-center justify-center text-xs font-bold ${filled ? "bg-gold border-gold text-navy" : "border-navy/20 text-navy/30"}`}>
                      {i + 1}
                    </div>
                  ))}
                </div>
                <p className="text-center font-sans text-sm text-muted-foreground">
                  {result.reward_earned ? "You've earned a FREE MEAL! Show this to your server." : `${10 - visits} more visits to go!`}
                </p>
              </>
            )}
            {!result.already_member && (
              <p className="text-center font-sans text-sm text-muted-foreground">{result.message}</p>
            )}
            <div className="text-center mt-4">
              <Button onClick={() => { setStep("join"); setResult(null); }} variant="outline" className="rounded-full border-navy/20 text-sm">
                {result.already_member ? "Check Another" : "Done"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="max-w-sm mx-auto space-y-4">
            {step === "join" && (
              <form onSubmit={handleJoin} className="space-y-3">
                <input data-testid="loyalty-name-input" value={formData.name} onChange={e => setFormData(p => ({ ...p, name: e.target.value }))} placeholder="Your Name" required className="w-full px-4 py-3 rounded-full bg-cream text-navy font-sans text-sm focus:outline-none focus:ring-2 focus:ring-gold" />
                <input data-testid="loyalty-phone-input" type="tel" value={formData.phone} onChange={e => setFormData(p => ({ ...p, phone: e.target.value }))} placeholder="Phone Number" required className="w-full px-4 py-3 rounded-full bg-cream text-navy font-sans text-sm focus:outline-none focus:ring-2 focus:ring-gold" />
                <Button data-testid="loyalty-join-btn" type="submit" disabled={submitting} className="w-full rounded-full bg-gold text-navy hover:bg-gold/90 py-3 h-auto font-semibold">
                  {submitting ? "Joining..." : "Join Loyalty Club"}
                </Button>
                <button type="button" onClick={() => setStep("lookup")} className="font-sans text-sm text-cream/60 hover:text-gold underline transition-colors">
                  Already a member? Check your visits
                </button>
              </form>
            )}
            {step === "lookup" && (
              <form onSubmit={handleLookup} className="space-y-3">
                <input data-testid="loyalty-lookup-input" type="tel" value={lookupPhone} onChange={e => setLookupPhone(e.target.value)} placeholder="Your Phone Number" required className="w-full px-4 py-3 rounded-full bg-cream text-navy font-sans text-sm focus:outline-none focus:ring-2 focus:ring-gold" />
                <Button data-testid="loyalty-lookup-btn" type="submit" disabled={submitting} className="w-full rounded-full bg-gold text-navy hover:bg-gold/90 py-3 h-auto font-semibold">
                  {submitting ? "Looking up..." : "Check My Visits"}
                </Button>
                <button type="button" onClick={() => setStep("join")} className="font-sans text-sm text-cream/60 hover:text-gold underline transition-colors">
                  New here? Join the club
                </button>
              </form>
            )}
          </div>
        )}
      </div>
    </section>
  );
};

// Catering Section
const CateringForm = () => {
  const [formData, setFormData] = useState({
    name: "", email: "", phone: "", event_date: "", guest_count: "", message: ""
  });
  const [status, setStatus] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setStatus(null);
    try {
      trackButtonClick("catering_inquiry");
      await axios.post(`${API}/catering/inquiry`, formData);
      setStatus("success");
      setFormData({ name: "", email: "", phone: "", event_date: "", guest_count: "", message: "" });
    } catch {
      setStatus("error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section data-testid="catering-section" className="py-24 md:py-32 paper-texture">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
          {/* Left: Info */}
          <div className="space-y-8">
            <div>
              <p className="font-accent text-3xl text-gold mb-2">Private Events</p>
              <h2 className="font-serif text-4xl md:text-5xl text-navy font-bold tracking-tight">
                Let Us Cater Your Event
              </h2>
            </div>
            <div className="section-divider !mx-0"></div>
            <div className="space-y-6 font-sans text-muted-foreground leading-relaxed">
              <p>
                From corporate lunches to family celebrations, the Faroldi family brings the same quality 
                and care to every catered event. Our Gulf seafood platters, signature burgers, and 
                Louisiana classics are perfect for any occasion.
              </p>
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <Users className="w-5 h-5 text-gold mt-1 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-navy">Groups of Any Size</p>
                    <p className="text-sm">From intimate gatherings to large events — we've got you covered.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <CalendarDays className="w-5 h-5 text-gold mt-1 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-navy">Flexible Scheduling</p>
                    <p className="text-sm">We work with your timeline to deliver fresh food exactly when you need it.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <MessageSquare className="w-5 h-5 text-gold mt-1 flex-shrink-0" />
                  <div>
                    <p className="font-semibold text-navy">Custom Menus</p>
                    <p className="text-sm">We'll tailor a menu to your event, budget, and dietary preferences.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right: Form */}
          <div className="bg-card border-2 border-navy/10 rounded-sm p-8 vintage-shadow">
            <h3 className="font-serif text-2xl text-navy font-bold mb-6">Request a Quote</h3>
            {status === "success" ? (
              <div data-testid="catering-success-msg" className="text-center py-12">
                <div className="w-16 h-16 mx-auto mb-4 border-2 border-gold rounded-full flex items-center justify-center">
                  <span className="text-gold text-2xl">⚜</span>
                </div>
                <h4 className="font-serif text-xl text-navy font-bold mb-2">Thank You!</h4>
                <p className="font-sans text-muted-foreground">We'll be in touch within 24 hours to discuss your event.</p>
                <Button
                  onClick={() => setStatus(null)}
                  className="mt-6 bg-gold text-navy hover:bg-gold/90 rounded-full"
                  data-testid="catering-another-btn"
                >
                  Submit Another Inquiry
                </Button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block font-sans text-sm text-muted-foreground mb-1">Name *</label>
                    <input
                      data-testid="catering-name-input"
                      name="name"
                      value={formData.name}
                      onChange={handleChange}
                      required
                      placeholder="Your name"
                      className="w-full px-4 py-2.5 border border-navy/20 rounded-sm font-sans text-sm focus:outline-none focus:ring-2 focus:ring-gold"
                    />
                  </div>
                  <div>
                    <label className="block font-sans text-sm text-muted-foreground mb-1">Email *</label>
                    <input
                      data-testid="catering-email-input"
                      name="email"
                      type="email"
                      value={formData.email}
                      onChange={handleChange}
                      required
                      placeholder="your@email.com"
                      className="w-full px-4 py-2.5 border border-navy/20 rounded-sm font-sans text-sm focus:outline-none focus:ring-2 focus:ring-gold"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block font-sans text-sm text-muted-foreground mb-1">Phone</label>
                    <input
                      data-testid="catering-phone-input"
                      name="phone"
                      type="tel"
                      value={formData.phone}
                      onChange={handleChange}
                      placeholder="(504) 555-0000"
                      className="w-full px-4 py-2.5 border border-navy/20 rounded-sm font-sans text-sm focus:outline-none focus:ring-2 focus:ring-gold"
                    />
                  </div>
                  <div>
                    <label className="block font-sans text-sm text-muted-foreground mb-1">Event Date</label>
                    <input
                      data-testid="catering-date-input"
                      name="event_date"
                      type="date"
                      value={formData.event_date}
                      onChange={handleChange}
                      className="w-full px-4 py-2.5 border border-navy/20 rounded-sm font-sans text-sm focus:outline-none focus:ring-2 focus:ring-gold"
                    />
                  </div>
                  <div>
                    <label className="block font-sans text-sm text-muted-foreground mb-1">Guest Count</label>
                    <input
                      data-testid="catering-guests-input"
                      name="guest_count"
                      value={formData.guest_count}
                      onChange={handleChange}
                      placeholder="e.g., 50"
                      className="w-full px-4 py-2.5 border border-navy/20 rounded-sm font-sans text-sm focus:outline-none focus:ring-2 focus:ring-gold"
                    />
                  </div>
                </div>
                <div>
                  <label className="block font-sans text-sm text-muted-foreground mb-1">Tell us about your event *</label>
                  <textarea
                    data-testid="catering-message-input"
                    name="message"
                    value={formData.message}
                    onChange={handleChange}
                    required
                    rows={4}
                    placeholder="Type of event, menu preferences, dietary requirements..."
                    className="w-full px-4 py-2.5 border border-navy/20 rounded-sm font-sans text-sm focus:outline-none focus:ring-2 focus:ring-gold resize-none"
                  />
                </div>
                {status === "error" && (
                  <p data-testid="catering-error-msg" className="text-red-500 text-sm font-sans">Something went wrong. Please try again.</p>
                )}
                <Button
                  data-testid="catering-submit-btn"
                  type="submit"
                  disabled={submitting}
                  className="w-full rounded-full bg-gold text-navy hover:bg-gold/90 py-3 h-auto font-semibold transition-all duration-300 hover:scale-[1.02] disabled:opacity-60"
                >
                  {submitting ? "Sending..." : "Get a Free Quote"}
                </Button>
              </form>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};

// Home Page Component
const Home = () => {
  const [content, setContent] = useState(null);
  const [menuCategories, setMenuCategories] = useState([]);

  useEffect(() => {
    trackPageView("home");
    const fetchContent = async () => {
      try {
        const [contentRes, menuRes] = await Promise.all([
          axios.get(`${API}/content`),
          axios.get(`${API}/menu`)
        ]);
        setContent(contentRes.data);
        setMenuCategories(menuRes.data);
      } catch (error) {
        console.error("Error fetching site content:", error);
      }
    };
    fetchContent();
  }, []);

  return (
    <div data-testid="home-page">
      <Navbar />
      <main>
        <Hero content={content?.hero} />
        <Specials />
        <About content={content?.about} />
        <Menu categories={menuCategories} />
        <EmailSignup />
        <LoyaltyCard />
        <CateringForm />
        <Contact content={content?.contact} />
      </main>
      <Footer />
      <StickyOrderBar />
      <SpinWheel onTrackClick={trackButtonClick} />
    </div>
  );
};

// Main App Component
function App() {
  return (
    <div className="App" data-testid="app-container">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
