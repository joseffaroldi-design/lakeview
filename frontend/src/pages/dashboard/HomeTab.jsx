import React from "react";
import { Image as ImageIcon, LayoutTemplate, Pencil, Users } from "lucide-react";
import BillingCard from "./BillingCard";
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
        eyebrow="Studio"
        title={<>Good to see you<span className="text-gold">.</span></>}
        subtitle="Keep the restaurant basics current without extra tools getting in the way."
      />

      <div className="mb-8" data-testid="home-quick-actions">
        <p className="ds-eyebrow mb-3">Quick actions</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <QuickAction
            icon={Pencil}
            label="Menu & Today's Pick"
            sub="Edit dishes, prices and today's feature"
            onClick={() => go("menu")}
            testId="qa-menu"
          />
          <QuickAction
            icon={ImageIcon}
            label="Library"
            sub="Manage saved photos and files"
            onClick={() => go("library")}
            testId="qa-library"
          />
          <QuickAction
            icon={Users}
            label="Customers"
            sub="Loyalty, subscribers and inquiries"
            onClick={() => go("customers")}
            testId="qa-customers"
          />
          <QuickAction
            icon={LayoutTemplate}
            label="Layout"
            sub="Manage website presentation"
            onClick={() => go("layout")}
            testId="qa-layout"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div className="ds-card p-5">
          <p className="ds-eyebrow mb-1">Daily operations</p>
          <h3 className="ds-display text-xl">Menu first</h3>
          <p className="text-sm text-navy/60 mt-2">
            Keep prices, descriptions and Today's Pick accurate. Those are the highest-value changes you make most often.
          </p>
          <button
            type="button"
            onClick={() => go("menu")}
            className="ds-btn-secondary mt-4 text-xs"
          >
            Open Menu
          </button>
        </div>

        <div className="ds-card p-5">
          <p className="ds-eyebrow mb-1">Customer retention</p>
          <h3 className="ds-display text-xl">Loyalty & customers</h3>
          <p className="text-sm text-navy/60 mt-2">
            View loyalty members, subscribers and catering inquiries from one place.
          </p>
          <button
            type="button"
            onClick={() => go("customers", "loyalty")}
            className="ds-btn-secondary mt-4 text-xs"
          >
            Open Customers
          </button>
        </div>
      </div>

      <div className="mb-8">
        <p className="ds-eyebrow mb-3">Budget</p>
        <BillingCard />
      </div>
    </section>
  );
};

export default HomeTab;
