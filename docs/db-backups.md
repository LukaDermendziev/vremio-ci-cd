# Database backups (GitHub Actions → Cloudflare R2)

Automated **weekly** off-site backups of the production Postgres database.

- **Runner:** GitHub Actions (`.github/workflows/db-backup.yml`) — independent of Railway, so
  backups keep running even if the Railway project is down or deleted.
- **Storage:** a Cloudflare R2 bucket (S3-compatible, 10 GB free tier, no egress fees).
- **Schedule:** every Sunday 03:00 UTC, plus manual "Run workflow" any time.
- **Retention:** the newest 12 backups are kept; older ones are pruned automatically
  (change `KEEP_BACKUPS` in the workflow).

## One-time setup

### 1. Create the Cloudflare R2 bucket

1. Cloudflare dashboard → **R2** → **Create bucket**.
2. Name it e.g. `vremio-db-backups`, pick a location, create.
3. On the R2 overview page, note your **Account ID** — your S3 endpoint is
   `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.

### 2. Create an R2 API token

1. R2 → **Manage R2 API Tokens** → **Create API token**.
2. Permissions: **Object Read & Write**, scoped to the `vremio-db-backups` bucket.
3. Copy the **Access Key ID** and **Secret Access Key** (shown once).

### 3. Get the database URL from Railway

- Railway → Postgres service → **Variables** → copy the value of **`DATABASE_PUBLIC_URL`**
  (the public one — GitHub runs outside Railway, so it must use the public endpoint).

### 4. Add GitHub repository secrets

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret | Value |
|---|---|
| `BACKUP_DATABASE_URL` | Railway `DATABASE_PUBLIC_URL` value |
| `R2_ENDPOINT` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
| `R2_BUCKET` | `vremio-db-backups` |
| `R2_ACCESS_KEY_ID` | R2 token access key id |
| `R2_SECRET_ACCESS_KEY` | R2 token secret access key |

### 5. Run it once to verify

- Repo → **Actions** → **DB Backup** → **Run workflow**.
- Confirm the run is green and a `vremio-<timestamp>.dump` file appears in the R2 bucket.

## Restoring a backup

You dump/restore with the PostgreSQL client on your machine (or any host). The dump is in
`pg_dump` custom format, so restore with `pg_restore`.

1. Download the dump from R2 (Cloudflare dashboard, or `aws s3 cp` with the R2 endpoint).
2. Restore into a target database (e.g. a fresh Railway Postgres). Use the target's
   **public** URL when restoring from your PC:

   ```bash
   pg_restore \
     --no-owner --no-acl \
     --clean --if-exists \
     -d "postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require" \
     vremio-<timestamp>.dump
   ```

   - `--clean --if-exists` drops existing objects first, so you can restore over an
     existing database. Omit it when restoring into a brand-new empty database.

## Restore test (do this once)

An untested backup is not a backup. Verify the whole loop works:

1. Create a **temporary** empty Postgres (a scratch Railway Postgres, or local Docker:
   `docker run -e POSTGRES_PASSWORD=test -p 5433:5432 postgres`).
2. `pg_restore` the latest dump into it (command above).
3. Connect and sanity-check a couple of tables, e.g.:

   ```bash
   psql "postgresql://.../DBNAME" -c "select count(*) from booking_booking;"
   ```

4. Tear the temporary database down.

If the counts look right, your backup + restore path is proven.

## Notes

- **Cost:** for a small database a weekly dump is a few MB; R2 storage/upload is free and
  Railway egress on the dump read is a fraction of a cent per month.
- **Security:** credentials live only in GitHub Actions secrets and are never printed. R2
  encrypts objects at rest. For extra safety you can add a `gpg` encryption step before
  upload.
- **Version safety:** the workflow installs the newest PostgreSQL client from the official
  PGDG repo, which can dump any equal-or-older server — so Railway minor security patches
  and future major upgrades won't break it.
