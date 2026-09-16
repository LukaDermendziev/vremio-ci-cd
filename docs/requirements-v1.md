# Requirements V1
# Salon Booking & Appointment Management System

## 1. Product Goal

Build a mobile-first web application that helps a nail salon owner manage appointments more professionally and reduce scheduling through Instagram, Messenger, and Viber messages.

The first version should focus on one real nail salon. The long-term product may later support barbers, hair salons, makeup artists, tattoo studios, and other beauty/service businesses.

---

## 2. Main Problems to Solve

The system should solve these confirmed problems:

1. The owner spends around 1–2 hours daily arranging appointments through messages.
2. Customers request unavailable times.
3. Customers try to book too late, including today for tomorrow.
4. Customers underestimate how long services take.
5. Customers do not always send design or case reference photos.
6. New clients sometimes waste time and do not show up.
7. Customers are often late.
8. The owner currently manages appointments in phone Notes.
9. The owner wants control over who gets approved.
10. The owner wants reminders to be sent 24 hours before appointments.

---

## 3. Chosen Tech Stack

### Backend

Django

### Database

PostgreSQL

### Frontend V1

Django Templates, Bootstrap or Tailwind, HTMX or small JavaScript for smooth interactions.

### Calendar UI

Simple custom calendar/list first. FullCalendar.js can be added when the dashboard calendar becomes more advanced.

### Not in V1

React should not be used in the first version unless specifically needed later. Django REST Framework should also be postponed unless an API becomes necessary.

---

## 4. User Roles

### Customer

A person who wants to request an appointment.

### Owner

The salon owner who reviews, approves, rejects, edits, and manually creates bookings.

### Admin/Developer

The person managing the system during development and early testing.

---

## 5. Customer Booking Flow

1. Customer opens the booking page from Instagram bio or direct link.
2. Customer chooses a service.
3. Customer chooses an available date.
4. Customer chooses an available time.
5. Customer enters required information.
6. Customer uploads a photo if required or desired.
7. Customer accepts salon rules.
8. Customer submits booking request.
9. System displays a pending confirmation message.

Important wording:

The system must say “appointment request sent” and not “appointment confirmed” before owner approval.

Suggested confirmation message:

“Вашето барање за термин е испратено. Терминот сè уште не е потврден. Салонот ќе го провери барањето и ќе ве контактира.”

---

## 6. Customer Form Fields

### Required

- Name and surname
- Phone number
- Instagram username
- Preferred contact method

### Optional

- Email
- Notes/message to owner

### Conditional

- Reference photo

Photo should be required for medical pedicure and recommended for manicure/design.

---

## 7. Services Requirements

The owner must be able to manage services.

Each service should have:

- Name
- Description
- Duration in minutes
- Price or base price
- Active/inactive status
- Requires photo: yes/no
- Optional extra duration notes

Initial service examples:

- Manicure
- Manicure with design
- Pedicure
- Medical pedicure

Default duration can start around 120 minutes, with design/medical cases possibly taking longer.

---

## 8. Booking Rules

The first salon should have these default rules:

- Working days: Monday–Saturday
- Working hours: 08:00–18:00
- Closed day: Sunday
- Minimum booking notice: 14 days
- Maximum booking window: 60 days
- Same-day booking: disabled
- Next-day booking: disabled by default
- Manual approval: enabled
- Late arrival limit: 15 minutes without notice
- Reminder time: 24 hours before appointment

The owner should eventually be able to edit these rules in settings.

---

## 9. Appointment Statuses

Appointments/bookings should support these statuses:

- Pending
- Approved
- Rejected
- Cancelled
- Completed
- No Show

Status behavior:

- New customer request starts as Pending.
- Owner can approve or reject.
- Approved bookings appear in the confirmed calendar/list.
- Completed and No Show can be used for customer history.

---

## 10. Owner Dashboard Requirements

The owner dashboard should allow the owner to:

- View today’s appointments
- View upcoming appointments
- View pending requests
- Approve booking requests
- Reject booking requests
- Edit bookings
- Manually add bookings
- Mark booking as completed
- Mark booking as no-show
- Cancel bookings
- View customer information
- View customer visit history
- Manage services
- Manage working hours
- Block dates
- Block unavailable time periods later
- View reminder list for tomorrow

---

## 11. Manual Add Booking

The owner must be able to manually add bookings because some customers may still contact her through Instagram, Messenger, Viber, phone, or in person.

Manual booking should include:

- Customer
- Service
- Date
- Time
- Duration
- Status
- Notes
- Optional photo

