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
import "@/public-site-polish.css";
import "@/revenue-conversion.css";
import { DEFAULT_IMAGES } from "@/config/siteImages";
import { event as gaEvent } from "@/lib/gaAnalytics";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const LOGO = "/logo.webp";
const PHONE = "(504) 289-1032";
const PHONE_HREF = "tel:+15042891032";
const ADDRESS = "872 Harrison Ave, New Orleans, LA 70124";
const SQUARE_URL = "https://lakeview-burgers-seafood.square.site";
const UBER_URL = "https://www.ubereats.com/store-browse-uuid/de2b0e6b-0fdf-44bc-92e9-2c223008bd36?diningMode=DELIVERY";
const GOOGLE_REVIEWS_URL = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent("Lakeview Burgers & Seafood 872 Harrison Ave New Orleans LA")}`;
const BUSINESS_TIME_ZONE = "America/Chicago";
const DEFAULT_OPEN_TIME = "11:30";
const DEFAULT_CLOSE_TIME = "23:00";

const absolutize = (url) => {
  if (!url) return url;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  if (url.startsWith("/api/")) return `${process.env.REACT_APP_BACKEND_URL}${url}`;
  return url;
};

const timeToMinutes = (value, fallback) => {
  const match = String(value || fallback).match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return timeToMinutes(fallback, "00:00");
  return Number(match[1]) * 60 + Number(match[2]);
};

const getBusinessStatus = (contact) => {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: BUSINESS_TIME_ZONE,
    weekday: "long",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const weekday = values.weekday;
  const nowMinutes = Number(values.hour) * 60 + Number(values.minute);
  const openMinutes = timeToMinutes(contact?.hours_open, DEFAULT_OPEN_TIME);
  const closeMinutes = timeToMinutes(contact?.hours_close, DEFAULT_CLOSE_TIME);
  const sundayClosed = contact?.sunday_closed !== false;

  if (weekday === "Sunday" && sundayClosed) return { open: false, label: "Closed today · Opens Monday at 11:30 AM" };
  if (nowMinutes < openMinutes) return { open: false, label: `Closed · Opens at ${contact?.hours_open_label || "11:30 AM"}` };
  if (nowMinutes >= closeMinutes) {
    return { open: false, label: weekday === "Saturday" ? "Closed · Opens Monday at 11:30 AM" : `Closed · Opens tomorrow at ${contact?.hours_open_label || "11:30 AM"}` };
  }
  return { open: true, label: `Open now · Until ${contact?.hours_close_label || "11:00 PM"}` };
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

// Map internal button_name values → GA4 event names. Only names in this
// map fire a GA4 event; everything else stays local-only. Each mapping
// entry returns { name, params } so we can attach lightweight context
// (link_url, location) without inflating the payload.
const GA_EVENTS = {
  // Menu views & clicks
  menu_view_hero:          { name: "menu_view",           params: { location: "hero" } },
  menu_view_favorites:     { name: "menu_view",           params: { location: "favorites" } },
  menu_view:               { name: "menu_view",           params: { location: "menu_page" } },
  // Order Now / pickup clicks (Square)
  order_online:            { name: "order_pickup_click",  params: { location: "generic",     link_url: SQUARE_URL } },
  order_online_hero:       { name: "order_pickup_click",  params: { location: "hero",        link_url: SQUARE_URL } },
  order_online_header:     { name: "order_pickup_click",  params: { location: "header",      link_url: SQUARE_URL } },
  order_online_drawer:     { name: "order_pickup_click",  params: { location: "mobile_menu", link_url: SQUARE_URL } },
  order_online_bottom_nav: { name: "order_pickup_click",  params: { location: "bottom_nav",  link_url: SQUARE_URL } },
  order_online_footer:     { name: "order_pickup_click",  params: { location: "footer",      link_url: SQUARE_URL } },
  order_online_menu_strip: { name: "order_pickup_click",  params: { location: "menu_strip",  link_url: SQUARE_URL } },
  pickup_click:            { name: "order_pickup_click",  params: { location: "order_band",  link_url: SQUARE_URL } },
  // Uber Eats / delivery clicks
  delivery_click:          { name: "order_delivery_click", params: { location: "order_band", link_url: UBER_URL } },
  // Catering
  catering_quote_click:    { name: "catering_quote_click", params: { location: "story_catering" } },
  catering_inquiry_submit: { name: "catering_submit",      params: { location: "catering_form" } },
  // Phone
  call_header:             { name: "phone_click", params: { location: "header",      link_url: PHONE_HREF } },
  call_mobile_header:      { name: "phone_click", params: { location: "mobile_header", link_url: PHONE_HREF } },
  call_order_click:        { name: "phone_click", params: { location: "order_band",  link_url: PHONE_HREF } },
  call_visit_click:        { name: "phone_click", params: { location: "visit",       link_url: PHONE_HREF } },
  // Directions / map
  directions_hero:         { name: "directions_click", params: { location: "hero" } },
  directions_click:        { name: "directions_click", params: { location: "visit" } },
};

const track = async (buttonName) => {
  // Fire GA4 event first (synchronous, non-blocking, guarded no-op if
  // GA4 isn't configured). Backend analytics call follows and its errors
  // are swallowed so a customer action never blocks on analytics.
  const mapped = GA_EVENTS[buttonName];
  if (mapped) gaEvent(mapped.name, mapped.params);
  try {
    await axios.post(`${API}/analytics/button-click`, {
      button_name: buttonName,
      session_id: sessionStorage.getItem("visitor_session") || undefined,
    });
  } catch (_) {
    // Analytics must never block a customer action.
  }
};

const OrderButton = ({ className = "", children = "Order Online", tracking = "order_online" }) => (
  <a href={SQUARE_URL} target="_blank" rel="noopener noreferrer" onClick={() => track(tracking)} className={`lv-btn lv-btn-gold ${className}`}>
    {children}<ChevronRight size={16} aria-hidden="true" />
  </a>
);

const Header = () => {
  const [open, setOpen] = useState(false);
  return (
    <header className="lv-header">
      <div className="lv-header-inner">
        <button className="lv-mobile-trigger" type="button" onClick={() => setOpen((v) => !v)} aria-label="Open menu" aria-expanded={open}>
          {open ? <X /> : <MenuIcon />}<span>Menu</span>
        </button>
        <Link to="/" className="lv-brand" aria-label="Lakeview Burgers and Seafood home"><img src={LOGO} alt="Lakeview Burgers & Seafood" /></Link>
        <nav className="lv-desktop-nav" aria-label="Primary navigation">
          <Link to="/menu">Menu</Link><span>★</span><a href="/#specials">Specials</a><span>★</span><a href="/#catering">Catering</a><span>★</span><a href="/#story">Our Story</a><span>★</span><a href="/#visit">Contact</a>
        </nav>
        <div className="lv-header-actions">
          <a className="lv-btn lv-btn-outline lv-call-desktop" href={PHONE_HREF} onClick={() => track("call_header")}>Call Us</a>
          <OrderButton className="lv-order-desktop" tracking="order_online_header" />
          <a href={PHONE_HREF} className="lv-mobile-call" onClick={() => track("call_mobile_header")} aria-label="Call Lakeview Burgers & Seafood"><Phone /><span>Call Us</span></a>
        </div>
      </div>
      {open && (
        <nav className="lv-mobile-drawer" aria-label="Mobile navigation">
          <Link to="/menu" onClick={() => setOpen(false)}>Menu</Link><a href="/#specials" onClick={() => setOpen(false)}>Specials</a><a href="/#catering" onClick={() => setOpen(false)}>Catering</a><a href="/#story" onClick={() => setOpen(false)}>Our Story</a><a href="/#visit" onClick={() => setOpen(false)}>Visit</a><a href={SQUARE_URL} target="_blank" rel="noopener noreferrer" onClick={() => track("order_online_drawer")}>Order Online</a>
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
      <a className="lv-bottom-order" href={SQUARE_URL} target="_blank" rel="noopener noreferrer" onClick={() => track("order_online_bottom_nav")}><span><ShoppingBag /></span><b>Order</b></a>
      <a href="/#catering"><ShoppingBag /><span>Catering</span></a><a href="/#visit"><MapPin /><span>Visit</span></a>
    </nav>
  );
};

const TrustBand = () => (
  <section className="lv-trust" aria-label="Lakeview highlights">
    <div><span>⚜</span><b>Family Owned</b></div><div><Star /><b>Serving Lakeview<br />Since 2015</b></div><div><Fish /><b>New Orleans<br />Cooking</b></div><div><Truck /><b>Pickup &<br />Delivery</b></div>
  </section>
);

const Hero = ({ contact }) => {
  const images = useSiteImages();
  const status = getBusinessStatus(contact);
  return (
    <section className="lv-hero">
      <div className="lv-hero-copy">
        <p className="lv-script">Lakeview, New Orleans</p>
        <h1>Burgers.<br />Seafood.<br /><span>Good Times.</span></h1>
        <p className="lv-hero-sub">A family-owned neighborhood restaurant serving Lakeview since 2015.</p>
        <div className="lv-hero-actions"><OrderButton tracking="order_online_hero" /><Link className="lv-btn lv-btn-cream" to="/menu" onClick={() => track("menu_view_hero")}>View Menu</Link></div>
        <p className="lv-order-modes">Pickup • Delivery • Call-in</p>
        <div className={`lv-open-status ${status.open ? "is-open" : "is-closed"}`}><span></span>{status.label}</div>
        <a className="lv-address" href={`https://maps.google.com/?q=${encodeURIComponent(ADDRESS)}`} target="_blank" rel="noopener noreferrer" onClick={() => track("directions_hero")}><MapPin /> 872 Harrison Ave, New Orleans, LA</a>
      </div>
      <div className="lv-hero-photo"><img src={images.homeHero} alt="Lakeview Burgers & Seafood burger" fetchPriority="high" /></div>
    </section>
  );
};

