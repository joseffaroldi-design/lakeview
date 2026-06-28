"""Default seed data for MongoDB collections + seeding routine."""
import logging
import uuid

logger = logging.getLogger(__name__)

DEFAULT_SITE_CONTENT = {
    "hero": {
        "tagline": "Lakeview",
        "subtitle": "Serving the finest burgers and fresh Gulf seafood in the heart of New Orleans since 2015"
    },
    "about": {
        "accent_text": "Our Story",
        "heading": "A New Orleans Tradition",
        "paragraph1": "Founded by Chef Joseph Faroldi in 2015, Lakeview Burgers & Seafood has become a beloved fixture in the charming Lakeview neighborhood. What started as a dream to bring quality burgers and fresh Gulf seafood to the community has grown into a true family affair.",
        "paragraph2": "Today, Chef Joseph works alongside his son Josef, passing down culinary traditions and a passion for great food to the next generation. Together, they take pride in sourcing the freshest Gulf seafood daily and crafting each dish with care and expertise.",
        "paragraph3": "Whether you're craving a perfectly charred burger or authentic Louisiana seafood, the Faroldi family invites you to experience the taste of the Crescent City at Lakeview Burgers & Seafood.",
        "established_text": "Est. 2015 \u2022 New Orleans, LA"
    },
    "contact": {
        "address_line1": "872 Harrison Ave",
        "address_line2": "New Orleans, LA 70124",
        "hours_weekday": "Monday - Saturday: 11:30am - 11pm",
        "hours_weekend": "Sunday: Closed",
        "phone": "(504) 289-1032",
        "email": "info@lakeviewburgers.com",
        "catering_text": "Catering available for private events and parties"
    }
}

