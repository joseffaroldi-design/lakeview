/**
 * Site-image slot registry — single source of truth for the public site's
 * editable photo slots.
 *
 * Used by:
 *   - `frontend/src/PublicSite.jsx`               (renders the public site)
 *   - `frontend/src/pages/dashboard/WebsiteImagesTab.jsx` (admin manager)
 *
 * The backend's allowlist lives in `backend/routers/site_images.py`
 * (`ALLOWED_SLOTS`) and MUST stay in sync with the `key` field below.
 *
 * `default` is the hard-coded fallback URL rendered when the admin has not
 * overridden a slot (or when the API/asset is temporarily unavailable).
 */

export const SITE_IMAGE_SLOTS = [
  {
    key: "homeHero",
    label: "Homepage Hero",
    sub: "Main burger photo on the homepage",
    ratio: "Portrait or square works best",
    default: "/hero-burger.jpg",
  },
  {
    key: "hero",
    label: "Menu Page Hero",
    sub: "Large photo at the top of /menu",
    ratio: "Landscape (16:9 or 3:2)",
    default: "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=1600&q=82&auto=format&fit=crop",
  },
  {
    key: "burger",
    label: "Lakeview Burger",
    sub: "Favorites carousel · card 1",
    ratio: "Square (1:1)",
    default: "https://images.unsplash.com/photo-1550547660-d9450f859349?w=1000&q=82&auto=format&fit=crop",
  },
  {
    key: "tacos",
    label: "Shrimp Tacos",
    sub: "Favorites carousel · card 2",
    ratio: "Square (1:1)",
    default: "/tacos.jpg",
  },
  {
    key: "poboy",
    label: "Shrimp Po'boy",
    sub: "Favorites carousel · card 3",
    ratio: "Square (1:1)",
    default: "/shrimp-poboy.jpg",
  },
  {
    key: "fries",
    label: "Café Fries",
    sub: "Favorites carousel · card 4",
    ratio: "Square (1:1)",
    default: "/cafe-fries.jpg",
  },
  {
    key: "tenders",
    label: "Chicken Tenders",
    sub: "Favorites carousel · card 5",
    ratio: "Square (1:1)",
    default: "/chicken-tenders.jpg",
  },
  {
    key: "catering",
    label: "Catering",
    sub: "Catering block on the homepage",
    ratio: "Landscape (16:9)",
    default: "https://images.unsplash.com/photo-1541544741938-0af808871cc0?w=1400&q=82&auto=format&fit=crop",
  },
  {
    key: "about",
    label: "Our Story",
    sub: "Story section photo",
    ratio: "Portrait or square",
    default: "https://customer-assets.emergentagent.com/job_lakeview-grill/artifacts/11ja5k21_IMG_1894.jpeg",
  },
];

/** Map of slot key → hard-coded default URL. */
export const DEFAULT_IMAGES = Object.fromEntries(
  SITE_IMAGE_SLOTS.map((s) => [s.key, s.default]),
);

/** Ordered list of allowed slot keys. Backend must stay in sync. */
export const SLOT_KEYS = SITE_IMAGE_SLOTS.map((s) => s.key);