const FavoriteCard = ({ image, name, category, note }) => (
  <Link to={`/menu?category=${encodeURIComponent(category)}`} className="lv-favorite-card" onClick={() => track(`favorite_${name.toLowerCase().replace(/[^a-z0-9]+/g, "_")}`)}>
    <img src={image} alt={`${name} from Lakeview Burgers & Seafood`} loading="lazy" /><strong>{name}</strong><small>{note}</small><span>★</span>
  </Link>
);

const Favorites = () => {
  const images = useSiteImages();
  const items = [
    [images.burger, "Lakeview Burger", "Burgers", "Our neighborhood classic"],
    [images.tacos, "Shrimp Tacos", "Tacos", "A Lakeview favorite"],
    [images.poboy, "Shrimp Po'boy", "Sandwiches & Po'Boys", "A New Orleans classic"],
    [images.fries, "Café Fries", "Appetizers", "Loaded and made for sharing"],
    [images.tenders, "Chicken Tenders", "Fried Plates", "Crispy comfort food"],
  ];
  return (
    <section className="lv-favorites" id="menu-preview">
      <div className="lv-favorites-intro"><p className="lv-kicker">Our</p><h2>Favorites</h2><p>The dishes our regulars keep coming back for.</p><Link to="/menu" className="lv-text-link" onClick={() => track("menu_view_favorites")}>View the full menu <ChevronRight /></Link></div>
      <div className="lv-favorites-scroll">{items.map(([image, name, category, note]) => <FavoriteCard key={name} image={image} name={name} category={category} note={note} />)}</div>
    </section>
  );
};

