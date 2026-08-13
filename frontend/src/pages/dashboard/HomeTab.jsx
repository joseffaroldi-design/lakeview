import React from "react";
import { Image as ImageIcon, Megaphone, Pencil, Users } from "lucide-react";
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
        eyebrow="Lakeview admin"
        title={<>Keep the restaurant current<span className="text-gold">.</span></>}
        subtitle="Five simple areas for the things you actually update."
      />

      <div className="mb-8" data-testid="home-quick-actions">
        <p className="ds-eyebrow mb-3">Quick actions</p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <QuickAction
            icon={Pencil}
            label="Menu"
            sub="Dishes, prices and descriptions"
            onClick={() => go("menu")}
            testId="qa-menu"
          />
          <QuickAction
            icon={Megaphone}
            label="Marketing"
            sub="Website copy and customer-facing info"
            onClick={() => go("marketing")}
            testId="qa-marketing"
          />
          <QuickAction
            icon={ImageIcon}
            label="Library"
            sub="Photos and saved files"
            onClick={() => go("library")}
            testId="qa-library"
          />
          <QuickAction
            icon={Users}
            label="Customers"
            sub="Loyalty, subscribers and catering"
            onClick={() => go("customers")}
            testId="qa-customers"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="ds-card p-5">
          <p className="ds-eyebrow mb-1">Most common task</p>
          <h3 className="ds-display text-xl">Keep the menu accurate</h3>
          <p className="text-sm text-navy/60 mt-2">
            Update prices and descriptions here and keep the public website in sync.
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
          <p className="ds-eyebrow mb-1">Customer activity</p>
          <h3 className="ds-display text-xl">One customer area</h3>
          <p className="text-sm text-navy/60 mt-2">
            Loyalty members, email subscribers and catering inquiries stay together.
          </p>
          <button
            type="button"
            onClick={() => go("customers")}
            className="ds-btn-secondary mt-4 text-xs"
          >
            Open Customers
          </button>
        </div>
      </div>
    </section>
  );
};

export default HomeTab;
