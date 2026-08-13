import React, { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  ChevronRight,
  Clock,
  ExternalLink,
  Fish,
  Home,
  MapPin,
  Menu as MenuIcon,
  MoreHorizontal,
  Phone,
  ShoppingBag,
  Star,
  Truck,
  UtensilsCrossed,
  X,
} from "lucide-react";
import axios from "axios";
import "@/public-site.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const LOGO = "/logo.webp";
const PHONE = "(504) 289-1032";
const PHONE_HREF = "tel:+15042891032";
const ADDRESS = "872 Harrison Ave, New Orleans, LA 70124";
const SQUARE_URL = "https://lakeview-burgers-seafood.square.site";
const UBER_URL = "https://www.ubereats.com/store-browse-uuid/de2b0e6b-0fdf-44bc-92e9-2c223008bd36?diningMode=DELIVERY";

// PHOTO PLAN
// These are temporary development references only. Do not treat them as final
// production photography. The public redesign is intentionally structured so
// each URL below can be replaced one-for-one with approved Lakeview photos
// without changing layout, data, or backend behavior.
const IMAGES = {
  hero: "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=1600&q=82&auto=format&fit=crop",
  homeHero: "/hero-burger.jpg",
  burger: "https://images.unsplash.com/photo-1550547660-d9450f859349?w=1000&q=82&auto=format&fit=crop",
  poboy: "/shrimp-poboy.jpg",
  fries: "/cafe-fries.jpg",
  tenders: "/chicken-tenders.jpg",
  tacos: "/tacos.jpg",
  catering: "https://images.unsplash.com/photo-1541544741938-0af808871cc0?w=1400&q=82&auto=format&fit=crop",
  about: "https://customer-assets.emergentagent.com/job_lakeview-grill/artifacts/11ja5k21_IMG_1894.jpeg",
};

const track = async (buttonName) => {
  try {
    await axios.post(`${API}/analytics/button-click`, {
      button_name: buttonName,
      session_id: sessionStorage.getItem("visitor_session") || undefined,
    });
  } catch (_) {
    // Analytics must never block a customer action.
  }
};

const OrderButton = ({ className = "", children = "Order Online" }) => (
  <a
    href={SQUARE_URL}
    target="_blank"
    rel="noopener noreferrer"
    onClick={() => track("square_public_redesign")}
    className={`lv-btn lv-btn-gold ${className}`}
  >
    {children}<ChevronRight size={16} aria-hidden="true" />
  </a>
);

const Header = () => {
  const [open, setOpen] = useState(false);
  return (
    <header className="lv-header">
      <div className="lv-header-inner">
        <button className="lv-mobile-trigger" type="button" onClick={() => setOpen((v) => !v)} aria-label="Open menu" aria-expanded={open}>
          {open ? <X /> : <MenuIcon />}
          <span>Menu</span>
        </button>

        <Link to="/" className="lv-brand" aria-label="Lakeview Burgers and Seafood home">
          <img src={LOGO} alt="Lakeview Burgers & Seafood" />
        </Link>

        <nav className="lv-desktop-nav" aria-label="Primary navigation">
          <Link to="/menu">Menu</Link><span>★</span>
          <a href="/#specials">Specials</a><span>★</span>
          <a href="/#catering">Catering</a><span>★</span>
          <a href="/#story">Our Story</a><span>★</span>
          <a href="/#visit">Contact</a>
        </nav>

        <div className="lv-header-actions">
          <a className="lv-btn lv-btn-outline lv-call-desktop" href={PHONE_HREF} onClick={() => track("call_header")}>Call Us</a>
          <OrderButton className="lv-order-desktop" />
          <a href={PHONE_HREF} className="lv-mobile-call" onClick={() => track("call_mobile_header")} aria-label="Call Lakeview Burgers & Seafood"><Phone /><span>Call Us</span></a>
        </div>
      </div>
      {open && (
        <nav className="lv-mobile-drawer" aria-label="Mobile navigation">
          <Link to="/menu" onClick={() => setOpen(false)}>Menu</Link>
          <a href="/#specials" onClick={() => setOpen(false)}>Specials</a>
          <a href="/#catering" onClick={() => setOpen(false)}>Catering</a>
          <a href="/#story" onClick={() => setOpen(false)}>Our Story</a>
          <a href="/#visit" onClick={() => setOpen(false)}>Contact</a>
          <a href={SQUARE_URL} target="_blank" rel="noopener noreferrer">Order Online</a>
        </nav>
      )}
    </header>
  );
};