const OrderBand = () => (
  <section className="lv-order-band">
    <div className="lv-order-title"><p>How do you</p><h2>Want It?</h2></div>
    <div className="lv-order-choice"><span className="mustard"><ShoppingBag /></span><div><h3>Pickup</h3><p>Order ahead and we'll have it ready.</p><a href={SQUARE_URL} target="_blank" rel="noopener noreferrer" onClick={() => track("pickup_click")}>Order Pickup →</a></div></div>
    <div className="lv-order-choice"><span className="blue"><Truck /></span><div><h3>Delivery</h3><p>Get Lakeview delivered to you.</p><a href={UBER_URL} target="_blank" rel="noopener noreferrer" onClick={() => track("delivery_click")}>Get Delivery →</a></div></div>
    <div className="lv-order-choice"><span className="orange"><Phone /></span><div><h3>Call It In</h3><p>Prefer the old-fashioned way?</p><a href={PHONE_HREF} onClick={() => track("call_order_click")}>Call an Order In →</a></div></div>
  </section>
);

const MobileStatusBar = ({ contact }) => {
  const status = getBusinessStatus(contact);
  return (
    <aside className={`lv-mobile-status-bar lv-open-status ${status.open ? "is-open" : "is-closed"}`} aria-label="Business hours status">
      <Clock aria-hidden="true" /><span aria-hidden="true"></span>{status.label}
    </aside>
  );
};

