# Vremio Compliance Notes

**This document is operational guidance, not legal advice.**

## Private pilot context

The first Vremio pilot may involve a friendly business owner and a free testing period. That does **not** remove the need for privacy and terms pages when real customers use the system. Real personal data is still collected (names, phone numbers, email, booking details, and sometimes photos).

The public legal pages in the app are **drafts**. They should be reviewed by a qualified lawyer before wider commercial launch.

## What Vremio collects (summary)

- Customer identity and contact details
- Booking details (service, date, time, status)
- Reference photos when required or uploaded
- Email verification and manage-booking tokens
- Security/rate-limit logs (e.g. IP address)
- Business owner account data

## Transactional email only

Vremio sends transactional emails for booking flow events (verification, request received, approve/reject/edit/cancel, password reset, owner notifications). **No marketing or newsletter emails** are sent unless a separate explicit opt-in is added later.

## Manual data handling today

There is no self-service privacy portal yet. Data requests are handled manually.

### Business owner dashboard

- Delete reference photo from a booking
- Block abusive customer (phone/email)
- Cancel or edit bookings
- View customer history

### Django admin

- Delete or edit bookings
- Delete customers or blocklist entries
- Access uploaded media files when needed for support

### Customer contact

- Public page: `/contact/` with mailto link when `VREMIO_CONTACT_EMAIL` or `OWNER_NOTIFICATION_EMAIL` is configured

## Production requirements

- Use **HTTPS** in production
- Use secure database and media storage
- Restrict admin and owner access with strong passwords
- Do not expose uploaded photos publicly
- Run `cleanup_unverified_bookings` and other maintenance commands on a schedule (see README / beta deployment docs)

## Before wider commercial launch

Consult professionals as needed:

- **Lawyer** — review Privacy Policy, Terms, owner agreement, photo policy, and data retention wording
- **Accountant** — if charging businesses regularly for the platform
- **Payments** — if online deposits or payments are added, separate payment/refund terms are required
- **Marketing email** — requires explicit opt-in and unsubscribe flow
- **Formal DPA** — if processing data for multiple businesses at scale

## Uploaded photos

Reference photos must be treated carefully:

- Visible only to logged-in owner/admin (not public)
- May be deleted if inappropriate
- Customers can be blocked for abuse
- Automated content moderation is limited; owner review is still important during pilot

## Updating legal pages

Legal content lives in templates under `backend/templates/booking/legal/` with translations in `backend/scripts/build_mk_locale.py`. After text changes, rebuild locale:

```bash
python backend/scripts/build_mk_locale.py
```
