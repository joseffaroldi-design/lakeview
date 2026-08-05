import React from "react";
import { Button } from "@/components/ui/button";
import { Phone, MapPin, Clock } from "lucide-react";

// Contact Section
const Contact = ({ content, titleOverride, bodyOverride }) => {
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
            {titleOverride || "Visit Us Today"}
          </h2>
          {bodyOverride ? (
            <p className="font-sans text-cream/80 max-w-2xl mx-auto mb-4 text-sm md:text-base">{bodyOverride}</p>
          ) : null}
          <div className="w-24 h-1 mx-auto" style={{ background: 'linear-gradient(90deg, transparent, #a5935b, transparent)' }}></div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-12 md:gap-8">
          <div className="text-center group">
            <div className="w-16 h-16 mx-auto mb-6 border-2 border-gold rounded-full flex items-center justify-center transition-transform group-hover:scale-110">
              <MapPin className="w-8 h-8 text-gold" />
            </div>
            <h3 className="font-serif text-xl font-bold mb-4 uppercase tracking-wider">Location</h3>
            <a
              href={`https://maps.google.com/?q=${encodeURIComponent(
                `${content?.address_line1 || "872 Harrison Ave"}, ${content?.address_line2 || "New Orleans, LA 70124"}`
              )}`}
              target="_blank"
              rel="noopener noreferrer"
              data-testid="address-tappable"
              className="font-sans text-cream/80 leading-relaxed hover:text-gold underline decoration-transparent hover:decoration-gold transition-colors block"
            >
              {content?.address_line1 || "872 Harrison Ave"}<br />
              {content?.address_line2 || "New Orleans, LA 70124"}
            </a>
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

        {/* Google Maps Embed — using maps?q= which works without an API key */}
        <div className="mt-16 rounded-sm overflow-hidden vintage-shadow" data-testid="google-maps-embed">
          <iframe
            title="Lakeview Burgers & Seafood Location"
            src="https://maps.google.com/maps?q=872%20Harrison%20Ave%2C%20New%20Orleans%2C%20LA%2070124&t=&z=15&ie=UTF8&iwloc=&output=embed"
            width="100%"
            height="350"
            style={{ border: 0, minHeight: 350 }}
            allowFullScreen=""
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
            className="w-full block"
          />
        </div>
      </div>
    </section>
  );
};

export default Contact;
