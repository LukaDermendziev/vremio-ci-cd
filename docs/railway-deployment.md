# Railway deployment — Fancy Fingers + Vremio (dual domain)

One Railway **web service** runs the Django app. Two domains point at it:

| Domain | Purpose | What visitors see |
|--------|---------|-------------------|
| `https://www.fancyfingers.mk` | Customer-facing (Instagram bio) | Salon page at `/`, booking flow |
| `https://YOUR-APP.up.railway.app` | Vremio platform (private for now) | Vremio homepage, admin, testing |

Both domains hit the **same** app and database. Customer emails and manage-booking links use `SITE_URL` (`www.fancyfingers.mk`).

---

## 1. Create the Railway project

> **If deploy fails at “Build image”:** open the web service → **Settings** → **Root Directory** must be `backend`. Also add PostgreSQL and reference `DATABASE_URL` before redeploying.

1. Go to [railway.app](https://railway.app) and create a new project.
2. **Deploy from GitHub** — connect this repo (`salon-scheduler-system`).
3. Open the web service → **Settings** → **Root Directory** → set to:
   ```
   backend
   ```
4. Railway reads `backend/railway.toml` automatically.

---

## 2. Add PostgreSQL

1. In the project, click **+ New** → **Database** → **PostgreSQL**.
2. Open the web service → **Variables** → **Add reference** → select `DATABASE_URL` from the Postgres service.

PostgreSQL is **required** in production (`DJANGO_DEBUG=False`).

---

## 3. Add Redis (recommended)

**Yes — add Redis in production.** Gunicorn runs multiple workers. Without Redis, rate limiting (`anti_abuse.py`) uses **in-memory cache per worker**, so limits are inconsistent and the `CACHE_URL is not set` warning appears in logs.

The app already supports Redis: set `CACHE_URL` and Django uses the built-in `RedisCache` backend (`redis` package is in `requirements.txt`).

### Steps on Railway

1. In the project canvas, click **+ New** → **Database** → **Redis**.
2. Open your **web service** → **Variables** → **Add reference**.
3. Pick the Redis service variable (usually `REDIS_URL`).
4. Add a **new** variable on the web service named `CACHE_URL` and set its value to the Redis **private** URL reference (e.g. `REDIS_PRIVATE_URL` or `${{Redis.REDIS_PRIVATE_URL}}`).

   Railway may expose both public and private URLs — use the **private** one so the web service can reach Redis on Railway’s internal network.

5. Redeploy the web service.

### Verify after deploy

In Railway logs, the `CACHE_URL is not set` warning should disappear. Rate limits (booking attempts per IP/phone/device) are then shared across all Gunicorn workers.

> Redis is for **caching/rate limits only**. Customer photos still need the media volume (next section). Booking emails still use Brevo SMTP — Redis does not replace email.

---

## 4. Add a volume for customer photos

Uploaded booking photos are stored on disk. Without a volume, they are lost on redeploy.

**Volumes are not in Settings.** Create one like this:

### Option A — Command palette (easiest)

1. Open your **Project** canvas (the diagram with your services).
2. Press **`Ctrl+K`** (Windows) or **`Cmd+K`** (Mac).
3. Type **`volume`** → choose **Create Volume** (or similar).
4. Select your **web service** (the GitHub repo service).
5. Mount path:

   ```
   /app/media
   ```

6. Redeploy the web service.

Also set variable `MEDIA_ROOT=/app/media` in **Variables** (if not already).

### Option B — Right-click canvas

1. On the project canvas, **right-click** empty space.
2. Look for **Create Volume** / **Add Volume**.
3. Attach to the web service, mount path `/app/media`.

### Option C — Railway CLI

```bash
railway link
railway volume add --mount-path /app/media
```

Then redeploy.

> **Note:** You can launch without a volume first — the site will work, but uploaded photos may disappear on the next redeploy until the volume is attached.

### Bootstrap salon on production (one-time)

`railway run` executes **on your PC** and cannot reach `postgres.railway.internal`. Use **SSH** into the running container instead:

```bash
railway login
railway link   # select the web service, not Postgres
railway ssh keys add   # first time only — register your SSH key

railway ssh /opt/venv/bin/python manage.py setup_beta_salon \
  --username OWNER_USERNAME \
  --email owner@example.com \
  --slug fancy-fingers \
  --salon-name "Fancy Fingers" \
  --instagram salon_instagram_handle

railway ssh /opt/venv/bin/python manage.py changepassword OWNER_USERNAME
```

Nixpacks installs packages in `/opt/venv`. Plain `python` over SSH may not see Django — always use `/opt/venv/bin/python`.

---

## 5. Environment variables

**Do not upload your local `.env` file to Railway.** Railway does not use a file on disk — you enter each variable separately in the dashboard (or via the Railway CLI). Your local `.env` stays on your machine only.

Use [`.env.example`](../.env.example) as a checklist. Copy values **one by one** into **web service → Variables → New Variable**. Skip anything that only applies locally (e.g. `DJANGO_DEBUG=True`).

| Local `.env` | Railway |
|--------------|---------|
| One file in the repo root | Individual key/value pairs in the dashboard |
| Gitignored | Stored encrypted by Railway |
| Used by `python-dotenv` locally | Injected as OS environment variables at runtime |
| SQLite when no `DATABASE_URL` | PostgreSQL via referenced `DATABASE_URL` |

`DATABASE_URL` should be added as a **reference** from the Postgres service (Railway links them automatically) — do not paste a local value.

### Complete variable list (copy into Railway)

Web service → **Variables** → **Raw Editor** — paste and fill in the `<...>` placeholders:

```env
DJANGO_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(50))">
DJANGO_DEBUG=False

DJANGO_ALLOWED_HOSTS=www.fancyfingers.mk,fancyfingers.mk
SITE_URL=https://www.fancyfingers.mk
USE_RAILWAY_SITE_URL=True

CUSTOMER_DOMAINS=www.fancyfingers.mk,fancyfingers.mk
CUSTOMER_DOMAIN_SALON_SLUG=fancy-fingers

MEDIA_ROOT=/app/media

BREVO_API_KEY=<your-brevo-api-key>
DEFAULT_FROM_EMAIL=Fancy Fingers Booking <noreply@fancyfingers.mk>
OWNER_NOTIFICATION_EMAIL=fancyfingers97@gmail.com
VREMIO_CONTACT_EMAIL=contact.vremio@gmail.com
```

Then separately add **`DATABASE_URL`** via **Add Reference** → Postgres service (do not paste into Raw Editor).

### Auto-set by Railway (do not add manually)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | From Postgres reference |
| `RAILWAY_PUBLIC_DOMAIN` | Your `*.up.railway.app` hostname |
| `RAILWAY_PRIVATE_DOMAIN` | Internal networking |
| `RAILWAY_ENVIRONMENT` | Detects Railway runtime |
| `PORT` | Port Gunicorn binds to |

### Redis (recommended — see section 3)

```env
CACHE_URL=<reference REDIS_URL from Redis service>
```

### Other optional

```env
SECURE_SSL_REDIRECT=False
SECURE_HSTS_PRELOAD=False
```

`SECURE_SSL_REDIRECT` defaults to **False** on Railway automatically (HTTPS is handled at the edge).

### Required (summary)

```env
DJANGO_SECRET_KEY=<generate-a-long-random-string>
DJANGO_DEBUG=False

DJANGO_ALLOWED_HOSTS=www.fancyfingers.mk,fancyfingers.mk
SITE_URL=https://www.fancyfingers.mk

CUSTOMER_DOMAINS=www.fancyfingers.mk,fancyfingers.mk
CUSTOMER_DOMAIN_SALON_SLUG=fancy-fingers

MEDIA_ROOT=/app/media
```

`RAILWAY_PUBLIC_DOMAIN` is injected by Railway and added to `ALLOWED_HOSTS` automatically.  
`CSRF_TRUSTED_ORIGINS` is auto-built from `https://` + each allowed host when `DEBUG=False`.

### Public URL for emails and verify links

Until `fancyfingers.mk` is live, keep **`USE_RAILWAY_SITE_URL=True`**. Verify links, manage-booking links, and email URLs then use your `*.up.railway.app` domain automatically.

When the custom domain is ready:

```env
SITE_URL=https://www.fancyfingers.mk
USE_RAILWAY_SITE_URL=False
```

(or remove `USE_RAILWAY_SITE_URL` entirely)

### Email (Brevo — use HTTPS API on Railway)

**Railway Hobby/Free blocks outbound SMTP** (ports 587/465). Brevo SMTP will not work unless you are on Railway **Pro**. Use the **Brevo API key** instead (HTTPS on port 443).

In Brevo: **SMTP & API** → create/copy your **API key** (starts with `xkeysib-`). Verify your sender domain or email under **Senders**.

```env
BREVO_API_KEY=<your-brevo-api-key>
DEFAULT_FROM_EMAIL=Fancy Fingers Booking <noreply@fancyfingers.mk>
OWNER_NOTIFICATION_EMAIL=fancyfingers97@gmail.com
VREMIO_CONTACT_EMAIL=contact.vremio@gmail.com
SITE_URL=https://www.fancyfingers.mk
```

Do **not** set `EMAIL_BACKEND=smtp` on Railway Hobby — the app auto-selects the Brevo API backend when `BREVO_API_KEY` is set.

Test after deploy:

```bash
railway ssh /opt/venv/bin/python manage.py test_email your@email.com
```

Look for `Brevo API email sent` in logs. On failure you will see `Brevo API HTTP 4xx` with the reason (e.g. unverified sender).

---


## CI/CD

| Layer | Tool | What happens |
|-------|------|----------------|
| **CI** | GitHub Actions (`.github/workflows/ci.yml`) | On every push/PR to `master`: runs tests + `check --deploy` |
| **CD** | Railway (GitHub integration) | On every push to `master`: build → migrate → redeploy |

Workflow:

```
git push → GitHub Actions runs tests
         → Railway builds and deploys (in parallel)
```

Railway does **not** wait for GitHub Actions to pass. If tests fail, fix before pushing, or add branch protection on `master` (see below).

### Recommended: protect `master`

In GitHub → **Settings** → **Branches** → **Branch protection rule** for `master`:

- Require status check **Tests** before merge
- Require pull request reviews (optional for solo dev)

That way broken code does not reach production via PR merges.

---

## 6. First deploy

Push to GitHub (or click **Deploy**). Railway will:

1. `pip install -r requirements.txt`
2. `collectstatic`
3. `migrate` (pre-deploy)
4. Start Gunicorn on `$PORT`

Check **Deployments → View logs** for errors.

Health check: `GET /health/` → `ok`

### Scheduled tasks (cron)

These commands are **not** run automatically on deploy. Add a **Cron Job** service in Railway (or an external scheduler) pointing at the same repo/image:

| Command | Suggested schedule | Purpose |
|---------|-------------------|---------|
| `python manage.py send_booking_reminders` | Every 15–30 minutes | Email/SMS reminders before appointments |
| `python manage.py cleanup_unverified_bookings` | Every 15–30 minutes | Remove expired unverified bookings |
| `python manage.py auto_complete_past_bookings` | Hourly | Mark past approved bookings completed |

Example Railway cron start command:

```bash
python manage.py send_booking_reminders
```

Because the web service uses `backend/railway.toml` (Gunicorn), the cron service must use a **separate config file** or it will also try to start Gunicorn. Point the cron service to `backend/railway.cron.toml`:

1. Open the **reminders-cron** service → **Settings**
2. Find **Config-as-code** / **Railway Config File** (path is from **repo root**, not `backend/`)
3. Set: `/backend/railway.cron.toml`
4. Redeploy

That file runs reminders, then cleanup (`&&` — cleanup runs only if reminders succeed).

Use `railway ssh` to test manually:

```bash
railway ssh /opt/venv/bin/python manage.py send_booking_reminders --dry-run
```

---

## 7. Bootstrap salon data (one time)

After the first successful deploy, run the setup command **inside** the Railway container (see bootstrap section above for SSH setup):

```bash
railway link
railway ssh keys add   # first time only

railway ssh /opt/venv/bin/python manage.py setup_beta_salon \
  --username sofija_stankova \
  --email fancyfingers97@gmail.com \
  --slug fancy-fingers \
  --salon-name "Fancy Fingers" \
  --instagram fancyy.fingerss

railway ssh /opt/venv/bin/python manage.py changepassword sofija_stankova
```

Do **not** use `railway run` — it runs locally and cannot reach the private database host.

Create a Django superuser for `/admin/` if needed:

```bash
railway run python manage.py createsuperuser
```

---

## 8. Custom domain — Fancy Fingers

1. Web service → **Settings** → **Networking** → **Custom Domain**
2. Add: `www.fancyfingers.mk`
3. Railway shows a **CNAME** target (e.g. `something.up.railway.app`).
4. At your domain registrar, add:

   | Type | Name | Value |
   |------|------|--------|
   | CNAME | `www` | Railway CNAME target |

5. Optional: redirect bare `fancyfingers.mk` → `www.fancyfingers.mk` (registrar redirect or second CNAME if Railway supports apex).

Railway provisions HTTPS automatically once DNS propagates (often 5–30 minutes).

---

## 9. What to put where

| Link | URL |
|------|-----|
| Instagram bio | `https://www.fancyfingers.mk/` |
| Owner login (bookmark, don’t share publicly) | `https://www.fancyfingers.mk/owner/login/` |
| Vremio platform (private) | `https://YOUR-APP.up.railway.app/` |
| Django admin | `https://YOUR-APP.up.railway.app/admin/` |

On `www.fancyfingers.mk`, visiting `/` redirects to the Fancy Fingers salon page. The Vremio homepage only appears on the Railway domain.

---

## 10. Post-deploy checklist

- [ ] `https://www.fancyfingers.mk/` → salon page
- [ ] `https://YOUR-APP.up.railway.app/` → Vremio homepage
- [ ] Submit a test booking (no CSRF error)
- [ ] Owner receives email notification
- [ ] Customer manage link in email uses `www.fancyfingers.mk`
- [ ] Owner login + dashboard work
- [ ] Photo upload persists after redeploy (volume mounted)
- [ ] `/health/` returns `ok`

---

## 11. Troubleshooting

**Healthcheck failure**
→ Build/deploy OK but `/health/` failed. Common causes: missing `DJANGO_SECRET_KEY` or `DATABASE_URL`, or app crash on startup. Click **View logs** on the Deploy step (not Build). Also **generate a public domain** (Settings → Networking) — your service may show as "Unexposed". A code fix auto-allows Railway internal healthcheck hosts and disables SSL redirect internally.

**Build failed during “Build image”**
→ Almost always **Root Directory** is not `backend`, or PostgreSQL/`DATABASE_URL` is missing while `DJANGO_DEBUG=False`. Set root to `backend`, reference `DATABASE_URL`, redeploy. Click **View logs** on the failed deploy for the exact error line.

**CSRF error on booking form**  
→ Ensure `DJANGO_DEBUG=False` and domain is in `DJANGO_ALLOWED_HOSTS`. CSRF origins are auto-added for HTTPS hosts.

**Static files missing**  
→ `collectstatic` runs in build; check build logs.

**Photos gone after redeploy**  
→ Volume not mounted or `MEDIA_ROOT` not set to `/app/media`.

**Password reset link wrong domain**  
→ Set `SITE_URL=https://www.fancyfingers.mk`.

**DisallowedHost error**  
→ Add the hostname to `DJANGO_ALLOWED_HOSTS` or rely on `RAILWAY_PUBLIC_DOMAIN` auto-add for the Railway URL.

**Booking hung or failed around deploy time**  
→ Logs like `Handling signal: term` and `Worker exiting` mean Railway restarted the app (new deploy), not a booking bug. In-flight requests are killed mid-response. Wait ~1 minute after deploy, then try again. If a booking was saved but the browser never got the redirect, delete the stuck **Unverified** or **Pending** row in the owner dashboard before retrying.

**Booking still slow after deploy**  
→ Check `CACHE_URL` uses Railway’s **private** Redis URL (`REDIS_PRIVATE_URL` or internal reference), not a public URL the app cannot reach. Wrong Redis can block rate-limit cache calls. With the latest code, cache failures are logged and bookings still proceed.

**Verification email not received**  
→ **Most common on Railway Hobby:** SMTP is blocked. Remove `EMAIL_BACKEND=smtp` and set **`BREVO_API_KEY`** (Brevo dashboard → SMTP & API → API keys). `DEFAULT_FROM_EMAIL` must use a **verified sender** in Brevo.

```env
BREVO_API_KEY=xkeysib-...
DEFAULT_FROM_EMAIL=Fancy Fingers Booking <noreply@fancyfingers.mk>
```

Test: `railway ssh /opt/venv/bin/python manage.py test_email your@email.com`  
Logs: `Brevo API email sent` = success; `Brevo API HTTP 400` = usually unverified sender.

---

## Local vs production

| | Local | Railway |
|---|-------|---------|
| Database | SQLite | PostgreSQL |
| Debug | `True` | `False` |
| Media | `backend/media/` | `/app/media` volume |
| Domains | `127.0.0.1:8000` | fancyfingers.mk + railway.app |

Keep using `.env` locally. **Never** commit `.env` — set variables only in Railway dashboard.
