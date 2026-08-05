# Lakeview Burgers & Seafood

Production website and owner marketing studio for Lakeview Burgers & Seafood.

## Product surfaces

- **Public website** — menu, featured items, specials, catering inquiries, loyalty signup, hours, location, and ordering links.
- **Lakeview Studio** — authenticated owner dashboard for menu/content management, promotion creation, media library, customer inquiries, and homepage layout controls.
- **Creative engine** — photo-to-flyer, template, HTML, and image-rendering workflows used to create restaurant marketing assets.

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
pip install -r requirements.txt
uvicorn server:app --reload
```

Configure the required backend environment variables before startup. Never commit secrets or production credentials.

### Frontend

```bash
cd frontend
yarn install
yarn start
```

The frontend expects `REACT_APP_BACKEND_URL` to point to the backend origin.

## Verification

### Backend

```bash
cd backend
pytest tests/
```

### Frontend

```bash
cd frontend
yarn build
```

Run focused regression tests for any workflow being changed, especially authentication, media storage, homepage layout, platform sizing, hidden-theme compatibility, and Photo-to-Flyer generation.

## Production-critical workflows

1. Public site loads content, menu data, and homepage layout.
2. Admin login verifies the stored token before loading Lakeview Studio.
3. Menu items can be edited and passed into the promotion workflow.
4. Photo-to-Flyer accepts a library image or fresh upload, analyzes it, generates variants, and stores retrievable outputs.
5. Catering inquiries are accepted publicly and reviewed through the owner workflow.
6. Homepage layout falls back safely when layout configuration is unavailable.

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
