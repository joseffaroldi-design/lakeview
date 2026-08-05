import React, { useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { API } from "@/lib/publicConfig";
import { trackButtonClick } from "@/lib/analytics";

// Loyalty Punch Card Section
const LoyaltyCard = ({ titleOverride, bodyOverride }) => {
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
    } catch (e) {
      if (process.env.NODE_ENV !== "production") console.warn("[App.LoyaltyJoin] join failed:", e);
      setResult({ message: "Something went wrong" }); setStep("result");
    } finally { setSubmitting(false); }
  };

  const handleLookup = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await axios.get(`${API}/loyalty/lookup?phone=${lookupPhone.trim()}`);
      setResult({ ...res.data, already_member: true });
      setStep("result");
    } catch (e) {
      if (process.env.NODE_ENV !== "production") console.warn("[App.LoyaltyLookup] lookup failed:", e);
      setResult({ message: "Phone not found. Join below!" }); setStep("join");
    } finally { setSubmitting(false); }
  };

  const visits = result?.visits || 0;
  const dots = Array.from({ length: 10 }, (_, i) => i < visits);

  return (
    <section data-testid="loyalty-section" className="py-20 md:py-24 bg-navy">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 text-center">
        <span className="text-gold text-2xl">⚜</span>
        <h2 className="font-serif text-3xl md:text-4xl text-cream font-bold mt-3 mb-2">
          {titleOverride || "Lakeview Loyalty Club"}
        </h2>
        <p className="font-sans text-cream/80 mb-8 text-sm md:text-base">
          {bodyOverride ? bodyOverride : (
            <>Earn a <strong className="text-gold">free meal</strong> after 10 visits. Sign up with your phone number!</>
          )}
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

export default LoyaltyCard;
