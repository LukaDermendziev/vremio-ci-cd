# Vremio Production Readiness

Checklist for deploying Vremio with **multiple businesses** (10+ salons) on PostgreSQL.  
For step-by-step deploy instructions, see [beta-deployment.md](beta-deployment.md).

Legend: **Completed** | **Needs configuration** | **Missing**

---

## Database

| Item | Status | Notes |
|------|--------|-------|
| PostgreSQL via `DATABASE_URL` | Needs configuration | Set on Railway/Render/Fly |
| PostgreSQL via `POSTGRES_*` | Needs configuration | Alternative to `DATABASE_URL` |
| SQLite local dev only | Completed | Blocked when `DJANGO_DEBUG=False` |
| Migrations through `0016` | Completed | Run `python manage.py migrate` on deploy |
| FK integrity (salon-scoped models) | Completed | Bookings, customers, services, blocklist, etc. |
| Booking composite indexes | Completed | `(salon, status, start_at)` |
| Blocklist / unavailable-block indexes | Completed | Migration `0016` |
| Connection pooling (`CONN_MAX_AGE`) | Completed | `DATABASE_URL` and `POSTGRES_*` paths |
| Automated tests | Completed | `python manage.py test` |

---

## Multi-business isolation

| Item | Status | Notes |
|------|--------|-------|
| Owner API scoped to `_get_owner_salon()` | Completed | All `/owner/*` data queries filter `salon=salon` |
| Public booking by salon slug | Completed | Services validated per salon |
| Manage booking by UUID token | Completed | Capability URL, not enumerable |
| Booking success page (no IDOR) | Completed | Session-gated `/booking/success/`; legacy int URL returns 404 |
| Block customer APIs salon-scoped | Completed | Cross-salon tests in `ProductionReadinessTests` |
| `BookingService` cross-salon guard | Completed | Model `clean()` rejects wrong salon service |
| Django admin tenant isolation | Needs configuration | **Do not grant staff access to salon owners** — admin shows all tenants |
| Multi-salon per owner account | Missing (future) | One owner user with multiple salons only sees `.first()` salon |

---

## Media / file uploads

| Item | Status | Notes |
|------|--------|-------|
| PIL validation (type, size) | Completed | JPEG/PNG/WebP, 5 MB default |
| UUID filenames | Completed | No overwrite collisions |
| Owner-only photo serving | Completed | `/owner/booking/<id>/photo/` with salon check |
| `/media/` public in DEBUG only | Completed | Production must not expose `/media/` |
| Persistent `MEDIA_ROOT` volume | Needs configuration | Required on PaaS (Render disk, Railway volume) |
| S3/object storage | Missing (future) | Local volume OK for initial 10+ businesses |

---

## Email

| Item | Status | Notes |
|------|--------|-------|
| Env-driven SMTP | Needs configuration | Set `EMAIL_BACKEND=smtp` + credentials |
| Brevo SMTP | Needs configuration | Example in `.env.example` |
| `SITE_URL` for links | Needs configuration | Must be HTTPS production URL |
| Verification emails | Completed | UUID token flow |
| Password reset | Completed | Django auth views |
| Owner notifications | Completed | `OWNER_NOTIFICATION_EMAIL` or owner User email |
| HTML email escaping | Completed | User content escaped in HTML part |
| Console backend (dev) | Completed | Default when SMTP not set |

Test: `python manage.py test_email --to you@example.com`

---

## Environment configuration

| Item | Status | Notes |
|------|--------|-------|
| `DJANGO_SECRET_KEY` | Needs configuration | Required when `DEBUG=False` |
| `DJANGO_DEBUG=False` | Needs configuration | Production default |
| `DJANGO_ALLOWED_HOSTS` | Needs configuration | Include production domain |
| `CSRF_TRUSTED_ORIGINS` | Needs configuration | HTTPS origins for forms |
| `SITE_URL` | Needs configuration | Public base URL |
| `.env.example` | Completed | Documents all variables |
| Secrets in source code | Completed | None committed |

---

## Security

