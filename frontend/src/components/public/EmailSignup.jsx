import React, { useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Mail } from "lucide-react";
import { API } from "@/lib/publicConfig";
import { trackButtonClick } from "@/lib/analytics";

// Email Signup Section
const EmailSignup = ({ titleOverride, bodyOverride }) => {
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
          {titleOverride || "Join the Lakeview Family"}
        </h2>
        <p className="font-sans text-cream/80 mb-8 text-sm md:text-base">
          {bodyOverride || "Get exclusive deals, new menu items, and event invites delivered straight to your inbox."}
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
            You&apos;re already on our list — stay tuned for great things!
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

export default EmailSignup;
