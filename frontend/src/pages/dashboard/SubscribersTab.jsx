import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Card, CardContent } from "@/components/ui/card";
import { Mail } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const SubscribersTab = ({ getAuthHeader }) => {
  const [subscribers, setSubscribers] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchSubscribers = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/newsletter/subscribers`, { headers: getAuthHeader() });
      setSubscribers(res.data.subscribers || []);
    } catch (err) {
      console.error("Error fetching subscribers:", err);
    } finally {
      setLoading(false);
    }
  }, [getAuthHeader]);

  useEffect(() => { fetchSubscribers(); }, [fetchSubscribers]);

  if (loading) return <p className="text-muted-foreground">Loading subscribers…</p>;

  return (
    <section>
      <h2 className="font-serif text-2xl text-navy font-bold mb-6 flex items-center gap-2">
        <Mail className="w-6 h-6 text-gold" />
        Newsletter Subscribers
        <span className="text-sm font-sans font-normal text-muted-foreground ml-2">({subscribers.length})</span>
      </h2>

      {subscribers.length === 0 ? (
        <Card className="bg-card border-2 border-navy/10">
          <CardContent className="py-8 text-center">
            <Mail className="w-10 h-10 mx-auto text-muted-foreground mb-3" />
            <p className="font-sans text-muted-foreground">No subscribers yet.</p>
          </CardContent>
        </Card>
      ) : (
        <Card className="bg-card border-2 border-navy/10">
          <CardContent className="py-4">
            <div className="space-y-2">
              {subscribers.map((sub, idx) => (
                <div
                  key={sub.id || idx}
                  className="flex items-center justify-between py-2 border-b border-navy/5 last:border-0"
                  data-testid={`newsletter-sub-${idx}`}
                >
                  <span className="font-sans text-navy">{sub.email}</span>
                  <span className="font-sans text-xs text-muted-foreground">
                    {new Date(sub.subscribed_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </section>
  );
};

export default SubscribersTab;
