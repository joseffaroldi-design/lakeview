import React, { useState, useEffect } from "react";
import "@/App.css";
import { Button } from "@/components/ui/button";
import { Phone, MapPin, Clock, ChevronDown } from "lucide-react";
import { burgers, appetizers, friedPlates, sandwiches, tacos, soups, salads, sides, kids, familyDinners } from "@/data/menu";

// Logo and Images
const LOGO = "https://customer-assets.emergentagent.com/job_703dcc6a-aa7a-4633-a18d-a8d37a8eb209/artifacts/y3vh8170_5D695FC6-4513-41E6-8C85-02DA2EA2EF08.png";
const HERO_BG = "https://images.unsplash.com/photo-1660882089809-9fe922300699?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMzl8MHwxfHNlYXJjaHw0fHxOZXclMjBPcmxlYW5zJTIwbGFrZWZyb250JTIwc3Vuc2V0JTIwd2F0ZXJ8ZW58MHx8fHwxNzcwMjc4MDg2fDA&ixlib=rb-4.1.0&q=85";
const ABOUT_IMG = "https://customer-assets.emergentagent.com/job_lakeview-grill/artifacts/11ja5k21_IMG_1894.jpeg";

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

          <Button
            data-testid="nav-call-btn"
            variant="outline"
            className={`hidden sm:flex items-center gap-2 border-2 ${
              scrolled 
                ? "border-navy text-navy hover:bg-navy hover:text-cream" 
                : "border-white text-white hover:bg-white hover:text-navy"
            } transition-all duration-300`}
          >
            <Phone className="w-4 h-4" />
            <span className="font-sans text-sm">Call Us</span>
          </Button>
        </div>
      </div>
    </nav>
  );
};

