# Lakeview Burgers & Seafood - Website PRD

## Original Problem Statement
Build a website for restaurant "Lakeview Burgers & Seafood" featuring menu, ordering, admin dashboard, SEO, CMS, summer giveaway, loyalty program, and messaging system.

## Architecture
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Auth**: JWT Bearer token
- **Integrations**: SendGrid (email), Twilio (SMS) — keys pending

## Implemented Features

### Public Site
- Hero, About, Menu, Contact (all CMS-editable)
- Specials (auto-displayed from dashboard)
- Email newsletter signup
- Loyalty Punch Card (join + lookup visits)
- Catering inquiry form
- Google Maps embed
- Sticky order bar (Uber Eats + Square)
- Spin & Win giveaway (admin-activated)

### Admin Dashboard (9 tabs)
1. Analytics, 2. Specials, 3. Site Content, 4. Menu Editor, 5. Giveaway, 6. Loyalty, 7. Messages, 8. Inquiries, 9. Subscribers

### Key Systems
- **CMS**: Edit all site text + full menu from dashboard
- **Giveaway**: Spin wheel with 8 prizes, admin activate/deactivate
- **Loyalty**: 10 visits = free meal, stamp from dashboard
- **Messaging**: Blast emails/SMS to subscribers, giveaway entries, loyalty members
- **SEO**: 4 JSON-LD schemas, robots.txt, sitemap.xml, geo tags

## Testing: 79/79 backend (100%), full frontend coverage

## Pending
- SendGrid API key (for email blasts)
- Twilio API key (for SMS blasts)
- Chef Joseph & Josef photos

## Future
- Social media links, photo gallery, customer reviews
