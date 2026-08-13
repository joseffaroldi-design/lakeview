import React from "react";
import { Image as ImageIcon, Pencil, Users, UtensilsCrossed } from "lucide-react";
import { PageHeader } from "@/components/dashboard/primitives";

const QuickAction = ({ icon: Icon, label, sub, onClick, testId }) => (
  <button
    type="button"
    onClick={onClick}
    className="ds-card p-4 text-left hover:-translate-y-0.5 transition-transform"
    data-testid={testId}
  >
    <div className="w-9 h-9 rounded-xl bg-navy/8 text-navy flex items-center justify-center mb-3">
      <Icon className="w-4 h-4" />
    </div>
    <p className="font-semibold text-navy text-sm">{label}</p>
    <p className="text-xs text-navy/55 mt-0.5">{sub}</p>
  </button>
);

const HomeTab = ({ onNavigate }) => {
  const go = (tab, subTab) => onNavigate && onNavigate(tab, subTab);

  return (
    <section data-testid="home-tab" className="ds-fade">
      <PageHeader
        eyebrow="Lakeview Admin"
        title={<>Keep it simple<span className="text-gold">.</span></>}
        subtitle="The everyday tools you need to keep the restaurant website and customer information current."
      />

      <div className="mb-8" data-testid="home-quick-actions">
        <p className="ds-eyebrow mb-3">Quick actions</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <QuickAction
            icon={Pencil}
            label="Menu & Website"
            sub="Prices, dishes and public copy"
            onClick={() => go("menu")}
            testId="qa-menu"
          />
          <QuickAction
            icon={ImageIcon}
            label="Library"
            sub="Photos and saved media"
            onClick={() => go("library")}
            testId="qa-library"
          />
          <QuickAction
            icon={Users}
            label="Customers"
            sub="Loyalty and subscribers"
            onClick={() => go("customers")}
            testId="qa-customers"
          />
          <QuickAction
            icon={UtensilsCrossed}
            label="Catering"
            sub="Review event inquiries"
            onClick={() => go("catering")}
            testId="qa-catering"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="ds-card p-5">
          <p className="ds-eyebrow mb-1">Most common task</p>
          <h3 className="ds-display text-xl">Update the menu</h3>
          <p className="text-sm text-navy/60 mt-2">
            Change prices, descriptions and restaurant website copy without digging through extra tools.
          </p>
          <button
            type="button"
            onClick={() => go("menu")}
            className="ds-btn-secondary mt-4 text-xs"
          >
            Open Menu & Website
          </button>
        </div>

        <div className="ds-card p-5">
          <p className="ds-eyebrow mb-1">Customer follow-up</p>
          <h3 className="ds-display text-xl">Customers & catering</h3>
          <p className="text-sm text-navy/60 mt-2">
            Keep loyalty, subscriber and catering follow-up easy to find and easy to use.
          </p>
          <div className="flex flex-wrap gap-2 mt-4">
            <button
              type="button"
              onClick={() => go("customers", "loyalty")}
              className="ds-btn-secondary text-xs"
            >
              Open Customers
            </button>
            <button
              type="button"
              onClick={() => go("catering")}
              className="ds-btn-secondary text-xs"
            >
              Open Catering
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default HomeTab;
