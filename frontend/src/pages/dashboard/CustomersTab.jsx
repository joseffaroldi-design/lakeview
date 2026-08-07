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
import { Mail, UtensilsCrossed, CreditCard, Send, Users } from "lucide-react";
import SubscribersTab from "./SubscribersTab";
import CateringTab from "./CateringTab";
import AllCustomers from "./AllCustomers";
import { LoyaltyManager, MessagingDashboard } from "@/pages/LoyaltyMessaging";
import { PageHeader } from "@/components/dashboard/primitives";

const FILTERS = [
  { id: "all",         label: "All",         icon: Users },
  { id: "subscribers", label: "Subscribers", icon: Mail },
  { id: "loyalty",     label: "Loyalty",     icon: CreditCard },
  { id: "inquiries",   label: "Inquiries",   icon: UtensilsCrossed },
  { id: "messages",    label: "Messages",    icon: Send },
];

const CustomersTab = ({ getAuthHeader, initialFilter }) => {
  const [active, setActive] = useState(initialFilter || "all");

  return (
    <section data-testid="customers-tab" className="ds-fade">
      <PageHeader
        eyebrow="Customers"
        title="Everyone you can talk to"
        subtitle="Subscribers, loyalty members, catering leads and your message blasts — all in one place."
      />

      <div className="flex flex-wrap gap-1 mb-6 ds-nav-scroll overflow-x-auto" data-testid="customers-filters">
        {FILTERS.map((f) => {
          const isActive = active === f.id;
          return (
            <button
              key={f.id}
              onClick={() => setActive(f.id)}
              className={`ds-tab whitespace-nowrap ${isActive ? "is-active" : ""}`}
              data-testid={`customers-filter-${f.id}`}
            >
              <f.icon className="w-4 h-4" /> {f.label}
            </button>
          );
        })}
      </div>

      {active === "all"         && <AllCustomers    getAuthHeader={getAuthHeader} />}
      {active === "subscribers" && <SubscribersTab getAuthHeader={getAuthHeader} />}
      {active === "loyalty"     && <LoyaltyManager getAuthHeader={getAuthHeader} />}
      {active === "inquiries"   && <CateringTab    getAuthHeader={getAuthHeader} />}
      {active === "messages"    && <MessagingDashboard getAuthHeader={getAuthHeader} />}
    </section>
  );
};

export default CustomersTab;