// Hero Section
const Hero = () => {
  const scrollToMenu = () => {
    const element = document.getElementById("menu");
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <section 
      id="hero" 
      data-testid="hero-section"
      className="relative min-h-screen flex items-center justify-center hero-bg"
      style={{ backgroundImage: `url(${HERO_BG})` }}
    >
      <div className="absolute inset-0 bg-navy/60"></div>
      
      <div className="relative z-10 text-center px-4 max-w-4xl mx-auto">
        <div className="animate-fade-in-up">
          <img 
            src={LOGO} 
            alt="Lakeview Burgers & Seafood" 
            data-testid="hero-logo"
            className="w-64 md:w-96 mx-auto mb-8 drop-shadow-2xl"
          />
        </div>
        
        <p className="font-accent text-3xl md:text-5xl text-gold mb-6 animate-fade-in-up animation-delay-200">
          Market • Kitchen • Catering
        </p>
        
        <p className="font-sans text-lg md:text-xl text-cream/90 mb-12 max-w-2xl mx-auto animate-fade-in-up animation-delay-400">
          Serving the finest burgers and fresh Gulf seafood in the heart of New Orleans since 1985
        </p>
        
        <Button
          data-testid="hero-view-menu-btn"
          onClick={scrollToMenu}
          className="btn-vintage bg-gold text-navy hover:bg-gold/90 text-lg animate-fade-in-up animation-delay-600"
        >
          View Our Menu
        </Button>
        
        {/* Online Ordering Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 mt-8 animate-fade-in-up animation-delay-600">
          <Button
            data-testid="hero-uber-eats-btn"
            asChild
            className="btn-vintage bg-forest text-cream hover:bg-forest/90 text-base"
          >
            <a href="https://www.ubereats.com/store-browse-uuid/de2b0e6b-0fdf-44bc-92e9-2c223008bd36?diningMode=DELIVERY" target="_blank" rel="noopener noreferrer">
              Order on Uber Eats
            </a>
          </Button>
          <Button
            data-testid="hero-square-btn"
            asChild
            className="btn-vintage bg-navy text-cream hover:bg-navy/90 text-base border-cream/30"
          >
            <a href="https://lakeview-burgers-seafood.square.site" target="_blank" rel="noopener noreferrer">
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
const About = () => {
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
                alt="New Orleans Street"
                data-testid="about-image" 
                className="w-full h-[400px] object-cover"
              />
            </div>
          </div>
          
          <div className="order-1 lg:order-2 space-y-8">
            <div>
              <p className="font-accent text-3xl text-gold mb-2">Our Story</p>
              <h2 className="font-serif text-4xl md:text-5xl text-navy font-bold tracking-tight">
                A New Orleans Tradition
              </h2>
            </div>
            
            <div className="section-divider !mx-0"></div>
            
            <div className="space-y-6 font-sans text-muted-foreground leading-relaxed">
              <p>
                Nestled in the charming Lakeview neighborhood, our family-owned restaurant has been 
                serving the community for nearly four decades. What started as a small burger stand 
                by Lake Pontchartrain has grown into a beloved local institution.
              </p>
              <p>
                We take pride in sourcing the freshest Gulf seafood daily and grinding our premium 
                Angus beef in-house. Every dish reflects our commitment to quality and our deep 
                roots in New Orleans culinary traditions.
              </p>
              <p>
                Whether you're craving a perfectly charred burger or authentic Louisiana seafood, 
                we invite you to experience the taste of the Crescent City at Lakeview Burgers & Seafood.
              </p>
            </div>
            
            <div className="flex items-center space-x-4 pt-4">
              <span className="text-gold text-2xl">⚜</span>
              <span className="font-serif italic text-navy text-lg">Est. 1985 • New Orleans, LA</span>
              <span className="text-gold text-2xl">⚜</span>
            </div>
          </div>
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
const Menu = () => {
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
          {/* Appetizers */}
          <div className="mb-12">
            <div className="flex items-center justify-center mb-8">
              <span className="text-gold">⚜</span>
              <h3 className="font-serif text-2xl md:text-3xl text-navy font-bold mx-4 uppercase tracking-wider">
                Appetizers
              </h3>
              <span className="text-gold">⚜</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16">
              {appetizers.map((item, idx) => (
                <MenuItem key={idx} index={`app-${idx}`} name={item.name} description={item.description} price={item.price} />
              ))}
            </div>
          </div>

          {/* Soups */}
          <div className="mb-12">
            <div className="flex items-center justify-center mb-8">
              <span className="text-gold">⚜</span>
              <h3 className="font-serif text-2xl md:text-3xl text-navy font-bold mx-4 uppercase tracking-wider">
                Soups
              </h3>
              <span className="text-gold">⚜</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-x-12">
              {soups.map((item, idx) => (
                <MenuItem key={idx} index={`soup-${idx}`} name={item.name} description={item.description} price={item.price} />
              ))}
            </div>
          </div>

          {/* Salads */}
          <div className="mb-12">
            <div className="flex items-center justify-center mb-8">
              <span className="text-gold">⚜</span>
              <h3 className="font-serif text-2xl md:text-3xl text-navy font-bold mx-4 uppercase tracking-wider">
                Salads
              </h3>
              <span className="text-gold">⚜</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16">
              {salads.map((item, idx) => (
                <MenuItem key={idx} index={`salad-${idx}`} name={item.name} description={item.description} price={item.price} />
              ))}
            </div>
          </div>

          {/* Burgers */}
          <div className="mb-12">
            <div className="flex items-center justify-center mb-8">
              <span className="text-gold">⚜</span>
              <h3 className="font-serif text-2xl md:text-3xl text-navy font-bold mx-4 uppercase tracking-wider">
                Burgers
              </h3>
              <span className="text-gold">⚜</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16">
              {burgers.map((item, idx) => (
                <MenuItem key={idx} index={`burger-${idx}`} name={item.name} description={item.description} price={item.price} />
              ))}
            </div>
          </div>
          
          {/* Sandwiches & Po'Boys */}
          <div className="mb-12">
            <div className="flex items-center justify-center mb-8">
              <span className="text-gold">⚜</span>
              <h3 className="font-serif text-2xl md:text-3xl text-navy font-bold mx-4 uppercase tracking-wider">
                Sandwiches & Po'Boys
              </h3>
              <span className="text-gold">⚜</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16">
              {sandwiches.map((item, idx) => (
                <MenuItem key={idx} index={`sandwich-${idx}`} name={item.name} description={item.description} price={item.price} />
              ))}
            </div>
          </div>

          {/* Tacos */}
          <div className="mb-12">
            <div className="flex items-center justify-center mb-8">
              <span className="text-gold">⚜</span>
              <h3 className="font-serif text-2xl md:text-3xl text-navy font-bold mx-4 uppercase tracking-wider">
                Tacos
              </h3>
              <span className="text-gold">⚜</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16">
              {tacos.map((item, idx) => (
                <MenuItem key={idx} index={`taco-${idx}`} name={item.name} description={item.description} price={item.price} />
              ))}
            </div>
          </div>

          {/* Fried Plates */}
          <div className="mb-12">
            <div className="flex items-center justify-center mb-8">
              <span className="text-gold">⚜</span>
              <h3 className="font-serif text-2xl md:text-3xl text-navy font-bold mx-4 uppercase tracking-wider">
                Fried Plates
              </h3>
              <span className="text-gold">⚜</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16">
              {friedPlates.map((item, idx) => (
                <MenuItem key={idx} index={`fried-${idx}`} name={item.name} description={item.description} price={item.price} />
              ))}
            </div>
          </div>

          {/* Family Dinners */}
          <div className="mb-12">
            <div className="flex items-center justify-center mb-8">
              <span className="text-gold">⚜</span>
              <h3 className="font-serif text-2xl md:text-3xl text-navy font-bold mx-4 uppercase tracking-wider">
                Family Dinners
              </h3>
              <span className="text-gold">⚜</span>
            </div>
            <p className="text-center text-muted-foreground mb-6 font-sans text-sm">Served with Bed of Fries & Garlic Bread</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16">
              {familyDinners.map((item, idx) => (
                <MenuItem key={idx} index={`family-${idx}`} name={item.name} description={item.description} price={item.price} />
              ))}
            </div>
          </div>

          {/* Sides */}
          <div className="mb-12">
            <div className="flex items-center justify-center mb-8">
              <span className="text-gold">⚜</span>
              <h3 className="font-serif text-2xl md:text-3xl text-navy font-bold mx-4 uppercase tracking-wider">
                Sides
              </h3>
              <span className="text-gold">⚜</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-x-12">
              {sides.map((item, idx) => (
                <MenuItem key={idx} index={`side-${idx}`} name={item.name} description={item.description} price={item.price} />
              ))}
            </div>
          </div>

          {/* Kids Menu */}
          <div>
            <div className="flex items-center justify-center mb-8">
              <span className="text-gold">⚜</span>
              <h3 className="font-serif text-2xl md:text-3xl text-navy font-bold mx-4 uppercase tracking-wider">
                Kids Menu
              </h3>
              <span className="text-gold">⚜</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-x-12">
              {kids.map((item, idx) => (
                <MenuItem key={idx} index={`kids-${idx}`} name={item.name} description={item.description} price={item.price} />
              ))}
            </div>
          </div>
        </div>
        
        <p className="text-center font-sans text-sm text-muted-foreground mt-8 italic">
          * Consuming raw or undercooked meats, poultry, seafood, shellfish or eggs may increase your risk of foodborne illness
        </p>
      </div>
    </section>
  );
};

