# Roadmap
# Salon Booking & Appointment Management System

## Phase 0 — Project Foundation

### Goal

Prepare the project before coding so development stays organized.

### Tasks

- Create project folder.
- Create `docs/` folder.
- Add `owner-interview-summary.md`.
- Add `requirements-v1.md`.
- Add `roadmap.md`.
- Add `AGENTS.md` for Codex.
- Create `README.md`.
- Decide initial tech stack.

### Output

A clean project structure with documentation ready for development.

---

## Phase 1 — Local Django Setup

### Goal

Create a working local Django project.

### Tasks

- Create Python virtual environment.
- Install Django.
- Install Pillow for image uploads.
- Start Django project.
- Create main app, for example `booking` or `appointments`.
- Configure templates and static files.
- Configure media files for local image uploads.
- Use SQLite temporarily or PostgreSQL if ready.
- Create base template.
- Create simple homepage.

### Output

Django project runs locally and displays a basic page.

---

## Phase 2 — Initial Database Models

### Goal

Create the first version of the core data structure.

### Suggested models

- Salon
- Service
- Customer
- Booking
- BookingService
- WorkingHours
- BlockedDate
- BookingPolicy
- CustomerBlocklist

### Tasks

- Define models.
- Run migrations.
- Register models in Django admin.
- Add useful admin list displays and filters.
- Create sample data.

### Output

Admin panel can manage services, customers, bookings, working hours, and booking policy.

---

## Phase 3 — Owner Admin and Management Basics

### Goal

Allow the owner to manage basic salon data.

### Tasks

- Owner can log in.
- Owner can manage services.
- Owner can set default working hours.
- Owner can set booking policy:
  - minimum booking notice
  - maximum booking window
  - manual approval mode
  - late arrival rule
- Owner can block dates.

### Output

The owner can configure the basic rules of the salon.

---

## Phase 4 — Customer Booking Flow V1

### Goal

Build the first complete customer booking flow.

### Customer steps

1. Choose service.
2. Choose date.
3. Choose available time.
4. Enter customer info.
5. Upload photo if needed.
6. Accept salon rules.
7. Submit request.
8. See pending confirmation message.

### Tasks

- Create service selection page.
- Create date selection logic.
- Create available time slot calculation.
- Create customer information form.
- Add photo upload field.
- Add rules checkbox.
- Create booking request.
- Prevent invalid dates/times.

### Output

A customer can create a pending booking request from the website.

---

## Phase 5 — Owner Dashboard V1

### Goal

Give the owner a useful dashboard for daily work.

### Tasks

- Create dashboard page.
- Show pending requests.
- Show today’s appointments.
- Show upcoming approved bookings.
- Add approve button.
- Add reject button.
- Add booking detail page/modal.
- Show customer info and uploaded photo.
- Show appointment status clearly.

### Output

Owner can review and manage incoming booking requests.

---

## Phase 6 — Manual Add Booking

### Goal

Allow owner to add appointments manually from Instagram, Viber, Messenger, phone, or in-person requests.

### Tasks

- Create manual booking form.
- Allow owner to search or create customer.
- Allow owner to choose service.
- Allow owner to choose date/time.
- Allow owner to set status directly as Approved.
- Prevent double booking.

### Output

The app can become the owner’s main calendar, not only an online booking form.

---

## Phase 7 — Availability and Calendar Improvements

### Goal

Make scheduling more realistic and useful.

### Tasks

- Improve slot generation.
- Respect service duration.
- Respect existing approved bookings.
- Decide how pending bookings lock slots.
- Add blocked dates.
- Add unavailable time blocks.
- Add custom working hours for a specific day.
- Add simple calendar/list view.
- Consider FullCalendar.js for advanced owner calendar.

### Output

The owner can manage real-world availability more accurately.

---

## Phase 8 — Prepared Messages and Contact Actions

### Goal

Help the owner contact customers quickly without full automation.

### Tasks

- Generate approval message.
- Generate rejection message.
- Generate reminder message.
- Add Copy Message button.
- Add Call button.
- Add SMS button.
- Add WhatsApp button if possible.
- Add Viber option if practical.
- Use customer preferred contact method to highlight best action.

### Output

Owner can approve/reject and contact customer quickly using prepared messages.

---

## Phase 9 — Reminder Helper V1

### Goal

Support the owner’s requirement for 24-hour reminders.

