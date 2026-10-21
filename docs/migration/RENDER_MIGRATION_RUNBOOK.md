# Lakeview independent deployment and rollback runbook

This runbook requires no login, API key, storage credential, or cooperation
from the former application provider. It uses the Git repository plus any
Lakeview-owned, provider-neutral database archive or object export already in
the owner's possession. It never scrapes the live site.

If no independent database or object backup exists, use the repository
reconstruction path below. That path produces a functional fresh deployment,
but cannot recover owner edits, customer records, analytics, or remote-only
media that are absent from Git.

Do not change production DNS or delete any old records during preparation or
staging.

## 1. Required target access and secrets

Provide these through provider secret managers or authenticated provider
sessions, never chat, Git, command-line arguments, screenshots, or reports:

- MongoDB Atlas target URI and database name;
- Cloudflare R2 endpoint, private bucket, access-key ID, and secret;
- Render workspace access connected to the GitHub repository;
- a new, randomly generated administrator password;
- DNS access only after production cutover is explicitly approved.

Use separate least-privilege migration and runtime credentials. The Render
database user needs application CRUD/index privileges for only the Lakeview
database. The R2 runtime token needs object read/write/list for only the
Lakeview bucket. Keep the bucket private because FastAPI serves media.

## 2. Choose the recovery path

### Path A: a Lakeview-owned neutral backup exists

Use this path only for a MongoDB archive/URI or filesystem object export that is
already controlled by Lakeview and does not require access to the former
provider.

1. Hash and preserve the original backup before using it.
2. For a live or restored source MongoDB, produce an inventory:

   ```bash
   export SOURCE_MONGO_URL='set-in-secret-shell'
   export SOURCE_DB_NAME='source-database-name'
   python backend/scripts/migrate_mongodb.py inventory \
     --output /secure/path/source-mongo-inventory.json
   ```

3. For an object export, preserve its original slash-containing keys beneath a
   single export directory and pass that directory as `--source-root`.
4. Never modify the only copy of a backup. Stop if its checksum or restore test
   fails.

### Path B: reconstruct solely from the repository

This is the default provider-independent path.

1. Record the deterministic local-media inventory:

   ```bash
   python backend/scripts/migrate_media.py local-inventory \
     --output /secure/path/repo-media-inventory.json
   ```

2. Start with an empty Atlas database. On first API startup,
   `backend/seed_data.py` idempotently creates the repository's default site
   content, menu categories, and homepage layout.
3. Have the restaurant owner review the seeded menu, prices, hours, contact
   information, and public images in staging. The repository snapshot—not the
   inaccessible prior database—is the source of truth for this path.
4. Treat the following historical state as unavailable unless a neutral backup
   is later supplied: prior admin edits, subscribers, loyalty members and
   stamps, catering inquiries, analytics, specials, sessions, media metadata,
   site-image assignments, and remote-only objects.

## 3. Provision targets

### MongoDB Atlas

1. Create a cluster near the Render region with backups enabled.
2. Create separate migration and runtime users.
3. Configure network access for the migration operator and Render egress.
4. Start with an empty target database and never use `mongorestore --drop`.

For repository-only reconstruction, deploy the API once and let the idempotent
startup seed initialize the empty database.

If a neutral archive exists, validate it before importing:

```bash
mongorestore --uri "$TARGET_MONGO_URL" --gzip \
  --archive="lakeview-source.archive.gz" --dryRun --verbose
```

Restore into the empty target without `--drop`, or use the non-destructive sync
tool and require the final comparison to show equal counts and checksums:

```bash
python backend/scripts/migrate_mongodb.py sync
python backend/scripts/migrate_mongodb.py sync --apply \
  --output /secure/path/initial-mongo-sync.json
python backend/scripts/migrate_mongodb.py compare \
  --output /secure/path/initial-mongo-compare.json
```

### Cloudflare R2