const MobileBottomNav = () => {
  const location = useLocation();
  const onMenu = location.pathname === "/menu";
  return (
    <nav className="lv-bottom-nav" aria-label="Mobile app navigation">
      <Link className={!onMenu ? "active" : ""} to="/"><Home /><span>Home</span></Link>
      <Link className={onMenu ? "active" : ""} to="/menu"><UtensilsCrossed /><span>Menu</span></Link>
      <a className="lv-bottom-order" href={SQUARE_URL} target="_blank" rel="noopener noreferrer" onClick={() => track("square_bottom_nav")}><span><ShoppingBag /></span><b>Order</b></a>
      <a href="/#catering"><ShoppingBag /><span>Catering</span></a>
      <a href="/#visit"><MoreHorizontal /><span>More</span></a>
    </nav>
  );
};

const TrustBand = () => (
  <section className="lv-trust" aria-label="Lakeview highlights">
    <div><span>⚜</span><b>Family Owned</b></div>
    <div><Star /><b>Serving Lakeview<br />Since 2015</b></div>
    <div><Fish /><b>New Orleans<br />Cooking</b></div>
    <div><Truck /><b>Pickup &<br />Delivery</b></div>
  </section>
);

const Hero = () => (
  <section className="lv-hero">
    <div className="lv-hero-copy">
      <p className="lv-script">Lakeview, New Orleans</p>
      <h1>Burgers.<br />Seafood.<br /><span>Good Times.</span></h1>
      <p className="lv-hero-sub">A family-owned neighborhood restaurant serving Lakeview since 2015.</p>
      <div className="lv-hero-actions">
        <OrderButton />
        <Link className="lv-btn lv-btn-cream" to="/menu">View Menu</Link>
      </div>
      <a className="lv-address" href={`https://maps.google.com/?q=${encodeURIComponent(ADDRESS)}`} target="_blank" rel="noopener noreferrer">
        <MapPin /> 872 Harrison Ave, New Orleans, LA
      </a>
    </div>
    <div className="lv-hero-photo"><img src={IMAGES.homeHero} alt="Lakeview Burgers & Seafood burger" fetchPriority="high" /></div>
  </section>
);

const FavoriteCard = ({ image, name }) => (
  <Link to="/menu" className="lv-favorite-card">
    <img src={image} alt={`Temporary ${name} photography placeholder`} loading="lazy" />
    <strong>{name}</strong><span>★</span>
  </Link>
);

const Favorites = () => {
  const items = [
    [IMAGES.burger, "Lakeview Burger"],
    [IMAGES.tacos, "Shrimp Tacos"],
    [IMAGES.poboy, "Shrimp Po'boy"],
    [IMAGES.fries, "Café Fries"],
    [IMAGES.tenders, "Chicken Tenders"],
  ];
  return (
    <section className="lv-favorites" id="menu-preview">
      <div className="lv-favorites-intro">
        <p className="lv-kicker">Our</p><h2>Favorites</h2>
        <p>The dishes our regulars keep coming back for.</p>
        <Link to="/menu" className="lv-text-link">View the full menu <ChevronRight /></Link>
      </div>
      <div className="lv-favorites-scroll">
        {items.map(([image, name]) => <FavoriteCard key={name} image={image} name={name} />)}
      </div>
    </section>
  );
};

const OrderBand = () => (
  <section className="lv-order-band">
    <div className="lv-order-title"><p>How do you</p><h2>Want It?</h2></div>
    <div className="lv-order-choice"><span className="mustard"><ShoppingBag /></span><div><h3>Pickup</h3><p>Order ahead and we'll have it ready.</p><a href={SQUARE_URL} target="_blank" rel="noopener noreferrer">Order pickup →</a></div></div>
    <div className="lv-order-choice"><span className="blue"><Truck /></span><div><h3>Delivery</h3><p>Get Lakeview delivered to you.</p><a href={UBER_URL} target="_blank" rel="noopener noreferrer">Order delivery →</a></div></div>
    <div className="lv-order-choice"><span className="orange"><Phone /></span><div><h3>Call It In</h3><p>Prefer the old-fashioned way?</p><a href={PHONE_HREF}>Call {PHONE} →</a></div></div>
  </section>
);

