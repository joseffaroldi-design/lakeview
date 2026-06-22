/**
 * PickDifferentModal — Shows top 5 eligible items when owner clicks "Pick Different Item"
 * 
 * Sprint 13A
 */
import React, { useState, useEffect } from "react";
import axios from "axios";
import { X, Loader2, Calendar, Megaphone } from "lucide-react";
import { Button } from "@/components/ui/button";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PickDifferentModal = ({ isOpen, onClose, getAuthHeader, onSelect }) => {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isOpen) {
      loadAlternatives();
    }
  }, [isOpen]);

  const loadAlternatives = async () => {
    setLoading(true);
    setError(null);
    try {
      const headers = getAuthHeader();
      const res = await axios.get(`${API}/todays-pick/alternatives`, { headers });
      setItems(res.data.items || []);
    } catch (err) {
      setError("Failed to load alternatives");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-card rounded-lg max-w-2xl w-full overflow-hidden shadow-2xl border-2 border-gold/30">
        <div className="px-6 py-4 border-b border-navy/10 bg-cream flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Megaphone className="w-5 h-5 text-gold" />
            <h3 className="font-serif text-navy font-semibold">Pick a Different Item</h3>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-navy/10 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-navy" />
          </button>
        </div>

        <div className="p-6">
          {loading ? (
            <div className="py-12 text-center">
              <Loader2 className="w-8 h-8 animate-spin text-gold mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">Loading alternatives...</p>
            </div>
          ) : error ? (
            <div className="py-12 text-center">
              <p className="text-sm text-red-600 mb-4">{error}</p>
              <Button onClick={loadAlternatives} variant="outline">
                Try Again
              </Button>
            </div>
          ) : items.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-sm text-muted-foreground">No alternative items available</p>
            </div>
          ) : (
            <>
              <p className="text-xs text-muted-foreground mb-4">
                These {items.length} items are most overdue for promotion:
              </p>
              <div className="space-y-2 max-h-[60vh] overflow-y-auto">
                {items.map((item, idx) => (
                  <button
                    key={item.item_key || idx}
                    onClick={() => {
                      onSelect(item);
                      onClose();
                    }}
                    className="w-full text-left border-2 border-navy/10 hover:border-gold/40 rounded-lg p-4 transition-colors group"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-navy group-hover:text-gold transition-colors">
                          {item.name}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">{item.category}</p>
                        {item.description && (
                          <p className="text-xs text-navy/70 mt-1 line-clamp-2">{item.description}</p>
                        )}
                        <div className="flex items-center gap-3 mt-2">
                          <span className="text-sm font-bold text-gold">${item.price}</span>
                          {item.days_since_promoted !== null && (
                            <span className="text-xs px-2 py-0.5 bg-navy/10 text-navy rounded-full flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {item.days_since_promoted === 999
                                ? "Never promoted"
                                : `${item.days_since_promoted}d ago`}
                            </span>
                          )}
                        </div>
                      </div>
                      <Megaphone className="w-5 h-5 text-navy/20 group-hover:text-gold flex-shrink-0 transition-colors" />
                    </div>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="px-6 py-4 border-t border-navy/10 bg-cream flex items-center justify-end">
          <Button onClick={onClose} variant="outline" className="border-navy/20">
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
};

export default PickDifferentModal;