const StoryCatering = () => {
  const images = useSiteImages();
  return (
    <section className="lv-story-catering">
      <article id="story" className="lv-story">
        <div className="lv-story-copy"><p className="lv-kicker">Our Story</p><h2>New Orleans Cooking.<br />Lakeview Family.</h2><p>Lakeview Burgers & Seafood has been part of the neighborhood since 2015. Built on decades of restaurant experience and a love for good food, we're proud to serve the community we call home.</p><a className="lv-btn lv-btn-outline" href="#visit">Visit Us <ChevronRight /></a></div>
        <div className="lv-story-photos"><img className="main" src={images.about} alt="Lakeview Burgers & Seafood restaurant and family story" loading="lazy" /><img className="small" src={images.burger} alt="Lakeview burger served at Lakeview Burgers & Seafood" loading="lazy" /></div>
      </article>
      <article id="catering" className="lv-catering">
        <div className="lv-catering-copy"><p className="lv-kicker">Lakeview Catering</p><h2>Feeding 20? 50? 100?</h2><p>Office lunches, game days, birthdays, family gatherings and events—we'll help you put together something everyone will want to eat.</p><a className="lv-btn lv-btn-cream" href="#catering-quote" onClick={() => track("catering_quote_click")}>Get a Catering Quote <ChevronRight /></a></div>
        <img src={images.catering} alt="Catering from Lakeview Burgers & Seafood" loading="lazy" />
      </article>
    </section>
  );
};

