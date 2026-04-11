# Lakeview Burgers & Seafood - Website PRD

## Original Problem Statement
Build a website for restaurant "Lakeview Burgers & Seafood" featuring a menu, locations, hours, online ordering integrations, admin dashboard with analytics and specials management, SEO optimization, full CMS, and a summer giveaway system.

## Business Info
- **Address**: 872 Harrison Ave, New Orleans, LA 70124
- **Phone**: (504) 289-1032
- **Hours**: Monday-Saturday 11:30am-11pm, Sunday Closed
- **Established**: 2015 by Chef Joseph Faroldi

## Architecture
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Auth**: JWT Bearer token (header-based)

## Implemented Features

### Public Landing Page
- Hero with dynamic tagline/subtitle (CMS-editable)
- Today's Specials (auto-displayed from dashboard)
- Our Story section (CMS-editable)
- Full Menu (10 categories, 60+ items, CMS-editable)
- Email Signup newsletter capture
- Catering Inquiry Form
- Contact section (CMS-editable) with Google Maps embed
- Sticky Order Bar (floating Uber Eats + Square)
- **Spin & Win Giveaway** (activatable from dashboard)

### Summer Spin & Win Giveaway
- Canvas-drawn spinning wheel with 8 prize segments
- Prizes: Free Appetizer, 10% Off, Free Side, 15% Off, Free Drink, Free Dessert, Dinner for 4, Try Again
- One spin per email (duplicate detection)
- Admin-controlled: activate/deactivate from dashboard
- Customizable title, subtitle, dates, prizes, and weights
- Entry tracking with "Mark Claimed" feature
- Prize distribution stats
- **Currently INACTIVE** — admin activates when ready

### Admin Dashboard (7 tabs)
1. **Analytics**: Pageviews, devices, browsers, hourly/daily charts, referrers, button clicks
2. **Specials**: CRUD with image upload, active/inactive toggle
3. **Site Content**: Edit hero, about, contact text
4. **Menu Editor**: Edit all categories with inline item editing
5. **Giveaway**: Activate/deactivate, configure prizes, view entries, mark claimed
6. **Inquiries**: Catering inquiry management with status tracking
7. **Subscribers**: Newsletter subscriber list

### CMS
- Hero: tagline, subtitle
- About: accent text, heading, 3 paragraphs, established text
- Contact: address, hours, phone, email, catering text
- Menu: 10 categories with items (name, description, price)

### SEO
- 4 JSON-LD schemas, robots.txt, sitemap.xml, geo tags, 25+ keywords, Open Graph, Twitter Cards

## Testing Status
- Backend: 58/58 tests passed (100%)
- Frontend: Full coverage including E2E

## Future Enhancements
- P1: Upload pictures of Chef Joseph and son Josef
- P2: Social media links, photo gallery, customer reviews