| Item | Status | Notes |
|------|--------|-------|
| CSRF protection | Completed | Middleware + form tokens |
| XSS (templates) | Completed | No `\|safe` on user content |
| XSS (owner calendar JS) | Completed | `escapeHtml()` on customer names |
| Session cookies secure (prod) | Completed | When `DEBUG=False` |
| HTTPS redirect + HSTS | Completed | When `DEBUG=False` |
| `SECURE_PROXY_SSL_HEADER` | Completed | For Railway/Render/nginx |
| Rate limiting / honeypot | Completed | Requires `CACHE_URL` (Redis) for multi-worker |
| Owner login brute-force | Completed | Cache lockout after 5 failures / 15 min |
| Content-Security-Policy | Completed | Middleware; allows fonts + jsDelivr CSS |
| Customer IP block match | Completed | Public IPs only; private/loopback ignored |
| Postgres SSL (prod) | Completed | `sslmode=require` when `DEBUG=False`; override via `DATABASE_SSLMODE` |
| Booking success IDOR | Completed | Session-gated success page |

---

## Performance

| Item | Status | Notes |
|------|--------|-------|
| Dashboard prefetch | Completed | `select_related` / `prefetch_related` |
| Blocklist lookup | Completed | Indexed ORM query |
| Redis cache | Needs configuration | `CACHE_URL` for Gunicorn multi-worker |
| N+1 on owner POST actions | Completed | Minor query validation on slot exclude |

---

## Logging

| Item | Status | Notes |
|------|--------|-------|
| `LOGGING` in settings | Completed | Console handler, `django.request` ERROR |
| Email failures logged | Completed | `booking.email` logger WARNING |
| Passwords/tokens in logs | Completed | Not logged |

**Needs configuration:** Ship logs to your host (Railway/Render log drain) or add a file/JSON handler if self-hosting.

---

## Deployment

| Item | Status | Notes |
|------|--------|-------|
| Gunicorn | Completed | In `requirements.txt` |
| WhiteNoise static files | Completed | `collectstatic` on deploy |
| `DEBUG=False` smoke test | Needs configuration | Verify after deploy |
| PostgreSQL backups | Needs configuration | Provider automated backups or `pg_dump` cron |
| Media backups | Needs configuration | Volume snapshots or rsync |
| Health check | Needs configuration | HTTP GET `/` or provider default |

Deploy commands:

```bash
cd backend
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

---

## HTTPS

| Item | Status | Notes |
|------|--------|-------|
| TLS termination | Needs configuration | Provider or nginx |
| `SECURE_SSL_REDIRECT` | Completed | Default True when `DEBUG=False` |
| `CSRF_TRUSTED_ORIGINS` | Needs configuration | Must match HTTPS domain |

---

## Monitoring (recommended before scale)

| Item | Status | Notes |
|------|--------|-------|
| Error alerting (Sentry, etc.) | Optional | Set `SENTRY_DSN` to enable; off by default |
| Uptime monitoring | Missing | Ping homepage + owner login |
| DB connection monitoring | Needs configuration | Provider dashboards |

---

## Scalability notes (10+ businesses)

- **Current model:** One `Salon` per business; one owner `User` per salon (recommended for initial rollout).
- **PostgreSQL:** Suitable for hundreds of salons at current query patterns (~4–5 appointments/day/salon).
- **Redis:** Recommended when running 2+ Gunicorn workers (rate limits, anti-abuse).
- **Media volume:** Plan ~5 MB × photo uploads; monitor disk on shared host.
- **Future:** Per-salon notification email, salon switcher for multi-location owners, S3 media.

---

## Pre-launch QA checklist

- [ ] `python manage.py check --deploy`
- [ ] `python manage.py test`
- [ ] Customer booking flow (submit → session success page → email)
- [ ] Owner dashboard, calendar, bookings, blocked customers
- [ ] Image upload + owner photo view
- [ ] Email verification + password reset (with real SMTP)
- [ ] MK/EN translations on mobile
- [ ] Two salons: confirm owner A cannot access salon B data

---

## Related docs

- [beta-deployment.md](beta-deployment.md) — deploy walkthrough
- [compliance-notes.md](compliance-notes.md) — privacy / legal
- [`.env.example`](../.env.example) — environment template
