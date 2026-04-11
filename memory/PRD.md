# Lakeview Burgers & Seafood - Website PRD

## Original Problem Statement
Build a website for restaurant "Lakeview Burgers & Seafood" featuring a menu, locations, hours, and online ordering integrations (Uber Eats, Square). Additional requirements include an admin dashboard protected by login to track website analytics and manage restaurant specials, SEO optimization, and a full CMS to edit all website content from the backend.

## Business Info
- **Address**: 872 Harrison Ave, New Orleans, LA 70124
- **Phone**: (504) 289-1032
- **Hours**: Monday-Saturday 11:30am-11pm, Sunday Closed
- **Established**: 2015 by Chef Joseph Faroldi

## Architecture
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB (collections: page_views, button_clicks, specials, status_checks, newsletter_subscribers, catering_inquiries, site_content, menu_categories)
- **Auth**: JWT Bearer token (header-based), password in backend .env

## Implemented Features

### CMS (Content Management System)
All website text is editable from the admin dashboard:
- **Hero Section**: Tagline, subtitle
- **About / Our Story**: Accent text, heading, 3 paragraphs, established text
- **Contact Info**: Address lines, hours (weekday/weekend), phone, email, catering text
- **Full Menu Editor**: 10 categories with items (name, description, price). Add/remove items, edit category names, subtitles, column layout

### Public Landing Page
- Hero with dynamic tagline/subtitle from CMS
- Today's Specials (auto-displayed from dashboard)
- Our Story section (dynamic from CMS)
- Full Menu (10 categories, 60+ items - dynamic from CMS)
- Email Signup ("Join the Lakeview Family")
- Catering Inquiry Form
- Contact section (dynamic from CMS) with Google Maps embed
- Sticky Order Bar (floating Uber Eats + Square)
- New Orleans theme, mobile responsive

### Admin Dashboard (6 tabs)
1. **Analytics**: Real-time pageviews, devices, browsers, hourly/daily charts, referrers, button clicks
2. **Specials**: CRUD with image upload, active/inactive toggle
3. **Site Content**: Edit hero, about, contact text with per-section Save
4. **Menu Editor**: Collapsible categories with inline item editing
5. **Inquiries**: Catering inquiry management with status tracking
6. **Subscribers**: Newsletter subscriber list

### SEO Optimization
- 4 JSON-LD schemas (Restaurant, WebSite, BreadcrumbList, FAQPage)
- robots.txt, sitemap.xml, geo tags, 25+ keywords, Open Graph, Twitter Cards

### Backend API Endpoints
- Auth: POST /api/auth/login, GET /api/auth/verify, POST /api/auth/logout
- CMS: GET /api/content, PUT /api/content/{section}
- Menu: GET /api/menu, PUT /api/menu/{id}, POST /api/menu, DELETE /api/menu/{id}
- Analytics: GET /api/analytics, POST /api/analytics/track, POST /api/analytics/button-click
- Specials: GET/POST /api/specials, GET/PUT/DELETE /api/specials/{id}
- Newsletter: POST /api/newsletter/subscribe, GET /api/newsletter/subscribers
- Catering: POST /api/catering/inquiry, GET /api/catering/inquiries, PUT /api/catering/inquiries/{id}/status
- Upload: POST /api/upload-image

## Testing Status (Feb 2026)
- Backend: 43/43 tests passed (100%)
- Frontend: Full coverage including E2E content persistence

## Future Enhancements (Backlog)
- P1: Upload pictures of Chef Joseph and son Josef for "Our Story" section
- P2: Social media links
- P2: Photo gallery of dishes
- P2: Customer reviews/testimonials section
