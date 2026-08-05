import React from "react";
import Hero from "@/components/public/Hero";
import About from "@/components/public/About";
import Specials from "@/components/public/Specials";
import Menu from "@/components/public/Menu";
import EmailSignup from "@/components/public/EmailSignup";
import LoyaltyCard from "@/components/public/LoyaltyCard";
import CateringForm from "@/components/public/CateringForm";
import Contact from "@/components/public/Contact";
import TodaysFeatured from "@/components/TodaysFeatured";

// Home Page Component
export const SECTION_COMPONENTS = {
  hero:             ({ content, ...p }) => <Hero content={content?.hero} {...p} />,
  todays_featured:  (p) => <TodaysFeatured {...p} />,
  specials:         (p) => <Specials {...p} />,
  about:            ({ content, ...p }) => <About content={content?.about} {...p} />,
  menu:             ({ menuCategories, ...p }) => <Menu categories={menuCategories} {...p} />,
  email_signup:     (p) => <EmailSignup {...p} />,
  loyalty:          (p) => <LoyaltyCard {...p} />,
  catering:         (p) => <CateringForm {...p} />,
  contact:          ({ content, ...p }) => <Contact content={content?.contact} {...p} />,
};

// Fallback if /api/homepage/layout is unreachable — keeps the public
// site usable even if a deploy was missed.
export const FALLBACK_LAYOUT = [
  { key: "hero", visible: true },
  { key: "todays_featured", visible: true },
  { key: "specials", visible: true },
  { key: "about", visible: true },
  { key: "menu", visible: true },
  { key: "email_signup", visible: true },
  { key: "loyalty", visible: true },
  { key: "catering", visible: true },
  { key: "contact", visible: true },
];
