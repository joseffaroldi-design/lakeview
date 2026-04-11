import React, { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Gift, X } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SpinWheel = ({ onTrackClick }) => {
  const [settings, setSettings] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [step, setStep] = useState("form"); // form | spinning | result
  const [formData, setFormData] = useState({ name: "", email: "", phone: "" });
  const [result, setResult] = useState(null);
  const [rotation, setRotation] = useState(0);
  const canvasRef = useRef(null);

  useEffect(() => {
    axios.get(`${API}/giveaway/settings`).then(res => {
      if (res.data?.is_active) setSettings(res.data);
    }).catch(() => {});
  }, []);

  // Draw the wheel on canvas
  useEffect(() => {
    if (!settings?.prizes || !canvasRef.current || !showModal) return;
    const timer = setTimeout(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      const size = canvas.width;
      const center = size / 2;
      const radius = center - 4;
      const prizes = settings.prizes;
      const sliceAngle = (2 * Math.PI) / prizes.length;

      ctx.clearRect(0, 0, size, size);

      prizes.forEach((prize, i) => {
        const startAngle = i * sliceAngle;
        const endAngle = startAngle + sliceAngle;

        ctx.beginPath();
        ctx.moveTo(center, center);
        ctx.arc(center, center, radius, startAngle, endAngle);
        ctx.closePath();
        ctx.fillStyle = prize.color;
        ctx.fill();
        ctx.strokeStyle = "#fcfbf7";
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.save();
        ctx.translate(center, center);
        ctx.rotate(startAngle + sliceAngle / 2);
        ctx.textAlign = "right";
        ctx.fillStyle = "#fcfbf7";
        ctx.font = "bold 11px Lato, sans-serif";
        ctx.fillText(prize.label, radius - 12, 4);
        ctx.restore();
      });

      // Center circle
      ctx.beginPath();
      ctx.arc(center, center, 20, 0, 2 * Math.PI);
      ctx.fillStyle = "#a5935b";
      ctx.fill();
      ctx.strokeStyle = "#fcfbf7";
      ctx.lineWidth = 3;
      ctx.stroke();
    }, 100);
    return () => clearTimeout(timer);
  }, [settings, showModal]);

  const handleSpin = async (e) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.email.trim()) return;

    if (onTrackClick) onTrackClick("giveaway_spin");
    setStep("spinning");

    try {
      const res = await axios.post(`${API}/giveaway/spin`, formData);
      const data = res.data;
      setResult(data);

      const prizes = settings.prizes;
      const prizeIdx = data.already_entered ? 0 : data.prize_index;
      const sliceAngle = 360 / prizes.length;
      // Land in the middle of the winning slice
      const targetAngle = 360 - (prizeIdx * sliceAngle + sliceAngle / 2);
      const totalRotation = 360 * 8 + targetAngle; // 8 full spins + target
      setRotation(prev => prev + totalRotation);

      setTimeout(() => setStep("result"), 5000);
    } catch (err) {
      const msg = err.response?.data?.detail || "Something went wrong";
      setResult({ prize: "Error", message: msg });
      setStep("result");
    }
  };

  if (!settings) return null;

  return (
    <>
      {/* Floating CTA Button */}
      <button
        data-testid="giveaway-cta-btn"
        onClick={() => { setShowModal(true); if (onTrackClick) onTrackClick("giveaway_open"); }}
        className="fixed left-4 bottom-20 z-40 bg-gradient-to-r from-gold to-yellow-500 text-navy rounded-full px-5 py-3 font-semibold shadow-xl hover:scale-110 transition-all duration-300 flex items-center gap-2 animate-bounce"
        style={{ animationDuration: "2s" }}
      >
        <Gift className="w-5 h-5" />
        <span className="hidden sm:inline">Spin & Win!</span>
      </button>

      {/* Modal Overlay */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-navy/80 backdrop-blur-sm flex items-center justify-center p-4" data-testid="giveaway-modal">
          <div className="bg-cream rounded-lg shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto relative">
            {/* Close button */}
            <button
              data-testid="giveaway-close-btn"
              onClick={() => { setShowModal(false); setStep("form"); setResult(null); }}
              className="absolute top-3 right-3 text-navy/50 hover:text-navy z-10"
            >
              <X className="w-6 h-6" />
            </button>

            <div className="p-6 sm:p-8 text-center">
              <h2 className="font-serif text-2xl sm:text-3xl text-navy font-bold mb-1">{settings.title}</h2>
              <p className="font-sans text-muted-foreground text-sm mb-6">{settings.subtitle}</p>

              {/* Wheel */}
              <div className="relative mx-auto mb-6" style={{ width: "280px", height: "280px" }}>
                {/* Pointer */}
                <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1 z-10 w-0 h-0"
                  style={{ borderLeft: "12px solid transparent", borderRight: "12px solid transparent", borderTop: "24px solid #a5935b" }}
                />
                <div
                  className="transition-transform"
                  style={{
                    transform: `rotate(${rotation}deg)`,
                    transition: step === "spinning" ? "transform 5s cubic-bezier(0.17, 0.67, 0.12, 0.99)" : "none",
                    width: "280px",
                    height: "280px"
                  }}
                >
                  <canvas ref={canvasRef} width={280} height={280} className="rounded-full shadow-lg" />
                </div>
              </div>

              {/* Form Step */}
              {step === "form" && (
                <form onSubmit={handleSpin} className="space-y-3 text-left">
                  <div>
                    <input
                      data-testid="giveaway-name-input"
                      value={formData.name}
                      onChange={e => setFormData(p => ({ ...p, name: e.target.value }))}
                      placeholder="Your Name *"
                      required
                      className="w-full px-4 py-2.5 border border-navy/20 rounded-sm font-sans text-sm focus:outline-none focus:ring-2 focus:ring-gold"
                    />
                  </div>
                  <div>
                    <input
                      data-testid="giveaway-email-input"
                      type="email"
                      value={formData.email}
                      onChange={e => setFormData(p => ({ ...p, email: e.target.value }))}
                      placeholder="Email Address *"
                      required
                      className="w-full px-4 py-2.5 border border-navy/20 rounded-sm font-sans text-sm focus:outline-none focus:ring-2 focus:ring-gold"
                    />
                  </div>
                  <div>
                    <input
                      data-testid="giveaway-phone-input"
                      type="tel"
                      value={formData.phone}
                      onChange={e => setFormData(p => ({ ...p, phone: e.target.value }))}
                      placeholder="Phone (optional)"
                      className="w-full px-4 py-2.5 border border-navy/20 rounded-sm font-sans text-sm focus:outline-none focus:ring-2 focus:ring-gold"
                    />
                  </div>
                  <Button
                    data-testid="giveaway-spin-btn"
                    type="submit"
                    className="w-full rounded-full bg-gold text-navy hover:bg-gold/90 py-3 h-auto font-bold text-lg transition-all hover:scale-[1.02]"
                  >
                    SPIN THE WHEEL!
                  </Button>
                  <p className="text-center text-xs text-muted-foreground mt-2">One spin per person. Everyone wins something!</p>
                </form>
              )}

              {/* Spinning Step */}
              {step === "spinning" && (
                <div className="py-4">
                  <p className="font-serif text-xl text-navy font-bold animate-pulse">Spinning...</p>
                </div>
              )}

              {/* Result Step */}
              {step === "result" && result && (
                <div className="py-4" data-testid="giveaway-result">
                  {result.already_entered ? (
                    <div>
                      <p className="font-sans text-muted-foreground mb-2">You've already entered!</p>
                      <p className="font-serif text-xl text-navy font-bold">Your prize: {result.prize}</p>
                    </div>
                  ) : result.prize === "Try Again" ? (
                    <div>
                      <p className="font-serif text-2xl text-navy font-bold mb-2">So close!</p>
                      <p className="font-sans text-muted-foreground">Better luck next time. Follow us for more chances to win!</p>
                    </div>
                  ) : (
                    <div>
                      <p className="font-accent text-2xl text-gold mb-1">Congratulations!</p>
                      <p className="font-serif text-2xl sm:text-3xl text-navy font-bold mb-3" data-testid="giveaway-prize-text">
                        {result.prize}
                      </p>
                      <p className="font-sans text-muted-foreground text-sm mb-4">
                        Show this screen when you visit to redeem your prize!
                      </p>
                      <div className="bg-navy/5 rounded-sm p-4 inline-block">
                        <p className="font-sans text-xs text-muted-foreground">Redeem at</p>
                        <p className="font-serif text-navy font-bold">Lakeview Burgers & Seafood</p>
                        <p className="font-sans text-sm text-muted-foreground">872 Harrison Ave, New Orleans</p>
                      </div>
                    </div>
                  )}
                  <Button
                    onClick={() => { setShowModal(false); setStep("form"); }}
                    className="mt-6 rounded-full bg-gold text-navy hover:bg-gold/90"
                    data-testid="giveaway-close-result-btn"
                  >
                    Close
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default SpinWheel;
