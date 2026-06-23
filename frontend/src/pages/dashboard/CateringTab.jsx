import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Card, CardContent } from "@/components/ui/card";
import { UtensilsCrossed, Mail, Phone } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_CLASS = {
  new: "bg-gold/20 text-gold",
  contacted: "bg-blue-100 text-blue-700",
  confirmed: "bg-green-100 text-green-700",
  completed: "bg-gray-100 text-gray-600",
  cancelled: "bg-red-100 text-red-600",
};

// Sprint 14B.3 — pre-fill a friendly reply so the owner clicks once and
// lands in their email client with the right subject + greeting + signature.
const buildMailto = (inq) => {
  const eventLine = inq.event_date
    ? `your event on ${inq.event_date}`
    : "your catering inquiry";
  const subject = `Re: Catering inquiry — ${
    inq.event_date ? inq.event_date : "Lakeview Burgers & Seafood"
  }`;
  const greeting = inq.name ? `Hi ${inq.name.split(/\s+/)[0]},` : "Hi,";
  const lines = [
    greeting,
    "",
    `Thanks for reaching out to Lakeview Burgers & Seafood about ${eventLine}.`,
    "",
    "We'd love to help — here are a few quick questions so we can put a quote together:",
    "  •  Final headcount (you mentioned " +
      (inq.guest_count ? `${inq.guest_count}` : "approx. guests") +
      ")",
    "  •  Preferred menu style (burgers + sides, seafood spread, mixed)",
    "  •  Delivery vs on-site service",
    "",
    "Reply whenever works for you and we'll get a quote back the same day.",
    "",
    "— Lakeview Burgers & Seafood",
  ];
  return `mailto:${encodeURIComponent(inq.email)}?subject=${encodeURIComponent(
    subject,
  )}&body=${encodeURIComponent(lines.join("\n"))}`;
};

export const CateringTab = ({ getAuthHeader }) => {
  const [inquiries, setInquiries] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchInquiries = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/catering/inquiries`, { headers: getAuthHeader() });
      setInquiries(res.data.inquiries || []);
    } catch (err) {
      console.error("Error fetching catering inquiries:", err);
    } finally {
      setLoading(false);
    }
  }, [getAuthHeader]);

  useEffect(() => { fetchInquiries(); }, [fetchInquiries]);

  const updateStatus = async (id, status) => {
    try {
      await axios.put(`${API}/catering/inquiries/${id}/status`, { status }, { headers: getAuthHeader() });
      fetchInquiries();
    } catch (err) {
      console.error("Error updating catering status:", err);
    }
  };

  if (loading) return <p className="text-muted-foreground">Loading inquiries…</p>;

  return (
    <section>
      <h2 className="font-serif text-2xl text-navy font-bold mb-6 flex items-center gap-2">
        <UtensilsCrossed className="w-6 h-6 text-gold" />
        Catering Inquiries
        <span className="text-sm font-sans font-normal text-muted-foreground ml-2">({inquiries.length})</span>
      </h2>

      {inquiries.length === 0 ? (
        <Card className="bg-card border-2 border-navy/10">
          <CardContent className="py-8 text-center">
            <UtensilsCrossed className="w-10 h-10 mx-auto text-muted-foreground mb-3" />
            <p className="font-sans text-muted-foreground">No catering inquiries yet.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {inquiries.map((inquiry) => (
            <Card key={inquiry.id} className="bg-card border-2 border-navy/10" data-testid={`catering-inquiry-${inquiry.id}`}>
              <CardContent className="py-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <h4 className="font-serif text-navy font-bold">{inquiry.name}</h4>
                      <span className={`text-xs font-sans px-2 py-0.5 rounded-full ${STATUS_CLASS[inquiry.status] || STATUS_CLASS.cancelled}`}>
                        {inquiry.status}
                      </span>
                    </div>
                    <p className="font-sans text-sm text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1">
                      <a
                        href={`mailto:${inquiry.email}`}
                        className="inline-flex items-center gap-1 text-navy hover:text-gold hover:underline"
                        data-testid={`catering-email-link-${inquiry.id}`}
                      >
                        <Mail className="w-3 h-3" /> {inquiry.email}
                      </a>
                      {inquiry.phone ? (
                        <a
                          href={`tel:${inquiry.phone.replace(/[^+\d]/g, "")}`}
                          className="inline-flex items-center gap-1 text-navy hover:text-gold hover:underline"
                          data-testid={`catering-phone-link-${inquiry.id}`}
                        >
                          <Phone className="w-3 h-3" /> {inquiry.phone}
                        </a>
                      ) : null}
                    </p>
                    {inquiry.event_date && (
                      <p className="font-sans text-sm text-muted-foreground">
                        Date: {inquiry.event_date}{inquiry.guest_count ? ` | ${inquiry.guest_count} guests` : ""}
                      </p>
                    )}
                    <p className="font-sans text-sm text-navy mt-2">{inquiry.message}</p>
                    <p className="font-sans text-xs text-muted-foreground mt-1">
                      {new Date(inquiry.submitted_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-2 flex-shrink-0">
                    <a
                      href={buildMailto(inquiry)}
                      className="inline-flex items-center gap-1.5 text-xs font-semibold bg-gold text-navy hover:bg-gold/90 px-3 py-1.5 rounded-sm transition-colors"
                      data-testid={`catering-reply-btn-${inquiry.id}`}
                    >
                      <Mail className="w-3.5 h-3.5" /> Reply via email
                    </a>
                    <select
                      data-testid={`catering-status-${inquiry.id}`}
                      value={inquiry.status}
                      onChange={(e) => updateStatus(inquiry.id, e.target.value)}
                      className="text-sm border border-navy/20 rounded-sm px-2 py-1 font-sans focus:outline-none focus:ring-2 focus:ring-gold"
                    >
                      <option value="new">New</option>
                      <option value="contacted">Contacted</option>
                      <option value="confirmed">Confirmed</option>
                      <option value="completed">Completed</option>
                      <option value="cancelled">Cancelled</option>
                    </select>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
};

export default CateringTab;
