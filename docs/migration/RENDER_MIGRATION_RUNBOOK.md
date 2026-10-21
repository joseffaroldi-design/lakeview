# Lakeview independent deployment and rollback runbook

This runbook deliberately separates preparation, staging, cutover, and source
retirement. Do not cancel Emergent, delete source data, expose credentials, or
change production DNS during preparation or staging.

## 1. Required access and named secrets

Obtain the following through provider secret managers, never chat, Git, shell
arguments, screenshots, or report files:

- source MongoDB URI and database name;
- MongoDB Atlas target URI and database name;
- Emergent source object key, or a complete filesystem export retaining object
  keys (the key is needed only if slash-path objects have no export);
- Cloudflare R2 account endpoint, bucket, access-key ID, and secret;
- Render workspace access connected to the GitHub repository;
- DNS provider access only when production cutover is approved.

Use separate least-privilege credentials for migration and runtime. The Render
runtime database user needs application CRUD/index privileges for only the
Lakeview database. The R2 runtime token needs object read/write/list for only
the Lakeview bucket. Keep the bucket private because FastAPI serves media.

## 2. Preserve the source and establish evidence

1. Confirm Emergent retention and do not cancel the service.
2. Record current DNS records and TTLs without changing them.
3. Create a timestamped source MongoDB archive with MongoDB Database Tools:

   ```bash
   mongodump --uri "$SOURCE_MONGO_URL" --db "$SOURCE_DB_NAME" \
     --archive="lakeview-source-YYYYMMDDTHHMMSSZ.archive.gz" --gzip
   shasum -a 256 lakeview-source-YYYYMMDDTHHMMSSZ.archive.gz
   ```

4. Store the archive and checksum in encrypted, access-controlled backup
   storage. Never commit it.
5. Produce a database inventory:

   ```bash
   export SOURCE_MONGO_URL='set-in-secret-shell'
   export SOURCE_DB_NAME='source-database-name'
   python backend/scripts/migrate_mongodb.py inventory \
     --output /secure/path/source-mongo-inventory.json
   ```

6. Produce the local-media inventory:

   ```bash
   python backend/scripts/migrate_media.py local-inventory \
     --output /secure/path/repo-media-inventory.json
   ```

7. With source Mongo access, produce the authoritative media classification:

   ```bash
   python backend/scripts/migrate_media.py inventory \
     --output /secure/path/source-media-inventory.json
   ```

Stop if any inventory fails or if the source archive cannot be restored in a
test environment.

## 3. Provision targets

### MongoDB Atlas

1. Create the cluster in a region near Render Ohio, with backups enabled.
2. Create separate migration and runtime users.
3. Configure Atlas network access for the migration operator and Render egress.
4. Start with an empty target database. Do not use `mongorestore --drop`.

For a binary restore, first validate the command without importing:

```bash
mongorestore --uri "$TARGET_MONGO_URL" --gzip \
  --archive="lakeview-source-YYYYMMDDTHHMMSSZ.archive.gz" --dryRun --verbose
```

Then restore into the empty target without `--drop`, or use the repository's
idempotent sync tool:

```bash
python backend/scripts/migrate_mongodb.py sync
python backend/scripts/migrate_mongodb.py sync --apply \
  --output /secure/path/initial-mongo-sync.json
python backend/scripts/migrate_mongodb.py compare \
  --output /secure/path/initial-mongo-compare.json
```

The compare report must show equal counts and checksums. A target that already
contains extra documents will intentionally compare unequal because the sync
tool never deletes target-only data.

### Cloudflare R2

