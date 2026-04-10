# Lakeview Burgers & Seafood - Website PRD

## Original Problem Statement
Build a website for restaurant "Lakeview Burgers & Seafood" featuring a menu, locations, hours, and online ordering integrations (Uber Eats, Square). Additional requirements include an admin dashboard protected by login to track website analytics (page views, unique visitors, button clicks) and manage restaurant specials, as well as SEO optimization to rank highly on Google.

## Business Info
- **Address**: 872 Harrison Ave, New Orleans, LA 70124
- **Phone**: (504) 289-1032
- **Hours**: Monday-Saturday 11:30am-11pm, Sunday Closed
- **Established**: 2015 by Chef Joseph Faroldi

## Architecture
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB (collections: page_views, button_clicks, specials, status_checks, newsletter_subscribers)
- **Auth**: JWT Bearer token (header-based), password stored in backend .env

## What's Been Implemented

### Public Landing Page
- Hero section with logo, tagline, View Our Menu + ordering buttons
- Our Story section (Chef Joseph Faroldi and son Josef, Est. 2015)
- Today's Specials section (auto-displays active specials from dashboard)
- Full Menu (10 categories, 60+ items from official PDF)
- Email Signup section ("Join the Lakeview Family" newsletter capture)
- Contact section (address, hours, phone, reservation button, Google Maps embed)
- Sticky Order Bar (floating Uber Eats + Square buttons on scroll)
- New Orleans-themed design (Navy, Forest Green, Cream, Gold, Playfair Display font)
- Mobile responsive

### External Ordering Integration
- Uber Eats: https://www.ubereats.com/store-browse-uuid/de2b0e6b-0fdf-44bc-92e9-2c223008bd36
- Square: https://lakeview-burgers-seafood.square.site

### Admin Dashboard (/login -> /dashboard)
- Password-protected login (JWT Bearer token auth)
- Real-time analytics: total views, today/week/month views, unique visitors, avg pages/visit
- Device & browser breakdown, page breakdown, hourly/daily charts
- Top referrers, button click tracking (all time + today)
- Specials CRUD: create, edit, delete, toggle active/inactive, image upload

### SEO Optimization
- Meta tags, Open Graph tags, JSON-LD schema in index.html

### Backend API Endpoints
- `POST /api/auth/login` - Admin login
- `GET /api/auth/verify` - Verify session
- `POST /api/auth/logout` - Logout
- `GET /api/analytics` - Dashboard analytics (protected)
- `POST /api/analytics/track` - Track pageview
- `POST /api/analytics/button-click` - Track button click
- `GET/POST /api/specials` - List/create specials
- `GET/PUT/DELETE /api/specials/{id}` - CRUD individual special
- `POST /api/newsletter/subscribe` - Subscribe to newsletter
- `GET /api/newsletter/subscribers` - List subscribers (protected)
- `POST /api/upload-image` - Upload image (protected)

## Revenue Features (Added Feb 2026)
1. **Sticky Order Bar** - Floating Uber Eats + Square buttons visible while browsing menu
2. **Email Newsletter Signup** - Captures customer emails for direct marketing
3. **Google Maps Embed** - Helps local SEO and customer directions
4. **Specials on Landing Page** - Showcases daily specials from dashboard to drive upsells

## Future Enhancements (Backlog)
- P1: Upload pictures of Chef Joseph and son Josef for "Our Story" section (waiting on user images)
- P2: Social media links
- P2: Photo gallery of dishes
- P2: Customer reviews/testimonials section
- P3: Catering inquiry form with email notifications
