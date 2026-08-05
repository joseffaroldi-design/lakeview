import React, { useState, useEffect } from "react";
import axios from "axios";
import Navbar from "@/components/public/Navbar";
import Footer from "@/components/public/Footer";
import StickyOrderBar from "@/components/public/StickyOrderBar";
import { SECTION_COMPONENTS, FALLBACK_LAYOUT } from "@/components/public/sectionRegistry";
import { API } from "@/lib/publicConfig";
import { trackPageView } from "@/lib/analytics";

const PublicSite = () => {
  const [content, setContent] = useState(null);
  const [menuCategories, setMenuCategories] = useState([]);
  const [layoutSections, setLayoutSections] = useState(FALLBACK_LAYOUT);

  useEffect(() => {
    trackPageView("home");
    const fetchContent = async () => {
      try {
        const [contentRes, menuRes, layoutRes] = await Promise.all([
          axios.get(`${API}/content`),
          axios.get(`${API}/menu`),
          axios.get(`${API}/homepage/layout`),
        ]);
        setContent(contentRes.data);
        setMenuCategories(menuRes.data);
        if (Array.isArray(layoutRes.data?.sections) && layoutRes.data.sections.length) {
          setLayoutSections(layoutRes.data.sections);
        }
      } catch (error) {
        console.error("Error fetching site content:", error);
      }
    };
    fetchContent();
  }, []);

  return (
    <div data-testid="home-page">
      <Navbar />
      <main>
        {layoutSections
          .filter((s) => s.visible !== false && SECTION_COMPONENTS[s.key])
          .map((s) => {
            const Render = SECTION_COMPONENTS[s.key];
            return (
              <Render
                key={s.key}
                content={content}
                menuCategories={menuCategories}
                titleOverride={s.title || ""}
                bodyOverride={s.body || ""}
              />
            );
          })}
      </main>
      <Footer />
      <StickyOrderBar />
      {/* Sprint 12D: SpinWheel + InstallPrompt removed */}
    </div>
  );
};

export default PublicSite;
