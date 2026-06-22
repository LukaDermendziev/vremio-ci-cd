# Beta Deployment Guide

This guide covers deploying the Salon Scheduler System for a real single-salon beta test. It is provider-neutral — adapt steps for Render, Railway, Fly.io, or a VPS.

## Architecture Overview

```
Customer browser  →  HTTPS  →  Gunicorn + Django
Owner browser     →  HTTPS  →  Gunicorn + Django
                              ↓
                         PostgreSQL
                         Media volume (photos)
                         WhiteNoise (static files)
```

## Prerequisites

- Python 3.11+ (3.12 or 3.14 tested locally)
- PostgreSQL database
- SMTP email account (Gmail app password, SendGrid, Mailgun, etc.)
- Domain name with HTTPS (recommended for beta)

## Environment Variables (Production)

Copy [`.env.example`](../.env.example) and set at minimum:

```env
DJANGO_SECRET_KEY=<long-random-string>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
SITE_URL=https://yourdomain.com

DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=Salon Scheduler <noreply@yourdomain.com>
```

Never commit `.env` or real credentials to git.

## Database Setup

1. Create a PostgreSQL database on your provider.
2. Set `DATABASE_URL` (or discrete `POSTGRES_*` variables).
3. Run migrations:

```bash
cd backend
python manage.py migrate
```

## Static Files

WhiteNoise serves collected static files in production.

Before each deploy:

```bash
cd backend
python manage.py collectstatic --noinput
```

Static files are collected to `backend/staticfiles/` (gitignored).

## Media Files (Customer Photos)

Reference photos are stored on disk at `MEDIA_ROOT` (default: `backend/media/`).

**Important:** Many PaaS platforms use ephemeral disks — uploaded photos are lost on redeploy unless you attach persistent storage.

| Platform | Strategy |
|----------|----------|
| **Render** | Attach a persistent disk and set `MEDIA_ROOT` to the mount path |
| **Railway** | Use a volume mount for `/media` |
| **VPS** | Store at `/var/www/salon-scheduler/media` with nginx serving or Django in DEBUG=False via reverse proxy |
| **Future** | S3/R2 cloud storage (post-beta milestone) |

For local development, media is served automatically when `DEBUG=True`.

In production, configure your reverse proxy (nginx/Caddy) to serve `/media/` from `MEDIA_ROOT`, or use a persistent volume path.

## Running with Gunicorn

From the `backend/` directory:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2
```

Most PaaS providers run a similar command via their config.

## Owner Account Setup (Beta)

Owners are **not** self-registered. Set up manually:

### Step 1: Create superuser (for admin panel access)

```bash
python manage.py createsuperuser
```

### Step 2: Bootstrap salon data

```bash
python manage.py setup_beta_salon \
  --username salon_owner \
  --email owner@salon.com \
  --slug your-salon-slug \
  --salon-name "Your Salon Name"
```

This creates:
- Owner user (no usable password)
- Salon linked to owner
- Booking policy with beta defaults (14-day notice, manual approval, etc.)
- Working hours Mon–Sat 08:00–18:00, Sunday closed
- Services: Manicure, Manicure with Design, Pedicure, Medical Pedicure

### Step 3: Set owner password

**Never email plain text passwords.**

Option A — password reset email (recommended):
1. Ensure SMTP is configured.
2. Owner visits `https://yourdomain.com/owner/password/reset/`
3. Owner receives link and sets their password.

Option B — admin sends reset from Django admin:
1. Log in to `/admin/`
2. Select the user → "Send password reset email" (if using admin action) or use management command:

```bash
python manage.py changepassword salon_owner
```

### Step 4: Verify owner access

1. Owner logs in at `/owner/login/`
2. Redirected to `/owner/dashboard/`
3. Owner can only see their own salon's data

## Email Flows

| Event | Recipient | When |
|-------|-----------|------|
| Password reset | Owner | Owner requests reset at `/owner/password/reset/` |
| New booking request | Owner | Customer submits booking (owner email or `OWNER_NOTIFICATION_EMAIL`) |
| Request received | Customer | After online submit (includes manage link) |
| Approved / rejected / edited / cancelled | Customer | Owner action (requires customer email) |
| Customer cancel | Owner + customer | Customer cancels via manage link |
| Pending expiration | — | Policy field exists; cron not yet implemented (post-beta) |

Development uses console email backend (emails print to terminal). Customer emails use `Reply-To: owner/salon email` when configured.

## Security Settings (Automatic when DEBUG=False)

When `DJANGO_DEBUG=False`, the following are enabled:

- `SECURE_SSL_REDIRECT` (HTTPS redirect)
- Secure session and CSRF cookies
- HSTS headers
- XSS / content-type protections

Set `SECURE_SSL_REDIRECT=False` only if testing production settings locally without HTTPS.

## Provider Notes

### Render

- Add PostgreSQL addon → copy `DATABASE_URL` to env
- Build command: `pip install -r backend/requirements.txt && cd backend && python manage.py collectstatic --noinput`
- Start command: `cd backend && gunicorn config.wsgi:application`
- Attach persistent disk for media if photo uploads are needed

### Railway

- Add PostgreSQL plugin
- Set env vars in Railway dashboard
- Use a volume for `MEDIA_ROOT`
- Deploy from repo root with start command pointing to `backend/`

### VPS (Ubuntu)

1. Install Python, PostgreSQL, nginx
2. Clone repo, create venv, install requirements
3. Configure `.env`
4. Run migrate + collectstatic
5. Gunicorn via systemd
6. nginx reverse proxy with SSL (Let's Encrypt)
7. nginx location `/media/` → `MEDIA_ROOT`

## Post-Deploy Smoke Tests

1. **Homepage** loads: `/`
2. **Salon page** loads: `/book/<slug>/`
3. **Customer booking** — submit a test request
4. **Owner email** — verify new booking notification received
5. **Owner login** — `/owner/login/`
6. **Approve booking** — pending count decreases, customer email if provided
7. **Photo upload** — submit booking with reference photo, verify file in media storage
8. **Password reset** — request reset, verify email link works

## What Is Deferred (Post-Beta)

- Cloud media storage (S3/R2)
- Login rate limiting (django-axes or reverse-proxy)
- Two-factor authentication for owners
- Automated SMS reminders
- Automated 24h reminder cron job (policy field exists, scheduler not yet implemented)
- Payments / deposits

## Troubleshooting

**Static files missing in production**
→ Run `collectstatic`. Verify WhiteNoise middleware is active.

**CSRF errors on HTTPS**
→ Add your domain to `CSRF_TRUSTED_ORIGINS`.

**Password reset link uses wrong domain**
→ Set `SITE_URL` and ensure `ALLOWED_HOSTS` is correct.

**Photos disappear after redeploy**
→ Ephemeral disk — attach persistent volume or plan cloud storage.

**Emails not sending**
→ Check SMTP credentials. Test with `EMAIL_BACKEND=console` first locally.