1. Create a private bucket and bucket-scoped migration token.
2. Export `S3_ENDPOINT_URL`, `S3_REGION=auto`, `S3_BUCKET`,
   `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, and
   `STORAGE_APP_NAME=lakeview` in a secret shell.
3. For repository-only reconstruction, migrate all top-level repository media
   without connecting to any source database:

   ```bash
   python backend/scripts/migrate_media.py local-sync --verify-existing \
     --output /secure/path/repo-media-dry-run.json
   python backend/scripts/migrate_media.py local-sync --apply --verify-existing \
     --output /secure/path/repo-media-apply.json
   python backend/scripts/migrate_media.py local-sync --verify-existing \
     --output /secure/path/repo-media-verify.json
   ```

4. If a neutral MongoDB and object export exist, use the fuller database-driven
   command instead:

   ```bash
   python backend/scripts/migrate_media.py sync \
     --source-root /secure/path/object-export --verify-existing
   python backend/scripts/migrate_media.py sync \
     --source-root /secure/path/object-export --apply --verify-existing
   python backend/scripts/migrate_media.py sync \
     --source-root /secure/path/object-export --verify-existing
   ```

The final report must set `verification_complete` to true and show zero
`missing_source`, zero conflicts, and zero unverified objects. Verification
downloads and hashes R2 bytes rather than trusting object metadata. Never use
`--overwrite-mismatch` until both byte sequences have been identified and the
overwrite has been approved.

## 4. Deploy staging on Render

1. Require the GitHub verification workflow to pass, including the Python
   dependency audit and production-container build. Review the documented
   Create React App build-chain advisories and record the release owner's risk
   decision.
2. Merge the reviewed deployment PR, connect the repository, and apply
   `render.yaml`.
3. Enter every `sync: false` value in the Render dashboard.
4. Set backend `CORS_ORIGINS` to the exact staging frontend origin; never use
   `*`. Set frontend `REACT_APP_BACKEND_URL` to the staging API origin.
5. Deploy `lakeview-api`, then `lakeview-web`.
6. Confirm `/api/health/live` returns 200 and `/api/health/ready` reports both
   MongoDB and storage reachable.
7. Restart the API before acceptance testing. Media must remain available;
   acceptance cannot depend on ephemeral disk.

## 5. Mandatory staging acceptance checklist

Record timestamp, tester, URL, expected result, actual result, and evidence for
each item:

- homepage renders the repository content and images;
- `/menu` renders every seeded category/item and the owner confirms prices;
- hours, address, phone, email, and restaurant description are owner-approved;
- mobile header/drawer navigation opens, closes, and reaches every section;
- every Square pickup/order link opens the intended Square destination;
- admin login rejects a bad password, accepts the new password, persists the
  session, logs out, and rejects the old token afterward;
- edit and restore one low-risk content field and one menu field;
- create and deactivate a test special;
- catering inquiry submission appears in admin and status can be changed;
- newsletter signup appears in admin and duplicate handling is correct;
- loyalty join/lookup/stamp/claim works with a designated test record;
- repository-local media render, and each migrated R2 checksum report passes;
- a new image upload appears in Library, survives API restart, and serves with
  the correct MIME type;
- thumbnail generation and a small video upload/thumbnail are tested;
- site-image assignment updates the public slot and reset restores its default;
- HTML featured image/template read path works;
- page views and button clicks appear in admin analytics;
- browser CORS succeeds from staging and fails from an unlisted origin;
- API restart and static-site redeploy do not lose database or media state;
- no active public/admin network request targets a former-provider domain;
- desktop and representative small mobile viewports have no blocking visual or
  navigation regression.

Any failure blocks production cutover.

## 6. Production cutover

1. Obtain explicit production-cutover and DNS approval.
2. For repository reconstruction, obtain written owner acceptance that
   historical state absent from Git will not appear in the new deployment.
3. Lower DNS TTL only after approval and before the maintenance window.
4. Export fresh Atlas and R2 inventories and retain their checksums.
5. Configure exact production frontend/backend origins and redeploy the exact
   staging-tested commit.
6. Change only the approved web/API DNS records and preserve the old values in
   the evidence log.
7. Repeat the staging checklist against the production domain.
8. Keep Atlas backups, R2 objects, and all neutral source archives intact
   throughout the rollback window.

If a neutral source database was used and remained writable, pause edits and
perform one final non-destructive delta and comparison immediately before DNS
cutover. This step does not apply to repository-only reconstruction.

## 7. Rollback

Rollback triggers include incorrect menu/content, missing media, failed writes,
authentication failure, repeated 5xx responses, broken CORS, or a checksum
mismatch.

1. Stop owner edits/uploads and record the incident time.
2. Restore the previous DNS records while leaving Atlas and R2 untouched.
3. Verify the previous public site is serving before declaring rollback
   complete.
4. Inventory Atlas and R2; never delete post-cutover data.
5. Preserve post-cutover records and uploads for reconciliation. The migration
   tools intentionally have no delete or legacy-provider write-back path.
6. Fix and redeploy staging, repeat the full checklist, and request new cutover
   approval.

## 8. Secret rotation and retention

After a user-approved rollback window:

1. Take final Atlas and R2 inventories and retain their checksums.
2. Rotate Atlas runtime, R2 runtime, Render administrator, and migration
   credentials. Remove migration-only credentials from shells and Render.
3. Confirm GitHub remains the deployment source of truth and branch protection
   requires the verification workflow.
4. Retain neutral archives according to the owner's retention policy.
5. Deleting historical data or provider accounts is a separate, explicitly
   approved action and is never part of this migration procedure.