const StoryCatering = () => (
  <section className="lv-story-catering">
    <article id="story" className="lv-story">
      <div className="lv-story-copy"><p className="lv-kicker">Our Story</p><h2>New Orleans Cooking.<br />Lakeview Family.</h2><p>Lakeview Burgers & Seafood has been part of the neighborhood since 2015. Built on decades of restaurant experience and a love for good food, we're proud to serve the community we call home.</p><a className="lv-btn lv-btn-outline" href="#visit">Meet the Family <ChevronRight /></a></div>
      <div className="lv-story-photos"><img className="main" src={IMAGES.about} alt="Temporary Lakeview story photography placeholder" loading="lazy" /><img className="small" src={IMAGES.burger} alt="Temporary Lakeview burger photography placeholder" loading="lazy" /></div>
    </article>
    <article id="catering" className="lv-catering">
      <div className="lv-catering-copy"><p className="lv-kicker">Lakeview Catering</p><h2>Feed Everybody.</h2><p>Office lunches, game days, birthdays, family gatherings and events—we'll help you put together something everyone will want to eat.</p><a className="lv-btn lv-btn-cream" href={PHONE_HREF}>Call About Catering <ChevronRight /></a></div>
      <img src={IMAGES.catering} alt="Temporary catering food photography placeholder" loading="lazy" />
    </article>
  </section>
);

const Specials = ({ specials }) => {
  if (!specials?.length) return null;
  return (
    <section id="specials" className="lv-specials">
      <div><p className="lv-script">Today's Board</p><h2>Specials</h2><p>Made fresh. Available while they last.</p></div>
      <div className="lv-special-list">
        {specials.slice(0, 4).map((item) => (
          <article key={item.id || item.name}><h3>{item.name || item.title}</h3><p>{item.description}</p>{item.price ? <strong>${item.price}</strong> : null}</article>
        ))}
      </div>
    </section>
  );
};

const Reviews = () => (
  <section className="lv-reviews">
    <div className="lv-reviews-heading"><p className="lv-kicker">What Our Neighbors Say</p><h2>Loved Around Lakeview.</h2></div>
    <div className="lv-review"><div>★★★★★</div><p>“The kind of neighborhood restaurant you want right around the corner.”</p><span>Google review</span></div>
    <div className="lv-review"><div>★★★★★</div><p>“Great seafood, burgers and friendly local service.”</p><span>Google review</span></div>
    <div className="lv-review"><div>★★★★★</div><p>“Always one of our go-to spots in Lakeview.”</p><span>Google review</span></div>
  </section>
);

const Visit = ({ contact }) => {
  const hours1 = contact?.hours_weekday || "Monday - Saturday: 11:30am - 11pm";
  const hours2 = contact?.hours_weekend || "Sunday: Closed";
  return (
    <section id="visit" className="lv-visit">
      <div className="lv-visit-copy"><p className="lv-script">Come See Us</p><h2>Right Here on Harrison.</h2><div className="lv-visit-details"><MapPin /><p><strong>Lakeview Burgers & Seafood</strong><br />872 Harrison Ave<br />New Orleans, LA 70124</p><Clock /><p><strong>Hours</strong><br />{hours1}<br />{hours2}</p><Phone /><p><strong>Phone</strong><br /><a href={PHONE_HREF}>{PHONE}</a></p></div><div className="lv-visit-actions"><a className="lv-btn lv-btn-green" href={`https://maps.google.com/?q=${encodeURIComponent(ADDRESS)}`} target="_blank" rel="noopener noreferrer">Get Directions <ExternalLink /></a><a className="lv-btn lv-btn-outline" href={PHONE_HREF}>Call Us</a></div></div>
      <div className="lv-map-wrap"><iframe title="Lakeview Burgers & Seafood location" src="https://maps.google.com/maps?q=872%20Harrison%20Ave%2C%20New%20Orleans%2C%20LA%2070124&t=&z=15&ie=UTF8&iwloc=&output=embed" loading="lazy" referrerPolicy="no-referrer-when-downgrade" /></div>
    </section>
  );
};

const Footer = () => (
  <footer className="lv-footer">
    <div className="lv-footer-cta"><p>What's for dinner?</p><span>Burgers • Seafood • Po'boys • New Orleans Favorites</span><OrderButton /></div>
    <div className="lv-footer-grid"><img src={LOGO} alt="Lakeview Burgers & Seafood" /><div><b>Lakeview Burgers & Seafood</b><p>872 Harrison Ave<br />New Orleans, LA 70124<br />{PHONE}</p></div><div><b>Quick Links</b><Link to="/menu">Menu</Link><a href="/#catering">Catering</a><a href="/#story">Our Story</a><a href="/#visit">Contact</a></div><div><b>Hours</b><p>Mon–Sat<br />11:30 AM – 11:00 PM<br />Sunday: Closed</p></div></div>
  </footer>
);

