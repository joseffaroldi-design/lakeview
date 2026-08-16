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
  Phone,
  ShoppingBag,
  Star,
  Truck,
  UtensilsCrossed,
  X,
} from "lucide-react";
import axios from "axios";
import "@/public-site.css";
import { DEFAULT_IMAGES } from "@/config/siteImages";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const LOGO = "/logo.webp";
const PHONE = "(504) 289-1032";
const PHONE_HREF = "tel:+15042891032";
const ADDRESS = "872 Harrison Ave, New Orleans, LA 70124";
const SQUARE_URL = "https://lakeview-burgers-seafood.square.site";
const UBER_URL = "https://www.ubereats.com/store-browse-uuid/de2b0e6b-0fdf-44bc-92e9-2c223008bd36?diningMode=DELIVERY";

const absolutize = (url) => {
  if (!url) return url;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  if (url.startsWith("/api/")) return `${process.env.REACT_APP_BACKEND_URL}${url}`;
  return url;
};

let IMAGES = { ...DEFAULT_IMAGES };
const imageListeners = new Set();
const notifyImageListeners = () => imageListeners.forEach((cb) => cb(IMAGES));

const loadSiteImages = async () => {
  try {
    const res = await axios.get(`${API}/site-images`);
    const overrides = res?.data?.slots || {};
    const merged = { ...DEFAULT_IMAGES };
    for (const [slot, url] of Object.entries(overrides)) {
      if (url && DEFAULT_IMAGES[slot] !== undefined) merged[slot] = absolutize(url);
    }
    IMAGES = merged;
    notifyImageListeners();
  } catch (_) {
    // Public pages always retain safe default photography.
  }
};

loadSiteImages();