### Tasks

- Create page/section for tomorrow’s appointments.
- Show customers who need reminder.
- Generate reminder message.
- Add Copy Message / SMS / WhatsApp / Viber actions.
- Add field to mark reminder as sent.

### Output

Owner can reliably send 24-hour reminders manually.

---

## Phase 10 — Testing With Salon Owner

### Goal

Test the app with the real owner before public launch.

### Tasks

- Add test services.
- Add test customers.
- Add fake bookings.
- Let owner test approve/reject.
- Let owner test manual add booking.
- Let owner test blocked dates.
- Let owner test customer booking flow.
- Collect feedback.

### Questions to ask after testing

- Was anything confusing?
- Did this feel faster than Instagram messages?
- What screen would you use every day?
- What button or feature is missing?
- Is manual approval practical?
- Are the booking rules correct?
- Is the customer form too long?

### Output

List of fixes before real customer testing.

---

## Phase 11 — Private Real Customer Test

### Goal

Let a small number of real customers use the booking page.

### Tasks

- Share link with 5–10 trusted customers.
- Let them request appointments.
- Owner approves/rejects.
- Track confusion and bugs.
- Ask customers if the process was clear.
- Check if owner saved time.

### Output

Real feedback from real customer behavior.

---

## Phase 12 — MVP Polish

### Goal

Make the app presentable and smooth.

### Tasks

- Improve mobile design.
- Improve forms.
- Improve error messages.
- Improve empty states.
- Improve dashboard layout.
- Add loading states for dynamic actions.
- Clean up templates.
- Improve Macedonian text.
- Improve admin labels.

### Output

A polished MVP ready for wider testing.

---

## Phase 13 — Deployment Preparation

### Goal

Prepare for online deployment.

### Tasks

- Move from SQLite to PostgreSQL if not already done.
- Configure environment variables.
- Configure static files.
- Configure media upload strategy.
- Set DEBUG=False.
- Set allowed hosts.
- Configure production email.
- Add HTTPS through hosting provider.
- Prepare database backup strategy.

### Output

App is ready to deploy safely.

---

## Phase 14 — Beta Launch

### Goal

Launch the first usable online version for the salon.

### Tasks

- Deploy to Render, Railway, or VPS.
- Create test domain/subdomain.
- Give owner login.
- Add real services and rules.
- Add link to Instagram bio or story.
- Monitor usage.
- Fix urgent bugs.

### Output

The salon can use the system in real life.

---

## Phase 15 — Post-Launch Feedback

### Goal

Decide what to build next based on real use.

### Metrics to observe

- Number of booking requests.
- Number of approved bookings.
- Number of rejected bookings.
- Number of no-shows.
- Time owner spends managing requests.
- Whether customers understand the rules.
- Whether customers upload useful photos.
- Whether 14-day minimum notice works.

### Output

Prioritized Version 2 feature list.

---

## Version 2 Candidate Features

Build only if feedback proves they are needed.

- Web push notifications.
- Automatic email confirmations.
- Automatic email reminders.
- Better calendar view with FullCalendar.js.
- Customer history page.
- Unavailable time blocks.
- Custom working hours per date.
- Edit booking with “inform customer” toggle.
- Add to Google/Apple Calendar through `.ics` file.
- Auto-confirm toggle.
- Trusted customer list.

---

## Version 3 Candidate Features

- SMS reminders.
- Deposit/payment support.
- Loyalty rewards.
- Multiple services in one booking.
- Multiple staff members.
- Staff-specific availability.
- Google Calendar sync.
- Customer self-cancellation/rescheduling.
- Statistics and reports.

---

## Long-Term Product Direction

Potential SaaS for:

- Nail salons
- Barbers
- Hair salons
- Makeup artists
- Tattoo studios
- Massage studios

Long-term modules:

- Multi-salon support
- Subscription plans
- Owner onboarding
- Staff management
- Payments/deposits
- Customer loyalty
- Automated reminders
- Analytics

---

## Current Immediate Next Steps

**Live product (first salon ~1 month in production).**

Locked milestone: **Schedule truth — base + add-ons durations and slot gaps**  
See [next-production-milestone.md](next-production-milestone.md).

Also: Railway cron must run `auto_complete_past_bookings` (now in `backend/railway.cron.toml`) so finished appointments leave Approved and become Completed.

