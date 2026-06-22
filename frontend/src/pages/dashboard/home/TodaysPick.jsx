/**
 * TodaysPick — Full-width hero card for the Home screen
 * 
 * Sprint 13A → Sprint 14A-Frontend: Complete workflow optimization.
 * Owner can see pre-generated graphic + copy, then post in < 90 seconds.
 */
import React, { useState, useEffect } from "react";
import axios from "axios";
import { Sparkles, Copy, CheckCircle2, RefreshCw, Calendar, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TodaysPick = ({ pick, onRefresh, getAuthHeader }) => {
  const [copiedCaption, setCopiedCaption] = useState(false);
  const [selectedGraphic, setSelectedGraphic] = useState(0);
  const [posted, setPosted] = useState(false);

  // Track view on mount
  useEffect(() => {
    if (pick) {
      trackEvent("todays_pick_viewed");
    }
  }, [pick?.id]);

  // Initialize posted state from pick metrics
  useEffect(() => {
    if (pick?.metrics?.posted) {
      setPosted(true);
    }
  }, [pick?.metrics?.posted]);

  const trackEvent = async (eventName, metadata = {}) => {
    try {
      const headers = getAuthHeader();
      await axios.post(
        `${API}/todays-pick/analytics`,
        { event: eventName, metadata },
        { headers }
      );
    } catch (err) {
      console.error("Analytics tracking failed:", err);
    }
  };

  const copyCaption = () => {
    if (!pick?.copy?.caption) return;
    
    const fullText = `${pick.copy.caption}\n\n${pick.copy.hashtags.map(t => `#${t}`).join(" ")}`;
    navigator.clipboard.writeText(fullText);
    setCopiedCaption(true);
    setTimeout(() => setCopiedCaption(false), 2000);
    
    trackEvent("todays_pick_caption_copied", { item: pick.item.name });
  };

  const openFacebook = () => {
    trackEvent("todays_pick_facebook_opened", { item: pick.item.name });
    
    const caption = pick?.copy?.caption || "";
    const hashtags = pick?.copy?.hashtags?.map(t => `#${t}`).join(" ") || "";
    const fullText = `${caption}\n\n${hashtags}`;
    
    // Facebook deep link (mobile) or web fallback
    const fbUrl = `fb://publish?text=${encodeURIComponent(fullText)}`;
    const webFallback = `https://www.facebook.com/sharer/sharer.php?u=https://lakeviewburgers.com&quote=${encodeURIComponent(fullText)}`;
    
    // Try deep link first (works on mobile)
    window.location.href = fbUrl;
    
    // Fallback to web after 500ms if deep link doesn't work
    setTimeout(() => {
      window.open(webFallback, "_blank");
    }, 500);
  };

  const openInstagram = () => {
    trackEvent("todays_pick_instagram_opened", { item: pick.item.name });
    
    // Instagram doesn't support pre-filled captions via URL
    // Copy to clipboard and open Instagram
    const caption = pick?.copy?.caption || "";
    const hashtags = pick?.copy?.hashtags?.map(t => `#${t}`).join(" ") || "";
    const fullText = `${caption}\n\n${hashtags}`;
    
    navigator.clipboard.writeText(fullText);
    
    // Try Instagram deep link
    const igUrl = "instagram://camera";
    const webFallback = "https://www.instagram.com/";
    
    window.location.href = igUrl;
    setTimeout(() => {
      window.open(webFallback, "_blank");
    }, 500);
    
    alert("Caption copied! Paste it when you create your Instagram post.");
  };

  const markPosted = async () => {
    try {
      const headers = getAuthHeader();
      await axios.patch(
        `${API}/todays-pick/metrics`,
        { posted: true },
        { headers }
      );
      setPosted(true);
      trackEvent("todays_pick_posted", { item: pick.item.name });
      onRefresh();
    } catch (err) {
      console.error("Failed to mark as posted:", err);
    }
  };

  if (!pick) {
    return (
      <Card className="bg-gradient-to-br from-gold/10 via-cream to-white border-2 border-gold/30 mb-6">
        <CardContent className="py-6 px-6 text-center">
          <Sparkles className="w-8 h-8 text-gold mx-auto mb-3" />
          <p className="text-navy font-semibold">Loading Today&apos;s Pick...</p>
        </CardContent>
      </Card>
    );
  }

  const { item, copy, graphics, metrics } = pick;
  const hasGraphics = graphics && graphics.length > 0;

  return (
    <Card className="bg-gradient-to-br from-gold/10 via-cream to-white border-2 border-gold/30 mb-6 overflow-hidden">
      <div className="px-6 py-4 border-b border-gold/20 bg-gold/5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-gold" />
          <h3 className="font-serif text-lg text-navy font-bold">Today&apos;s Pick</h3>
          {posted && (
            <span className="text-xs px-2 py-1 bg-forest/10 text-forest rounded-full flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" />
              Posted
            </span>
          )}
        </div>
        <button
          onClick={onRefresh}
          className="p-2 hover:bg-gold/10 rounded-lg transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4 text-navy/60" />
        </button>
      </div>

      <CardContent className="p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Graphics Preview */}
          <div>
            {hasGraphics ? (
              <div>
                {/* Main Graphic */}
                <div className="aspect-square bg-navy/5 rounded-lg overflow-hidden border-2 border-navy/10 mb-3">
                  <img
                    src={`${API}${graphics[selectedGraphic].url}`}
                    alt={`${item.name} - Variation ${graphics[selectedGraphic].variation}`}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                </div>
                
                {/* Thumbnail Selector */}
                {graphics.length > 1 && (
                  <div className="flex gap-2">
                    {graphics.map((g, idx) => (
                      <button
                        key={g.asset_id}
                        onClick={() => setSelectedGraphic(idx)}
                        className={`flex-1 aspect-square rounded-lg overflow-hidden border-2 transition-all ${
                          selectedGraphic === idx
                            ? "border-gold scale-105"
                            : "border-navy/10 hover:border-gold/40"
                        }`}
                      >
                        <img
                          src={`${API}${g.thumb_url}`}
                          alt={`Variation ${g.variation}`}
                          className="w-full h-full object-cover"
                        />
                      </button>
                    ))}
                  </div>
                )}
                
                {/* Download Link */}
                <a
                  href={`${API}${graphics[selectedGraphic].url}`}
                  download
                  className="text-xs text-navy/60 hover:text-gold mt-2 inline-flex items-center gap-1"
                >
                  <ExternalLink className="w-3 h-3" />
                  Download graphic
                </a>
              </div>
            ) : (
              <div className="aspect-square bg-navy/5 rounded-lg flex items-center justify-center border-2 border-dashed border-navy/10">
                <div className="text-center p-4">
                  <Sparkles className="w-8 h-8 text-navy/20 mx-auto mb-2" />
                  <p className="text-xs text-muted-foreground">Graphics will appear here</p>
                  <p className="text-xs text-muted-foreground mt-1">(Generated daily at 5:30 AM)</p>
                </div>
              </div>
            )}
          </div>

          {/* Right: Item Info + Actions */}
          <div className="flex flex-col">
            <div className="flex-1">
              <h4 className="font-serif text-2xl text-navy font-bold mb-1">{item.name}</h4>
              <p className="text-sm text-muted-foreground mb-2">{item.category}</p>
              {item.description && (
                <p className="text-sm text-navy/80 mb-3">{item.description}</p>
              )}
              <div className="flex items-center gap-4 mb-4">
                <span className="text-2xl font-bold text-gold">${item.price}</span>
                {item.days_since_promoted !== null && (
                  <span className="text-xs px-3 py-1.5 bg-navy/10 text-navy rounded-full flex items-center gap-1">
                    <Calendar className="w-3 h-3" />
                    {item.days_since_promoted === 999
                      ? "Never promoted"
                      : `${item.days_since_promoted}d ago`}
                  </span>
                )}
              </div>

              {/* Caption Preview */}
              <div className="bg-white border-2 border-navy/10 rounded-lg p-4 mb-4">
                <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">
                  Ready to Post
                </p>
                <p className="text-sm text-navy leading-relaxed mb-3">{copy.caption}</p>
                <div className="flex flex-wrap gap-1">
                  {copy.hashtags.slice(0, 6).map((tag, idx) => (
                    <span key={idx} className="text-xs text-gold">
                      #{tag}
                    </span>
                  ))}
                  {copy.hashtags.length > 6 && (
                    <span className="text-xs text-muted-foreground">
                      +{copy.hashtags.length - 6} more
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="space-y-2">
              <Button
                onClick={copyCaption}
                className="w-full bg-navy text-white hover:bg-navy/90"
                disabled={posted}
              >
                {copiedCaption ? (
                  <>
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4 mr-2" />
                    Copy Caption
                  </>
                )}
              </Button>

              <div className="grid grid-cols-2 gap-2">
                <Button
                  onClick={openFacebook}
                  variant="outline"
                  className="border-navy/20 hover:bg-navy/5"
                  disabled={posted}
                >
                  <ExternalLink className="w-4 h-4 mr-2" />
                  Facebook
                </Button>
                <Button
                  onClick={openInstagram}
                  variant="outline"
                  className="border-navy/20 hover:bg-navy/5"
                  disabled={posted}
                >
                  <ExternalLink className="w-4 h-4 mr-2" />
                  Instagram
                </Button>
              </div>

              {!posted && (
                <Button
                  onClick={markPosted}
                  className="w-full bg-forest text-white hover:bg-forest/90"
                >
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  Mark as Posted
                </Button>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default TodaysPick;