// Contact Section
const Contact = () => {
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
              872 Harrison Ave<br />
              New Orleans, LA 70124
            </p>
          </div>
          
          <div className="text-center group">
            <div className="w-16 h-16 mx-auto mb-6 border-2 border-gold rounded-full flex items-center justify-center transition-transform group-hover:scale-110">
              <Clock className="w-8 h-8 text-gold" />
            </div>
            <h3 className="font-serif text-xl font-bold mb-4 uppercase tracking-wider">Hours</h3>
            <div className="font-sans text-cream/80 space-y-1">
              <p>Monday - Saturday: 11:30am - 11pm</p>
              <p>Sunday: Closed</p>
            </div>
          </div>
          
          <div className="text-center group">
            <div className="w-16 h-16 mx-auto mb-6 border-2 border-gold rounded-full flex items-center justify-center transition-transform group-hover:scale-110">
              <Phone className="w-8 h-8 text-gold" />
            </div>
            <h3 className="font-serif text-xl font-bold mb-4 uppercase tracking-wider">Contact</h3>
            <p className="font-sans text-cream/80 leading-relaxed">
              <a href="tel:+15045551234" className="hover:text-gold transition-colors" data-testid="contact-phone">
                (504) 289-1032
              </a>
              <br />
              <a href="mailto:info@lakeviewburgers.com" className="hover:text-gold transition-colors" data-testid="contact-email">
                info@lakeviewburgers.com
              </a>
            </p>
          </div>
        </div>
        
        <div className="text-center mt-16">
          <p className="font-sans text-cream/70 mb-6">
            Catering available for private events and parties
          </p>
          <Button
            data-testid="contact-call-btn"
            asChild
            className="btn-vintage bg-transparent border-gold text-gold hover:bg-gold hover:text-navy"
          >
            <a href="tel:+15042891032">
              <Phone className="w-4 h-4 mr-2" />
              Call for Reservations
            </a>
          </Button>
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

// Main App Component
function App() {
  return (
    <div className="App" data-testid="app-container">
      <Navbar />
      <main>
        <Hero />
        <About />
        <Menu />
        <Contact />
      </main>
      <Footer />
    </div>
  );
}

export default App;
