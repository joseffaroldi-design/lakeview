import React from "react";
import { ABOUT_IMG } from "@/lib/publicConfig";

// About Section
const About = ({ content, titleOverride, bodyOverride }) => {
  return (
    <section 
      id="about" 
      data-testid="about-section"
      className="py-24 md:py-32 paper-texture"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          <div className="order-2 lg:order-1">
            <div className="img-zoom decorative-border p-2 vintage-shadow">
              <img 
                src={ABOUT_IMG} 
                alt="Lakeview Burgers & Seafood Restaurant"
                data-testid="about-image" 
                className="w-full h-[400px] object-cover"
                loading="lazy"
                decoding="async"
              />
            </div>
          </div>
          
          <div className="order-1 lg:order-2 space-y-8">
            <div>
              <p className="font-accent text-3xl text-gold mb-2">{content?.accent_text || "Our Story"}</p>
              <h2 className="font-serif text-4xl md:text-5xl text-navy font-bold tracking-tight">
                {titleOverride || content?.heading || "A New Orleans Tradition"}
              </h2>
            </div>
            
            <div className="section-divider !mx-0"></div>
            
            <div className="space-y-6 font-sans text-muted-foreground leading-relaxed">
              <p>{bodyOverride || content?.paragraph1 || "Founded by Chef Joseph Faroldi in 2015, Lakeview Burgers & Seafood has become a beloved fixture in the charming Lakeview neighborhood. What started as a dream to bring quality burgers and fresh Gulf seafood to the community has grown into a true family affair."}</p>
              <p>{content?.paragraph2 || "Today, Chef Joseph works alongside his son Josef, passing down culinary traditions and a passion for great food to the next generation. Together, they take pride in sourcing the freshest Gulf seafood daily and crafting each dish with care and expertise."}</p>
              <p>{content?.paragraph3 || "Whether you're craving a perfectly charred burger or authentic Louisiana seafood, the Faroldi family invites you to experience the taste of the Crescent City at Lakeview Burgers & Seafood."}</p>
            </div>
            
            <div className="flex items-center space-x-4 pt-4">
              <span className="text-gold text-2xl">⚜</span>
              <span className="font-serif italic text-navy text-lg">{content?.established_text || "Est. 2015 \u2022 New Orleans, LA"}</span>
              <span className="text-gold text-2xl">⚜</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default About;
