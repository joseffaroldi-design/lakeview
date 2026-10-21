# Lakeview Burgers & Seafood

Production website and core owner/admin tools for Lakeview Burgers & Seafood.

## Product surfaces

- **Public website** — menu, featured items, specials, catering inquiries, loyalty signup, hours, location, and ordering links.
- **Lakeview Admin** — authenticated owner dashboard for menu/content management,
  media library, website images, customers, catering, and analytics.
- **Historical creative source** — archived AI/design/rendering modules remain in
  the repository but are not mounted by the production server.

## Repository structure

```text
backend/                 FastAPI application, routers, services, renderers, storage, and tests
frontend/                React/CRACO application and frontend tests
docs/                    Product, architecture, audit, and historical project documentation
FROZEN_FEATURES.md       Current protected product scope
```

## Local development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-test.txt
uvicorn server:app --reload
```

Configure the required backend environment variables before startup. Never commit secrets or production credentials.

### Frontend

```bash
cd frontend
yarn install --frozen-lockfile
yarn start
```

Copy values from `backend/env.example` and `frontend/env.example` into local
untracked `.env` files. The frontend expects `REACT_APP_BACKEND_URL` to point
to the backend origin.

## Verification

### Backend

```bash
cd backend
pytest -q \
  tests/test_storage_s3.py \
  tests/test_migration_tools.py \
  tests/test_independent_deployment.py \
  tests/test_v1_security_config.py \
  tests/test_analytics_beacon.py
pip-audit -r requirements-prod.txt
```

### Frontend

```bash
cd frontend
yarn build
yarn test --watchAll=false --runInBand src/lib/publicNavigation.test.js
```

## Production deployment

The supported production architecture is a Render Static Site (`frontend`), a
Render Docker Web Service (`backend`), MongoDB Atlas, and private Cloudflare R2
object storage. `render.yaml` defines the two Render services without embedding
secrets. The backend proxies media reads, so the R2 bucket does not need public
object access.

Use `backend/requirements-prod.txt` for the mounted server routes. The larger
historical `backend/requirements.txt` remains for archived AI/design code and is
not installed in the production image.

See `docs/migration/EMERGENT_EXIT_AUDIT.md` for the recoverability boundary and
`docs/migration/RENDER_MIGRATION_RUNBOOK.md` for staging, cutover, and rollback.

Run focused regression tests for any workflow being changed, especially
authentication, media storage, homepage layout, menu/content editing, customer
records, analytics, and responsive public navigation.

## Production-critical workflows

1. Public site loads content, menu data, and homepage layout.
2. Admin login verifies the stored token before loading Lakeview Studio.
3. Menu items and public-site content can be edited and restored safely.
4. Media uploads are written to durable object storage and remain retrievable
   after backend restart.
5. Catering inquiries are accepted publicly and reviewed through the owner workflow.
6. Newsletter, loyalty, site-image assignments, and analytics retain their
   current public/admin behavior.
7. Homepage layout falls back safely when layout configuration is unavailable.

## Change discipline

- Treat `FROZEN_FEATURES.md` as the scope contract.
- Prefer simplification and regression-safe extraction over feature expansion.
- Do not delete renderer, storage, theme, or API fallback paths until production usage and test dependencies are mapped.
- Keep public website changes, dashboard workflow changes, and renderer refactors in separate commits.
- Validate production URLs and remove preview-environment references before deployment.

## Current architectural priorities

1. Keep the public website focused on ordering, menu discovery, trust, and catering conversion.
2. Simplify Lakeview Studio around Create, Library, Menu, and low-frequency management tasks.
3. Extract the oversized public-site implementation from `frontend/src/App.js` without changing behavior.
4. Document and map all active creative-generation paths before consolidating backend renderers.
5. Move historical sprint reports out of the repository root into organized documentation folders.
