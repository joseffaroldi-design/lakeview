# Lakeview Burgers & Seafood — Operator Guide

A non-technical guide for the restaurant owner / manager.

---

## Login

1. Open `https://lakeview-grill.emergent.host/login`
2. Password: see your sealed envelope (or `/app/memory/test_credentials.md` for staging).
3. Lockout after 5 wrong tries for 15 minutes — protects the dashboard from random tries.

---

## Where things live in the dashboard

| Tab | What it's for |
|---|---|
| **Analytics** | Website visitors + Owner Quick Start (6 shortcut tiles) |
| **Specials** | Manual specials (daily / weekly) — separate from AI campaigns |
| **Site Content** | Hero text, story, hours, contact info on the public website |
| **Menu Editor** | Add / edit / delete menu items. **Promote** button on each item runs AI |
| **Giveaway** | Spin-to-win + signups |
| **Loyalty** | Customer cards & manual messaging |
| **Messages** | Inbox of customer messages |
| **Inquiries** | Catering inquiries from the public form |
| **Subscribers** | Email/SMS marketing list |
| **AI Ads** | The full Marketing Studio (see below) |

---

## AI Ads — the Marketing Studio

Default sub-tab is **Automation Center** with 4 production wizards:

1. **Daily Specials** — pick a menu item, choose channels, generate Facebook / Instagram / SMS / etc. in one click.
2. **Google Review Requests** — SMS, Email, or Follow-up templates that ask happy guests for a Google review.
3. **Loyalty Campaigns** — First Visit / Repeat / Birthday / Win-Back / VIP templates.
4. **Catering Marketing** — Office Lunch / Corporate / School / Holiday Party / Family Gathering templates.

After generating, click **Schedule This Bundle** → pick a start time and stagger between posts → posts go into the **Calendar** + **Queue**.

Other tabs:
- **Campaign Builder** — manual brief for one-off campaigns.
- **Social / Email / SMS / Image / Video** — single-channel generators.
- **Library** — every asset you've saved. Bulk archive / delete / export TXT / CSV / JSON / clipboard.
- **Calendar** — month / week / day view, drag-drop to reschedule, click to cancel.
- **Queue** — kanban of queued / publishing / published / failed.
- **Rules** — recurring auto-generation (e.g. "Every Friday at 9am — Seafood Special").
- **Providers** — connect Facebook / Instagram / Google Business / Mailchimp / SendGrid / Twilio. **Test Connection** verifies credentials without sending anything.
- **Analytics** — Restaurant KPIs band + 6 stat cards + 3 charts.
- **Settings** — pick the AI model (default GPT-5, also GPT-5-mini, Claude, Gemini).

---

## Daily Checklist (≈10 min)

- [ ] Check **Queue** — any failed publishes? If yes, hit Retry or Cancel.
- [ ] Glance at **Analytics** — yesterday's visitors + the 6 KPI cards.
- [ ] Open **Inquiries** + **Messages** — reply to any new requests.
- [ ] If you have a daily special, open **Menu Editor** → click the gold **Promote** sparkle next to the item → pick channels → schedule for 11am or 5pm.

## Weekly Marketing Checklist (≈30 min)

- [ ] Run **Automation Center → Google Review Requests** → SMS template → schedule to a small group of recent diners.
- [ ] Run **Automation Center → Loyalty → Repeat Customer** for last week's repeat list.
- [ ] Run **Automation Center → Catering** if there's an upcoming holiday — schedule the bundle.
- [ ] Open **Calendar** and confirm next week is filled (gold = scheduled, green = published).
- [ ] Run **Providers → Test Connection** on each connected provider to confirm credentials still work.

## Monthly Checklist

- [ ] **Settings** → confirm the AI model. If usage is high, switch to GPT-5-mini to cut cost.
- [ ] **Analytics → Restaurant KPIs** — note Best Platform + Best Campaign Type, lean into the winners.
- [ ] Review **Rules** — turn off any automation that's no longer relevant.
- [ ] Export **Library → CSV** to a Google Sheet for offline records.

---

## When something looks wrong

- **AI generation returned an error** → check **Settings** → "Test Generation". Likely the Universal LLM key needs a top-up.
- **Publish failed** → click the failed item in the Queue. The error message will say what's wrong (most often: provider needs reconnecting). Open **Providers** → click **Test Connection** for that platform.
- **The public website looks weird** → hit the Refresh button on your browser. If that doesn't fix it, the **Error Boundary** screen will appear with a Refresh button — click it.
- **Forgot password** → contact the developer who set up the system. Password reset is locked down.

---

## Don't do this

- Don't share the dashboard password with anyone outside the management team.
- Don't enter live SendGrid / Twilio credentials on a shared computer.
- Don't send the same SMS campaign more than once per week to the same list — Twilio flags it as spam.
- Don't use real customer data in test runs. The default SMS recipients in Providers should be your own phone, not the customer list, until you're ready for production.
