/**
 * CustomersTab — Phase 9E consolidation.
 *
 * Merges 4 previously-separate top-level tabs into one filter-chip surface:
 *   • Subscribers — newsletter signups
 *   • Loyalty    — loyalty members
 *   • Inquiries  — catering inquiries
 *   • Messages   — SMS/email blast composer
 *
 * No new business logic — each sub-view delegates to the original component.
 * No data migration. No collection changes.
 */
import React, { useState } from "react";
import { Users, Mail, UtensilsCrossed, CreditCard, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import SubscribersTab from "./SubscribersTab";
import CateringTab from "./CateringTab";
import { LoyaltyManager, MessagingDashboard } from "@/pages/LoyaltyMessaging";

const FILTERS = [
  { id: "subscribers", label: "Subscribers", icon: Mail },
  { id: "loyalty",     label: "Loyalty",     icon: CreditCard },
  { id: "inquiries",   label: "Inquiries",   icon: UtensilsCrossed },
  { id: "messages",    label: "Messages",    icon: Send },
];

const CustomersTab = ({ getAuthHeader, initialFilter }) => {
  const [active, setActive] = useState(initialFilter || "subscribers");

  return (
    <section data-testid="customers-tab">
      <h2 className="font-serif text-2xl text-navy font-bold mb-2 flex items-center gap-2">
        <Users className="w-6 h-6 text-gold" /> Customers
      </h2>
      <p className="text-sm text-muted-foreground mb-6">Everyone you can talk to — one place.</p>

      <div className="flex flex-wrap gap-2 mb-6 border-b-2 border-navy/10 pb-3" data-testid="customers-filters">
        {FILTERS.map((f) => (
          <Button
            key={f.id}
            onClick={() => setActive(f.id)}
            variant={active === f.id ? "default" : "outline"}
            size="sm"
            className={active === f.id ? "bg-navy text-cream hover:bg-navy/90" : "border-navy/20 text-navy hover:bg-navy/5"}
            data-testid={`customers-filter-${f.id}`}
          >
            <f.icon className="w-3.5 h-3.5 mr-1.5" /> {f.label}
          </Button>
        ))}
      </div>

      {active === "subscribers" && <SubscribersTab getAuthHeader={getAuthHeader} />}
      {active === "loyalty"     && <LoyaltyManager getAuthHeader={getAuthHeader} />}
      {active === "inquiries"   && <CateringTab    getAuthHeader={getAuthHeader} />}
      {active === "messages"    && <MessagingDashboard getAuthHeader={getAuthHeader} />}
    </section>
  );
};

export default CustomersTab;