export const PublicHome = () => {
  const [content, setContent] = useState(null);
  const [specials, setSpecials] = useState([]);
  useEffect(() => {
    window.scrollTo(0, 0);
    Promise.allSettled([axios.get(`${API}/content`), axios.get(`${API}/specials?active_only=true`)]).then(([contentResult, specialsResult]) => {
      if (contentResult.status === "fulfilled") setContent(contentResult.value.data);
      if (specialsResult.status === "fulfilled") setSpecials(specialsResult.value.data || []);
    });
  }, []);
  return <div className="lv-site"><Header /><main><Hero /><TrustBand /><Favorites /><OrderBand /><StoryCatering /><Specials specials={specials} /><Reviews /><Visit contact={content?.contact} /></main><Footer /><MobileBottomNav /></div>;
};

const categoryAliases = {
  burger: "Burgers",
  burgers: "Burgers",
  poboy: "Po'boys",
  "po-boys": "Po'boys",
  "po'boys": "Po'boys",
  seafood: "Seafood",
  plates: "Plates",
  sides: "Sides",
  drinks: "Drinks",
};

export const PublicMenu = () => {
  const [categories, setCategories] = useState([]);
  const [active, setActive] = useState("");
  useEffect(() => {
    window.scrollTo(0, 0);
    axios.get(`${API}/menu`).then((res) => setCategories(Array.isArray(res.data) ? res.data : [])).catch(() => setCategories([]));
  }, []);

  const navCategories = useMemo(() => categories.filter((cat) => (cat.items || []).length > 0), [categories]);
  useEffect(() => { if (!active && navCategories[0]) setActive(navCategories[0].slug || navCategories[0].id || "category-0"); }, [active, navCategories]);

  const jumpTo = (cat, index) => {
    const id = `menu-${cat.slug || cat.id || index}`;
    setActive(cat.slug || cat.id || `category-${index}`);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="lv-site lv-menu-page">
      <Header />
      <main>
        <section className="lv-menu-hero">
          <div className="lv-menu-hero-copy"><p className="lv-script">Made in Lakeview; Loved in New Orleans.</p><h1>Our Menu</h1><div className="lv-rule">⚜</div><p>From big, juicy burgers to fresh Gulf seafood and New Orleans favorites—there's something here for every appetite.</p></div>
          <img src={IMAGES.hero} alt="Temporary Lakeview menu hero photography placeholder" />
        </section>
        <nav className="lv-category-nav" aria-label="Menu categories">
          {navCategories.map((cat, index) => {
            const key = cat.slug || cat.id || `category-${index}`;
            const label = categoryAliases[String(cat.slug || "").toLowerCase()] || cat.display_name || cat.name || "Menu";
            return <button key={key} className={active === key ? "active" : ""} onClick={() => jumpTo(cat, index)}>{label}</button>;
          })}
        </nav>
        <section className="lv-menu-sheet">
          {navCategories.length === 0 ? <div className="lv-menu-loading">Loading today's menu…</div> : navCategories.map((cat, catIndex) => {
            const id = `menu-${cat.slug || cat.id || catIndex}`;
            return (
              <section className="lv-menu-category" id={id} key={id}>
                <div className="lv-menu-category-heading"><span></span><h2>{cat.display_name || cat.name}</h2><span></span></div>
                {cat.subtitle ? <p className="lv-menu-subtitle">{cat.subtitle}</p> : null}
                <div className="lv-menu-items">
                  {(cat.items || []).map((item, itemIndex) => (
                    <article className="lv-menu-item" key={`${id}-${item.name || itemIndex}`}>
                      <div className="lv-menu-item-copy"><div className="lv-menu-item-title"><h3>{item.name}</h3><span></span><strong>{item.price !== undefined && item.price !== null ? `$${item.price}` : ""}</strong></div>{item.description ? <p>{item.description}</p> : null}</div>
                      {catIndex === 0 && itemIndex < 4 ? <img src={[IMAGES.burger, IMAGES.hero, IMAGES.burger, IMAGES.hero][itemIndex]} alt="" aria-hidden="true" loading="lazy" /> : null}
                    </article>
                  ))}
                </div>
              </section>
            );
          })}
          <p className="lv-menu-disclaimer">* Consuming raw or undercooked meats, poultry, seafood, shellfish or eggs may increase your risk of foodborne illness.</p>
        </section>
      </main>
      <MobileBottomNav />
    </div>
  );
};