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

## 3. Add a volume for customer photos

Uploaded booking photos are stored on disk. Without a volume, they are lost on redeploy.

1. Web service → **Settings** → **Volumes** → **Add volume**
2. Mount path:
   ```
   /app/media
   ```
3. Add variable:
   ```
   MEDIA_ROOT=/app/media
   ```

---

## 4. Environment variables

**Do not upload your local `.env` file to Railway.** Railway does not use a file on disk — you enter each variable separately in the dashboard (or via the Railway CLI). Your local `.env` stays on your machine only.

Use [`.env.example`](../.env.example) as a checklist. Copy values **one by one** into **web service → Variables → New Variable**. Skip anything that only applies locally (e.g. `DJANGO_DEBUG=True`).

| Local `.env` | Railway |
|--------------|---------|
| One file in the repo root | Individual key/value pairs in the dashboard |
| Gitignored | Stored encrypted by Railway |
| Used by `python-dotenv` locally | Injected as OS environment variables at runtime |
| SQLite when no `DATABASE_URL` | PostgreSQL via referenced `DATABASE_URL` |

`DATABASE_URL` should be added as a **reference** from the Postgres service (Railway links them automatically) — do not paste a local value.

### Required

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

### Email (you already use Brevo locally)

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<your-brevo-login>
EMAIL_HOST_PASSWORD=<your-brevo-smtp-key>
DEFAULT_FROM_EMAIL=Fancy Fingers Booking <noreply@fancyfingers.mk>
OWNER_NOTIFICATION_EMAIL=fancyfingers97@gmail.com
VREMIO_CONTACT_EMAIL=contact.vremio@gmail.com
```

Use a verified sender in Brevo (domain or email).

### Optional (recommended later)

```env
CACHE_URL=<redis-url-from-railway-redis-plugin>
```

Without Redis, rate limiting uses in-memory cache per worker. Add Redis before scaling traffic.

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

## 5. First deploy

Push to GitHub (or click **Deploy**). Railway will:

1. `pip install -r requirements.txt`
2. `collectstatic`
3. `migrate` (pre-deploy)
4. Start Gunicorn on `$PORT`

Check **Deployments → View logs** for errors.

Health check: `GET /health/` → `ok`

---

## 6. Bootstrap salon data (one time)

After the first successful deploy, run the setup command on Railway:

**Option A — Railway CLI**

```bash
railway link
railway run python manage.py setup_beta_salon \
  --username fancy_fingers_owner \
  --email fancyfingers97@gmail.com \
  --slug fancy-fingers \
  --salon-name "Fancy Fingers"
```

**Option B — Railway dashboard**

Service → **Settings** → run a one-off command (if available) or use the CLI above.

Then set the owner password:

```bash
railway run python manage.py changepassword fancy_fingers_owner
```

Or use **password reset** at `https://www.fancyfingers.mk/owner/password/reset/`.

Create a Django superuser for `/admin/` if needed:

```bash
railway run python manage.py createsuperuser
```

---

## 7. Custom domain — Fancy Fingers

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

## 8. What to put where

| Link | URL |
|------|-----|
| Instagram bio | `https://www.fancyfingers.mk/` |
| Owner login (bookmark, don’t share publicly) | `https://www.fancyfingers.mk/owner/login/` |
| Vremio platform (private) | `https://YOUR-APP.up.railway.app/` |
| Django admin | `https://YOUR-APP.up.railway.app/admin/` |

On `www.fancyfingers.mk`, visiting `/` redirects to the Fancy Fingers salon page. The Vremio homepage only appears on the Railway domain.

---

## 9. Post-deploy checklist

- [ ] `https://www.fancyfingers.mk/` → salon page
- [ ] `https://YOUR-APP.up.railway.app/` → Vremio homepage
- [ ] Submit a test booking (no CSRF error)
- [ ] Owner receives email notification
- [ ] Customer manage link in email uses `www.fancyfingers.mk`
- [ ] Owner login + dashboard work
- [ ] Photo upload persists after redeploy (volume mounted)
- [ ] `/health/` returns `ok`

---

## 10. Troubleshooting

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

---

## Local vs production

| | Local | Railway |
|---|-------|---------|
| Database | SQLite | PostgreSQL |
| Debug | `True` | `False` |
| Media | `backend/media/` | `/app/media` volume |
| Domains | `127.0.0.1:8000` | fancyfingers.mk + railway.app |

Keep using `.env` locally. **Never** commit `.env` — set variables only in Railway dashboard.