const CateringInquiry = () => {
  const [form, setForm] = useState({ name: "", email: "", phone: "", event_date: "", guest_count: "", message: "" });
  const [status, setStatus] = useState("idle");
  const [feedback, setFeedback] = useState("");
  const fieldStyle = { width: "100%", minHeight: 46, border: "1px solid rgba(16,40,57,.22)", background: "#fbf7e8", color: "#102839", padding: "11px 12px", font: "inherit", borderRadius: 4 };
  const setField = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  const submit = async (event) => {
    event.preventDefault();
    if (status === "sending") return;
    setStatus("sending"); setFeedback("");
    try {
      const response = await axios.post(`${API}/catering/inquiry`, form);
      setStatus("success"); setFeedback(response?.data?.message || "Thank you! We'll be in touch soon.");
      setForm({ name: "", email: "", phone: "", event_date: "", guest_count: "", message: "" }); track("catering_inquiry_submit");
    } catch (error) {
      setStatus("error"); setFeedback(error?.response?.data?.detail || "We couldn't send your request. Please call us and we'll help you directly.");
    }
  };
  return (
    <section id="catering-quote" className="lv-catering-inquiry" aria-labelledby="catering-inquiry-title">
      <div className="lv-catering-inquiry-inner">
        <div><p className="lv-kicker">Planning an Event?</p><h2 id="catering-inquiry-title">Tell Us What You Need.</h2><p>Send the basics and we'll follow up about menu options, quantities and timing. Prefer to talk it through? Call us at <a href={PHONE_HREF}>{PHONE}</a>.</p></div>
        <form onSubmit={submit}>
          <div className="lv-form-row two"><label>Name<input aria-label="Name" required value={form.name} onChange={setField("name")} style={fieldStyle} /></label><label>Email<input aria-label="Email" type="email" required value={form.email} onChange={setField("email")} style={fieldStyle} /></label></div>
          <div className="lv-form-row three"><label>Phone<input aria-label="Phone" value={form.phone} onChange={setField("phone")} style={fieldStyle} /></label><label>Event date<input aria-label="Event date" type="date" value={form.event_date} onChange={setField("event_date")} style={fieldStyle} /></label><label>Guests<input aria-label="Approximate guest count" inputMode="numeric" value={form.guest_count} onChange={setField("guest_count")} style={fieldStyle} /></label></div>
          <label>What are you planning?<textarea aria-label="Catering message" required rows={4} value={form.message} onChange={setField("message")} style={{ ...fieldStyle, resize: "vertical" }} /></label>
          <button type="submit" className="lv-btn lv-btn-green" disabled={status === "sending"}>{status === "sending" ? "Sending…" : "Get My Catering Quote"}</button>
          {feedback ? <p role="status" className={status === "error" ? "lv-form-error" : "lv-form-success"}>{feedback}</p> : null}
        </form>
      </div>
    </section>
  );
};

const Specials = ({ specials }) => {
  if (!specials?.length) return null;
  return (
    <section id="specials" className="lv-specials">
      <div><p className="lv-script">Today at Lakeview</p><h2>Specials</h2><p>Made fresh. Available while they last.</p></div>
      <div className="lv-special-list">{specials.slice(0, 4).map((item) => (
        <article key={item.id || item.name}><h3>{item.name || item.title}</h3><p>{item.description}</p>{item.price ? <strong>${item.price}</strong> : null}<a className="lv-special-order" href={SQUARE_URL} target="_blank" rel="noopener noreferrer" onClick={() => track(`special_${String(item.name || item.title || "item").toLowerCase().replace(/[^a-z0-9]+/g, "_")}`)}>Order This →</a></article>
      ))}</div>
    </section>
  );
};

const Visit = ({ contact }) => {
  const hours1 = contact?.hours_weekday || "Monday - Saturday: 11:30am - 11pm";
  const hours2 = contact?.hours_weekend || "Sunday: Closed";
  const status = getBusinessStatus(contact);
  return (
    <section id="visit" className="lv-visit">
      <div className="lv-visit-copy"><p className="lv-script">Come See Us</p><h2>Right Here on Harrison.</h2><div className={`lv-open-status ${status.open ? "is-open" : "is-closed"}`}><span></span>{status.label}</div><div className="lv-visit-details"><MapPin /><p><strong>Lakeview Burgers & Seafood</strong><br />872 Harrison Ave<br />New Orleans, LA 70124</p><Clock /><p><strong>Hours</strong><br />{hours1}<br />{hours2}</p><Phone /><p><strong>Phone</strong><br /><a href={PHONE_HREF}>{PHONE}</a></p></div><div className="lv-visit-actions"><a className="lv-btn lv-btn-green" href={`https://maps.google.com/?q=${encodeURIComponent(ADDRESS)}`} target="_blank" rel="noopener noreferrer" onClick={() => track("directions_click")}>Get Directions <ExternalLink /></a><a className="lv-btn lv-btn-outline" href={PHONE_HREF} onClick={() => track("call_visit_click")}>Call Us</a></div></div>
      <div className="lv-map-wrap"><iframe title="Lakeview Burgers & Seafood location" src="https://maps.google.com/maps?q=872%20Harrison%20Ave%2C%20New%20Orleans%2C%20LA%2070124&t=&z=15&ie=UTF8&iwloc=&output=embed" loading="lazy" referrerPolicy="no-referrer-when-downgrade" /></div>
    </section>
  );
};