DEFAULT_MENU_CATEGORIES = [
    {
        "id": str(uuid.uuid4()), "slug": "appetizers", "display_name": "Appetizers",
        "subtitle": None, "columns": 2, "sort_order": 1,
        "items": [
            {"name": "Caf\u00e9 Fries", "description": "With Roast Beef Gravy, Cheddar Cheese, Sour Cream & Jalape\u00f1os", "price": "13.25"},
            {"name": "Chicken Wings (6)", "description": "Asian Glaze, BBQ or Buffalo", "price": "11.00"},
            {"name": "Chicken Wings (12)", "description": "Asian Glaze, BBQ or Buffalo", "price": "17.25"},
            {"name": "Fresh Mozzarella Cheese Sticks", "description": "With Marinara Sauce", "price": "10.00"},
            {"name": "Fried Louisiana Okra", "description": "With Ranch", "price": "9.00"},
            {"name": "Fried Onion Rings", "description": "", "price": "9.00"},
            {"name": "Fried Pickles", "description": "With Ranch", "price": "8.00"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "soups", "display_name": "Soups",
        "subtitle": None, "columns": 3, "sort_order": 2,
        "items": [
            {"name": "Chicken Andouille Gumbo", "description": "Cup / Bowl", "price": "7.00 / 9.00"},
            {"name": "Corn & Crab Bisque", "description": "Cup / Bowl", "price": "7.00 / 9.00"},
            {"name": "Seafood Gumbo", "description": "Cup / Bowl", "price": "7.00 / 9.00"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "salads", "display_name": "Salads",
        "subtitle": None, "columns": 2, "sort_order": 3,
        "items": [
            {"name": "Caesar Salad", "description": "", "price": "10.00"},
            {"name": "Garden Salad", "description": "Mixed Greens, Tomato, Red Onion & Cucumber", "price": "10.00"},
            {"name": "Spinach Salad", "description": "Red Onions, Pecans, Hot Bacon & Honey Mustard Dressing", "price": "10.00"},
            {"name": "Add Grilled/Blackened Tuna or Shrimp", "description": "", "price": "10.95"},
            {"name": "Add Fried Oysters or Shrimp", "description": "", "price": "12.95"},
            {"name": "Add Grilled/Blackened Chicken", "description": "", "price": "7.50"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "burgers", "display_name": "Burgers",
        "subtitle": None, "columns": 2, "sort_order": 4,
        "items": [
            {"name": "Classic Burger (8oz)", "description": "Served on a fresh bun with your choice of toppings", "price": "13.50"},
            {"name": "Extra Patty", "description": "Add another 8oz patty", "price": "5.75"},
            {"name": "Add Bacon", "description": "", "price": "0.50"},
            {"name": "Add Cheese", "description": "American, Blue Cheese, Cheddar, Pepper Jack, Provolone or Swiss", "price": "0.50"},
            {"name": "Add Fried Egg", "description": "", "price": "1.75"},
            {"name": "Add Mushroom", "description": "", "price": "0.50"},
            {"name": "Add Onion", "description": "Grilled or Raw", "price": "0.50"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "sandwiches", "display_name": "Sandwiches & Po'Boys",
        "subtitle": None, "columns": 2, "sort_order": 5,
        "items": [
            {"name": "Chicken Sandwich", "description": "Grilled, Blackened, or Paneed - Bun or Po'Boy, Dressed", "price": "12.00"},
            {"name": "Chicken Parmesan", "description": "Mozzarella/Provolone", "price": "12.00"},
            {"name": "Cuban", "description": "Ham, Salami & Pork", "price": "12.00"},
            {"name": "French Fry Po'Boy", "description": "Cheddar Cheese & Gravy", "price": "9.00"},
            {"name": "Fried Fish Po'Boy", "description": "Dressed", "price": "12.00"},
            {"name": "Fried Oyster Po'Boy", "description": "Dressed", "price": "17.50"},
            {"name": "Fried Shrimp Po'Boy", "description": "Dressed", "price": "13.25"},
            {"name": "Grilled Shrimp Po'Boy", "description": "Blackened", "price": "13.25"},
            {"name": "Grilled Ham", "description": "", "price": "9.00"},
            {"name": "Ham/Roast/Swiss", "description": "", "price": "12.00"},
            {"name": "Hot Sausage", "description": "", "price": "10.50"},
            {"name": "Meatball Sub", "description": "Mozzarella/Provolone", "price": "12.00"},
            {"name": "Pulled Pork", "description": "BBQ or Plain", "price": "11.00"},
            {"name": "Roast Beef", "description": "New Orleans Debris Style", "price": "14.50"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "tacos", "display_name": "Tacos",
        "subtitle": None, "columns": 2, "sort_order": 6,
        "items": [
            {"name": "Chicken Tacos", "description": "Blackened or Grilled, topped with Cheddar Cheese, Lettuce, Pico de Gallo & Sour Cream", "price": "12.00"},
            {"name": "Fish Tacos", "description": "Blackened, Fried or Grilled, topped with Cheddar Cheese, Lettuce, Pico de Gallo & Sour Cream", "price": "13.25"},
            {"name": "Pork Tacos", "description": "Topped with Cheddar Cheese, Lettuce, Pico de Gallo & Sour Cream", "price": "12.50"},
            {"name": "Shrimp Tacos", "description": "Blackened, Fried or Grilled, topped with Cheddar Cheese, Lettuce, Pico de Gallo & Sour Cream", "price": "13.25"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "fried-plates", "display_name": "Fried Plates",
        "subtitle": None, "columns": 2, "sort_order": 7,
        "items": [
            {"name": "Fried Fish Plate", "description": "Your Choice of 2 Sides", "price": "16.25"},
            {"name": "Chicken Tenders Plate", "description": "Your Choice of 2 Sides", "price": "13.25"},
            {"name": "Fried Oyster Plate", "description": "Your Choice of 2 Sides", "price": "23.00"},
            {"name": "Fried Shrimp Plate", "description": "Your Choice of 2 Sides", "price": "17.25"},
            {"name": "Seafood Platter", "description": "Fish, Oyster, Shrimp & Your Choice of 2 Sides", "price": "23.50"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "family-dinners", "display_name": "Family Dinners",
        "subtitle": "Served with Bed of Fries & Garlic Bread", "columns": 2, "sort_order": 8,
        "items": [
            {"name": "Catfish Pirogue", "description": "Served with French Fries & Garlic Bread", "price": "29.00"},
            {"name": "Oyster Pirogue", "description": "Served with French Fries & Garlic Bread", "price": "33.95"},
            {"name": "Shrimp Pirogue", "description": "Served with French Fries & Garlic Bread", "price": "31.00"},
            {"name": "Seafood Pirogue", "description": "Fish, Oyster & Shrimp with French Fries & Garlic Bread", "price": "33.50"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "sides", "display_name": "Sides",
        "subtitle": None, "columns": 3, "sort_order": 9,
        "items": [
            {"name": "Corn on the Cob (3)", "description": "", "price": "3.00"},
            {"name": "Green Beans", "description": "", "price": "3.00"},
            {"name": "Coleslaw", "description": "", "price": "2.50"},
            {"name": "French Fries", "description": "", "price": "4.50"},
            {"name": "Cajun Potatoes", "description": "", "price": "3.00"},
            {"name": "Side Salad", "description": "Garden or Caesar", "price": "4.75"},
        ]
    },
    {
        "id": str(uuid.uuid4()), "slug": "kids", "display_name": "Kids Menu",
        "subtitle": None, "columns": 4, "sort_order": 10,
        "items": [
            {"name": "Fish Plate", "description": "With French Fries", "price": "8.00"},
            {"name": "Chicken Tenders", "description": "With French Fries", "price": "8.00"},
            {"name": "Shrimp Plate", "description": "With French Fries", "price": "8.00"},
            {"name": "Sliders (2)", "description": "With French Fries", "price": "9.00"},
        ]
    },
]

DEFAULT_GIVEAWAY_SETTINGS = {
    "id": "main",
    "is_active": False,
    "title": "Summer Spin & Win!",
    "subtitle": "Spin the wheel for a chance to win free food, discounts, and more!",
    "start_date": "2026-06-01",
    "end_date": "2026-08-31",
    "prizes": [
        {"label": "Free Appetizer", "weight": 15, "color": "#366343"},
        {"label": "10% Off", "weight": 25, "color": "#a5935b"},
        {"label": "Free Side", "weight": 20, "color": "#1d2a3b"},
        {"label": "15% Off", "weight": 15, "color": "#366343"},
        {"label": "Free Drink", "weight": 15, "color": "#a5935b"},
        {"label": "Free Dessert", "weight": 5, "color": "#1d2a3b"},
        {"label": "Dinner for 4", "weight": 2, "color": "#8B0000"},
        {"label": "Try Again", "weight": 3, "color": "#555555"}
    ]
}


# Sprint 22C — Homepage Layout Editor.
# Single doc in `homepage_layout` controls the order, visibility, and
# optional title/body overrides of every public-site section. The Home
# component fetches this and renders sections in `sections[]` order,
# skipping any with `visible: false`. Empty `title`/`body` = use the
# component's hardcoded default copy.
DEFAULT_HOMEPAGE_LAYOUT_SECTIONS = [
    {"key": "hero",            "label": "Hero",                "visible": True, "title": "", "body": ""},
    {"key": "todays_featured", "label": "Today's Featured",    "visible": True, "title": "", "body": ""},
    {"key": "specials",        "label": "Specials & Promos",   "visible": True, "title": "", "body": ""},
    {"key": "about",           "label": "About",               "visible": True, "title": "", "body": ""},
    {"key": "menu",            "label": "Menu",                "visible": True, "title": "", "body": ""},
    {"key": "email_signup",    "label": "Email Signup",        "visible": True, "title": "", "body": ""},
    {"key": "loyalty",         "label": "Loyalty Card",        "visible": True, "title": "", "body": ""},
    {"key": "catering",        "label": "Catering Inquiry",    "visible": True, "title": "", "body": ""},
    {"key": "contact",         "label": "Contact / Map",       "visible": True, "title": "", "body": ""},
]

# Friendly editor metadata — describes which fields each section supports
# in the Layout Editor so the UI can hide irrelevant fields (e.g. body
# override on the auto-rendered Menu grid is pointless).
HOMEPAGE_SECTION_META = {
    "hero":            {"supports_title": True,  "supports_body": True,  "note": "Top banner. Full copy edited in Site Content."},
    "todays_featured": {"supports_title": True,  "supports_body": True,  "note": "Today's auto-picked dish."},
    "specials":        {"supports_title": True,  "supports_body": True,  "note": "Active specials from the dashboard."},
    "about":           {"supports_title": True,  "supports_body": True,  "note": "Restaurant story. Full copy in Site Content."},
    "menu":            {"supports_title": True,  "supports_body": True,  "note": "Full dish list."},
    "email_signup":    {"supports_title": True,  "supports_body": True,  "note": "Newsletter signup."},
    "loyalty":         {"supports_title": True,  "supports_body": True,  "note": "Loyalty punch card."},
    "catering":        {"supports_title": True,  "supports_body": True,  "note": "Catering inquiry form."},
    "contact":         {"supports_title": True,  "supports_body": True,  "note": "Hours, map, address. Full copy in Site Content."},
}


async def seed_defaults(db):
    """Seed default site content, menu categories, and giveaway settings if missing."""
    existing = await db.site_content.find_one({}, {"_id": 0})
    if not existing:
        await db.site_content.insert_one({**DEFAULT_SITE_CONTENT, "id": "main"})
        logger.info("Seeded default site content")

    existing_menu = await db.menu_categories.count_documents({})
    if existing_menu == 0:
        await db.menu_categories.insert_many(DEFAULT_MENU_CATEGORIES)
        logger.info("Seeded default menu categories")

    # Sprint 22C — Homepage Layout default. Idempotent: only seeds when
    # the collection is empty; never overwrites an admin's saved layout.
    existing_layout = await db.homepage_layout.find_one({"id": "main"}, {"_id": 0})
    if not existing_layout:
        await db.homepage_layout.insert_one({
            "id": "main",
            "sections": DEFAULT_HOMEPAGE_LAYOUT_SECTIONS,
        })
        logger.info("Seeded default homepage layout")

    # Sprint 12D: giveaway feature retired — seed removed
