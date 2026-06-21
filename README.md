# Salon Scheduler System

Salon Scheduler System is a web-based appointment booking and management application for beauty and service businesses.

The first real-world use case is a nail salon owner who currently manages appointments through Instagram, Messenger, Viber, and phone notes. The goal of the system is to reduce manual messaging, prevent scheduling confusion, reduce no-shows, and give the owner a clean dashboard/calendar for managing appointments.

## Main Goal

Build a real-world booking system where customers can request appointments online and the salon owner can manage, approve, reject, edit, and track appointments from an owner dashboard.

## First Target Business

The first target business is a nail salon.

Future possible businesses:

* Barbers
* Hair salons
* Makeup artists
* Tattoo studios
* Massage studios
* Beauty salons

## Current Tech Decision

Initial stack:

* Backend: Django
* Database: PostgreSQL
* Frontend: Django Templates
* Styling: Bootstrap or Tailwind
* Smooth UI interactions: HTMX or small JavaScript
* Calendar UI later: FullCalendar.js

React and Django REST Framework are not part of the first MVP unless they become necessary later.

## Core Problems Being Solved

The salon owner currently:

* receives appointment requests through Instagram, Messenger, and Viber
* tracks appointments in phone notes
* spends around 1-2 hours daily arranging appointments
* deals with customers asking for unavailable times
* deals with customers asking today for tomorrow
* wants customers to send reference photos for certain services
* wants customers to accept salon rules before booking
* wants to manually approve bookings
* wants 24-hour appointment reminders

## Main MVP Features

Customer side:

* Select service
* Select date
* Select available time
* Enter name, phone number, Instagram, and optional email
* Choose preferred contact method
* Upload reference photo if needed
* Accept salon rules
* Submit booking request
* See pending confirmation message

Owner side:

* Login
* Dashboard
* View pending bookings
* Approve or reject bookings
* Manually add bookings
* Edit bookings
* View appointments
* Manage services
* Manage working hours
* Block days or unavailable times
* View customer history
* Use prepared messages to contact customers

## Important Booking Rules for First Salon

* Working days: Monday to Saturday
* Working hours: 08:00 - 18:00
* Closed: Sunday
* Same-day booking: not allowed
* Next-day booking: generally not allowed
* Minimum booking notice: 14 days
* Maximum booking window: 60 days
* Manual approval: enabled
* Reminder: 24 hours before appointment
* Late arrival limit: 15 minutes without notice

## Appointment Statuses

Appointments can have these statuses:

* Pending
* Approved
* Rejected
* Cancelled
* Completed
* No Show

## Documentation

Detailed project documents are stored in the `docs/` folder:

* `owner-interview-summary.md`
* `requirements-v1.md`
* `roadmap.md`
* `beta-deployment.md` — beta/production deployment guide

---

## Developer Setup (Local)

### 1. Clone and create a virtual environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
# From repo root
cp .env.example .env
```

Edit `.env` — for local development the defaults are fine (SQLite + console email).

See [`.env.example`](.env.example) for all supported variables.

### 4. Run migrations

```bash
cd backend
python manage.py migrate
```

### 5. Create a superuser (Django admin)

```bash
python manage.py createsuperuser
```

Admin panel: `http://127.0.0.1:8000/admin/`

### 6. Create owner + salon data (beta setup command)

```bash
python manage.py setup_beta_salon \
  --username salon_owner \
  --email owner@example.com \
  --slug fancy-fingers \
  --salon-name "Fancy Fingers"
```

This creates the owner user (no password), salon, booking policy, working hours, and four default services.

**Set the owner password** (never send plain text passwords):

* Option A: `python manage.py changepassword salon_owner`
* Option B: Owner visits `/owner/password/reset/` and receives an email link

### 7. Run the development server

```bash
python manage.py runserver
```

* Customer salon page: `http://127.0.0.1:8000/book/fancy-fingers/`
* Owner login: `http://127.0.0.1:8000/owner/login/`
* Owner dashboard: `http://127.0.0.1:8000/owner/dashboard/`

### 8. Run tests

```bash
python manage.py check
python manage.py test booking
```

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `DJANGO_SECRET_KEY` | Required in production — long random string |
| `DJANGO_DEBUG` | `True` locally, `False` for beta/production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames |
| `CSRF_TRUSTED_ORIGINS` | HTTPS origins for CSRF (production) |
| `SITE_URL` | Public URL for emails (password reset, owner notifications) |
| `DATABASE_URL` | PostgreSQL connection URL (PaaS providers) |
| `POSTGRES_*` | Alternative discrete PostgreSQL settings |
| `EMAIL_*` | SMTP settings for production email |
| `MEDIA_ROOT` | Optional override for uploaded photos path |

Full list with examples: [`.env.example`](.env.example)

**Database priority:** `DATABASE_URL` → `POSTGRES_DB` → SQLite (local dev fallback).

---

## Beta Deployment Checklist

Before giving the app to a real salon owner:

- [ ] `DJANGO_DEBUG=False`
- [ ] Strong unique `DJANGO_SECRET_KEY` set
- [ ] PostgreSQL configured (`DATABASE_URL` or `POSTGRES_*`)
- [ ] `DJANGO_ALLOWED_HOSTS` includes your domain
- [ ] `CSRF_TRUSTED_ORIGINS` includes your HTTPS URL
- [ ] `SITE_URL` set to your public URL
- [ ] SMTP email configured and tested (password reset + booking emails)
- [ ] `python manage.py migrate` run on production database
- [ ] `python manage.py collectstatic` run before deploy
- [ ] Persistent storage for `MEDIA_ROOT` (customer reference photos)
- [ ] Owner account created via `setup_beta_salon` + password reset email
- [ ] Smoke test: customer booking → owner receives email → owner approves

See [`docs/beta-deployment.md`](docs/beta-deployment.md) for provider-neutral deployment steps.

---

## Development Philosophy

Build the project in small steps.

Do not overbuild early.

First goal:

Create a working local MVP for one nail salon.

Later goals:

* Improve based on real owner feedback
* Test with a barber
* Add reminders
* Add customer history
* Add calendar improvements
* Add deposits/payments later
* Add loyalty features later
* Add multiple salons/employees later