const ReviewProof = () => (
  <section className="lv-review-proof" aria-label="Lakeview customer reviews">
    <div><p className="lv-kicker">Our Neighbors Say It Best</p><h2>See Why Lakeview Keeps Coming Back.</h2><div className="lv-review-stars" aria-hidden="true">★★★★★</div><p>Read recent customer reviews, then come see us on Harrison Avenue.</p></div>
    <a className="lv-btn lv-btn-outline" href={GOOGLE_REVIEWS_URL} target="_blank" rel="noopener noreferrer" onClick={() => track("google_reviews_click")}>Read Google Reviews <ExternalLink size={15} /></a>
  </section>
);

const Footer = () => (
  <footer className="lv-footer">
    <div className="lv-footer-cta"><p>What's for dinner?</p><span>Burgers • Seafood • Po'boys • New Orleans Favorites</span><OrderButton tracking="order_online_footer" /></div>
    <div className="lv-footer-grid"><img src={LOGO} alt="Lakeview Burgers & Seafood" /><div><b>Lakeview Burgers & Seafood</b><p>872 Harrison Ave<br />New Orleans, LA 70124<br />{PHONE}</p></div><div><b>Quick Links</b><Link to="/menu">Menu</Link><a href="/#catering">Catering</a><a href="/#story">Our Story</a><a href="/#visit">Visit</a></div><div><b>Hours</b><p>Mon–Sat<br />11:30 AM – 11:00 PM<br />Sunday: Closed</p></div></div>
    <div style={{ maxWidth: 1200, margin: "24px auto 0", padding: "0 4px", textAlign: "right" }}><Link to="/login" style={{ fontSize: "0.7rem", letterSpacing: "0.14em", textTransform: "uppercase", color: "rgba(246,241,219,0.38)", textDecoration: "none" }}>Admin</Link></div>
  </footer>
);

export const PublicHome = () => {
  const [content, setContent] = useState(null);
  const [specials, setSpecials] = useState([]);
  useEffect(() => {
    window.scrollTo(0, 0);
    track("home_view");
    Promise.allSettled([axios.get(`${API}/content`), axios.get(`${API}/specials?active_only=true`)]).then(([contentResult, specialsResult]) => {
      if (contentResult.status === "fulfilled") setContent(contentResult.value.data);
      if (specialsResult.status === "fulfilled") setSpecials(specialsResult.value.data || []);
    });
  }, []);
  return <div className="lv-site"><Header /><main><Hero contact={content?.contact} /><TrustBand /><Favorites /><OrderBand /><MobileStatusBar contact={content?.contact} /><Visit contact={content?.contact} /><Specials specials={specials} /><StoryCatering /><CateringInquiry /><ReviewProof /></main><Footer /><MobileBottomNav /></div>;
};

const categoryAliases = {
  burger: "Burgers", burgers: "Burgers", poboy: "Po'boys", "po-boys": "Po'boys", "po'boys": "Po'boys", seafood: "Seafood", plates: "Plates", sides: "Sides", drinks: "Drinks",
};

const POPULAR_ITEMS = new Set(["lakeview burger", "shrimp tacos", "café fries", "cafe fries", "shrimp po'boy"]);
const normalize = (value) => String(value || "").toLowerCase().trim();