const useSiteImages = () => {
  const [imgs, setImgs] = useState(IMAGES);
  useEffect(() => {
    const cb = (next) => setImgs(next);
    imageListeners.add(cb);
    setImgs(IMAGES);
    return () => imageListeners.delete(cb);
  }, []);
  return imgs;
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

const OrderButton = ({ className = "", children = "Order Pickup" }) => (
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
          <a href="/#visit" onClick={() => setOpen(false)}>Visit</a>
          <a href={SQUARE_URL} target="_blank" rel="noopener noreferrer">Order Pickup</a>
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
      <a href="/#visit"><MapPin /><span>Visit</span></a>
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

const Hero = () => {
  const images = useSiteImages();
  return (
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
      <div className="lv-hero-photo"><img src={images.homeHero} alt="Lakeview Burgers & Seafood burger" fetchPriority="high" /></div>
    </section>
  );
};

const FavoriteCard = ({ image, name }) => (
  <Link to="/menu" className="lv-favorite-card">
    <img src={image} alt={`${name} from Lakeview Burgers & Seafood`} loading="lazy" />
    <strong>{name}</strong><span>★</span>
  </Link>
);

const Favorites = () => {
  const images = useSiteImages();
  const items = [
    [images.burger, "Lakeview Burger"],
    [images.tacos, "Shrimp Tacos"],
    [images.poboy, "Shrimp Po'boy"],
    [images.fries, "Café Fries"],
    [images.tenders, "Chicken Tenders"],
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
    <div className="lv-order-choice"><span className="mustard"><ShoppingBag /></span><div><h3>Pickup</h3><p>Order ahead and we'll have it ready.</p><a href={SQUARE_URL} target="_blank" rel="noopener noreferrer" onClick={() => track("square_pickup_band")}>Order Pickup →</a></div></div>
    <div className="lv-order-choice"><span className="blue"><Truck /></span><div><h3>Delivery</h3><p>Get Lakeview delivered to you.</p><a href={UBER_URL} target="_blank" rel="noopener noreferrer" onClick={() => track("uber_delivery_band")}>Get Delivery →</a></div></div>
    <div className="lv-order-choice"><span className="orange"><Phone /></span><div><h3>Call It In</h3><p>Prefer the old-fashioned way?</p><a href={PHONE_HREF} onClick={() => track("call_order_band")}>Call an Order In →</a></div></div>
  </section>
);

const StoryCatering = () => {
  const images = useSiteImages();
  return (
    <section className="lv-story-catering">
      <article id="story" className="lv-story">
        <div className="lv-story-copy"><p className="lv-kicker">Our Story</p><h2>New Orleans Cooking.<br />Lakeview Family.</h2><p>Lakeview Burgers & Seafood has been part of the neighborhood since 2015. Built on decades of restaurant experience and a love for good food, we're proud to serve the community we call home.</p><a className="lv-btn lv-btn-outline" href="#visit">Visit Us <ChevronRight /></a></div>
        <div className="lv-story-photos"><img className="main" src={images.about} alt="Lakeview Burgers & Seafood restaurant and family story" loading="lazy" /><img className="small" src={images.burger} alt="Lakeview burger served at Lakeview Burgers & Seafood" loading="lazy" /></div>
      </article>
      <article id="catering" className="lv-catering">
        <div className="lv-catering-copy"><p className="lv-kicker">Lakeview Catering</p><h2>Feed Everybody.</h2><p>Office lunches, game days, birthdays, family gatherings and events—we'll help you put together something everyone will want to eat.</p><a className="lv-btn lv-btn-cream" href={PHONE_HREF} onClick={() => track("call_catering")}>Call About Catering <ChevronRight /></a></div>
        <img src={images.catering} alt="Catering from Lakeview Burgers & Seafood" loading="lazy" />
      </article>
    </section>
  );
};

const CateringInquiry = () => {
  const [form, setForm] = useState({ name: "", email: "", phone: "", event_date: "", guest_count: "", message: "" });
  const [status, setStatus] = useState("idle");
  const [feedback, setFeedback] = useState("");

  const fieldStyle = {
    width: "100%",
    minHeight: 46,
    border: "1px solid rgba(16,40,57,.22)",
    background: "#fbf7e8",
    color: "#102839",
    padding: "11px 12px",
    font: "inherit",
    borderRadius: 4,
  };

  const setField = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    if (status === "sending") return;
    setStatus("sending");
    setFeedback("");
    try {
      const response = await axios.post(`${API}/catering/inquiry`, form);
      setStatus("success");
      setFeedback(response?.data?.message || "Thank you! We'll be in touch soon.");
      setForm({ name: "", email: "", phone: "", event_date: "", guest_count: "", message: "" });
      track("catering_inquiry_submit");
    } catch (error) {
      setStatus("error");
      setFeedback(error?.response?.data?.detail || "We couldn't send your request. Please call us and we'll help you directly.");
    }
  };

  return (
    <section aria-labelledby="catering-inquiry-title" style={{ padding: "44px max(22px,5vw) 50px", background: "#fbf7e8", borderTop: "1px solid rgba(221,154,58,.3)" }}>
      <div style={{ maxWidth: 980, margin: "0 auto", display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))", gap: 34, alignItems: "start" }}>
        <div>
          <p className="lv-kicker">Planning an Event?</p>
          <h2 id="catering-inquiry-title" style={{ fontSize: "clamp(2.5rem,5vw,4.4rem)", lineHeight: .96, margin: "8px 0 16px" }}>Tell Us What You Need.</h2>
          <p style={{ color: "rgba(16,40,57,.72)", lineHeight: 1.65, maxWidth: 500 }}>Send the basics and we'll follow up about menu options, quantities and timing. Prefer to talk it through? Call us at <a href={PHONE_HREF} style={{ fontWeight: 700 }}>{PHONE}</a>.</p>
        </div>
        <form onSubmit={submit} style={{ display: "grid", gap: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 12 }}>
            <label style={{ fontWeight: 700, fontSize: ".82rem" }}>Name<input aria-label="Name" required value={form.name} onChange={setField("name")} style={{ ...fieldStyle, marginTop: 6 }} /></label>
            <label style={{ fontWeight: 700, fontSize: ".82rem" }}>Email<input aria-label="Email" type="email" required value={form.email} onChange={setField("email")} style={{ ...fieldStyle, marginTop: 6 }} /></label>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 12 }}>
            <label style={{ fontWeight: 700, fontSize: ".82rem" }}>Phone<input aria-label="Phone" value={form.phone} onChange={setField("phone")} style={{ ...fieldStyle, marginTop: 6 }} /></label>
            <label style={{ fontWeight: 700, fontSize: ".82rem" }}>Event date<input aria-label="Event date" type="date" value={form.event_date} onChange={setField("event_date")} style={{ ...fieldStyle, marginTop: 6 }} /></label>
            <label style={{ fontWeight: 700, fontSize: ".82rem" }}>Guests<input aria-label="Approximate guest count" inputMode="numeric" value={form.guest_count} onChange={setField("guest_count")} style={{ ...fieldStyle, marginTop: 6 }} /></label>
          </div>
          <label style={{ fontWeight: 700, fontSize: ".82rem" }}>What are you planning?<textarea aria-label="Catering message" required rows={4} value={form.message} onChange={setField("message")} style={{ ...fieldStyle, resize: "vertical", marginTop: 6 }} /></label>
          <button type="submit" className="lv-btn lv-btn-green" disabled={status === "sending"} style={{ justifySelf: "start", cursor: status === "sending" ? "wait" : "pointer" }}>{status === "sending" ? "Sending…" : "Send Catering Request"}</button>
          {feedback ? <p role="status" style={{ margin: 0, fontWeight: 700, color: status === "error" ? "#965d26" : "#364526" }}>{feedback}</p> : null}
        </form>
      </div>
    </section>
  );
};

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
    <div className="lv-footer-grid"><img src={LOGO} alt="Lakeview Burgers & Seafood" /><div><b>Lakeview Burgers & Seafood</b><p>872 Harrison Ave<br />New Orleans, LA 70124<br />{PHONE}</p></div><div><b>Quick Links</b><Link to="/menu">Menu</Link><a href="/#catering">Catering</a><a href="/#story">Our Story</a><a href="/#visit">Visit</a></div><div><b>Hours</b><p>Mon–Sat<br />11:30 AM – 11:00 PM<br />Sunday: Closed</p></div></div>
    <div style={{ maxWidth: 1200, margin: "24px auto 0", padding: "0 4px", textAlign: "right" }}>
      <Link to="/login" style={{ fontSize: "0.7rem", letterSpacing: "0.14em", textTransform: "uppercase", color: "rgba(246,241,219,0.38)", textDecoration: "none" }}>Admin</Link>
    </div>
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
  return <div className="lv-site"><Header /><main><Hero /><TrustBand /><Favorites /><OrderBand /><StoryCatering /><CateringInquiry /><Specials specials={specials} /><Visit contact={content?.contact} /></main><Footer /><MobileBottomNav /></div>;
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
  const images = useSiteImages();
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
          <img src={images.hero} alt="Lakeview Burgers & Seafood menu favorites" />
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
                  {(cat.items || []).map((item, itemIndex) => {
                    const primary = Array.isArray(item.photos) && item.photos[0]
                      ? `${API}/media/file/${item.photos[0]}`
                      : null;
                    return (
                      <article className="lv-menu-item" key={`${id}-${item.name || itemIndex}`}>
                        <div className="lv-menu-item-copy"><div className="lv-menu-item-title"><h3>{item.name}</h3><span></span><strong>{item.price !== undefined && item.price !== null ? `$${item.price}` : ""}</strong></div>{item.description ? <p>{item.description}</p> : null}</div>
                        {primary ? (
                          <img
                            src={primary}
                            alt={`${item.name} from Lakeview Burgers & Seafood`}
                            loading="lazy"
                            onError={(e) => { e.currentTarget.style.display = "none"; }}
                          />
                        ) : null}
                      </article>
                    );
                  })}
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
