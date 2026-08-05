import React from "react";

// Menu Item Component
const MenuItem = ({ name, description, price, index }) => (
  <div className="menu-item py-4 px-2 rounded-sm" data-testid={`menu-item-${index}`}>
    <div className="flex items-baseline">
      <h4 className="font-serif text-lg text-navy font-semibold">{name}</h4>
      <span className="dotted-leader"></span>
      <span className="font-sans font-bold text-forest text-lg">${price}</span>
    </div>
    {description && (
      <p className="font-sans text-sm text-muted-foreground mt-1">{description}</p>
    )}
  </div>
);

// Menu Section
const Menu = ({ categories, titleOverride, bodyOverride }) => {
  const getGridCols = (cols) => {
    if (cols === 4) return "grid-cols-2 md:grid-cols-4 gap-x-12";
    if (cols === 3) return "grid-cols-1 md:grid-cols-3 gap-x-12";
    return "grid-cols-1 md:grid-cols-2 gap-x-16";
  };

  return (
    <section 
      id="menu" 
      data-testid="menu-section"
      className="py-24 md:py-32 bg-cream"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <p className="font-accent text-3xl text-gold mb-2">Delicious</p>
          <h2 className="font-serif text-4xl md:text-5xl text-navy font-bold tracking-tight mb-4">
            {titleOverride || "Our Menu"}
          </h2>
          {bodyOverride ? (
            <p className="font-sans text-muted-foreground max-w-2xl mx-auto mb-4 text-sm md:text-base">{bodyOverride}</p>
          ) : null}
          <div className="section-divider"></div>
        </div>
        
        <div className="decorative-border p-8 md:p-12 bg-card paper-texture vintage-shadow">
          {categories.map((cat, catIdx) => (
            <div key={cat.id || catIdx} className={catIdx < categories.length - 1 ? "mb-12" : ""}>
              <div className="flex items-center justify-center mb-8">
                <span className="text-gold">⚜</span>
                <h3 className="font-serif text-2xl md:text-3xl text-navy font-bold mx-4 uppercase tracking-wider">
                  {cat.display_name}
                </h3>
                <span className="text-gold">⚜</span>
              </div>
              {cat.subtitle && (
                <p className="text-center text-muted-foreground mb-6 font-sans text-sm">{cat.subtitle}</p>
              )}
              <div className={`grid ${getGridCols(cat.columns)}`}>
                {(cat.items || []).map((item, idx) => (
                  <MenuItem key={`${cat.slug}-${item.name || idx}`} index={`${cat.slug}-${idx}`} name={item.name} description={item.description} price={item.price} />
                ))}
              </div>
            </div>
          ))}
        </div>
        
        <p className="text-center font-sans text-sm text-muted-foreground mt-8 italic">
          * Consuming raw or undercooked meats, poultry, seafood, shellfish or eggs may increase your risk of foodborne illness
        </p>
      </div>
    </section>
  );
};

export default Menu;
