# Emergent exit: recoverability and portability audit

Audit date: 2026-10-20. This is a repository-only audit. No production
credentials, legacy-provider account, MongoDB source, R2 account, Render
account, or DNS provider was accessed. The selected migration path requires no
legacy-provider login, API key, or storage API.

## Verified from the repository

- Git status was clean on `main` at audit start (`00832a1`).
- `backend/server.py` mounts the public site and core admin routes only:
  authentication, content/menu/homepage layout, specials, analytics, loyalty,
  catering, newsletter, media, site-image assignments, owner-home aggregates,
  and the HTML featured/template endpoints.
- Historical AI/design/provider source remains present but is not mounted.
- Public Square ordering links are ordinary outbound links and require no
  server-side Square credential migration.
- The repository contains **683 tracked files under `backend/media_storage`**,
  totaling **56,253,401 bytes**: 328 top-level legacy-media candidates, 275
  cached thumbnails, and 80 render scratch artifacts. A deterministic inventory
  produced aggregate manifest SHA-256
  `7adadec4c96dad53a63681c71678bb9644ad5bb1d5810954d6ceb0b2ea6e1c06`.
- The repository contains public fallback images, logos, seed content, source,
  and tests. Active public HTML no longer loads Emergent scripts or
  Emergent-hosted fallback/SEO images.
- No MongoDB BSON dump/archive was found in the repository.
- No repository evidence proves the previous note of 279 remote objects. That
  count remains unverified and cannot be recovered without a Lakeview-owned,
  provider-neutral database/object backup.

The old February count of 346 local assets is stale, but 683 is not a direct
replacement asset count because it includes derivative caches. In the
repository-only reconstruction path, the 328 top-level files are the migration
set; the authoritative historical referenced-media count remains unknown.

## Recoverable without external access

1. Application source and Git history.
2. React static assets and local fallback photography.
3. All repository-local media bytes, including 328 top-level candidate source
   files plus derivative caches retained in Git history.
4. Default content/menu/layout values in `backend/seed_data.py`.
5. Static Square, Uber Eats, phone, location, and social links in the frontend.
6. The active route contract and automated tests.

## Not recoverable from the repository

1. The authoritative MongoDB database: owner edits, menu/content state,
   sessions, subscribers, loyalty members, catering inquiries, analytics,
   specials/marketing-pack records, media metadata, and site-image mappings.
2. Every object whose `media_assets.storage_path` contains `/` unless an object
   export already exists elsewhere.
3. Confirmation of how many bare-filename database records correspond to the
   683 repository files, and which local files are orphaned or unreferenced.
4. Current production environment values and current DNS ownership.

These items are treated as unavailable unless Lakeview already owns a neutral
MongoDB archive/URI or filesystem object export. They are not prerequisites for
starting a fresh Atlas database from the repository's idempotent seed data.

## Portability changes

- `backend/storage.py` now uses the S3 API through `boto3`; Cloudflare R2 is
  configured with its account endpoint and region `auto`.
- Existing slash-containing object keys are preserved.
- Bare legacy filenames use a safe dual read: packaged local file first, then
  `lakeview/legacy/<filename>` in R2. Database rows do not need a bulk path
  rewrite during cutover.
- New writes are object-storage-only. Local storage is explicitly rejected in
  production.
- Storage health is a read-only bucket probe; it no longer creates probe files.
- Production startup fails closed if CORS, R2, or a sufficiently long admin
  password is missing.
- The production dependency file excludes dormant Emergent/LLM/rembg/scientific
  packages while retaining dependencies required by mounted media and HTML
  rendering routes.

## Dependency and build-chain audit

- The active backend requirements were upgraded together and pinned. On the
  audit date, `pip-audit -r backend/requirements-prod.txt` reported **no known
  vulnerabilities**, `pip check` reported no broken requirements, and the
  focused backend verification suite passed on Python 3.11. CI repeats the
  vulnerability audit and builds the production container.
- The React application still uses Create React App / `react-scripts` 5.0.1.
  `yarn audit --groups dependencies` reports 20 high, 24 moderate, and 3 low
  advisories in its build/development dependency tree, including transitive
  webpack, PostCSS, SVGO, and development-server packages. Render publishes the
  generated static files rather than running a Node server, which limits the
  production runtime exposure, but the build supply-chain debt remains. A
  future migration from Create React App should be tracked separately; release
  owners must explicitly accept this known build-time risk for the migration.

## Safe tooling

### MongoDB

`backend/scripts/migrate_mongodb.py` reads URIs from environment variables,
produces counts and collection SHA-256 values, and can upsert an initial or
delta copy by `_id`. It never drops collections or deletes target documents.
`sync` is dry-run unless `--apply` is supplied.

### Media

`backend/scripts/migrate_media.py` inventories local/database media and copies
content to R2 with SHA-256 metadata and downloaded-byte verification. It
preserves remote keys, maps bare names to the legacy prefix, refuses to
overwrite a conflicting target by default, never mutates MongoDB, and has no
delete path. `local-sync` migrates all top-level repository media without any
source database or former-provider connection. The optional database-driven
path accepts only a neutral filesystem object export through `--source-root`.

## Readiness conclusion

Code/configuration readiness: **locally verified**.

Repository reconstruction readiness: **locally verified**. An empty Atlas
database will be initialized from `backend/seed_data.py`, and the 328 top-level
repository media files can be migrated directly to R2.

Historical-data readiness: **unavailable unless a Lakeview-owned neutral backup
is supplied**. This does not block staging, but it means prior edits, customer
records, analytics, media metadata, and remote-only objects will not be present.

Deployment readiness: **ready for staging configuration, not production
cutover**. Production DNS must remain unchanged until the staging checklist and
data/media checksum gates in the runbook pass. The documented Create React App
build-chain risk must also be accepted or remediated before the release decision.
