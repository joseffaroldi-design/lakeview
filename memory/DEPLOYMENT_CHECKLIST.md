# Lakeview Burgers & Seafood — Deployment & Safety Checklist

## Environment variables

### Backend (`/app/backend/.env` — never commit live values)
| Key | Purpose | Notes |
|---|---|---|
| `MONGO_URL` | MongoDB connection string | Pre-configured for the pod. Do not change. |
| `DB_NAME` | Mongo database name | Pre-configured. Do not change. |
| `EMERGENT_LLM_KEY` | Universal LLM key (OpenAI / Claude / Gemini) | Required for any AI generation. Top-up at Profile → Universal Key → Add Balance. |
| `CORS_ORIGINS` | Comma-separated origins | Defaults are safe; restrict to your domain in prod. |
| `ADMIN_PASSWORD` | First-time admin password (seed only) | Replaced by bcrypt hash on first login. |

### Frontend (`/app/frontend/.env`)
| Key | Purpose |
|---|---|
| `REACT_APP_BACKEND_URL` | Public URL the browser uses for `/api/*` calls. **Must NOT include `/api`** suffix — the router adds it. |

### Provider credentials (entered IN-APP only — never in .env)
Provider credentials are stored in MongoDB `provider_connections` and are never returned to the frontend in plain text. Saved via:
- Dashboard → AI Ads → Providers → Connect (per provider)

Never paste tokens into chat, version control, screenshots, or environment variables.

---

## API key safety

- The backend NEVER returns provider credentials to the frontend. The `GET /api/ai-ads/provider-connections` endpoint omits the `credentials` sub-document.
- The `Test Connection` button uses the stored credentials server-side and returns only `{ok, message, latency_ms}`.
- The bcrypt admin password is hashed on the server. Plain password is never logged.

---

## Pre-launch checklist

- [ ] **Default admin password rotated** — login once, change in Profile (or update `ADMIN_PASSWORD` and re-seed).
- [ ] **HTTPS** — preview & production both terminate TLS at the ingress. No mixed-content warnings.
- [ ] **CORS** — set `CORS_ORIGINS` to your final domain(s).
- [ ] **GET /api/ai-ads/health** returns `{ok: true}` for: database, llm_key, scheduler, providers.
- [ ] **Logo (101 KB WebP)** loads in < 200 ms.
- [ ] **Sitemap.xml** & **robots.txt** present in `/app/frontend/public/`.
- [ ] **Service Worker** (`sw.js`) registered (PWA install prompt works).
- [ ] **Manifest.json** has correct app name + icons.

---

## Safety features in place

| Risk | Mitigation |
|---|---|
| Accidental delete | `window.confirm()` on every destructive frontend action (assets, menu, automation rules, etc.). |
| Bulk delete | Confirms with count: "Delete 12 selected assets?". |
| Lost work | Library assets are soft-deletable via Archive (status=`archived`). Hard delete only via explicit Delete button. |
| Failed publish | Recorded in `publish_jobs` + `publish_logs`. Retry available from Queue. |
| Auth brute force | 5 attempts → 15 min lockout via `slowapi`. |
| LLM cost runaway | `gpt-5-mini` used for multi-channel Promote runs by default. Settings tab lets owner switch global model. |
| Credentials leak | `credentials` field never serialized to the frontend. Test Connection result only carries `{ok, message}`. |
| Page crashes | React `ErrorBoundary` at the app root catches uncaught errors and shows Refresh button. |

---

## Database backup

This deployment uses managed MongoDB. To take a manual snapshot:

```bash
# Run from inside the pod
mongodump --uri="$MONGO_URL" --db="$DB_NAME" --out=/tmp/backup-$(date +%F)
tar -czf /tmp/lakeview-$(date +%F).tgz /tmp/backup-*
```

Restore:
```bash
mongorestore --uri="$MONGO_URL" --db="$DB_NAME" /tmp/backup-YYYY-MM-DD/$DB_NAME
```

The most critical collections to back up:
- `cms_site` (homepage content)
- `menu_items` + `menu_categories`
- `ai_assets`, `ai_campaigns`, `ai_generations`
- `scheduled_posts`, `publish_logs`, `automation_rules`
- `provider_connections` (encrypted credentials — handle with care)
- `subscribers`, `loyalty_signups`, `messages`, `catering_inquiries`

---

## What to do if a service stops responding

1. Check the deployed app first (`https://lakeview-grill.emergent.host/`). If preview is up but production isn't, redeploy via the Emergent dashboard.
2. Check `GET /api/ai-ads/health` — pinpoints which subsystem is down.
3. If `database.ok=false` → check the MongoDB pod logs.
4. If `scheduler.ok=false` for >5 min → restart backend (`sudo supervisorctl restart backend` in the pod).
5. Frontend won't load → hard refresh (Cmd+Shift+R / Ctrl+F5).

---

## Owner support channels

- Daily questions → see `OPERATOR_GUIDE.md`.
- Bug reports → email the developer who deployed the system.
- LLM key budget → Profile → Universal Key → Add Balance / Auto Top-Up.
