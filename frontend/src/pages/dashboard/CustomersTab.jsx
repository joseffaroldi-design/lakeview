/**
 * CustomersTab — simplified customer follow-up.
 *
 * Keeps the two day-to-day customer lists in one place:
 *   • Subscribers — newsletter signups
 *   • Loyalty     — loyalty members
 *
 * Catering inquiries live in the top-level Catering tab.
 */
import React, { useState } from "react";
import { Mail, CreditCard } from "lucide-react";
import SubscribersTab from "./SubscribersTab";
import { LoyaltyManager } from "@/pages/LoyaltyMessaging";
import { PageHeader } from "@/components/dashboard/primitives";

const FILTERS = [
  { id: "subscribers", label: "Subscribers", icon: Mail },
  { id: "loyalty", label: "Loyalty", icon: CreditCard },
];

const CustomersTab = ({ getAuthHeader, initialFilter }) => {
  const initial = FILTERS.some((item) => item.id === initialFilter)
    ? initialFilter
    : "subscribers";
  const [active, setActive] = useState(initial);

  return (
    <section data-testid="customers-tab" className="ds-fade">
      <PageHeader
        eyebrow="Customers"
        title="Customer lists"
        subtitle="Keep subscribers and loyalty members easy to find. Catering inquiries have their own tab."
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

      {active === "subscribers" && <SubscribersTab getAuthHeader={getAuthHeader} />}
      {active === "loyalty" && <LoyaltyManager getAuthHeader={getAuthHeader} />}
    </section>
  );
};

export default CustomersTab;