1. Create a private bucket and a bucket-scoped migration token.
2. Export target variables (`S3_ENDPOINT_URL`, `S3_REGION=auto`, `S3_BUCKET`,
   `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `STORAGE_APP_NAME=lakeview`).
3. For remote slash-path objects, set either `--source-root` to a complete
   object export or `SOURCE_EMERGENT_LLM_KEY` in the secret shell.
4. Dry-run, then apply, then rerun in verification mode:

   ```bash
   python backend/scripts/migrate_media.py sync --verify-existing \
     --output /secure/path/media-dry-run.json
   python backend/scripts/migrate_media.py sync --apply --verify-existing \
     --output /secure/path/media-apply.json
   python backend/scripts/migrate_media.py sync --verify-existing \
     --output /secure/path/media-verify.json
   ```

The final report must have zero `missing_source`, zero conflicts, and every
planned record already verified. Never use `--overwrite-mismatch` until the
conflicting source/target bytes have been manually identified and approved.

## 4. Deploy staging on Render

1. Require the GitHub verification workflow to pass, including the Python
   dependency audit and production-container build. Review the documented
   Create React App build-chain advisories and record the release-owner's risk
   decision.
2. Connect the GitHub repository and apply `render.yaml`.
3. Enter every `sync: false` value in the Render dashboard. Render does not
   automatically provide these values to preview environments.
4. Set backend `CORS_ORIGINS` to the exact staging frontend origin; do not use
   `*`. Set frontend `REACT_APP_BACKEND_URL` to the public staging API origin.
5. Deploy `lakeview-api`, then `lakeview-web`.
6. Confirm `/api/health/live` returns 200 and `/api/health/ready` reports both
   MongoDB and storage reachable.
7. Restart/redeploy the API once before acceptance testing. Media must still be
   available afterward; no acceptance result may depend on ephemeral disk.

## 5. Mandatory staging acceptance checklist

Record timestamp, tester, URL, expected result, actual result, and evidence for
each item:

- homepage renders correct content and site images;
- `/menu` renders every category/item and prices match the source;
- mobile header/drawer navigation opens, closes, and reaches every section;
- every Square pickup/order link opens the existing Square destination;
- admin login rejects a bad password, accepts the real password, persists the
  session, logs out, and rejects the old token afterward;
- edit and restore one low-risk content field;
- edit and restore one menu field;
- active specials render correctly;
- catering inquiry submission appears in admin and status can be changed;
- newsletter signup appears in admin and duplicate handling is correct;
- loyalty join/lookup/stamp/claim works with a designated test record;
- existing local-legacy and former-remote media both render;
- new image upload appears in Library, survives API restart, and serves with
  the correct MIME type;
- thumbnail generation and a small video upload/thumbnail are tested;
- site-image assignment updates the public slot and reset restores its default;
- HTML featured image/template read path works;
- page views and button clicks appear in admin analytics;
- browser CORS succeeds from the staging frontend and fails from an unlisted
  origin;
- API restart and static-site redeploy do not lose database or media state;
- no active public/admin network request targets an Emergent domain;
- desktop and representative small mobile viewport have no blocking visual or
  navigation regression.

Any failure blocks production cutover.

## 6. Final delta and production cutover

1. Obtain explicit production-cutover approval.
2. Lower DNS TTL only after approval and before the maintenance window.
3. Ask the owner to pause admin edits/uploads during the final sync.
4. Rerun MongoDB source-to-target sync with `--apply`, then `compare`.
5. Rerun media sync and require all objects verified.
6. Configure production frontend/backend origins and redeploy from the exact
   tested Git commit.
7. Change only the approved web/API DNS records. Do not delete the old records
   from the evidence log.
8. Repeat the staging checklist against the production domain, including CORS,
   media, Square links, and admin login/logout.
9. Keep Emergent, the source database, its objects, and the source archive
   intact through the rollback window.
10. Because visitors may reach the old origin during DNS propagation, run one
    more source-to-target Mongo delta after propagation. The tool will not
    delete records created directly on the target.

## 7. Rollback

Rollback triggers include incorrect menu/content, missing media, failed writes,
admin authentication failure, repeated 5xx responses, broken CORS, or any data
checksum mismatch.

1. Stop owner edits/uploads and record the incident time.
2. Restore the previous DNS records (or switch the frontend API variable back)
   while leaving Atlas and R2 untouched.
3. Verify the old site is serving before declaring rollback complete.
4. Inventory Atlas and R2; do not delete post-cutover data.
5. If the old database must receive post-cutover records, reverse the Mongo
   tool's source/target environment variables and perform dry-run, approved
   `--apply`, and compare. The tool still performs no deletes.
6. Preserve R2-only uploads separately; the media tool intentionally does not
   write back to Emergent. Reconcile them after the application fault is fixed.
7. Redeploy staging, repeat the full checklist, and request a new cutover
   approval. Never "roll forward" while checksums are uncertain.

## 8. Source retirement and secret rotation

After a user-approved rollback window and a successful final delta:

1. Take final MongoDB and media inventories and retain their checksums.
2. Rotate Atlas runtime, R2 runtime, Render admin, and any source migration
   credentials. Remove migration-only credentials from local shells and Render.
3. Confirm GitHub remains the deployment source of truth and branch protection
   requires the verification workflow.
4. Only with explicit authorization, cancel Emergent after exports, archives,
   inventories, rollback evidence, and provider billing ownership are verified.
5. Deletion of old data is a separate, explicitly approved retention action;
   it is never part of migration completion.
