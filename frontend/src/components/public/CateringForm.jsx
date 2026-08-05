import React, { useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Users, CalendarDays, MessageSquare } from "lucide-react";
import { API } from "@/lib/publicConfig";
import { trackButtonClick } from "@/lib/analytics";

// Catering Section
const CateringForm = ({ titleOverride, bodyOverride }) => {
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
    <section id="catering" data-testid="catering-section" className="py-24 md:py-32 paper-texture">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
          {/* Left: Info */}
          <div className="space-y-8">
            <div>
              <p className="font-accent text-3xl text-gold mb-2">Private Events</p>
              <h2 className="font-serif text-4xl md:text-5xl text-navy font-bold tracking-tight">
                {titleOverride || "Let Us Cater Your Event"}
              </h2>
              {bodyOverride ? (
                <p className="font-sans text-muted-foreground mt-3 leading-relaxed">{bodyOverride}</p>
              ) : null}
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
                    <p className="text-sm">From intimate gatherings to large events — we&apos;ve got you covered.</p>
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
                    <p className="text-sm">We&apos;ll tailor a menu to your event, budget, and dietary preferences.</p>
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
                <p className="font-sans text-muted-foreground">We&apos;ll be in touch within 24 hours to discuss your event.</p>
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

export default CateringForm;