This helps the app become the main calendar instead of only an online request tool.

---

## 12. Approval Mode

For V1, manual approval is required.

Reason:

The owner wants to know who is coming and may reject a customer based on previous bad experience.

Future setting:

- Manual approval ON/OFF
- Auto-confirm bookings ON/OFF

Auto-confirmation can later be used for trusted customers, simple services, or different businesses like barbers.

---

## 13. Anti-Abuse Requirements

The system should reduce fake/spam bookings.

Required or planned protections:

- One active pending booking per phone number
- Rate limit booking attempts
- Prevent double booking
- Customer cannot book outside working hours
- Customer cannot book before minimum notice period
- Customer cannot book beyond maximum booking window
- Owner can block customer phone numbers
- Optional pending request expiration

---

## 14. Notification Requirements

### Owner notifications

V1 should support:

- Dashboard notification / pending count
- Email notification when a new request is created

Later:

- Web push notifications
- SMS notifications

### Customer notifications

V1 should support:

- Confirmation screen after request
- Prepared approval/rejection message generated for owner
- Email notification only if valid email is provided

Later:

- Web push notifications
- SMS reminders
- Automatic email confirmations

---

## 15. Prepared Message Requirements

When the owner approves, rejects, edits, or reminds a customer, the system should generate a prepared Macedonian message.

The owner should have action buttons:

- Call
- Send Viber message
- Send WhatsApp message
- Send SMS
- Copy message

Copy Message is mandatory as a universal fallback.

Example approval message:

“Здраво [име], вашиот термин за [датум] во [време] е потврден. Ве очекуваме.”

Example rejection message:

“Здраво [име], за жал терминот за [датум] во [време] не е достапен. Ве молиме изберете друг термин.”

Example reminder message:

“Здраво [име], ве потсетуваме дека имате термин утре во [време]. Ве очекуваме.”

---

## 16. Salon Rules Requirements

The customer must accept rules before submitting a booking request.

Initial rules:

- Appointment must be requested at least 2 weeks in advance.
- Same-day appointments are not accepted.
- Appointment is not confirmed until approved by the salon.
- If the customer is more than 15 minutes late without notice, the appointment may be cancelled.
- For certain services, a reference photo is required.

---

## 17. Availability Requirements

The system should calculate available slots based on:

- Working days
- Working hours
- Service duration
- Existing approved bookings
- Existing pending bookings, depending on locking rule
- Blocked dates
- Unavailable time blocks later
- Minimum booking notice
- Maximum booking window

For V1, pending slots should probably be temporarily unavailable to prevent multiple customers from requesting the same time.

---

## 18. Data Model Direction

The database should be designed to grow.

Likely core models:

- Salon
- Service
- Customer
- Booking
- BookingService
- WorkingHours
- BlockedDate
- UnavailableTimeBlock
- BookingPolicy
- CustomerBlocklist
- NotificationLog later

BookingService is useful because the system may later allow multiple services inside one booking.

---

## 19. Smoothness and UX Requirements

The app should not just work; it should feel smooth.

Customer side:

- Mobile-first
- Simple steps
- Big buttons
- Clean design
- No confusing fields
- Available times should appear dynamically after date selection

Owner side:

- Fast dashboard
- Clear pending requests
- Easy approve/reject buttons
- Easy manual add booking
- Calendar/list view
- Minimal clicks

Use HTMX or small JavaScript to avoid unnecessary full-page reloads where needed.

---

## 20. Security Requirements

The system stores personal data:

- Name
- Phone number
- Instagram username
- Optional email
- Appointment times
- Uploaded photos

Security requirements:

- Use Django authentication
- Use Django ORM
- Keep CSRF protection enabled
- Validate all forms
- Validate uploaded images
- Limit upload file size
- Use environment variables for secrets
- Use HTTPS in production
- Use strong owner password
- Ensure owner only sees own salon data later if multi-salon support is added
- Do not store payment card details in the system

---

## 21. Out of Scope for V1

Do not build these in V1:

- Online payments/deposits
- Loyalty system
- Full SMS automation
- React frontend
- Customer accounts
- Multiple salons
- Multiple employees
- Google Calendar sync
- Full statistics/reports
- Invoices/receipt printing

These are future features.

---

## 22. V1 Success Criteria

V1 is successful if:

1. The owner can stop using phone Notes as the main appointment system.
2. Customers can request appointments through the website.
3. Customers can only select valid available times.
4. The owner can approve or reject requests.
5. The owner can manually add bookings received through messages.
6. The system reduces appointment negotiation through messages.
7. The owner says the system saves time.