export const PublicMenu = () => {
  const images = useSiteImages();
  const location = useLocation();
  const [categories, setCategories] = useState([]);
  const [active, setActive] = useState("");

  useEffect(() => {
    window.scrollTo(0, 0);
    track("menu_view");
    axios.get(`${API}/menu`).then((res) => setCategories(Array.isArray(res.data) ? res.data : [])).catch(() => setCategories([]));
  }, []);

  const navCategories = useMemo(() => categories.filter((cat) => (cat.items || []).length > 0), [categories]);
  useEffect(() => { if (!active && navCategories[0]) setActive(navCategories[0].slug || navCategories[0].id || "category-0"); }, [active, navCategories]);

  const jumpTo = (cat, index) => {
    const id = `menu-${cat.slug || cat.id || index}`;
    setActive(cat.slug || cat.id || `category-${index}`);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  useEffect(() => {
    if (!navCategories.length) return;
    const requested = new URLSearchParams(location.search).get("category");
    if (!requested) return;
    const target = navCategories.find((cat) => normalize(cat.display_name || cat.name).includes(normalize(requested)) || normalize(cat.slug).includes(normalize(requested)));
    if (!target) return;
    const index = navCategories.indexOf(target);
    const timer = window.setTimeout(() => jumpTo(target, index), 80);
    return () => window.clearTimeout(timer);
  }, [location.search, navCategories]);

  return (
    <div className="lv-site lv-menu-page">
      <Header />
      <main>
        <section className="lv-menu-hero"><div className="lv-menu-hero-copy"><p className="lv-script">Made in Lakeview; Loved in New Orleans.</p><h1>Our Menu</h1><div className="lv-rule">⚜</div><p>From big, juicy burgers to fresh Gulf seafood and New Orleans favorites—there's something here for every appetite.</p></div><img src={images.hero} alt="Lakeview Burgers & Seafood menu favorites" /></section>
        <nav className="lv-category-nav" aria-label="Menu categories">{navCategories.map((cat, index) => {
          const key = cat.slug || cat.id || `category-${index}`;
          const label = categoryAliases[String(cat.slug || "").toLowerCase()] || cat.display_name || cat.name || "Menu";
          return <button key={key} className={active === key ? "active" : ""} onClick={() => jumpTo(cat, index)}>{label}</button>;
        })}</nav>
        <div className="lv-menu-conversion-strip"><span>Ready to eat?</span><OrderButton tracking="order_online_menu_strip" /></div>
        <section className="lv-menu-sheet">
          {navCategories.length === 0 ? <div className="lv-menu-loading">Loading today's menu…</div> : navCategories.map((cat, catIndex) => {
            const id = `menu-${cat.slug || cat.id || catIndex}`;
            return (
              <section className="lv-menu-category" id={id} key={id}>
                <div className="lv-menu-category-heading"><span></span><h2>{cat.display_name || cat.name}</h2><span></span></div>
                {cat.subtitle ? <p className="lv-menu-subtitle">{cat.subtitle}</p> : null}
                <div className="lv-menu-items">{(cat.items || []).map((item, itemIndex) => {
                  const primary = Array.isArray(item.photos) && item.photos[0] ? `${API}/media/file/${item.photos[0]}` : null;
                  const popular = POPULAR_ITEMS.has(normalize(item.name));
                  return (
                    <article className={`lv-menu-item ${popular ? "is-popular" : ""}`} key={`${id}-${item.name || itemIndex}`}>
                      <div className="lv-menu-item-copy">{popular ? <span className="lv-popular-badge">★ Lakeview Favorite</span> : null}<div className="lv-menu-item-title"><h3>{item.name}</h3><span></span><strong>{item.price !== undefined && item.price !== null ? `$${item.price}` : ""}</strong></div>{item.description ? <p>{item.description}</p> : null}</div>
                      {primary ? <img src={primary} alt={`${item.name} from Lakeview Burgers & Seafood`} loading="lazy" onError={(e) => { e.currentTarget.style.display = "none"; }} /> : null}
                    </article>
                  );
                })}</div>
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